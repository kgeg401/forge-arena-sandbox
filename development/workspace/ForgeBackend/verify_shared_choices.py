"""Headless, input-driven shared choice checks against the pinned Forge engine.

Initial library order and expected outcomes are authored here. Only initial
objects are seeded; all movement, draws, costs and effects are executed by Forge.
This does not grant production admission or establish native UI presentation.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import traceback


CASES = [
    dict(id='opt-keep',card='Opt',library=['Forest','Mountain','Plains'],plans=[dict(type='partition',groups=['top'],names=['Forest'])],draw=['Forest'],libraryAfter=[1,2],grave=[]),
    dict(id='opt-bottom',card='Opt',library=['Forest','Mountain','Plains'],plans=[dict(type='partition',groups=['bottom'],names=['Forest'])],draw=['Mountain'],libraryAfter=[2,0],grave=[]),
    dict(id='preordain-reverse-top',card='Preordain',library=['Forest','Mountain','Plains','Island'],plans=[dict(type='partition',groups=['top','top'],order=[1,0],names=['Forest','Mountain'])],draw=['Mountain'],libraryAfter=[0,2,3],grave=[]),
    dict(id='preordain-mixed',card='Preordain',library=['Forest','Mountain','Plains','Island'],plans=[dict(type='partition',groups=['bottom','top'],names=['Forest','Mountain'])],draw=['Mountain'],libraryAfter=[2,3,0],grave=[]),
    dict(id='consider-keep',card='Consider',library=['Forest','Mountain','Plains'],plans=[dict(type='partition',groups=['top'],names=['Forest'])],draw=['Forest'],libraryAfter=[1,2],grave=[]),
    dict(id='consider-graveyard',card='Consider',library=['Forest','Mountain','Plains'],plans=[dict(type='partition',groups=['graveyard'],names=['Forest'])],draw=['Mountain'],libraryAfter=[2],grave=['Forest']),
    dict(id='tavern-choose-pump',card='You Meet in a Tavern',library=['Forest','Mountain','Plains'],lands=['Forest']*4,battlefield=['Grizzly Bears'],plans=[dict(type='modes',choose=[2],count=2,minimum=1,maximum=1)],draw=[],libraryAfter=[0,1,2],grave=[],stats=[dict(name='Grizzly Bears',power=4,toughness=4)]),
    dict(id='anticipate-select-order',card='Anticipate',library=['Forest','Mountain','Plains','Island'],lands=['Island']*2,plans=[dict(type='entities',choose=[2],count=3,minimum=1,maximum=1,names=['Forest','Mountain','Plains']),dict(type='order',choose=[2,1],count=2,minimum=2,maximum=2)],draw=['Mountain'],libraryAfter=[3,2,0],grave=[]),
    dict(id='impulse-select-order',card='Impulse',library=['Forest','Mountain','Plains','Island','Swamp'],lands=['Island']*2,plans=[dict(type='entities',choose=[3],count=4,minimum=1,maximum=1),dict(type='order',choose=[3,1,2],count=3,minimum=3,maximum=3)],draw=['Plains'],libraryAfter=[4,3,0,1],grave=[]),
    dict(id='strategic-planning-select-graveyard',card='Strategic Planning',library=['Forest','Mountain','Plains','Island'],lands=['Island']*2,plans=[dict(type='entities',choose=[2],count=3,minimum=1,maximum=1),dict(type='order',choose=[2,1],count=2,minimum=2,maximum=2)],draw=['Mountain'],libraryAfter=[3],grave=['Forest','Plains']),
    dict(id='preordain-all-bottom-reversed',card='Preordain',library=['Forest','Mountain','Plains','Island'],plans=[dict(type='partition',groups=['bottom','bottom'],order=[1,0],names=['Forest','Mountain'])],draw=['Plains'],libraryAfter=[3,1,0],grave=[]),
    dict(id='preordain-one-card',card='Preordain',library=['Forest'],plans=[dict(type='partition',groups=['bottom'],names=['Forest'])],draw=['Forest'],libraryAfter=[],grave=[]),
    dict(id='tavern-choose-party-one',card='You Meet in a Tavern',library=['Grizzly Bears','Forest','Savannah Lions','Mountain','Plains','Island'],lands=['Forest']*4,plans=[dict(type='modes',choose=[1],count=2,minimum=1,maximum=1),dict(type='entities',choose=[2],count=2,minimum=0,maximum=2,names=['Grizzly Bears','Savannah Lions'])],draw=['Savannah Lions'],libraryPrefix=[5],librarySet=[0,1,3,4,5],grave=[]),
    dict(id='tavern-choose-party-none',card='You Meet in a Tavern',library=['Grizzly Bears','Forest','Savannah Lions','Mountain','Plains','Island'],lands=['Forest']*4,plans=[dict(type='modes',choose=[1],count=2,minimum=1,maximum=1),dict(type='entities',choose=[],count=2,minimum=0,maximum=2)],draw=[],libraryPrefix=[5],librarySet=[0,1,2,3,4,5],grave=[]),
    dict(id='invitation-one',card='By Invitation Only',library=['Forest','Mountain','Plains'],lands=['Plains']*5,battlefield=['Grizzly Bears','Savannah Lions'],initialCounters=[dict(seat=1,cardName='Grizzly Bears',occurrence=0,type='P1P1',count=3)],plans=[dict(type='number',number=1,minimum=0,maximum=13),dict(type='sacrifice',choose=[2],count=2,minimum=1,maximum=1)],draw=[],libraryAfter=[0,1,2],grave=['Savannah Lions'],stats=[dict(name='Grizzly Bears',power=5,toughness=5)]),
    dict(id='invitation-zero',card='By Invitation Only',library=['Forest','Mountain','Plains'],lands=['Plains']*5,battlefield=['Grizzly Bears','Savannah Lions'],plans=[dict(type='number',number=0,minimum=0,maximum=13)],draw=[],libraryAfter=[0,1,2],grave=[],stats=[dict(name='Grizzly Bears',power=2,toughness=2),dict(name='Savannah Lions',power=2,toughness=1)]),
    dict(id='invitation-thirteen-shortage',card='By Invitation Only',library=['Forest','Mountain','Plains'],lands=['Plains']*5,battlefield=['Grizzly Bears','Savannah Lions'],plans=[dict(type='number',number=13,minimum=0,maximum=13),dict(type='sacrifice',choose=[1,2],count=2,minimum=2,maximum=2),dict(type='legacy-order',choose=[2,1],count=2)],draw=[],libraryAfter=[0,1,2],grave=['Grizzly Bears','Savannah Lions']),
    dict(id='rampant-growth-find',card='Rampant Growth',library=['Forest','Mountain','Plains','Grizzly Bears'],lands=['Forest']*2,plans=[dict(type='cards-zone',choose=[2],count=3,minimum=0,maximum=1,names=['Forest','Mountain','Plains'])],draw=[],libraryPrefix=[],librarySet=[0,2,3],grave=[],landArrivals=[dict(name='Mountain',tapped=True)]),
    dict(id='rampant-growth-fail-to-find',card='Rampant Growth',library=['Forest','Mountain','Plains','Grizzly Bears'],lands=['Forest']*2,plans=[dict(type='cards-zone',choose=[],count=3,minimum=0,maximum=1),dict(type='confirm',accept=True)],draw=[],libraryPrefix=[],librarySet=[0,1,2,3],grave=[]),
    dict(id='rampant-growth-resume-search',card='Rampant Growth',library=['Forest','Mountain','Plains','Grizzly Bears'],lands=['Forest']*2,plans=[dict(type='cards-zone',choose=[],count=3,minimum=0,maximum=1),dict(type='confirm',accept=False),dict(type='cards-zone',choose=[2],count=3,minimum=0,maximum=1)],draw=[],libraryPrefix=[],librarySet=[0,2,3],grave=[],landArrivals=[dict(name='Mountain',tapped=True)]),
    dict(id='snakeskin-counter-add',card='Snakeskin Veil',library=['Forest','Mountain','Plains'],lands=['Forest'],battlefield=['Grizzly Bears'],plans=[dict(type='targets',name='Grizzly Bears')],draw=[],libraryAfter=[0,1,2],grave=[],stats=[dict(name='Grizzly Bears',power=3,toughness=3,counters={'P1P1':1})]),
    dict(id='render-inert-remove-all',card='Render Inert',library=['Forest','Mountain','Plains'],lands=['Swamp']*3,battlefield=['Grizzly Bears'],initialCounters=[dict(seat=1,cardName='Grizzly Bears',occurrence=0,type='P1P1',count=3)],plans=[dict(type='targets',name='Grizzly Bears'),dict(type='number',number=3,minimum=0,maximum=3),dict(type='number',number=0,minimum=0,maximum=2)],draw=['Forest'],libraryAfter=[1,2],grave=[],stats=[dict(name='Grizzly Bears',power=2,toughness=2,counters={})]),
    dict(id='render-inert-two-types',card='Render Inert',library=['Forest','Mountain','Plains'],lands=['Swamp']*3,battlefield=['Grizzly Bears'],initialCounters=[dict(seat=1,cardName='Grizzly Bears',occurrence=0,type='P1P1',count=3),dict(seat=1,cardName='Grizzly Bears',occurrence=0,type='CHARGE',count=2)],plans=[dict(type='targets',name='Grizzly Bears'),dict(type='counter-type',chooseType='CHARGE',types=['CHARGE','P1P1'],count=2,minimum=1,maximum=1),dict(type='number',number=2,minimum=0,maximum=2),dict(type='counter-type',chooseType='P1P1',types=['CHARGE','P1P1'],count=2,minimum=1,maximum=1),dict(type='number',number=3,minimum=0,maximum=3)],draw=['Forest'],libraryAfter=[1,2],grave=[],stats=[dict(name='Grizzly Bears',power=2,toughness=2,counters={})]),
    dict(id='cancel-creature-spell',card='Cancel',library=['Forest','Mountain','Plains'],lands=['Island']*3,opponentSpell='Savannah Lions',opponentLands=['Plains'],plans=[dict(type='targets',name='Savannah Lions')],draw=[],libraryAfter=[0,1,2],grave=[],counterDestination='graveyard'),
    dict(id='negate-noncreature-spell',card='Negate',library=['Forest','Mountain','Plains'],lands=['Island']*2,opponentSpell='Divination',opponentLands=['Island']*3,plans=[dict(type='targets',name='Divination')],draw=[],libraryAfter=[0,1,2],grave=[],counterDestination='graveyard'),
    dict(id='disdainful-stroke-large-spell',card='Disdainful Stroke',library=['Forest','Mountain','Plains'],lands=['Island']*2,opponentSpell='Siege Mastodon',opponentLands=['Plains']*5,plans=[dict(type='targets',name='Siege Mastodon')],draw=[],libraryAfter=[0,1,2],grave=[],counterDestination='graveyard'),
    dict(id='dissipate-exile-spell',card='Dissipate',library=['Forest','Mountain','Plains'],lands=['Island']*3,opponentSpell='Divination',opponentLands=['Island']*3,plans=[dict(type='targets',name='Divination')],draw=[],libraryAfter=[0,1,2],grave=[],counterDestination='exile'),
    dict(id='sinister-sabotage-counter-surveil',card='Sinister Sabotage',library=['Forest','Mountain','Plains'],lands=['Island']*3,opponentSpell='Siege Mastodon',opponentLands=['Plains']*5,plans=[dict(type='targets',name='Siege Mastodon'),dict(type='partition',groups=['graveyard'],names=['Forest'])],draw=[],libraryAfter=[1,2],grave=['Forest'],counterDestination='graveyard'),
]
NATIVE = None


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_case(case,engine_factory=None,test_invalid=True):
    from engine_test_client import Engine
    engine=None
    try:
        opponent=dict(fixtureOpponentSpell=case['opponentSpell'],fixtureOpponentLands=case['opponentLands']) if case.get('opponentSpell') else {}
        engine=(engine_factory or Engine)('card-family',randomSeed=7274,fixtureHand=[case['card']],fixtureLands=case.get('lands',['Island']),fixtureLibrary=case['library'],fixtureBattlefield=case.get('battlefield',[]),fixtureCounters=case.get('initialCounters',[]),**opponent)
        e=engine
        def check(label,value):e.check(label,value)
        check('Independent research human controller is active',e.state['researchControls']['strictHumanCallbacks'])
        initial_ids=[v['forgeId'] for v in e.state['hidden'] if v['owner']==1 and v['zone']=='Library']
        check('Initial library has exactly authored objects',len(initial_ids)==len(case['library']))
        spell=next(v['forgeId'] for v in e.state['hand'] if v['name']==case['card'])
        opposing=next((c['forgeId'] for c in e.state['stack'] if c['owner']==2),None)
        plans=iter(case['plans']);used=0

        def answer(decision):
            nonlocal used
            plan=next(plans);used+=1
            check('No unmapped callback was silently delegated',not e.state['fidelityGap'])
            if plan['type']=='targets':
                check('Actual Forge targeting decision is pending',decision['kind']=='targets')
                target=next(c['forgeId'] for c in e.state['battlefield']+e.state['stack'] if c['name']==plan['name'])
                check('Target is among the actual legal offered objects',any(o['forgeId']==target for o in decision['options']))
                fields=dict(decisionToken=decision['token'])
                if test_invalid:
                    reply=e.send('select_targets',assignments=[dict(forgeId=-99999)],**fields);check('Foreign native target is rejected',not reply['accepted'])
                    reply=e.send('submit_targets',**fields);check('Target cannot be omitted before casting payment',not reply['accepted'])
                reply=e.send('select_targets',assignments=[dict(forgeId=target)],**fields);check('Explicit human target accepted',reply['accepted'])
                reply=e.send('submit_targets',**fields);check('Explicit target submission accepted',reply['accepted']);return
            legacy=plan['type']=='legacy-order'
            check('Shared choice type is explicitly expected',decision['kind']=='order_cards' if legacy else decision['kind']=='choice' and decision['choice']['schema']==1 and decision['choice']['type']==plan['type'])
            spec=decision if legacy else decision['choice'];token=decision['token'];options=spec['options'];submit='submit_order_cards' if legacy else 'submit_choice'
            if legacy:
                check('Legacy graveyard order includes every sacrificed creature',len(options)==plan['count'])
                values=[dict(forgeId=options[i-1]['forgeId']) for i in plan['choose']]
                invalid=[[],values+values,[dict(forgeId=-1)],[dict(forgeId=1.5)]]
            elif plan['type']=='partition':
                check('Player sees exactly the authored peeked cards',[v['label'] for v in options]==plan['names'])
                check('Peeked card identities are the original top objects',[v['forgeId'] for v in options]==initial_ids[:len(options)])
                order=plan.get('order',list(range(len(options))))
                values=[dict(choiceId=options[i]['choiceId'],group=plan['groups'][i]) for i in order]
                invalid=[[],values+values[:1],[dict(choiceId=-99999,group='top')], [{**v,'group':'unoffered'} for v in values], [{**v,'extra':True} for v in values]]
            elif plan['type']=='number':
                check('Numeric bounds come from the actual Forge callback',spec['min']==plan['minimum'] and spec['max']==plan['maximum'])
                values=[dict(number=plan['number'])]
                invalid=[[],values+values,[dict(number=spec['min']-1)],[dict(number=spec['max']+1)],[dict(number=1.5)],[dict(number='1')],[dict(number=True)],[dict(number=plan['number'],extra=True)]]
            elif plan['type']=='confirm':
                values=[dict(accept=plan['accept'])]
                invalid=[[],values+values,[dict(accept=1)],[dict(accept='true')],[dict(accept=plan['accept'],extra=True)]]
            else:
                check('Selection bounds come from the actual Forge callback',len(options)==plan['count'] and spec['min']==plan['minimum'] and spec['max']==plan['maximum'])
                if 'names' in plan:check('Selection labels match the authored cards',[v['label'] for v in options]==plan['names'])
                if plan['type']=='counter-type':
                    check('Counter picker contains the exact offered counter types',sorted(v['counterType'] for v in options)==plan['types'])
                    values=[dict(choiceId=next(v['choiceId'] for v in options if v['counterType']==plan['chooseType']))]
                else:values=[dict(choiceId=i) for i in plan['choose']]
                invalid=[[dict(choiceId=0)],[dict(choiceId=len(options)+1)],[dict(choiceId=1)]*(spec['max']+1),[dict(choiceId=1.5)],[dict(choiceId=1,extra=True)]]
                if spec['min']>0:invalid.append([])
            before=copy.deepcopy(e.state)
            for bad in invalid if test_invalid else []:
                reply=e.send(submit,decisionToken=token,assignments=bad)
                check('Invalid choice stays rejected and pending',not reply['accepted'] and e.state['decision']['token']==token)
                check('Invalid choice does not mutate game state',all(e.state[k]==before[k] for k in ('hand','battlefield','graveyard','hidden','life','stack')))
            if test_invalid:
                reply=e.send(submit,decisionToken='stale-choice',assignments=values)
                check('Stale choice token is rejected',not reply['accepted'] and e.state['decision']['token']==token)
            if NATIVE:
                probe,managed,fixture=NATIVE
                incoming=e.ipc/f'native-choice-{used}-input.json';outgoing=e.ipc/f'native-choice-{used}-report.json'
                from runtime_paths import ROOT
                incoming.write_text(json.dumps(dict(decision=decision,assignments=values,labRoot=str(ROOT/'native-lab'),researchIpc=str(e.ipc)),indent=2),encoding='utf8')
                from headless_resources import process_flags
                native=subprocess.run(['dotnet',str(probe),str(managed),str(fixture),str(incoming),str(outgoing)],capture_output=True,text=True,encoding='utf8',timeout=15,creationflags=process_flags())
                (e.ipc/f'native-choice-{used}-log.txt').write_text(native.stdout+'\n'+native.stderr,encoding='utf8')
                check('Installed Arena parser and response handler complete the round trip',native.returncode==0)
                result=json.loads(outgoing.read_text(encoding='utf8'))
                check('Native protocol checks pass before applying the response',result['passed'])
                values=result['assignments']
                if result.get('submittedRequestId'):
                    reply=e.finish(result['submittedRequestId'])
                    check('Actual bridge submitted a valid human choice to Forge',reply['accepted'])
                    return
            reply=e.send(submit,decisionToken=token,assignments=values)
            check('Explicit valid human choice is accepted',reply['accepted'])

        def transact(op,identity=0):
            parent=e.begin(op,identity);deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                result=e.ipc/'responses'/(parent+'.json')
                if result.exists():
                    reply=e.finish(parent);check('Parent Forge operation accepted',reply['accepted']);return
                path=e.ipc/'decision.json'
                if path.exists():
                    try:observed=json.loads(path.read_text())
                    except (FileNotFoundError,PermissionError,json.JSONDecodeError):time.sleep(.02);continue
                    if observed['parentRequestId']==parent:
                        e.state=observed['state'];answer(e.state['decision'])
                if e.process.poll() is not None:raise RuntimeError((e.ipc/'engine.log').read_text()[-2500:])
                time.sleep(.025)
            raise TimeoutError('Forge operation did not complete')

        transact('cast_spell',spell)
        check('Spell is really on the stack',any(v['forgeId']==spell for v in e.state['stack']))
        for _ in range(10):
            if any(v['forgeId']==spell for v in e.state['graveyard']):break
            transact('pass_priority')
        check('Every expected choice occurred',used==len(case['plans']))
        check('Spell really resolved to graveyard',any(v['forgeId']==spell for v in e.state['graveyard']))
        if case.get('counterDestination'):
            check('Countered spell actually reaches the required destination',any(c['forgeId']==opposing for c in e.state[case['counterDestination']]) and not any(c['forgeId']==opposing for c in e.state['stack']+e.state['battlefield']))
            check('Actual counter effect identifies its real source and target',any(event['kind']=='countered' and event['sourceForgeId']==spell and event['targetForgeId']==opposing for event in e.state['events']))
        check('Drawn cards match the independent expected result',[v['name'] for v in e.state['hand'] if v['owner']==1]==case['draw'])
        if 'drawnOriginalIndices' in case:check('Drawn duplicate-name cards retain the independently chosen original identities',[v['forgeId'] for v in e.state['hand'] if v['owner']==1]==[initial_ids[i] for i in case['drawnOriginalIndices']])
        actual=[v['forgeId'] for v in e.state['hidden'] if v['owner']==1 and v['zone']=='Library']
        if 'libraryAfter' in case:check('Library order matches authored post-resolution order',actual==[initial_ids[i] for i in case['libraryAfter']])
        else:
            check('Randomized remainder preserves exactly the authored objects',sorted(actual)==sorted(initial_ids[i] for i in case['librarySet']))
            check('Untouched library prefix stays above the randomized remainder',actual[:len(case['libraryPrefix'])]==[initial_ids[i] for i in case['libraryPrefix']])
        check('Actual surveilled cards arrive in graveyard',sorted(v['name'] for v in e.state['graveyard'] if v['forgeId']!=spell and v['owner']==1)==sorted(case['grave']))
        if 'graveyardOriginalIndices' in case:check('Graveyard insertion order preserves the independently authored original identities',[v['forgeId'] for v in e.state['graveyard'] if v['forgeId']!=spell and v['owner']==1]==[initial_ids[i] for i in case['graveyardOriginalIndices']])
        for expected in case.get('stats',[]):
            card=next(v for v in e.state['battlefield'] if v['name']==expected['name'])
            check('Selected mode applied the authored creature stats',(card['power'],card['toughness'])==(expected['power'],expected['toughness']))
            if 'counters' in expected:check('Actual counter totals match the independent oracle',{v['type']:v['count'] for v in card['counters']}==expected['counters'])
        for expected in case.get('landArrivals',[]):
            matches=[c for c in e.state['battlefield'] if c['name']==expected['name'] and c['owner']==1]
            check('Searched land really enters the battlefield in the required state',len(matches)==1 and matches[0]['tapped']==expected['tapped'])
        check('No fidelity gap or accidental outcome',not e.state['fidelityGap'] and not e.state['gameOver'])
        return dict(id=case['id'],passed=True,checks=len(e.checks),evidence=str(e.ipc))
    except Exception as error:
        return dict(id=case['id'],passed=False,error=str(error),traceback=traceback.format_exc(),evidence=str(engine.ipc) if engine else None)
    finally:
        if engine:engine.close()


def main():
    global NATIVE
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append')
    p.add_argument('--snapshot-source',action='store_true',help='Pin the immutable prepared source snapshot while development continues in the checkout')
    for key in ('native-probe','native-worker','native-managed','native-fixture'):p.add_argument('--'+key,type=Path)
    a=p.parse_args()
    if a.native_probe and a.native_worker:p.error('Choose one native test path')
    executable=a.native_probe or a.native_worker
    values=(executable,a.native_managed,a.native_fixture);factory=None
    if any(values):
        if not all(values):p.error('Native probe, managed directory and fixture are required together')
        if a.native_probe:NATIVE=values
        else:
            from native_engine_test_client import NativeEngine
            factory=lambda scenario,**kwargs:NativeEngine(scenario,worker=a.native_worker,managed=a.native_managed,fixture=a.native_fixture,**kwargs)
    a.output.mkdir(parents=True,exist_ok=False)
    cases=[c for c in CASES if not a.case or c['id'] in a.case];assert cases,'No selected authored cases'
    from runtime_paths import ROOT
    checkout_source=Path(__file__).with_name('ForgeLandEngine.java');checkout_before=sha(checkout_source)
    source=ROOT.parent/'sources/ForgeBackend/ForgeLandEngine.java' if a.snapshot_source else checkout_source
    before=sha(source);rows=[]
    preparation=json.loads((ROOT.parent/'preparation.json').read_text(encoding='utf8'))
    if preparation['sourceSha256']!=before:raise RuntimeError('Compiled research engine differs from the current test source')
    if sha(ROOT/'native-lab/bridge-card-manifest.json')!=preparation['generatedManifestSha256']:raise RuntimeError('Research mapping changed after preparation')
    for name,digest in preparation['classes'].items():
        if sha(ROOT/'build/ForgeBackend/classes'/name)!=digest:raise RuntimeError('Prepared class bytes changed: '+name)
    native_hashes={}
    if executable:
        expected={'SharedClientCore.dll':'42f2fb5f062ccc6098182a902d411746070759a404e875b6e0aac44d3b7ccc6e','Wizards.MDN.GreProtobuf.dll':'7ca28480089cc2b21417abfea82b9c8721ff855f0369966858d70d58f2afcdae','Google.Protobuf.dll':'592761c0cea52110c818978c94e33202d942a9a36ef8742b224d08fac5d42f2b'}
        for name,digest in expected.items():
            native_hashes[name]=sha(a.native_managed/name)
            if native_hashes[name]!=digest:raise RuntimeError('Owned parser build changed; review before testing: '+name)
        native_hashes.update({str(path):sha(path) for path in executable.parent.glob('*.dll')})
    for case in cases:
        row=run_case(case,factory,not bool(factory));rows.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ('error','traceback')}|({'error':row['error'][:350]} if 'error' in row else {})),flush=True)
        if sha(source)!=before:raise RuntimeError('Engine source changed during this run')
        for name,digest in preparation['classes'].items():
            if sha(ROOT/'build/ForgeBackend/classes'/name)!=digest:raise RuntimeError('Prepared class changed during the run: '+name)
        for path,digest in native_hashes.items():
            candidate=Path(path) if Path(path).is_absolute() else a.native_managed/path
            if sha(candidate)!=digest:raise RuntimeError('Native test binaries changed during the run')
    result=dict(passed=all(v['passed'] for v in rows),cases=rows,inputs=cases,sourceSha256=before,testedSource=str(source),checkoutSourceAtStart=checkout_before,checkoutSourceAtEnd=sha(checkout_source),preparedRuntimeSha256=sha(ROOT.parent/'preparation.json'),nativeResponseRoundTrip=bool(executable),persistentNativeSession=bool(factory),invalidInputChecks=not bool(factory),nativeBinarySha256=native_hashes,nativeProbeSha256=sha(executable) if executable else None,finishedUtc=datetime.now(timezone.utc).isoformat(),scope='Headless actual Forge decisions and independent initial-state/result oracles. Optional installed Arena parser/response round trip. No rendered UI, production admission or exhaustive interactions claimed.')
    (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
