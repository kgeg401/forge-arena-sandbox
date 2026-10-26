"""Independent temporary/static keyword, source and lifetime scenarios.

Native keyword IDs come from exact owned metadata. Forge still executes every
spell, cost, continuous effect, phase change, attachment and zone transition.
These scenarios do not verify every other ability printed on the Aura cards.
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
    dict(card='Crash Through',lands=['Mountain'],keywords=['trample'],delta=[0,0],draw=True,all=True),
    dict(card='Expedite',lands=['Mountain'],keywords=['haste'],delta=[0,0],draw=True,haste=True),
    dict(card='Mighty Leap',lands=['Plains']*2,keywords=['flying'],delta=[2,2]),
    dict(card='Moment of Heroism',lands=['Plains']*2,keywords=['lifelink'],delta=[2,2]),
    dict(card='Battle-Rage Blessing',lands=['Swamp']*2,keywords=['deathtouch','indestructible'],delta=[0,0]),
    dict(card='Sure Strike',lands=['Mountain']*2,keywords=['first strike'],delta=[3,0]),
    dict(card='Uncaged Fury',lands=['Mountain']*3,keywords=['double strike'],delta=[1,1]),
    dict(card='Aim High',lands=['Forest']*2,keywords=['reach'],delta=[2,2]),
    dict(card='Rush of Vitality',lands=['Swamp']*2,keywords=['indestructible','lifelink'],delta=[1,0]),
    dict(card="Sentinel's Eyes",lands=['Plains'],keywords=['vigilance'],delta=[1,1],aura=True),
    dict(card='Sticky Fingers',lands=['Mountain'],keywords=['menace'],delta=[0,0],aura=True),
]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(case,factory):
    e=None
    try:
        hand=[case['card']]+(['Unsummon'] if case.get('aura') else [])
        e=factory('card-family',randomSeed=7274,fixtureHand=hand,fixtureLands=case['lands']+(['Island'] if case.get('aura') else []),fixtureLibrary=['Forest','Mountain','Plains','Island','Swamp','Forest'],fixtureBattlefield=['Grizzly Bears','Savannah Lions'])
        def check(label,value):e.check(label,value)
        source=next(c['forgeId'] for c in e.state['hand'] if c['name']==case['card']);target=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears');other=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Savannah Lions')
        top=next(c['forgeId'] for c in e.state['hidden'] if c['zone']=='Library' and c['owner']==1);attacker_seen=False
        def transact(op,identity=0):
            nonlocal attacker_seen
            parent=e.begin(op,identity);end=time.monotonic()+20
            while time.monotonic()<end:
                if (e.ipc/'responses'/(parent+'.json')).exists():check('Original native command reaches accepted Forge boundary',e.finish(parent)['accepted']);return
                try:message=json.loads((e.ipc/'decision.json').read_text())
                except (FileNotFoundError,PermissionError,json.JSONDecodeError):message=None
                if message and message['parentRequestId']==parent:
                    e.state=message['state'];d=e.state['decision'];fields=dict(decisionToken=d['token']);check('No callback is silently delegated',not e.state['fidelityGap'])
                    if d['kind']=='targets':
                        check('Actual targeting offers the authored creature',target in [o.get('forgeId') for o in d['options']])
                        check('Native target selection accepted',e.send('select_targets',assignments=[dict(forgeId=target)],**fields)['accepted'])
                        check('Native target submission accepted',e.send('submit_targets',**fields)['accepted'])
                    elif d['kind']=='choice' and d['choice']['type']=='entities':
                        spec=d['choice'];check('Actual Aura attachment confirmation has only the chosen legal host',len(spec['options'])==1 and spec['options'][0]['forgeId']==target and spec['min']==spec['max']==1)
                        check('Native Aura attachment confirmation accepted',e.send('submit_choice',assignments=[dict(choiceId=spec['options'][0]['choiceId'])],**fields)['accepted'])
                    elif d['kind']=='attackers':
                        check('Haste actually permits the initially summoning-sick creature to attack',case.get('haste') and target in [o['forgeId'] for o in d['options']]);attacker_seen=True
                        check('Explicit native no-attack submission accepted',e.send('submit_attackers',**fields)['accepted'])
                    else:raise AssertionError('Unexpected callback '+json.dumps(d))
                time.sleep(.025)
            raise TimeoutError('Keyword operation did not complete')
        def resolve(identity,destination):
            for _ in range(12):
                if any(c['forgeId']==identity for c in e.state[destination]):return
                transact('pass_priority')
            raise AssertionError('Source did not reach its actual destination')
        transact('cast_spell',source);resolve(source,'battlefield' if case.get('aura') else 'graveyard')
        def assert_grants(active=True):
            for identity,base in [(target,[2,2]),(other,[2,1])]:
                card=next(c for c in e.state['battlefield'] if c['forgeId']==identity);affected=active and (identity==target or case.get('all'))
                grants=card['keywordGrants'];expected=case['keywords'] if affected else []
                check('Active keyword identities match independent printed-rule expectations',sorted(g['keyword'].lower() for g in grants)==sorted(expected))
                check('Every native keyword grant has the actual original source object',all(g['sourceForgeId']==source for g in grants))
                check('No keyword was silently dropped due to missing presentation support',not card['keywordPresentationGaps'])
                delta=case['delta'] if affected else [0,0];check('Actual characteristics match the independently expected deltas',[card['power'],card['toughness']]==[base[0]+delta[0],base[1]+delta[1]])
        assert_grants()
        check('Cantrip moves the independently authored top object to hand',([c['forgeId'] for c in e.state['hand']]==[top]) if case.get('draw') else (len(e.state['hand'])==int(bool(case.get('aura')))))
        if case.get('aura'):
            aura=next(c for c in e.state['battlefield'] if c['forgeId']==source);check('Continuous keyword source is the really attached Aura',aura.get('attachedToForgeId')==target)
            unsummon=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Unsummon');transact('cast_spell',unsummon);resolve(unsummon,'graveyard')
            check('Host really returns to hand and Aura reaches graveyard through SBA',any(c['forgeId']==target for c in e.state['hand']) and any(c['forgeId']==source for c in e.state['graveyard']))
            check('No keyword grant survives departure of its actual objects',all(not c['keywordGrants'] for zone in ('hand','battlefield','graveyard') for c in e.state[zone]))
        else:
            turn=e.state['turn']
            for _ in range(45):
                if e.state['turn']>turn and e.state['activeSeat']==1 and e.state['phase']=='MAIN1':break
                transact('pass_priority')
            check('Real phase loop reaches the next local main phase',e.state['turn']>turn and e.state['activeSeat']==1 and e.state['phase']=='MAIN1');assert_grants(False)
            if case.get('haste'):check('Haste attack permission was genuinely exercised before expiry',attacker_seen)
        check('No unintended outcome or fidelity gap',not e.state['gameOver'] and not e.state['fidelityGap'])
        return dict(id=case['card'],passed=True,checks=len(e.checks),evidence=str(e.ipc))
    except Exception as failure:return dict(id=case['card'],passed=False,error=str(failure)[:1000]+'\n'+str(failure)[-1000:],traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--card',choices=[c['card'] for c in CASES],action='append');a=p.parse_args();os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy))
    from native_engine_test_client import NativeEngine
    from runtime_paths import ROOT
    prep=json.loads((ROOT.parent/'preparation.json').read_text());source=ROOT.parent/'sources/ForgeBackend/ForgeLandEngine.java';assert sha(source)==prep['sourceSha256']
    a.output.mkdir(parents=True,exist_ok=False);hashes={str(f):sha(f) for f in a.worker.parent.glob('*.dll')};rows=[]
    factory=lambda scenario,**settings:NativeEngine(scenario,worker=a.worker,managed=a.managed,fixture=a.fixture,**settings)
    for case in CASES:
        if a.card and case['card'] not in a.card:continue
        row=run_case(case,factory);rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='traceback'}),flush=True)
    if any(sha(Path(path))!=digest for path,digest in hashes.items()) or sha(source)!=prep['sourceSha256']:raise RuntimeError('Pinned test bytes changed during run')
    result=dict(passed=all(r['passed'] for r in rows),cases=rows,sourceSha256=prep['sourceSha256'],nativeBinaries=hashes,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
    (a.output/'report.json').write_text(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
