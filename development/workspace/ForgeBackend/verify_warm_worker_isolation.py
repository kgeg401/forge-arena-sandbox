"""Real-game order, aborted-choice, timeout, session and retirement probes."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import time


def run(a):
    os.environ['FORGE_ARENA_CONFIG']=str(a.config.resolve());os.environ['FORGE_ARENA_POLICY']=str(a.policy.resolve())
    from warm_game_worker import WarmPool
    from runtime_paths import ROOT
    from compare_card_batch_runs import canonical_trace,difference
    from run_background_validation import lower_resources
    lower_resources()
    if (ROOT/'native-lab/MTGA.exe').exists():raise ValueError('No playable lab allowed')
    suite=json.loads((Path(__file__).with_name('card_batch_suites')/'decisions-history.json').read_text(encoding='utf8'))
    by={c['id']:c for c in suite['cases']}
    a.output.mkdir(parents=True,exist_ok=False);checks=[];cases=[]
    def check(label,condition):
        checks.append(dict(check=label,passed=bool(condition)))
        if not condition:raise AssertionError(label)
    def execute(pool,case,timeout=60):
        r=pool.execute(case,timeout,2);cases.append(r)
        return r
    locks=ROOT/'research/background-runs';locks.mkdir(parents=True,exist_ok=True)
    with (locks/'validation.lock').open('a+b') as lease:
        lease.seek(0);lease.write(b'1');lease.flush();lease.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
        with WarmPool(a.output/'main-pool',25) as pool:
            first=execute(pool,by['life-old-graveyard']);check('Initial A passes',first['status']=='passed')
            death=deepcopy(by['life-real-death-and-expiry']);death['steps']=death['steps'][:3]
            b=execute(pool,death);check('B ends after an actual same-turn death and eight life',b['status']=='passed')
            again=execute(pool,by['life-old-graveyard']);check('A after B passes without inherited death history',again['status']=='passed')
            check('A/B/A uses one worker but three different sessions',len({r['worker']['token'] for r in (first,b,again)})==1 and len({r['worker']['completion']['session'] for r in (first,b,again)})==3)
            check('Complete A traces match after B',difference(canonical_trace(Path(first['evidence'])/'engine-journal.jsonl'),canonical_trace(Path(again['evidence'])/'engine-journal.jsonl')) is None)
            bad=deepcopy(by['unsummon-friendly-target']);bad['steps'][0]['targetPlan']['expectedOptions']=bad['steps'][0]['targetPlan']['expectedOptions'][:1]
            failed=execute(pool,bad);check('Wrong target oracle fails while a choice is pending',failed['status']=='failed' and failed['category']=='target')
            after=execute(pool,by['life-old-graveyard']);check('Aborted-choice worker is replaced before the next passing game',after['status']=='passed' and after['worker']['token']!=failed['worker']['token'])
            timeout=execute(pool,by['life-old-graveyard'],.001)
            check('Injected deadline kills only the owned case worker',timeout['status']=='failed' and timeout['category']=='timeout')
            recovered=execute(pool,by['life-old-graveyard']);check('A fresh worker passes after the deadline',recovered['status']=='passed' and recovered['worker']['token']!=after['worker']['token'])
            settings=by['life-old-graveyard']['fixture']
            e1=pool.engine('card-family',randomSeed=7274,**settings)
            request=e1.begin('snapshot');e1.finish(request);old=e1.session;e1.close()
            e2=pool.engine('card-family',randomSeed=7274,**settings)
            try:
                before=e2.state
                identity=next(c['forgeId'] for c in before['hand'] if c['name']=='Life Goes On')
                r=e2.send('cast_spell',identity,session=old)
                check('Old session cannot mutate a new game',not r['accepted'] and e2.state['hand']==before['hand'] and e2.state['battlefield']==before['battlefield'] and e2.state['life']==before['life'])
                r=e2.send('snapshot',id=request)
                check('Reused request ID gets a new-session response, not an old cache',r['accepted'] and r['state']['session']==e2.session and e2.session!=old)
            finally:e2.close()
        with WarmPool(a.output/'retirement-pool',2) as pool:
            rows=[execute(pool,by['life-old-graveyard']) for _ in range(3)]
            check('Bounded worker retirement preserves all case results',all(r['status']=='passed' for r in rows))
            check('The third case uses a new worker after the two-case limit',rows[0]['worker']['token']==rows[1]['worker']['token']!=rows[2]['worker']['token'] and rows[2]['worker']['completion']['ordinal']==1)
        result=dict(checks=len(checks),results=checks,cases=cases,
            scope='Order/failure/session/retirement fault-injection evidence for this research runtime; not all-card behavior or admission.')
        (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','output'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
