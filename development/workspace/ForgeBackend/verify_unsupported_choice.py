"""A real Opt resolution must expose Scry as a gap, never use an AI answer.

This is a negative capability probe. It must not be used as card admission.
The supplied independent research manifest must contain source-checked Opt.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path


def run(a):
    os.environ['FORGE_ARENA_CONFIG']=str(a.config.resolve())
    os.environ['FORGE_ARENA_POLICY']=str(a.policy.resolve())
    from warm_game_worker import WarmPool
    from runtime_paths import ROOT
    from run_background_validation import lower_resources
    lower_resources()
    if (ROOT/'native-lab/MTGA.exe').exists():raise ValueError('Independent research runtime required')
    a.output.mkdir(parents=True,exist_ok=False)
    checks=[];rows=[]
    def check(label,value):
        checks.append(dict(check=label,passed=bool(value)))
        if not value:raise AssertionError(label)
    locks=ROOT/'research/background-runs';locks.mkdir(parents=True,exist_ok=True)
    try:
        with (locks/'validation.lock').open('a+b') as lease:
            lease.seek(0);lease.write(b'1');lease.flush();lease.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
            with WarmPool(a.output/'pool',25) as pool:
                e=pool.engine('card-family',randomSeed=7274,fixtureHand=['Opt'],fixtureLands=['Island'])
                token=e.worker.ready['worker']
                try:
                    check('Strict human research controller enabled',e.state['researchControls']['strictHumanCallbacks'])
                    card=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Opt')
                    library={c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library'}
                    check('Original Opt cast is legal and accepted',card in e.state['legalCasts'] and e.send('cast_spell',card)['accepted'])
                    check('Opt is on the real stack before resolution',any(c['forgeId']==card for c in e.state['stack']))
                    # An explicitly unsupported callback rejects the resolution
                    # request; do not use pass_or_decision's success assertion.
                    reply=e.send('pass_priority')
                    check('Scry produces the exact unsupported human callback',bool(e.state.get('fidelityGap')) and 'arrangeForScry' in e.state['fidelityGap'])
                    check('Missing Scry never silently draws a card',not e.state['hand'] and library=={c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library'})
                    blocked=e.send('pass_priority')
                    check('Further gameplay refuses the unresolved fidelity gap',not blocked['accepted'] and blocked['state']['fidelityGap']==e.state['fidelityGap'])
                    rows.append(dict(evidence=str(e.ipc),reply=reply,blocked=blocked))
                finally:e.close()
                check('Java worker itself retires after a fidelity gap',not e.completion['reusable'] and 'arrangeForScry' in e.completion.get('fidelityGap',''))
                clean=pool.engine('card-family',randomSeed=7274,fixtureHand=['Divination'],fixtureLands=['Island']*3)
                try:
                    check('Next game gets a fresh worker/session and no gap',clean.worker.ready['worker']!=token and clean.session!=e.session and not clean.state['fidelityGap'])
                    identity=next(c['forgeId'] for c in clean.state['hand'] if c['name']=='Divination')
                    check('Supported cast still works after rejected Scry',clean.send('cast_spell',identity)['accepted'])
                    clean.pass_or_decision()
                    check('Supported resolution draws two actual cards',len(clean.state['hand'])==2 and not clean.state['fidelityGap'])
                    rows.append(dict(evidence=str(clean.ipc)))
                finally:clean.close()
    finally:
        result=dict(checks=len(checks),passed=bool(checks) and all(c['passed'] for c in checks),results=checks,cases=rows,
            configSha256=hashlib.sha256(a.config.read_bytes()).hexdigest(),policySha256=hashlib.sha256(a.policy.read_bytes()).hexdigest(),
            scope='Negative capability and worker recovery probe; Opt remains unsupported and unadmitted.')
        (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','output'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
