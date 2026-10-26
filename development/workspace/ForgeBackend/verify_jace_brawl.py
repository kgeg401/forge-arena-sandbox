"""Jace Brawl integration checks through original owned Arena handlers.
Requires an isolated research runtime; no GUI or account service is used.
The bounded scenarios verify outcomes, not all possible deck interactions.
"""
from pathlib import Path
import argparse,os,sys,json,time,hashlib
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
E=a.output;E.mkdir(parents=True,exist_ok=False)
def Engine(*args,**kw):return NativeEngine(*args,worker=a.worker,managed=a.managed,fixture=a.fixture,**kw)

def action(e,op,card=0,plans=None,plan_queue=None,**fields):
    prior=e.state.get('decision') or {};seen={prior.get('token')} if op.startswith('submit_') else set()
    shared=plan_queue is not None;plans=plan_queue if shared else list(plans or []);root=e.begin(op,card,**fields);pending=[root];deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        if e.process.poll() is not None:raise RuntimeError((e.ipc/'engine.log').read_text()[-2500:])
        for key in pending[:]:
            p=e.ipc/'responses'/(key+'.json')
            if p.exists():
                r=json.loads(p.read_text());assert r['accepted'],r['reason'];pending.remove(key);e.state=r['state']
        p=e.ipc/'decision.json'
        if p.exists():
            try:d=json.loads(p.read_text())
            except (FileNotFoundError,PermissionError,json.JSONDecodeError):continue
            spec=d['state'].get('decision',{})
            if d['token'] not in seen:
                seen.add(d['token']);e.state=d['state'];assert plans,('Unexpected choice',spec)
                plan=plans.pop(0)
                if plan['type']=='targets':
                    assert spec['kind']=='targets',spec
                    if 'ids' in plan:targets=plan['ids']
                    elif 'ability' in plan:targets=[next(a['forgeId'] for a in e.state['stackAbilities'] if a['name']==plan['ability'])]
                    elif 'player' in plan:targets=[next(o['forgeId'] for o in spec['options'] if o.get('targetSeat')==plan['player'])]
                    else:targets=[next(c['forgeId'] for zone in ['battlefield','stack','graveyard','hand','command','exile'] for c in e.state.get(zone,[]) if c['name']==plan['name'] and (not plan.get('seat') or c['controller']==plan['seat']))]
                    if targets:
                        reply=e.send('select_targets',decisionToken=d['token'],assignments=[dict(forgeId=target) for target in targets]);assert reply['accepted'],reply
                    pending.append(e.begin('submit_targets',decisionToken=d['token']));continue
                if plan['type']=='attackers':
                    assert spec['kind']=='attackers',spec
                    plan['check'](e.state,spec)
                    reply=e.send('select_attackers',decisionToken=d['token'],assignments=plan['assignments']);assert reply['accepted'],reply
                    pending.append(e.begin('submit_attackers',decisionToken=d['token']));continue
                assert spec['kind']=='choice',spec
                choice=spec['choice'];assert plan['type']==choice['type'],(plan,choice)
                if choice['type']=='number':values=[dict(number=plan['number'])]
                elif choice['type']=='confirm':values=[dict(accept=plan['accept'])]
                else:
                    options=choice['options']
                    if 'all' in plan:selected=options
                    elif 'none' in plan:selected=[]
                    elif 'index' in plan:selected=[options[plan['index']]]
                    elif 'contains' in plan:
                        selected=[o for o in options if plan['contains'] in o['label']];assert len(selected)==1,selected
                    elif 'label' in plan:selected=[next(o for o in options if o['label']==plan['label'])]
                    else:selected=[next(o for o in options if o.get('label')==plan['name'])]
                    values=[dict(choiceId=o['choiceId']) for o in selected]
                pending.append(e.begin('submit_choice',decisionToken=d['token'],assignments=values))
        elif not pending:
            e.state=json.loads((e.ipc/'state.json').read_text())
            if not shared:assert not plans,plans
            return
        time.sleep(.025)
    raise TimeoutError((op,pending,plans,e.ipc))

def resolve(e,plans=None):
    queue=list(plans or [])
    for _ in range(40):
        if not e.state['stack'] and not e.state['stackAbilities']:
            assert not queue,queue
            return
        action(e,'pass_priority',plan_queue=queue)
    raise AssertionError('Explicit sequence exceeded its resolution budget')


