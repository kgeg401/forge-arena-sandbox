"""Cross-family protection, Aura legality, type layers and native attachment retirement."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time
import traceback


CASES=[('Frogify','blue',True),('Frogify','red',False),('Pacifism','white',True),('Pacifism','blue',False)]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(aura_name,color,falls,factory):
    e=None;identity=aura_name+'-'+color
    try:
        e=factory('card-family',randomSeed=7274,fixtureHand=[aura_name,'Gods Willing'],fixtureLands=['Island','Island','Plains','Plains','Plains'],fixtureBattlefield=["Healer's Hawk"],fixtureLibrary=['Forest','Mountain','Plains'])
        def check(label,value):e.check(label,value)
        creature=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=="Healer's Hawk")
        aura=next(c['forgeId'] for c in e.state['hand'] if c['name']==aura_name);protection=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Gods Willing');choices=[]
        def transact(op,source=0):
            parent=e.begin(op,source);end=time.monotonic()+20
            while time.monotonic()<end:
                if (e.ipc/'responses'/(parent+'.json')).exists():check('Original native action reaches accepted rules boundary',e.finish(parent)['accepted']);return
                try:message=json.loads((e.ipc/'decision.json').read_text())
                except (FileNotFoundError,PermissionError,json.JSONDecodeError):message=None
                if message and message['parentRequestId']==parent:
                    e.state=message['state'];d=e.state['decision'];fields=dict(decisionToken=d['token']);check('No cross-family callback or native presentation gap',not e.state['fidelityGap'])
                    if d['kind']=='targets':
                        check('Actual Hawk remains a legal offered target',any(o['forgeId']==creature for o in d['options']))
                        check('Original target handler selects the authored creature',e.send('select_targets',assignments=[dict(forgeId=creature)],**fields)['accepted'])
                        check('Original target handler submits actual source targeting',e.send('submit_targets',**fields)['accepted'])
                    elif d['kind']=='choice' and d['choice']['type']=='colors':
                        spec=d['choice'];choices.append('color');check('Color request is bound to the resolving protection spell',spec['sourceForgeId']==protection)
                        selected=next(o['choiceId'] for o in spec['options'] if o['color'].lower()==color)
                        check('Original native color chooser submits authored color',e.send('submit_choice',assignments=[dict(choiceId=selected)],**fields)['accepted'])
                    elif d['kind']=='choice' and d['choice']['type']=='entities':
                        spec=d['choice'];check('Aura attachment choice is source-bound and offers the authored creature',spec['sourceForgeId']==aura and spec['min']==spec['max']==1 and any(o['forgeId']==creature for o in spec['options']))
                        selected=next(o['choiceId'] for o in spec['options'] if o['forgeId']==creature)
                        check('Original native entity chooser selects the authored Aura endpoint',e.send('submit_choice',assignments=[dict(choiceId=selected)],**fields)['accepted'])
                    elif d['kind']=='choice' and d['choice']['type']=='partition':
                        spec=d['choice'];choices.append('scry');check('Protection spell then exposes exactly its actual scry card',[o['label'] for o in spec['options']]==['Forest'])
                        check('Original scry control keeps that card on top',e.send('submit_choice',assignments=[dict(choiceId=o['choiceId'],group='top') for o in spec['options']],**fields)['accepted'])
                    else:raise AssertionError('Unexpected shared decision '+json.dumps(d))
                time.sleep(.025)
            raise TimeoutError('Cross-family command deadline')
        def cast(source):
            transact('cast_spell',source)
            for _ in range(12):
                if not e.state['stack'] and not e.state['stackAbilities']:return
                transact('pass_priority')
            raise AssertionError('Cross-family spell resolution bound')
        cast(aura)
        attached=next(c for c in e.state['battlefield'] if c['forgeId']==aura)
        check('Aura resolves attached to the actual authored creature',attached['attachedToForgeId']==creature)
        cast(protection)
        check('Protection and scry decisions occur in original effect order',choices==['color','scry'])
        check('Illegal Aura falls by actual Forge state-based actions; other colors preserve it',any(c['forgeId']==aura for c in e.state['graveyard'])==falls and any(c['forgeId']==aura for c in e.state['battlefield'])!=falls)
        creature_state=next(c for c in e.state['battlefield'] if c['forgeId']==creature)
        if aura_name=='Frogify':
            expected=['Bird'] if falls else ['Frog']
            check('Type-layer lifetime follows the real Aura attachment',set(creature_state['currentSubtypes'])==set(expected))
            check('Printed Flying returns only after the overwriting Aura leaves',('flying' in [k.lower() for k in creature_state['rulesKeywords']])==falls)
        if not falls:check('Unrelated-color protection leaves the original Aura endpoint intact',next(c for c in e.state['battlefield'] if c['forgeId']==aura)['attachedToForgeId']==creature)
        check('Protection spell resolves to graveyard without moving the creature',any(c['forgeId']==protection for c in e.state['graveyard']) and not any(c['forgeId']==creature for c in e.state['graveyard']))
        check('Protection does not consume or reorder the scryed library',len([c for c in e.state['hidden'] if c['zone']=='Library' and c['owner']==1])==3)
        check('Rules game remains usable without a hidden gap',not e.state['gameOver'] and not e.state['fidelityGap'])
        return dict(id=identity,passed=True,checks=len(e.checks),evidence=str(e.ipc))
    except Exception as error:return dict(id=identity,passed=False,error=str(error)[:1200],traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy),DOTNET_PROCESSOR_COUNT='2')
    from native_engine_test_client import NativeEngine
    a.output.mkdir(parents=True,exist_ok=False);rows=[];hashes={str(path):sha(path) for path in [a.config,a.policy,*a.worker.parent.glob('*.dll')]}
    for aura,color,falls in CASES:
        row=run_case(aura,color,falls,lambda *args,**settings:NativeEngine(*args,worker=a.worker,managed=a.managed,fixture=a.fixture,**settings));rows.append(row);print(json.dumps(row),flush=True)
        drift=any(sha(Path(path))!=digest for path,digest in hashes.items())
        result=dict(passed=not drift and len(rows)==len(CASES) and all(r['passed'] for r in rows),cases=rows,artifactDrift=drift,pinnedArtifacts=hashes,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
        (a.output/'report.json').write_text(json.dumps(result,indent=2));
        if drift:break
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
