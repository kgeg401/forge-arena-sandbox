"""Type/color replacement, ability removal, layer order and restoration.

Owned Arena Frogify/Healer's Hawk/Mighty Leap/Revoke Existence provide the
independent printed-rule expectations. No intermediate native state is replayed
into Forge. The worker separately interprets native ability modification order.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time
import traceback


CASES=['frog-restore','grant-after-loss','loss-after-grant','two-auras-remove-first','two-auras-remove-last']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(name,factory):
    e=None
    try:
        double=name.startswith('two-auras');hand=['Frogify']*(2 if double else 1)+['Revoke Existence']*(2 if double else 1)+(['Mighty Leap'] if 'grant' in name else [])
        e=factory('card-family',randomSeed=7274,fixtureHand=hand,fixtureLands=['Island']*5+['Plains']*6,fixtureLibrary=['Forest','Mountain','Plains','Island','Swamp'],fixtureBattlefield=["Healer's Hawk"])
        def check(label,value):e.check(label,value)
        target=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=="Healer's Hawk");auras=[];leap=None
        def hawk():return next(c for c in e.state['battlefield'] if c['forgeId']==target)
        def assert_state(frog,pumped=False,flying=False):
            card=hawk();expected=['flying'] if frog and flying else [] if frog else ['flying','lifelink']
            check('Actual current card types match the independent replacement rule',card['currentTypes']==['Creature'] and card['currentSupertypes']==[] and card['currentSubtypes']==(['Frog'] if frog else ['Bird']))
            check('Actual current color is blue only while transformed',card['colorMask']==(2 if frog else 1))
            check('Actual active abilities respect independent layer order',sorted(set(k.lower() for k in card['rulesKeywords']))==sorted(expected))
            check('Actual base characteristics and later pump use different layers',(card['power'],card['toughness'])==((3,3) if pumped else (1,1)))
            check('No presentation fallback or unknown layer was hidden',not card['keywordPresentationGaps'])
            removals=card['keywordRemovals'];check('Every active loss-of-abilities layer has its actual source',len(removals)==len(auras) and all(r['all'] and r['sourceForgeId'] in auras for r in removals))
            if flying and frog:check('Flying gained after the loss keeps its real later source',[g['sourceForgeId'] for g in card['keywordGrants'] if g['keyword'].lower()=='flying']==[leap])
        def transact(op,identity=0,chosen=target):
            parent=e.begin(op,identity);end=time.monotonic()+20
            while time.monotonic()<end:
                if (e.ipc/'responses'/(parent+'.json')).exists():check('Native command reaches actual accepted Forge boundary',e.finish(parent)['accepted']);return
                try:message=json.loads((e.ipc/'decision.json').read_text())
                except (FileNotFoundError,PermissionError,json.JSONDecodeError):message=None
                if message and message['parentRequestId']==parent:
                    e.state=message['state'];d=e.state['decision'];fields=dict(decisionToken=d['token']);check('No human choice is silently delegated',not e.state['fidelityGap'])
                    if d['kind']=='targets':
                        check('Actual Forge target list contains the authored object',chosen in [o.get('forgeId') for o in d['options']])
                        check('Native target selection accepted',e.send('select_targets',assignments=[dict(forgeId=chosen)],**fields)['accepted'])
                        check('Native target submission accepted',e.send('submit_targets',**fields)['accepted'])
                    elif d['kind']=='choice' and d['choice']['type']=='entities':
                        spec=d['choice'];check('Aura resolution still attaches to the actual chosen object',len(spec['options'])==1 and spec['options'][0]['forgeId']==chosen)
                        check('Native attach confirmation accepted',e.send('submit_choice',assignments=[dict(choiceId=spec['options'][0]['choiceId'])],**fields)['accepted'])
                    else:raise AssertionError('Unexpected callback '+json.dumps(d))
                time.sleep(.025)
            raise TimeoutError('Characteristic command did not complete')
        def cast(card,chosen=target,destination='graveyard'):
            identity=next(c['forgeId'] for c in e.state['hand'] if c['name']==card);transact('cast_spell',identity,chosen)
            for _ in range(12):
                if any(c['forgeId']==identity for c in e.state[destination]):return identity
                transact('pass_priority',chosen=chosen)
            raise AssertionError('Source did not reach actual expected zone')
        assert_state(False)
        if name=='loss-after-grant':leap=cast('Mighty Leap')
        auras.append(cast('Frogify',destination='battlefield'))
        assert_state(True,pumped=leap is not None)
        if name=='grant-after-loss':leap=cast('Mighty Leap');assert_state(True,pumped=True,flying=True)
        if double:
            auras.append(cast('Frogify',destination='battlefield'));assert_state(True)
            selected=auras[0] if name.endswith('first') else auras[-1]
            cast('Revoke Existence',selected);check('Selected Aura is really exiled',any(c['forgeId']==selected for c in e.state['exile']));auras.remove(selected);assert_state(True)
        remaining=auras[0];cast('Revoke Existence',remaining);check('Last Aura is really exiled',any(c['forgeId']==remaining for c in e.state['exile']));auras.remove(remaining);assert_state(False,pumped=leap is not None)
        if leap is not None:
            turn=e.state['turn']
            for _ in range(45):
                if e.state['turn']>turn and e.state['activeSeat']==1 and e.state['phase']=='MAIN1':break
                transact('pass_priority')
            check('Real Forge phase loop crosses temporary effect expiry',e.state['turn']>turn and e.state['activeSeat']==1 and e.state['phase']=='MAIN1');assert_state(False)
        check('No unintended outcome or unresolved fidelity gap',not e.state['gameOver'] and not e.state['fidelityGap'])
        return dict(id=name,passed=True,checks=len(e.checks),evidence=str(e.ipc))
    except Exception as failure:return dict(id=name,passed=False,error=str(failure)[:1000]+'\n'+str(failure)[-1000:],traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--case',choices=CASES,action='append');a=p.parse_args();os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy))
    from native_engine_test_client import NativeEngine
    from runtime_paths import ROOT
    prep=json.loads((ROOT.parent/'preparation.json').read_text());source=ROOT.parent/'sources/ForgeBackend/ForgeLandEngine.java';assert sha(source)==prep['sourceSha256']
    a.output.mkdir(parents=True,exist_ok=False);hashes={str(f):sha(f) for f in a.worker.parent.glob('*.dll')};rows=[]
    factory=lambda scenario,**settings:NativeEngine(scenario,worker=a.worker,managed=a.managed,fixture=a.fixture,**settings)
    for case in a.case or CASES:
        row=run_case(case,factory);rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='traceback'}),flush=True)
    if any(sha(Path(path))!=digest for path,digest in hashes.items()) or sha(source)!=prep['sourceSha256']:raise RuntimeError('Pinned test bytes changed during run')
    result=dict(passed=all(r['passed'] for r in rows),cases=rows,sourceSha256=prep['sourceSha256'],nativeBinaries=hashes,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
    (a.output/'report.json').write_text(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