def check_jace_draw():
    e=Engine('card-family',fixtureHand=['Island'],fixtureLands=[],fixtureBattlefield=['Jace, Multiverse Architect',"Bolas's Citadel"],fixtureCounters=[dict(seat=1,cardName='Jace, Multiverse Architect',occurrence=0,type='LOYALTY',count=4)],fixtureLibrary=['Plains','Swamp'])
    try:
     c=next(c for c in e.state['battlefield'] if c['name']=='Jace, Multiverse Architect')
     print('initial',e.ipc,'loyalty',c.get('loyalty'),'actions',e.state['legalActivations'],flush=True)
     a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'] and a['api']=='Draw')
     action(e,'activate_ability',c['forgeId'],abilityId=a['abilityId'])
     resolve(e,[dict(type='cards-zone',name='Island')])
     print('final',json.dumps({k:e.state.get(k) for k in ['hand','hidden','battlefield','gap','decision']}),flush=True)
     assert {c['name'] for c in e.state['hand']}=={'Plains','Swamp'}
     assert [c['name'] for c in e.state['hidden'] if c.get('name')]==['Island']
     assert next(x for x in e.state['battlefield'] if x['forgeId']==c['forgeId'])['loyalty']==5
     assert not any(a['forgeId']==c['forgeId'] for a in e.state['legalActivations'])
     (E/'jace-plus-result.json').write_text(json.dumps(dict(passed=True,evidence=str(e.ipc))))
    finally:e.close()

def check_jace_polymorph():
    results=[]
    for case,library,found in [('creature',['Island','Brainstorm','Grizzly Bears','Plains'],'Grizzly Bears'),('planeswalker',['Island','Jace, Cunning Castaway','Plains'],'Jace, Cunning Castaway'),('none',['Island','Plains','Brainstorm'],None)]:
     e=None
     try:
      e=Engine('card-family',fixtureHand=[],fixtureLands=[],fixtureBattlefield=['Jace, Multiverse Architect','Esper Sentinel',"Bolas's Citadel"],fixtureCounters=[dict(seat=1,cardName='Jace, Multiverse Architect',occurrence=0,type='LOYALTY',count=4)],fixtureLibrary=library)
      jace=next(c for c in e.state['battlefield'] if c['name']=='Jace, Multiverse Architect');target=next(c for c in e.state['battlefield'] if c['name']=='Esper Sentinel')
      ability=next(a for a in e.state['legalActivations'] if a['forgeId']==jace['forgeId'] and a['api']=='ChangeZone')
      action(e,'activate_ability',jace['forgeId'],[dict(type='targets',name='Esper Sentinel',seat=1)],abilityId=ability['abilityId']);resolve(e,[dict(type='look',none=True)])
      assert any(c['forgeId']==target['forgeId'] for c in e.state['exile'])
      assert next(c for c in e.state['battlefield'] if c['forgeId']==jace['forgeId'])['loyalty']==1
      if found:
       card=next(c for c in e.state['battlefield'] if c['name']==found)
       if case=='planeswalker':assert card['loyalty']==3,card
       assert [c['name'] for c in e.state['hidden'] if c.get('name')]==['Plains']
      else:assert {c['name'] for c in e.state['battlefield']}=={'Jace, Multiverse Architect',"Bolas's Citadel"}
      results.append(dict(case=case,passed=True,evidence=str(e.ipc)))
     except Exception as ex:results.append(dict(case=case,passed=False,error=str(ex),evidence=str(e.ipc) if e else ''))
     finally:
      if e:e.close()
     print(json.dumps(results[-1]),flush=True);(E/'jace-minus-results.json').write_text(json.dumps(results,indent=2))
    assert all(r['passed'] for r in results),results

