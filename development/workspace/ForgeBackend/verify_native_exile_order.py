"""Explicit exile movement permutations through real Crypt costs and native UI handlers.

Only initial graveyards and authored human inputs are seeded. Expected original
objects, local-player movement order and conservation are specified before
resolution. The bot owns its own ordering; its object conservation and absence
of an unauthorized local chooser are checked without predicting AI ordering.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time
import traceback


CASES=[
    dict(id='own-reverse',seat=1,names=['Forest','Mountain','Plains'],order=[3,2,1,0]),
    dict(id='own-duplicate-permutation',seat=1,names=['Forest','Forest','Island'],order=[1,3,0,2]),
    dict(id='own-only-cost',seat=1,names=[],order=[0]),
    dict(id='opponent-owned-order',seat=2,names=['Forest','Mountain','Plains'],order=[0,1,2]),
    dict(id='opponent-duplicate-identity',seat=2,names=['Forest','Forest','Island'],order=[0,1,2]),
    dict(id='opponent-empty',seat=2,names=[],order=[]),
]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(case,factory):
    e=None
    try:
        settings={'fixtureGraveyard' if case['seat']==1 else 'fixtureOpponentGraveyard':case['names']}
        e=factory('card-family',randomSeed=7274,fixtureHand=["Tormod's Crypt"],fixtureLands=[],fixtureLibrary=['Island'],**settings)
        def check(label,value):e.check(label,value)
        crypt=next(c['forgeId'] for c in e.state['hand'] if c['name']=="Tormod's Crypt")
        originals=[c['forgeId'] for c in e.state['graveyard'] if c['owner']==case['seat']]
        check('Authored initial graveyard names and count match actual objects',[c['name'] for c in e.state['graveyard'] if c['owner']==case['seat']]==case['names'])
        offered=originals+([crypt] if case['seat']==1 else [])
        expected=[offered[i] for i in case['order']];orders=[]
        def transact(op,identity=0,**arguments):
            parent=e.begin(op,identity,**arguments);end=time.monotonic()+20
            while time.monotonic()<end:
                if (e.ipc/'responses'/(parent+'.json')).exists():check('Original native handler reaches accepted Forge boundary',e.finish(parent)['accepted']);return
                try:message=json.loads((e.ipc/'decision.json').read_text())
                except (FileNotFoundError,PermissionError,json.JSONDecodeError):message=None
                if message and message['parentRequestId']==parent:
                    e.state=message['state'];d=e.state['decision'];fields=dict(decisionToken=d['token'])
                    check('No implicit human callback or native model gap',not e.state['fidelityGap'])
                    if d['kind']=='targets':
                        target=next(o['forgeId'] for o in d['options'] if o.get('targetSeat')==case['seat'])
                        check('Explicit player target selected',e.send('select_targets',assignments=[dict(forgeId=target)],**fields)['accepted'])
                        check('Original target handler submits chosen player',e.send('submit_targets',**fields)['accepted'])
                    elif d['kind']=='choice' and d['choice']['type']=='order':
                        spec=d['choice'];orders.append(spec['destination'])
                        check('Exile picker exposes precisely the expected original objects in offered order',spec['destination']=='Exile' and [o['forgeId'] for o in spec['options']]==offered)
                        check('Every offered card must appear exactly once',spec['min']==spec['max']==len(offered) and spec['repeats'] is False)
                        assignments=[dict(choiceId=next(o['choiceId'] for o in spec['options'] if o['forgeId']==card)) for card in expected]
                        bad=e.send('submit_choice',assignments=assignments[:-1],**fields)
                        check('Partial order rejected without consuming native request',not bad['accepted'] and e.state['decision']['token']==d['token'])
                        check('Original native order handler submits authored permutation',e.send('submit_choice',assignments=assignments,**fields)['accepted'])
                    else:raise AssertionError('Unexpected human decision '+json.dumps(d))
                time.sleep(.025)
            raise TimeoutError('Exile ordering command deadline')
        transact('cast_spell',crypt)
        for _ in range(8):
            if any(c['forgeId']==crypt for c in e.state['battlefield']):break
            transact('pass_priority')
        check('Crypt enters through actual spell resolution',any(c['forgeId']==crypt for c in e.state['battlefield']))
        transact('activate_ability',crypt,abilityId=12870)
        check('Source sacrifice cost moves actual Crypt to graveyard before resolution',any(c['forgeId']==crypt for c in e.state['graveyard']) and not any(c['forgeId']==crypt for c in e.state['battlefield']))
        for _ in range(8):
            if not e.state['stackAbilities']:break
            transact('pass_priority')
        check('Exile ability resolves completely',not e.state['stackAbilities'])
        actual=[c['forgeId'] for c in e.state['exile'] if c['owner']==case['seat']]
        if case['seat']==1:check('Actual local exile order matches independently authored permutation',actual==expected)
        else:check('Bot-owned exile preserves every original identity without local ordering input',len(actual)==len(expected) and set(actual)==set(expected))
        check('Every selected graveyard object moves exactly once',not any(c['owner']==case['seat'] for c in e.state['graveyard']) and len(set(expected))==len(offered))
        check('Local ordering callback appears only for multiple local-owned objects',orders==(['Exile'] if case['seat']==1 and len(offered)>1 else []))
        if case['seat']==2:check('Opponent targeting leaves sacrificed Crypt in its own graveyard',[c['forgeId'] for c in e.state['graveyard'] if c['owner']==1]==[crypt])
        return dict(id=case['id'],passed=True,checks=len(e.checks),evidence=str(e.ipc),nativeJournal=str(e.native_folder/'native-model.jsonl'))
    except Exception as error:return dict(id=case['id'],passed=False,error=str(error),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy),DOTNET_PROCESSOR_COUNT='2')
    from native_engine_test_client import NativeEngine
    a.output.mkdir(parents=True,exist_ok=False);rows=[]
    hashes={str(path):sha(path) for path in [a.config,a.policy,*a.worker.parent.glob('*.dll')]}
    for case in CASES:
        row=run_case(case,lambda *args,**settings:NativeEngine(*args,worker=a.worker,managed=a.managed,fixture=a.fixture,**settings));rows.append(row);print(json.dumps(row),flush=True)
        drift=any(sha(Path(path))!=digest for path,digest in hashes.items())
        report=dict(passed=not drift and len(rows)==len(CASES) and all(r['passed'] for r in rows),cases=rows,artifactDrift=drift,pinnedArtifacts=hashes,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
        (a.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        if drift:break
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
