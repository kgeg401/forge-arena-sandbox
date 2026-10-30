"""Real hand reveal, constrained discard and private-identity native checks.

Initial opposing cards are authored, never read from the native result to build
the outcome oracle. All valid choices use original Arena request handlers.
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
    dict(id='duress-first-eligible',card='Duress',enemy=['Divination','Cancel','Grizzly Bears','Plains'],eligible=[0,1],selected=[0],life=20),
    dict(id='duress-second-eligible',card='Duress',enemy=['Divination','Cancel','Grizzly Bears','Plains'],eligible=[0,1],selected=[1],life=20),
    dict(id='duress-duplicate-identity',card='Duress',enemy=['Divination','Divination','Grizzly Bears','Plains'],eligible=[0,1],selected=[1],life=20),
    dict(id='duress-no-eligible',card='Duress',enemy=['Grizzly Bears','Plains'],eligible=[],selected=[],life=20),
    dict(id='thoughtseize-creature',card='Thoughtseize',enemy=['Divination','Grizzly Bears','Plains'],eligible=[0,1],selected=[1],life=18),
    dict(id='thoughtseize-spell',card='Thoughtseize',enemy=['Divination','Grizzly Bears','Plains'],eligible=[0,1],selected=[0],life=18),
    dict(id='thoughtseize-only-lands',card='Thoughtseize',enemy=['Island','Plains'],eligible=[],selected=[],life=18),
    dict(id='mind-rot-self',card='Mind Rot',own=['Divination','Cancel','Grizzly Bears'],selected=[2,0],life=20,target=1),
    dict(id='mind-rot-self-shortage',card='Mind Rot',own=['Divination'],selected=[0],life=20,target=1),
]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(case,factory,full_human_choices=False):
    e=None
    try:
        own=case.get('own',[]);enemy=case.get('enemy',[])
        e=factory('card-family',randomSeed=7274,fixtureHand=[case['card']]+own,fixtureLands=['Swamp']*3,
                  fixtureLibrary=['Forest','Mountain','Plains'],fixtureOpponentHand=enemy)
        def check(label,value):e.check(label,value)
        spell=next(c['forgeId'] for c in e.state['hand'] if c['name']==case['card'])
        original=[c['forgeId'] for c in e.state['hidden'] if c['zone']=='Hand' and c['owner']==2] if enemy else [c['forgeId'] for c in e.state['hand'] if c['forgeId']!=spell]
        check('Initial authored hand has exactly the expected object count',len(original)==len(enemy or own))
        selected=[original[i] for i in case['selected']];eligible=[original[i] for i in case.get('eligible',range(len(own)))];seen=[]
        def transact(op,identity=0):
            parent=e.begin(op,identity);end=time.monotonic()+20
            while time.monotonic()<end:
                if (e.ipc/'responses'/(parent+'.json')).exists():check('Native command reaches an accepted actual Forge boundary',e.finish(parent)['accepted']);return
                try:message=json.loads((e.ipc/'decision.json').read_text())
                except (FileNotFoundError,PermissionError,json.JSONDecodeError):message=None
                if message and message['parentRequestId']==parent:
                    e.state=message['state'];d=e.state['decision'];fields=dict(decisionToken=d['token']);check('No human callback is silently delegated',not e.state['fidelityGap'])
                    if d['kind']=='targets':
                        seat=case.get('target',2);target=next(o['forgeId'] for o in d['options'] if o.get('targetSeat')==seat)
                        check('Native player target update is accepted',e.send('select_targets',assignments=[dict(forgeId=target)],**fields)['accepted'])
                        check('Native player target submission is accepted',e.send('submit_targets',**fields)['accepted']);seen.append('target')
                    elif d['kind']=='choice' and d['choice']['type']=='look':
                        spec=d['choice'];seen.append('look')
                        check('Original look-only request reveals every actual opposing hand card in order',[o['forgeId'] for o in spec['options']]==original and [o['label'] for o in spec['options']]==enemy and spec['min']==spec['max']==0)
                        check('Reveal does not falsely make any hand public in the rules snapshot',all('name' not in c for c in e.state['hidden'] if c['owner']==2 and c['zone']=='Hand'))
                        bad=e.send('submit_choice',assignments=[dict(choiceId=1)],**fields);check('Look-only acknowledgement cannot select or move a card',not bad['accepted'] and e.state['decision']['token']==d['token'])
                        check('Original look-only handler acknowledges without a selection',e.send('submit_choice',assignments=[],**fields)['accepted'])
                    elif d['kind']=='choice' and d['choice']['type']=='discard-effect':
                        spec=d['choice'];seen.append('discard');options=spec['options']
                        check('Discard picker offers exactly the independently legal original objects',[o['forgeId'] for o in options]==eligible)
                        check('Discard bounds reflect actual Forge shortage rules',spec['min']==spec['max']==len(selected))
                        if enemy:check('Nonselectable revealed cards remain visible through explicit reveal provenance',[o['forgeId'] for o in spec['revealed']]==original and [o['label'] for o in spec['revealed']]==enemy)
                        assignments=[dict(choiceId=next(o['choiceId'] for o in options if o['forgeId']==identity)) for identity in selected]
                        bad=e.send('submit_choice',assignments=[dict(choiceId=9999)],**fields);check('Unrevealed or ineligible identities cannot be selected',not bad['accepted'] and e.state['decision']['token']==d['token'])
                        check('Original native discard handler submits explicit selected objects',e.send('submit_choice',assignments=assignments,**fields)['accepted'])
                    elif d['kind']=='order_cards':
                        check('Discard ordering contains exactly the selected actual objects',sorted(o['forgeId'] for o in d['options'])==sorted(selected))
                        check('Original native order handler preserves the authored discard order',e.send('submit_order_cards',assignments=[dict(forgeId=identity) for identity in selected],**fields)['accepted']);seen.append('order')
                    else:raise AssertionError('Unexpected callback '+json.dumps(d))
                time.sleep(.025)
            raise TimeoutError('Discard/reveal command did not complete')
        transact('cast_spell',spell)
        for _ in range(12):
            if any(c['forgeId']==spell for c in e.state['graveyard']):break
            transact('pass_priority')
        check('Actual source spell resolves to graveyard',any(c['forgeId']==spell for c in e.state['graveyard']))
        actual=[c for c in e.state['graveyard'] if c['forgeId']!=spell]
        check('Only the independently selected original objects were discarded',[c['forgeId'] for c in actual]==selected)
        check('Discarded card names match the authored selected cards',[c['name'] for c in actual]==[(enemy or own)[i] for i in case['selected']])
        retained=[identity for identity in original if identity not in selected]
        remaining=[c['forgeId'] for c in e.state['hidden'] if c['zone']=='Hand' and c['owner']==2] if enemy else [c['forgeId'] for c in e.state['hand']]
        check('Every unselected original card stays in its real hand',remaining==retained)
        check('Actual spell life cost matches the independent oracle',e.state['life']==case['life'] and e.state['opponentLife']==20)
        # These fixtures contain no graveyard-order-sensitive cards. The full
        # human controller therefore skips ordering, and a single mandatory
        # discard from a one-card hand has no choice. Keep reveal acknowledgments.
        forced_single=full_human_choices and len(eligible)==len(selected)==1
        expected=['target']+(['look'] if enemy else [])+(['discard'] if selected and not forced_single else [])+(['order'] if len(selected)>1 and not full_human_choices else [])
        check('The complete expected reveal/discard sequence occurs',seen==expected)
        check('No fidelity gap or unintended match outcome',not e.state['fidelityGap'] and not e.state['gameOver'])
        return dict(id=case['id'],passed=True,checks=len(e.checks),evidence=str(e.ipc))
    except Exception as failure:return dict(id=case['id'],passed=False,error=str(failure)[:1000]+'\n'+str(failure)[-1000:],traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--case',choices=[c['id'] for c in CASES],action='append');a=p.parse_args()
    os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy))
    from native_engine_test_client import NativeEngine
    from runtime_paths import ROOT
    prep=json.loads((ROOT.parent/'preparation.json').read_text());source=ROOT.parent/'sources/ForgeBackend/ForgeLandEngine.java';assert sha(source)==prep['sourceSha256']
    a.output.mkdir(parents=True,exist_ok=False);hashes={str(f):sha(f) for f in a.worker.parent.glob('*.dll')};rows=[]
    factory=lambda scenario,**settings:NativeEngine(scenario,worker=a.worker,managed=a.managed,fixture=a.fixture,**settings)
    full_human_choices=json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text()).get('fullHumanChoices') is True
    for case in CASES:
        if a.case and case['id'] not in a.case:continue
        row=run_case(case,factory,full_human_choices);rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='traceback'}),flush=True)
    if any(sha(Path(path))!=digest for path,digest in hashes.items()) or sha(source)!=prep['sourceSha256']:raise RuntimeError('Pinned test bytes changed during run')
    result=dict(passed=all(r['passed'] for r in rows),cases=rows,sourceSha256=prep['sourceSha256'],nativeBinaries=hashes,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
    (a.output/'report.json').write_text(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