def check_jace_combat_tax():
    results=[]
    for pay in [False,True]:
     e=None
     try:
      jaces=['Jace, Multiverse Architect','Jace, Cunning Castaway'];other='Narset, Parter of Veils'
      e=Engine('card-family',fixtureHand=[],fixtureLands=['Plains','Island'],fixtureBattlefield=['Grizzly Bears'],fixtureBattlefieldReady=True,fixtureOpponentBattlefield=[jaces[1],other],fixtureCounters=[dict(seat=2,cardName=n,occurrence=0,type='LOYALTY',count=c) for n,c in zip([jaces[1],other],[3,5])],fixtureOpponentSpell=jaces[0],fixtureOpponentLands=['Plains','Island','Swamp','Mountain','Plains'],fixtureLibrary=['Plains']*10)
      resolve(e)
      creature=next(c for c in e.state['battlefield'] if c['name']=='Grizzly Bears');pws={c['name']:c['forgeId'] for c in e.state['battlefield'] if c['controller']==2};seen=[]
      def check(state,spec):
       offered=next(o for o in spec['options'] if o['forgeId']==creature['forgeId']);targets=offered['attackTargets']
       ids={x['targetForgeId'] for x in targets};assert 0 in ids and pws[other] in ids,targets
       assert all((pws[n] in ids)==pay for n in jaces),targets
       seen.append(True)
      attacked='Jace, Multiverse Architect' if pay else other
      plans=[dict(type='confirm',accept=pay),dict(type='attackers',check=check,assignments=[dict(forgeId=creature['forgeId'],targetSeat=2,targetForgeId=pws[attacked])])]
      for _ in range(18):
       action(e,'pass_priority',plan_queue=plans)
       if seen:break
      assert seen and not plans,(seen,plans,e.state.get('decision'))
      for _ in range(12):
       if next(c for c in e.state['battlefield'] if c['forgeId']==pws[attacked])['loyalty']==(2 if pay else 3):break
       action(e,'pass_priority')
      assert next(c for c in e.state['battlefield'] if c['forgeId']==pws[attacked])['loyalty']==(2 if pay else 3)
      tapped=sum(c['tapped'] for c in e.state['battlefield'] if c['controller']==1 and c['name'] in ['Plains','Island'])
      assert tapped==(2 if pay else 0),tapped
      results.append(dict(case='pay' if pay else 'decline',passed=True,evidence=str(e.ipc)))
     except Exception as ex:results.append(dict(case='pay' if pay else 'decline',passed=False,error=str(ex),evidence=str(e.ipc) if e else ''))
     finally:
      if e:e.close()
     print(json.dumps(results[-1]),flush=True);(E/'jace-tax-results.json').write_text(json.dumps(results,indent=2))
    assert all(r['passed'] for r in results),results

def check_narset_rebound():
    e=Engine('card-family',fixtureHand=['Divination'],fixtureLands=['Island']*3,fixtureBattlefield=['Narset Transcendent'],fixtureCounters=[dict(seat=1,cardName='Narset Transcendent',occurrence=0,type='LOYALTY',count=6)],fixtureLibrary=['Plains']*20)
    try:
     c=next(c for c in e.state['battlefield'] if c['name']=='Narset Transcendent');action(e,'activate_ability',c['forgeId'],abilityId=102148);resolve(e);action(e,'cast_spell',e.state['hand'][0]['forgeId']);resolve(e)
     plans=[dict(type='confirm',accept=True),dict(type='entities',name='Divination'),dict(type='confirm',accept=True)]
     for i in range(80):
      if e.state['turn']>=3 and any(c['name']=='Divination' for c in e.state['graveyard']):break
      action(e,'pass_priority',plan_queue=plans)
     else:raise AssertionError('Rebound did not finish at next upkeep')
     assert e.state['phase']=='UPKEEP',e.state['phase']
     assert len(e.state['hand'])==4,e.state['hand']
     assert not any(c['tapped'] for c in e.state['battlefield'] if c['name']=='Island')
     (E/'narset-rebound-result.json').write_text(json.dumps(dict(passed=True,phase=e.state['phase'],hand=len(e.state['hand']),remainingTestPlans=len(plans),evidence=str(e.ipc))))
     print('passed',e.ipc)
    finally:e.close();print(e.ipc)

def check_ichormoon():
    e=Engine('card-family',fixtureHand=['Ichormoon Gauntlet'],fixtureLands=['Island']*3,fixtureBattlefield=['Jace, the Perfected Mind'],fixtureCounters=[dict(seat=1,cardName='Jace, the Perfected Mind',occurrence=0,type='LOYALTY',count=5)],fixtureLibrary=['Plains']*10)
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId']);action(e,'pass_priority')
     j=next(c for c in e.state['battlefield'] if c['name']=='Jace, the Perfected Mind');offer=next(a for a in e.state['legalActivations'] if a['forgeId']==j['forgeId'] and a['api']=='Proliferate')
     action(e,'activate_ability',j['forgeId'],abilityId=offer['abilityId']);action(e,'pass_priority',plans=[dict(type='entities',name='Jace, the Perfected Mind')])
     j=next(c for c in e.state['battlefield'] if c['name']=='Jace, the Perfected Mind');assert j['loyalty']==6,j['loyalty']
     r=dict(id='native-ichormoon-granted-proliferate',passed=True,evidence=str(e.ipc));(E/'ichormoon-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()

checks=[]
for check in [check_jace_draw,check_jace_polymorph,check_jace_combat_tax,check_narset_rebound,check_ichormoon]:
    try:check();checks.append(dict(name=check.__name__,passed=True))
    except Exception as error:checks.append(dict(name=check.__name__,passed=False,error=str(error)))
result=dict(passed=all(c["passed"] for c in checks),checks=checks,sourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(E/"report.json").write_text(json.dumps(result,indent=2));print(json.dumps(result));raise SystemExit(0 if result["passed"] else 1)
