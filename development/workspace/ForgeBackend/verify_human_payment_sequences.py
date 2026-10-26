"""Pinned Forge human payment/effect sequences through original Arena handlers.
These are explicit scenario tests, not a full card-catalogue support claim.
"""
import argparse,json,os,time,hashlib
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for k in ('config','worker','managed','fixture','output'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--group',action='append',help='Run only a named scenario group')
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
a.output.mkdir(parents=True,exist_ok=False);E=a.output
records=[]
inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__),a.config,a.fixture,a.worker,Path(json.loads(a.config.read_text())['privateRoot'])/'native-lab/bridge-card-manifest.json')}
started=time.time()
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



def check_payments_and_search():
 results=[]
 cases=[
  dict(id='village-rites-sacrifice',card='Village Rites',lands=['Swamp'],battlefield=['Grizzly Bears'],library=['Forest','Plains'],plans=[dict(type='cards-effect',name='Grizzly Bears')],check='sacrifice'),
  dict(id='finale-x',card='Finale of Devastation',lands=['Forest','Forest','Plains','Plains'],battlefield=[],library=['Grizzly Bears'],plans=[dict(type='number',number=2)],check='search'),
  dict(id='chord-x-convoke',card='Chord of Calling',lands=['Forest']*3,battlefield=['Grizzly Bears','Grizzly Bears'],library=['Grizzly Bears'],plans=[dict(type='number',number=2),dict(type='cards-effect',all=True),dict(type='options',label='Green'),dict(type='options',label='Green')],check='search')
 ]
 for case in cases:
     e=Engine('card-family',fixtureHand=[case['card']],fixtureLands=case['lands'],fixtureBattlefield=case['battlefield'],fixtureLibrary=case['library'])
     try:
         card=e.state['hand'][0];assert card['forgeId'] in e.state['legalCasts'],e.state['unavailableActions']
         action(e,'cast_spell',card['forgeId'],case['plans']);assert not e.state['fidelityGap'],e.state['fidelityGap']
         assert len(e.state['stack'])==1
         if case['check']=='sacrifice':
             assert any(c['name']=='Grizzly Bears' for c in e.state['graveyard']);action(e,'pass_priority');assert {c['name'] for c in e.state['hand']}=={'Forest','Plains'}
         else:
             search=[dict(type='confirm',accept=True),dict(type='confirm',accept=False)] if case['card']=='Finale of Devastation' else []
             action(e,'pass_priority',plans=search+[dict(type='cards-zone',name='Grizzly Bears')]);assert any(c['name']=='Grizzly Bears' and not c['tapped'] for c in e.state['battlefield'])
         assert not e.state['fidelityGap'] and e.process.poll() is None
         results.append(dict(id=case['id'],passed=True,evidence=str(e.ipc)));print(json.dumps(results[-1]),flush=True)
     finally:e.close()
     (E/'human-payment-native-results.json').write_text(json.dumps(results,indent=2))

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_token_creation():
 results=[]
 cases=[
  dict(id='chatterstorm-token',card='Chatterstorm',lands=['Forest']*2,battlefield=[],plans=[],tokens={'Squirrel Token':1}),
  dict(id='chatterfang-replacement',card='Chatterstorm',lands=['Forest']*2,battlefield=['Chatterfang, Squirrel General'],plans=[],tokens={'Squirrel Token':2}),
  dict(id='goose-food',card='Gilded Goose',lands=['Forest'],battlefield=[],plans=[],tokens={'Food Token':1}),
  dict(id='squirrel-girl-enter',card='The Unbeatable Squirrel Girl',lands=['Forest']*4,battlefield=[],plans=[],tokens={'Squirrel Token':1})
 ]
 for c in cases:
  e=None
  try:
   e=Engine('card-family',randomSeed=7274,fixtureHand=[c['card']],fixtureLands=c['lands'],fixtureBattlefield=c['battlefield'],fixtureLibrary=['Plains']*20)
   action(e,'cast_spell',e.state['hand'][0]['forgeId'],c['plans'])
   for n in range(8):
    if not e.state['stack'] and not e.state.get('stackAbilities'):break
    action(e,'pass_priority')
   found={name:sum(x['name']==name for x in e.state['battlefield']) for name in c['tokens']};assert found==c['tokens'],found
   assert not e.state['fidelityGap'];r=dict(id=c['id'],passed=True,tokens=found,evidence=str(e.ipc))
  except BaseException as ex:r=dict(id=c['id'],passed=False,error=str(ex),evidence=str(e.ipc) if e else '')
  finally:
   if e:e.close()
  results.append(r);print(json.dumps(r),flush=True);(E/'token-native-results.json').write_text(json.dumps(results,indent=2))

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_autopay_with_tower():
 for lands in [['Swamp','Forest','Forest'],['Swamp','Forest'],['Overgrown Tomb','Forest','Swamp','Forest']]:
  e=Engine('card-family',fixtureHand=['Bastion of Remembrance'],fixtureLands=[n for n in lands if n!='Overgrown Tomb'],fixtureBattlefield=['Phyrexian Tower','Llanowar Elves']+([n for n in lands if n=='Overgrown Tomb']),fixtureLibrary=['Plains']*10)
  try:
   creature=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Llanowar Elves')
   action(e,'cast_spell',e.state['hand'][0]['forgeId'])
   assert any(c['name']=='Bastion of Remembrance' for c in e.state['stack']),e.state
   assert any(c['forgeId']==creature for c in e.state['battlefield'])
   assert not e.state.get('decision')
   assert e.state['life']==20
   print(json.dumps(dict(id='bastion-autopay-with-tower',lands=lands,passed=True,evidence=str(e.ipc))),flush=True)
  finally:e.close()

def check_tower_sacrifice_not_automatic():
 e=Engine('card-family',fixtureHand=['Bastion of Remembrance'],fixtureLands=['Forest'],fixtureBattlefield=['Phyrexian Tower','Grizzly Bears'],fixtureLibrary=['Plains']*10)
 try:
  creature=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears')
  e.begin('cast_spell',e.state['hand'][0]['forgeId'])
  limit=time.monotonic()+10
  while not e.state.get('decision') and time.monotonic()<limit:
   status=e.native_wait(e.native_folder/'status.json');e.state=status['state'];time.sleep(.05)
  decision=e.state.get('decision') or {}
  assert decision.get('kind')=='choice',decision
  assert 'Choose a mana source' in decision['choice']['prompt'],decision
  assert any(c['forgeId']==creature for c in e.state['battlefield'])
  print(json.dumps(dict(id='tower-never-sacrifices-creature-automatically',passed=True,evidence=str(e.ipc))),flush=True)
 finally:e.close()

def check_nonbasic_mana():
 results=[]
 cases=[dict(id='relic-tap-any-color',source='Relic of Legends',ability=1055,plans=[dict(type='colors',label='blue')],mana=2),dict(id='peatland-green-life',source='Nurturing Peatland',plans=[dict(type='confirm',accept=True),dict(type='colors',label='green')],mana=16)]
 for c in cases:
  e=None
  try:
   e=Engine('card-family',fixtureHand=[],fixtureLands=[],fixtureBattlefield=[c['source']],fixtureLibrary=['Plains']*10)
   card=next(x for x in e.state['battlefield'] if x['name']==c['source']);offers=[x for x in e.state['legalManaOffers'] if x['forgeId']==card['forgeId']];ability=c.get('ability',offers[0]['abilityId']);before=e.state['life']
   action(e,'activate_mana',card['forgeId'],c['plans'],abilityId=ability)
   assert e.state['manaTotal']==1 and e.state['mana'][0]['color']==c['mana'],e.state['mana'];assert next(x for x in e.state['battlefield'] if x['forgeId']==card['forgeId'])['tapped']
   assert e.state['life']==before-(1 if 'Peatland' in c['source'] else 0)
   r=dict(id=c['id'],passed=True,evidence=str(e.ipc))
  except BaseException as ex:r=dict(id=c['id'],passed=False,error=str(ex),evidence=str(e.ipc) if e else '')
  finally:
   if e:e.close()
  results.append(r);print(json.dumps(r),flush=True);(E/'mana-native-results.json').write_text(json.dumps(results,indent=2))

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_phyrexian_compleated():
 results=[]
 for pay_life in [True,False]:
  e=None
  try:
   e=Engine('card-family',fixtureHand=['Jace, the Perfected Mind'],fixtureLands=['Island']*(3 if pay_life else 4),fixtureLibrary=['Plains']*10)
   action(e,'cast_spell',e.state['hand'][0]['forgeId'],[dict(type='confirm',accept=pay_life)])
   action(e,'pass_priority');j=next(c for c in e.state['battlefield'] if c['name']=='Jace, the Perfected Mind')
   assert e.state['life']==(18 if pay_life else 20),e.state['life'];assert j['loyalty']==(3 if pay_life else 5),j['loyalty']
   r=dict(id='jace-compleated-life' if pay_life else 'jace-compleated-mana',passed=True,evidence=str(e.ipc))
  except BaseException as ex:r=dict(id=str(pay_life),passed=False,error=str(ex),evidence=str(e.ipc) if e else '')
  finally:
   if e:e.close()
  results.append(r);print(json.dumps(r),flush=True);(E/'phyrexian-native-results.json').write_text(json.dumps(results,indent=2))

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_food():
 e=Engine('card-family',fixtureHand=['Gilded Goose'],fixtureLands=['Forest','Plains','Plains'],fixtureLibrary=['Plains']*10)
 try:
  action(e,'cast_spell',e.state['hand'][0]['forgeId']);action(e,'pass_priority');action(e,'pass_priority')
  food=next(c for c in e.state['battlefield'] if c['name']=='Food Token');offer=next(o for o in e.state['legalActivations'] if o['forgeId']==food['forgeId'])
  action(e,'activate_ability',food['forgeId'],abilityId=offer['abilityId']);action(e,'pass_priority')
  assert e.state['life']==23 and not any(c['name']=='Food Token' for c in e.state['battlefield'])
  r=dict(id='native-food-sacrifice-gain-life',passed=True,evidence=str(e.ipc));(E/'food-activation-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
 finally:e.close()

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_card_naming():
 e=Engine('card-family',fixtureHand=['Anointed Peacekeeper'],fixtureLands=['Plains']*3,fixtureOpponentHand=['Grizzly Bears'],fixtureLibrary=['Plains']*10)
 try:
  action(e,'cast_spell',e.state['hand'][0]['forgeId']);action(e,'pass_priority',plans=[dict(type='entities',name='Opponent'),dict(type='look',none=True),dict(type='card-name',name='Grizzly Bears')])
  p=next(c for c in e.state['battlefield'] if c['name']=='Anointed Peacekeeper')
  assert p['namedCards']==['Grizzly Bears'] and len(p['namedCardTitleIds'])==1
  r=dict(id='native-anointed-peacekeeper-name',passed=True,evidence=str(e.ipc));(E/'card-name-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
 finally:e.close()

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_shockland_branches():
 results=[]
 for pay in [True,False]:
  e=Engine('card-family',fixtureHand=['Blood Crypt'],fixtureLands=[],fixtureLibrary=['Plains']*10)
  try:
   action(e,'play_land',e.state['hand'][0]['forgeId'],[dict(type='confirm',accept=pay)])
   card=next(c for c in e.state['battlefield'] if c['name']=='Blood Crypt');assert card['tapped']==(not pay);assert e.state['life']==(18 if pay else 20)
   r=dict(id='blood-crypt-'+str(pay),passed=True,evidence=str(e.ipc));results.append(r);print(json.dumps(r),flush=True)
  finally:e.close()
  (E/'shock-native-results.json').write_text(json.dumps(results,indent=2))

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_storm():
 e=Engine('card-family',fixtureHand=['Veil of Summer','Chatterstorm'],fixtureLands=['Forest']*3,fixtureLibrary=['Plains']*10)
 try:
  v=next(c for c in e.state['hand'] if c['name']=='Veil of Summer');action(e,'cast_spell',v['forgeId']);action(e,'pass_priority')
  c=next(c for c in e.state['hand'] if c['name']=='Chatterstorm');action(e,'cast_spell',c['forgeId'])
  for _ in range(8):
   if not e.state['stack'] and not e.state['stackAbilities']:break
   action(e,'pass_priority')
  squirrels=[c for c in e.state['battlefield'] if c['name']=='Squirrel Token'];assert len(squirrels)==2,len(squirrels)
  r=dict(id='native-storm-copy-token',passed=True,evidence=str(e.ipc));(E/'storm-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
 finally:e.close()

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_creature_types():
 e=Engine('card-family',fixtureHand=['Cavern of Souls'],fixtureLands=[],fixtureLibrary=['Plains']*10)
 try:
  action(e,'play_land',e.state['hand'][0]['forgeId'],[dict(type='type',name='Human')])
  c=next(c for c in e.state['battlefield'] if c['name']=='Cavern of Souls')
  r=dict(id='native-cavern-type',passed=True,evidence=str(e.ipc));(E/'cavern-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
 finally:e.close()

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_granted_abilities():
 e=Engine('card-family',fixtureHand=['Ichormoon Gauntlet'],fixtureLands=['Island']*3,fixtureBattlefield=['Jace, the Perfected Mind'],fixtureCounters=[dict(seat=1,cardName='Jace, the Perfected Mind',occurrence=0,type='LOYALTY',count=5)],fixtureLibrary=['Plains']*10)
 try:
  action(e,'cast_spell',e.state['hand'][0]['forgeId']);action(e,'pass_priority')
  j=next(c for c in e.state['battlefield'] if c['name']=='Jace, the Perfected Mind');offer=next(a for a in e.state['legalActivations'] if a['forgeId']==j['forgeId'] and a['api']=='Proliferate')
  action(e,'activate_ability',j['forgeId'],abilityId=offer['abilityId']);action(e,'pass_priority',plans=[dict(type='entities',name='Jace, the Perfected Mind')])
  j=next(c for c in e.state['battlefield'] if c['name']=='Jace, the Perfected Mind');assert j['loyalty']==6,j['loyalty']
  r=dict(id='native-ichormoon-granted-proliferate',passed=True,evidence=str(e.ipc));(E/'ichormoon-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
 finally:e.close()

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_ad_nauseam_stop():
 e=Engine('card-family',fixtureHand=['Ad Nauseam'],fixtureLands=['Swamp']*5,fixtureLibrary=['Grizzly Bears','Llanowar Elves','Plains'])
 try:
  action(e,'cast_spell',e.state['hand'][0]['forgeId']);action(e,'pass_priority',plans=[dict(type='look',none=True),dict(type='confirm',accept=True),dict(type='look',none=True),dict(type='confirm',accept=False)])
  assert {c['name'] for c in e.state['hand']}=={'Grizzly Bears','Llanowar Elves'},[c['name'] for c in e.state['hand']];assert e.state['life']==17,e.state['life']
  r=dict(id='native-ad-nauseam-repeat-stop',passed=True,evidence=str(e.ipc));(E/'ad-nauseam-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
 finally:e.close()

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_modal_farewell():
 e=Engine('card-family',fixtureHand=['Farewell'],fixtureLands=['Plains']*6,fixtureBattlefield=['Arcane Signet','Grizzly Bears','Bitterblossom'],fixtureGraveyard=['Llanowar Elves'],fixtureLibrary=['Plains']*10)
 try:
  action(e,'cast_spell',e.state['hand'][0]['forgeId'],[dict(type='modes',all=True)]);action(e,'pass_priority')
  assert not any(c['name'] in {'Arcane Signet','Grizzly Bears','Bitterblossom'} for c in e.state['battlefield']);assert {c['name'] for c in e.state['graveyard']}=={'Farewell'};assert {c['name'] for c in e.state['exile']}>={'Arcane Signet','Grizzly Bears','Bitterblossom','Llanowar Elves'}
  r=dict(id='native-farewell-four-modes',passed=True,evidence=str(e.ipc));(E/'farewell-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
 finally:e.close()

 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_saga_mana():
 e=Engine('card-family',fixtureHand=["Urza's Saga"],fixtureLands=['Plains']*2,fixtureLibrary=['Plains']*20)
 try:
  action(e,'play_land',e.state['hand'][0]['forgeId'])
  while e.state['stackAbilities'] or e.state['stack']:action(e,'pass_priority')
  c=next(c for c in e.state['battlefield'] if c['name']=="Urza's Saga");assert any(a['forgeId']==c['forgeId'] for a in e.state['legalManaOffers'])
  action(e,'activate_mana',c['forgeId'],abilityId=1152);assert e.state['manaTotal']==1 and e.state['mana'][0]['color']==32
  r=dict(id='native-saga-chapter-one-mana',passed=True,evidence=str(e.ipc));(E/'saga-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
 finally:e.close()


 if 'results' in locals():assert all(r['passed'] for r in results),results

def check_faces():
    results=[]
    for case in [dict(name='Darkbore Pathway',op='play_land',lands=[],face='Slitherbore Pathway',plan=dict(type='options',name='Slitherbore Pathway')),dict(name='Reidane, God of the Worthy',op='cast_spell',lands=['Plains']*4,face="Valkmira, Protector's Shield",plan=dict(type='options',contains='Valkmira'))]:
     e=None
     try:
      e=Engine('card-family',fixtureHand=[case['name']],fixtureLands=case['lands'],fixtureLibrary=['Plains']*10)
      action(e,case['op'],e.state['hand'][0]['forgeId'],[case['plan']])
      if case['op']=='cast_spell':action(e,'pass_priority')
      card=next(c for c in e.state['battlefield'] if c['name']==case['face']);assert card['owner']==1
      r=dict(id=case['face'],passed=True,evidence=str(e.ipc))
     except BaseException as ex:r=dict(id=case['face'],passed=False,error=str(ex),evidence=str(e.ipc) if e else '')
     finally:
      if e:e.close()
     results.append(r);print(json.dumps(r),flush=True);(E/'faces-native-results.json').write_text(json.dumps(results,indent=2))
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_rituals():
    results=[]
    for name,amount,plans in [('Dark Ritual',3,[]),('Culling the Weak',4,[dict(type='cards-effect',name='Grizzly Bears')])]:
     e=Engine('card-family',fixtureHand=[name],fixtureLands=['Swamp'],fixtureBattlefield=['Grizzly Bears'],fixtureLibrary=['Plains']*10)
     try:
      action(e,'cast_spell',e.state['hand'][0]['forgeId'],plans);action(e,'pass_priority');assert e.state['manaTotal']==amount;assert sum(m['count'] for m in e.state['mana'])==amount;assert len({m['id'] for m in e.state['mana']})==len(e.state['mana'])
      r=dict(id=name,passed=True,evidence=str(e.ipc));results.append(r);print(json.dumps(r),flush=True)
     finally:e.close()
     (E/'rituals-native-results.json').write_text(json.dumps(results,indent=2))
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_cycling():
    e=Engine('card-family',fixtureHand=["Raffine's Tower"],fixtureLands=['Plains']*3,fixtureLibrary=['Grizzly Bears','Plains'])
    try:
     c=e.state['hand'][0];offer=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'] and a['api']=='Draw')
     action(e,'activate_ability',c['forgeId'],abilityId=offer['abilityId']);action(e,'pass_priority');assert [c['name'] for c in e.state['hand']]==['Grizzly Bears'];assert any(c['name']=="Raffine's Tower" for c in e.state['graveyard'])
     r=dict(id='native-hand-cycling',passed=True,evidence=str(e.ipc));(E/'cycling-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_fluster():
    e=Engine('card-family',fixtureHand=['Flusterstorm'],fixtureLands=['Island'],fixtureOpponentSpell='Veil of Summer',fixtureOpponentLands=['Forest'],fixtureLibrary=['Plains']*10)
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId'],[dict(type='targets',name='Veil of Summer',seat=2)])
     action(e,'pass_priority',plans=[dict(type='confirm',accept=False)])
     for _ in range(8):
      if not e.state['stack'] and not e.state['stackAbilities']:break
      action(e,'pass_priority')
     assert not e.state['stack'] and not e.state['stackAbilities'];assert any(c['name']=='Veil of Summer' and c['owner']==2 for c in e.state['graveyard'])
     r=dict(id='native-flusterstorm-copy-retain-target',passed=True,evidence=str(e.ipc));(E/'fluster-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_fluster_new():
    e=Engine('card-family',fixtureHand=['Flusterstorm'],fixtureLands=['Island'],fixtureOpponentSpell='Veil of Summer',fixtureOpponentLands=['Forest'],fixtureLibrary=['Plains']*10)
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId'],[dict(type='targets',name='Veil of Summer',seat=2)])
     action(e,'pass_priority',plans=[dict(type='confirm',accept=True),dict(type='targets',name='Veil of Summer',seat=2)])
     for _ in range(8):
      if not e.state['stack'] and not e.state['stackAbilities']:break
      action(e,'pass_priority')
     assert not e.state['stack'] and not e.state['stackAbilities'];assert any(c['name']=='Veil of Summer' and c['owner']==2 for c in e.state['graveyard'])
     r=dict(id='native-flusterstorm-copy-choose-target-and-cleanup',passed=True,evidence=str(e.ipc));(E/'fluster-new-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_swat():
    e=Engine('card-family',fixtureHand=['Deflecting Swat'],fixtureLands=['Mountain']*3,fixtureBattlefield=['Grizzly Bears'],fixtureOpponentBattlefield=['Grizzly Bears'],fixtureOpponentSpell='Swords to Plowshares',fixtureOpponentLands=['Plains'],fixtureOpponentTargets=[dict(seat=1,cardName='Grizzly Bears',occurrence=0)],fixtureLibrary=['Plains']*10)
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId'],[dict(type='targets',name='Swords to Plowshares',seat=2)])
     action(e,'pass_priority',plans=[dict(type='confirm',accept=True),dict(type='targets',name='Grizzly Bears',seat=2)])
     action(e,'pass_priority');assert any(c['name']=='Grizzly Bears' and c['controller']==1 for c in e.state['battlefield']);assert not any(c['name']=='Grizzly Bears' and c['controller']==2 for c in e.state['battlefield']);assert e.state['opponentLife']==22,e.state['opponentLife']
     r=dict(id='native-deflecting-swat-retarget-removal',passed=True,evidence=str(e.ipc));(E/'swat-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_clue():
    e=Engine('card-family',fixtureHand=['Fateful Absence'],fixtureLands=['Plains']*4,fixtureBattlefield=['Grizzly Bears'],fixtureLibrary=['Llanowar Elves','Plains'])
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId'],[dict(type='targets',name='Grizzly Bears',seat=1)]);action(e,'pass_priority')
     c=next(c for c in e.state['battlefield'] if c['name']=='Clue Token');assert c['controller']==1;assert any(x['name']=='Grizzly Bears' for x in e.state['graveyard']);offer=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'])
     action(e,'activate_ability',c['forgeId'],abilityId=offer['abilityId']);action(e,'pass_priority');assert [x['name'] for x in e.state['hand']]==['Llanowar Elves'];assert not any(x['name']=='Clue Token' for x in e.state['battlefield'])
     r=dict(id='native-investigate-clue-sacrifice-draw',passed=True,evidence=str(e.ipc));(E/'clue-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_incubator():
    e=Engine('card-family',fixtureHand=['Sunfall'],fixtureLands=['Plains']*7,fixtureBattlefield=['Grizzly Bears'],fixtureOpponentBattlefield=['Grizzly Bears'],fixtureLibrary=['Plains']*10)
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId']);action(e,'pass_priority');c=next(c for c in e.state['battlefield'] if c['name']=='Incubator Token');assert not any(x['name']=='Grizzly Bears' for x in e.state['battlefield']);offer=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'])
     action(e,'activate_ability',c['forgeId'],abilityId=offer['abilityId']);action(e,'pass_priority');c=next(x for x in e.state['battlefield'] if x['forgeId']==c['forgeId']);assert 'Creature' in c['currentTypes'] and c['power']==c['toughness']==2,c;assert c['presentationKey'].endswith(':Backside')
     r=dict(id='native-sunfall-incubate-transform-two-counters',passed=True,evidence=str(e.ipc));(E/'incubator-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_orc():
    e=Engine('card-family',fixtureHand=['Orcish Bowmasters'],fixtureLands=['Swamp']*2,fixtureOpponentBattlefield=['Grizzly Bears'],fixtureLibrary=['Plains']*10)
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId']);action(e,'pass_priority',plans=[dict(type='targets',name='Grizzly Bears',seat=2)]);action(e,'pass_priority',plans=[dict(type='entities',name='Orc Army Token')])
     c=next(c for c in e.state['battlefield'] if c['name']=='Orc Army Token');assert c['power']==c['toughness']==1,c;assert next(x for x in e.state['battlefield'] if x['name']=='Grizzly Bears')['damage']==1
     r=dict(id='native-bowmasters-damage-amass',passed=True,evidence=str(e.ipc));(E/'orc-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_teferi_emblem():
    e=Engine('card-family',fixtureHand=['Divination'],fixtureLands=['Island']*3,fixtureBattlefield=['Teferi, Hero of Dominaria'],fixtureOpponentBattlefield=['Grizzly Bears','Ornithopter'],fixtureCounters=[dict(seat=1,cardName='Teferi, Hero of Dominaria',occurrence=0,type='LOYALTY',count=9)],fixtureLibrary=['Plains']*10)
    try:
     t=next(c for c in e.state['battlefield'] if c['name']=='Teferi, Hero of Dominaria');offer=next(a for a in e.state['legalActivations'] if a['forgeId']==t['forgeId'] and a['api']=='Effect')
     action(e,'activate_ability',t['forgeId'],abilityId=offer['abilityId']);action(e,'pass_priority');assert any(c.get('objectKind')=='emblem' for c in e.state['command']),e.state['command']
     action(e,'cast_spell',e.state['hand'][0]['forgeId']);action(e,'pass_priority',plans=[dict(type='options',index=0),dict(type='targets',name='Grizzly Bears',seat=2),dict(type='targets',name='Ornithopter',seat=2)])
     for _ in range(5):
      if not e.state['stackAbilities'] and not e.state['stack']:break
      action(e,'pass_priority')
     assert not any(c['controller']==2 and c['name'] in ['Grizzly Bears','Ornithopter'] for c in e.state['battlefield']);assert {'Grizzly Bears','Ornithopter'}<={c['name'] for c in e.state['exile']}
     r=dict(id='native-teferi-emblem-draw-order-two-exiles',passed=True,evidence=str(e.ipc));(E/'teferi-emblem-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_jace_emblem():
    e=Engine('card-family',fixtureHand=[],fixtureLands=[],fixtureBattlefield=['Jace, Unraveler of Secrets'],fixtureOpponentBattlefield=['Forest','Forest'],fixtureOpponentHand=['Llanowar Elves','Elvish Mystic'],fixtureOpponentSpellPlan=['Llanowar Elves','Elvish Mystic'],fixtureCounters=[dict(seat=1,cardName='Jace, Unraveler of Secrets',occurrence=0,type='LOYALTY',count=9)],fixtureLibrary=['Plains']*20)
    try:
     c=next(c for c in e.state['battlefield'] if c['name']=='Jace, Unraveler of Secrets');a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'] and a['api']=='Effect');action(e,'activate_ability',c['forgeId'],abilityId=a['abilityId']);action(e,'pass_priority')
     for _ in range(32):
      if any(c['name']=='Elvish Mystic' and c['controller']==2 for c in e.state['battlefield']):break
      action(e,'pass_priority')
     assert any(c['name']=='Llanowar Elves' and c['owner']==2 for c in e.state['graveyard']),[(c['name'],c['owner']) for c in e.state['graveyard']];assert any(c['name']=='Elvish Mystic' and c['controller']==2 for c in e.state['battlefield'])
     r=dict(id='native-jace-emblem-first-opponent-spell-only',passed=True,evidence=str(e.ipc));(E/'jace-emblem-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_emblem_creators():
    m=json.loads((Path(json.loads(a.config.read_text())['privateRoot'])/'native-lab/bridge-card-manifest.json').read_text());results=[]
    for key,d in m['cards'].items():
     if not d.get('emblemPresentation'):continue
     name=d['parentName'];e=None
     try:
      e=Engine('card-family',fixtureHand=[],fixtureLands=[],fixtureBattlefield=[name],fixtureCounters=[dict(seat=1,cardName=name,occurrence=0,type='LOYALTY',count=99)],fixtureLibrary=['Plains']*10)
      c=next(c for c in e.state['battlefield'] if c['name']==name);action(e,'activate_ability',c['forgeId'],abilityId=d['sourceCreatingAbilityId']);action(e,'pass_priority')
      assert any(c.get('presentationKey')==key for c in e.state['command']),e.state['command']
      r=dict(id=name,passed=True,evidence=str(e.ipc))
     except BaseException as ex:r=dict(id=name,passed=False,error=str(ex),evidence=str(e.ipc) if e else '')
     finally:
      if e:e.close()
     results.append(r);print(json.dumps(r),flush=True);(E/'emblem-creators-native-results.json').write_text(json.dumps(results,indent=2))
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_mindbreak():
    results=[]
    for live in [False,True]:
     settings=dict(fixtureHand=['Mindbreak Trap'],fixtureLands=['Island']*4,fixtureLibrary=['Plains']*10)
     if live:settings.update(fixtureOpponentSpell='Divination',fixtureOpponentLands=['Island']*3)
     e=Engine('card-family',**settings)
     try:
      spell=e.state['hand'][0];assert spell['forgeId'] in e.state['legalCasts']
      action(e,'cast_spell',spell['forgeId'],[dict(type='targets',name='Divination',seat=2)] if live else [])
      action(e,'pass_priority')
      assert not e.state['stack'] and not e.state['stackAbilities']
      if live:assert any(c['name']=='Divination' and c['owner']==2 for c in e.state['exile'])
      results.append(dict(id='native-mindbreak-'+('exile-opponent-spell' if live else 'zero-targets'),passed=True,evidence=str(e.ipc)))
     finally:e.close()
    (E/'mindbreak-native-results.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_citadel_library():
    e=Engine('card-family',fixtureHand=["Bolas's Citadel"],fixtureLands=['Swamp']*6,fixtureLibrary=['Forest','Ornithopter','Grizzly Bears']+['Plains']*8)
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId']);action(e,'pass_priority')
     visible=[c for c in e.state['hidden'] if c.get('name')]
     assert [c['name'] for c in visible]==['Forest'],visible
     land=visible[0];assert land['forgeId'] in e.state['legalLands'];action(e,'play_land',land['forgeId'])
     top=next(c for c in e.state['hidden'] if c.get('name'));assert top['name']=='Ornithopter';assert top['forgeId'] in e.state['legalCasts']
     action(e,'cast_spell',top['forgeId']);action(e,'pass_priority')
     top=next(c for c in e.state['hidden'] if c.get('name'));assert top['name']=='Grizzly Bears';assert top['forgeId'] in e.state['legalCasts']
     action(e,'cast_spell',top['forgeId'],[dict(type='confirm',accept=True)]);action(e,'pass_priority')
     assert e.state['life']==18,e.state['life'];assert {'Forest','Ornithopter','Grizzly Bears'}<={c['name'] for c in e.state['battlefield']}
     assert [c['name'] for c in e.state['hidden'] if c.get('name')]==['Plains']
     r=dict(id='native-citadel-top-library-land-zero-and-two-life-casts',passed=True,evidence=str(e.ipc));(E/'citadel-library-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_lair():
    e=Engine('card-family',fixtureHand=[],fixtureLands=['Forest']*4,fixtureBattlefield=['Lair of the Hydra'],fixtureBattlefieldReady=True,fixtureLibrary=['Plains']*10)
    try:
     c=next(c for c in e.state['battlefield'] if c['name']=='Lair of the Hydra');a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'])
     action(e,'activate_ability',c['forgeId'],[dict(type='number',number=2)],abilityId=a['abilityId']);action(e,'pass_priority')
     c=next(x for x in e.state['battlefield'] if x['forgeId']==c['forgeId']);assert c['colorMask']==16 and c['power']==c['toughness']==2 and 'Creature' in c['currentTypes'],c
     attacked=False
     for _ in range(30):
      if e.state['turn']>1:break
      _,d=e.pass_or_decision()
      if d:
       spec=e.state['decision'];kind=spec['kind'];assert kind=='attackers',spec
       r=e.send('select_attackers',decisionToken=d['token'],assignments=[dict(forgeId=c['forgeId'],targetSeat=2)]);assert r['accepted'],r
       r=e.send('submit_attackers',decisionToken=d['token']);assert r['accepted'],r;attacked=True
     else:raise AssertionError('Did not reach turn boundary')
     assert attacked and e.state['opponentLife']==18,e.state['opponentLife'];c=next(x for x in e.state['battlefield'] if x['forgeId']==c['forgeId']);assert 'Creature' not in c['currentTypes'] and c['colorMask']==0,c
     r=dict(id='native-lair-animation-attack-and-expiry',passed=True,evidence=str(e.ipc));(E/'lair-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_chandra_sweeper():
    e=Engine('card-family',fixtureHand=[],fixtureLands=[],fixtureBattlefield=['Chandra, Awakened Inferno','Grizzly Bears','Llanowar Elves'],fixtureOpponentBattlefield=['Grizzly Bears','Ornithopter'],fixtureCounters=[dict(seat=1,cardName='Chandra, Awakened Inferno',occurrence=0,type='LOYALTY',count=6)],fixtureLibrary=['Plains']*10)
    try:
     c=next(c for c in e.state['battlefield'] if c['name']=='Chandra, Awakened Inferno');a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'] and a['api']=='DamageAll')
     action(e,'activate_ability',c['forgeId'],abilityId=a['abilityId']);action(e,'pass_priority',plans=[dict(type='order',all=True)])
     assert not any('Creature' in c['currentTypes'] for c in e.state['battlefield']);assert len([c for c in e.state['graveyard'] if c['name']=='Grizzly Bears'])==2
     r=dict(id='native-chandra-multiplayer-public-graveyard-order',passed=True,evidence=str(e.ipc));(E/'chandra-sweeper-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_grim_treasure():
    e=Engine('card-family',fixtureHand=[],fixtureLands=['Swamp'],fixtureBattlefield=['Warren Soultrader','Grim Hireling','Grizzly Bears','Llanowar Elves'],fixtureOpponentBattlefield=['Grizzly Bears'],fixtureLibrary=['Plains']*10)
    try:
     w=next(c for c in e.state['battlefield'] if c['name']=='Warren Soultrader');a=next(a for a in e.state['legalActivations'] if a['forgeId']==w['forgeId'])
     for name in ['Grizzly Bears','Llanowar Elves']:
      action(e,'activate_ability',w['forgeId'],[dict(type='confirm',accept=True),dict(type='cards-effect',name=name)],abilityId=a['abilityId']);action(e,'pass_priority')
     assert len([c for c in e.state['battlefield'] if c['name']=='Treasure Token'])==2
     c=next(c for c in e.state['battlefield'] if c['name']=='Grim Hireling');a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'])
     action(e,'activate_ability',c['forgeId'],[dict(type='number',number=2),dict(type='targets',name='Grizzly Bears',seat=2),dict(type='cards-effect',all=True)],abilityId=a['abilityId']);action(e,'pass_priority')
     assert not any(c['name']=='Treasure Token' for c in e.state['battlefield']);assert not any(c['name']=='Grizzly Bears' and c['controller']==2 for c in e.state['battlefield']);assert e.state['life']==18,e.state['life']
     r=dict(id='native-soultrader-create-and-hireling-sacrifice-two-treasures',passed=True,evidence=str(e.ipc));(E/'grim-treasure-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_necropotence():
    e=Engine('card-family',fixtureHand=['Necropotence'],fixtureLands=['Swamp']*3,fixtureLibrary=['Grizzly Bears']+['Plains']*10)
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId']);action(e,'pass_priority');n=next(c for c in e.state['battlefield'] if c['name']=='Necropotence');a=next(a for a in e.state['legalActivations'] if a['forgeId']==n['forgeId'])
     before={c['forgeId'] for c in e.state['hidden'] if c['zone']=='Library'}
     action(e,'activate_ability',n['forgeId'],[dict(type='confirm',accept=True)],abilityId=a['abilityId']);action(e,'pass_priority');assert e.state['life']==19
     after={c['forgeId'] for c in e.state['hidden'] if c['zone']=='Library'};exiled=before-after;assert len(exiled)==1
     assert exiled<={c['forgeId'] for c in e.state['hidden'] if c['zone']=='Exile'},e.state['exile']
     for _ in range(30):
      if any(c['name']=='Grizzly Bears' for c in e.state['hand']):break
      _,d=e.pass_or_decision()
      if d:
       assert e.state['decision']['kind']=='attackers',e.state['decision'];r=e.send('submit_attackers',decisionToken=d['token']);assert r['accepted'],r
     else:raise AssertionError('Delayed return did not occur')
     assert e.state['turn']==1 and e.state['phase']=='END_OF_TURN',e.state['phase'];assert not any(c['forgeId'] in exiled for c in e.state['hidden'] if c['zone']=='Exile')
     r=dict(id='native-necropotence-private-exile-endstep-return',passed=True,evidence=str(e.ipc));(E/'necropotence-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_dauthi():
    e=Engine('card-family',fixtureHand=['Counterspell'],fixtureLands=['Island']*2,fixtureBattlefield=['Dauthi Voidwalker'],fixtureBattlefieldReady=True,fixtureOpponentSpell='Veil of Summer',fixtureOpponentLands=['Forest'],fixtureLibrary=['Plains']*10)
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId'],[dict(type='targets',name='Veil of Summer',seat=2)]);action(e,'pass_priority')
     stolen=next(c for c in e.state['exile'] if c['name']=='Veil of Summer');assert any(c['type']=='VOID' and c['count']==1 for c in stolen['counters']),stolen
     v=next(c for c in e.state['battlefield'] if c['name']=='Dauthi Voidwalker');a=next(a for a in e.state['legalActivations'] if a['forgeId']==v['forgeId'])
     action(e,'activate_ability',v['forgeId'],abilityId=a['abilityId']);action(e,'pass_priority',plans=[dict(type='cards-effect',name='Veil of Summer')])
     assert stolen['forgeId'] in e.state['legalCasts'],e.state['unavailableActions']
     action(e,'cast_spell',stolen['forgeId']);action(e,'pass_priority');assert not e.state['hand'] and e.state['manaTotal']==0
     assert any(c['name']=='Veil of Summer' and c['owner']==2 for c in e.state['graveyard'])
     r=dict(id='native-dauthi-replacement-void-counter-opponent-exile-free-cast',passed=True,evidence=str(e.ipc));(E/'dauthi-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_reported_veil():
    e=Engine('card-family',fixtureHand=['Veil of Summer'],fixtureLands=[],fixtureBattlefield=['Nurturing Peatland'],fixtureLibrary=['Plains']*10)
    try:
     c=e.state['hand'][0];assert c['forgeId'] in e.state['legalCasts'],e.state['unavailableActions']
     action(e,'cast_spell',c['forgeId']);action(e,'pass_priority')
     assert e.state['life']==19 and not e.state['fidelityGap'];assert any(c['name']=='Veil of Summer' for c in e.state['graveyard']);assert e.process.poll() is None and e.native_process.poll() is None
     r=dict(id='native-reported-veil-peatland-payment-crash-regression',passed=True,evidence=str(e.ipc));(E/'reported-veil-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_context_activation():
    results=[]
    cases=['derevi','elspeth','emperor','hermit','field']
    for name in cases:
     e=None
     try:
      settings=dict(fixtureHand=[],fixtureLands=['Plains','Island','Forest','Plains'],fixtureLibrary=['Forest']*10)
      if name=='derevi':settings.update(fixtureCommander='Derevi, Empyrial Tactician',traceChoices=True)
      elif name=='elspeth':settings.update(fixtureBattlefield=['Elspeth, Storm Slayer'],fixtureOpponentBattlefield=['Warren Soultrader'],fixtureCounters=[dict(seat=1,cardName='Elspeth, Storm Slayer',occurrence=0,type='LOYALTY',count=6)])
      elif name=='emperor':settings.update(fixtureBattlefield=['The Wandering Emperor','Llanowar Elves'],fixtureBattlefieldReady=True,fixtureCounters=[dict(seat=1,cardName='The Wandering Emperor',occurrence=0,type='LOYALTY',count=4)])
      elif name=='hermit':settings.update(fixtureBattlefield=['Malevolent Hermit'],fixtureBattlefieldReady=True,fixtureOpponentSpell='Veil of Summer',fixtureOpponentLands=['Forest'])
      elif name=='field':settings.update(fixtureBattlefield=['Field of Ruin'],fixtureOpponentBattlefield=['Nurturing Peatland'])
      e=Engine('card-family',**settings)
      if name=='emperor':
       elf=next(c for c in e.state['battlefield'] if c['name']=='Llanowar Elves');mana=next(a for a in e.state['legalManaOffers'] if a['forgeId']==elf['forgeId']);action(e,'activate_mana',elf['forgeId'],abilityId=mana['abilityId'])
      source={'derevi':'Derevi, Empyrial Tactician','elspeth':'Elspeth, Storm Slayer','emperor':'The Wandering Emperor','hermit':'Malevolent Hermit','field':'Field of Ruin'}[name];api={'derevi':'ChangeZone','elspeth':'Destroy','emperor':'ChangeZone','hermit':'Counter','field':'Destroy'}[name]
      c=next(c for z in ['command','battlefield'] for c in e.state[z] if c['name']==source);a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'] and a['api']==api)
      targets={'elspeth':('Warren Soultrader',2),'emperor':('Llanowar Elves',1),'hermit':('Veil of Summer',2),'field':('Nurturing Peatland',2)}
      plans=[dict(type='targets',name=targets[name][0],seat=targets[name][1])] if name in targets else []
      action(e,'activate_ability',c['forgeId'],plans,abilityId=a['abilityId'])
      resolution_plans=[dict(type='targets',name='Forest',seat=1),dict(type='confirm',accept=True),dict(type='confirm',accept=True)] if name=='derevi' else [dict(type='cards-zone',name='Forest')] if name=='field' else []
      resolve(e,resolution_plans)
      if name=='derevi':
       assert any(c['name']==source for c in e.state['battlefield'])
      elif name=='elspeth':assert any(c['name']=='Warren Soultrader' and c['owner']==2 for c in e.state['graveyard'])
      elif name=='emperor':assert e.state['life']==22 and any(c['name']=='Llanowar Elves' for c in e.state['exile'])
      elif name=='hermit':assert any(c['name']=='Veil of Summer' and c['owner']==2 for c in e.state['graveyard'])
      elif name=='field':assert any(c['name']=='Nurturing Peatland' and c['owner']==2 for c in e.state['graveyard'])
      results.append(dict(id='native-context-'+name,passed=True,evidence=str(e.ipc)))
     except Exception as ex:results.append(dict(id='native-context-'+name,passed=False,error=str(ex),evidence=str(e.ipc) if e else ''))
     finally:
      if e:e.close()
     print(json.dumps(results[-1]),flush=True);(E/'context-activation-native-results.json').write_text(json.dumps(results,indent=2))
    assert all(r['passed'] for r in results),results
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_combat_context():
    results=[]
    for name in ['eiganjo','najeela']:
     e=None
     try:
      if name=='eiganjo':
       e=Engine('card-family',fixtureHand=['Eiganjo, Seat of the Empire'],fixtureLands=['Plains']*3,fixtureActiveSeat=2,fixtureOpponentBattlefield=['Grizzly Bears'],fixtureOpponentPolicy='attack-all',fixtureLibrary=['Plains']*10)
       c=e.state['hand'][0]
       for _ in range(32):
        offer=next((a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'] and a['api']=='DealDamage'),None)
        if offer:break
        _,d=e.pass_or_decision()
        if d:
         assert e.state['decision']['kind']=='blockers',e.state['decision'];action(e,'submit_blockers',decisionToken=d['token'])
       else:raise AssertionError('No legal attacking-creature channel opportunity')
       action(e,'activate_ability',c['forgeId'],[dict(type='targets',name='Grizzly Bears',seat=2)],abilityId=offer['abilityId']);action(e,'pass_priority')
       assert not any(c['name']=='Grizzly Bears' for c in e.state['battlefield']);assert any(c['name']=='Eiganjo, Seat of the Empire' for c in e.state['graveyard']);assert e.state['life']==20
      else:
       e=Engine('card-family',fixtureHand=[],fixtureLands=['Plains','Island','Swamp','Mountain','Forest'],fixtureBattlefield=['Najeela, the Blade-Blossom'],fixtureBattlefieldReady=True,fixtureLibrary=['Plains']*10)
       c=next(c for c in e.state['battlefield'] if c['name']=='Najeela, the Blade-Blossom')
       for _ in range(16):
        _,d=e.pass_or_decision()
        if d:
         assert e.state['decision']['kind']=='attackers',e.state['decision'];r=e.send('select_attackers',decisionToken=d['token'],assignments=[dict(forgeId=c['forgeId'],targetSeat=2)]);assert r['accepted'],r
         queue=[dict(type='confirm',accept=True),dict(type='entities',name='Opponent')];action(e,'submit_attackers',plan_queue=queue,decisionToken=d['token']);resolve(e,queue);break
       else:raise AssertionError('No first combat')
       warriors=[x for x in e.state['battlefield'] if x.get('token') and 'Warrior' in x['currentSubtypes']];assert len(warriors)==1 and warriors[0]['attackTarget']==2,warriors
       offer=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'] and a['api']=='UntapAll');action(e,'activate_ability',c['forgeId'],abilityId=offer['abilityId']);action(e,'pass_priority')
       for creature in [x for x in e.state['battlefield'] if x['attackTarget']==2]:assert not creature['tapped'] and {'Trample','Lifelink','Haste'}<=set(creature['rulesKeywords']),creature
       for _ in range(32):
        _,d=e.pass_or_decision()
        if d:
         assert e.state['decision']['kind']=='attackers' and e.state['turn']==1,e.state['decision'];action(e,'submit_attackers',decisionToken=d['token']);break
       else:raise AssertionError('No additional combat')
       assert e.state['opponentLife']==16 and e.state['life']==24,(e.state['opponentLife'],e.state['life'])
      results.append(dict(id='native-combat-'+name,passed=True,evidence=str(e.ipc)))
     except Exception as ex:results.append(dict(id='native-combat-'+name,passed=False,error=str(ex),evidence=str(e.ipc) if e else ''))
     finally:
      if e:e.close()
     print(json.dumps(results[-1]),flush=True);(E/'combat-context-native-results.json').write_text(json.dumps(results,indent=2))
    assert all(r['passed'] for r in results),results
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_ivy_oak():
    e=Engine('card-family',fixtureHand=['Elvish Mystic'],fixtureLands=['Forest'],fixtureBattlefield=['Ivy Lane Denizen','Scurry Oak'],fixtureLibrary=['Plains']*10)
    try:
     action(e,'cast_spell',e.state['hand'][0]['forgeId'])
     plans=[dict(type='targets',name='Scurry Oak',seat=1)]
     for _ in range(2):plans.extend([dict(type='confirm',accept=True),dict(type='targets',name='Scurry Oak',seat=1)])
     plans.append(dict(type='confirm',accept=False));resolve(e,plans)
     assert not e.state['stack'] and not e.state['stackAbilities'];oak=next(c for c in e.state['battlefield'] if c['name']=='Scurry Oak');assert oak['power']==4 and oak['toughness']==5,oak
     assert len([c for c in e.state['battlefield'] if c['name']=='Squirrel Token'])==2
     r=dict(id='native-ivy-scurry-token-loop-two-iterations-explicit-stop',passed=True,evidence=str(e.ipc));(E/'ivy-oak-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_facebreaker():
    e=Engine('card-family',fixtureHand=[],fixtureLands=['Forest'],fixtureBattlefield=['Warren Soultrader','Professional Face-Breaker','Grizzly Bears'],fixtureLibrary=['Elvish Mystic']+['Plains']*10)
    try:
     c=next(c for c in e.state['battlefield'] if c['name']=='Warren Soultrader');a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'])
     action(e,'activate_ability',c['forgeId'],[dict(type='confirm',accept=True),dict(type='cards-effect',name='Grizzly Bears')],abilityId=a['abilityId']);action(e,'pass_priority')
     c=next(c for c in e.state['battlefield'] if c['name']=='Professional Face-Breaker');a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'])
     action(e,'activate_ability',c['forgeId'],[dict(type='cards-effect',name='Treasure Token')],abilityId=a['abilityId']);action(e,'pass_priority')
     top=next(c for c in e.state['exile'] if c['name']=='Elvish Mystic');assert top['forgeId'] in e.state['legalCasts'];action(e,'cast_spell',top['forgeId']);action(e,'pass_priority')
     assert any(c['name']=='Elvish Mystic' for c in e.state['battlefield']);assert not any(c['name']=='Treasure Token' for c in e.state['battlefield'])
     r=dict(id='native-facebreaker-sacrifice-treasure-exile-and-cast',passed=True,evidence=str(e.ipc));(E/'facebreaker-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_mana_recovery():
    e=Engine('card-family',fixtureHand=['Gilded Goose','Llanowar Elves'],fixtureLands=['Forest'],fixtureBattlefield=['Gilded Goose'],fixtureBattlefieldReady=True,fixtureLibrary=['Plains']*10)
    try:
     source=next(c for c in e.state['battlefield'] if c['name']=='Gilded Goose');goose=next(c for c in e.state['hand'] if c['name']=='Gilded Goose');action(e,'cast_spell',goose['forgeId']);resolve(e)
     assert any(c['name']=='Food Token' for c in e.state['battlefield']);elf=next(c for c in e.state['hand'] if c['name']=='Llanowar Elves')
     try:
      action(e,'cast_spell',elf['forgeId'],[dict(type='options',contains='Gilded Goose #'+str(source['forgeId'])),dict(type='cards-effect',name='Food Token'),dict(type='colors',label='white')])
      raise AssertionError('White mana must not pay a green cost')
     except RuntimeError as ex:assert 'Forge human' in str(ex) or 'Human play was canceled' in str(ex),str(ex)
     assert not e.state.get('decision') and not e.state['fidelityGap'];assert any(c['forgeId']==elf['forgeId'] for c in e.state['hand']);assert e.state['manaTotal']==1 and e.state['mana'][0]['color']==1
     # The next legal native action must work without restarting either process.
     action(e,'pass_priority')
     for _ in range(40):
      if e.state['turn']>=3 and e.state['phase']=='MAIN1':break
      _,d=e.pass_or_decision()
      if d:
       assert e.state['decision']['kind']=='attackers',e.state['decision'];action(e,'submit_attackers',decisionToken=d['token'])
     else:raise AssertionError('Did not reach the next local main phase')
     action(e,'cast_spell',elf['forgeId']);resolve(e);assert any(c['name']=='Llanowar Elves' for c in e.state['battlefield'])
     r=dict(id='native-wrong-mana-color-rejection-retires-choice-and-recovers',passed=True,evidence=str(e.ipc));(E/'mana-recovery-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_generated_token_triggers():
    results=[]
    for name in ['decayed','illusion','spirit']:
     e=None
     try:
      if name=='decayed':
       e=Engine('card-family',fixtureHand=['Jadar, Ghoulcaller of Nephalia'],fixtureLands=['Swamp']*2,fixtureLibrary=['Plains']*10)
       action(e,'cast_spell',e.state['hand'][0]['forgeId']);resolve(e)
       for _ in range(40):
        zombie=next((c for c in e.state['battlefield'] if c.get('presentationKey')=='token:b_2_2_zombie_decayed'),None)
        if zombie:break
        _,d=e.pass_or_decision()
        if d:assert e.state['decision']['kind']=='attackers',e.state['decision'];action(e,'submit_attackers',decisionToken=d['token'])
       else:raise AssertionError('Jadar did not create its original Zombie')
       for _ in range(40):
        _,d=e.pass_or_decision()
        if d:
         assert e.state['decision']['kind']=='attackers',e.state['decision'];r=e.send('select_attackers',decisionToken=d['token'],assignments=[dict(forgeId=zombie['forgeId'],targetSeat=2)]);assert r['accepted'],r;action(e,'submit_attackers',decisionToken=d['token']);break
       else:raise AssertionError('No Zombie attack declaration')
       assert any(a['sourceForgeId']==zombie['forgeId'] and a['abilityId']==214 for a in e.state['stackAbilities']),e.state['stackAbilities'];resolve(e)
       assert any(c['forgeId']==zombie['forgeId'] for c in e.state['battlefield']);delayed=False
       for _ in range(32):
        if any(a['sourceForgeId']==zombie['forgeId'] and a['abilityId']==147665 for a in e.state['stackAbilities']):delayed=True
        if not any(c['forgeId']==zombie['forgeId'] for c in e.state['battlefield']):break
        action(e,'pass_priority')
       else:raise AssertionError('Decayed token did not sacrifice at end of combat')
       assert delayed and e.state['opponentLife']==18 and e.state['phase']=='COMBAT_END',(delayed,e.state['opponentLife'],e.state['phase'])
      else:
       parent='Jace, Cunning Castaway' if name=='illusion' else 'Teferi, Temporal Pilgrim';spell='Giant Growth' if name=='illusion' else 'Divination'
       e=Engine('card-family',fixtureHand=[spell],fixtureLands=['Forest'] if name=='illusion' else ['Island']*3,fixtureBattlefield=[parent],fixtureCounters=[dict(seat=1,cardName=parent,occurrence=0,type='LOYALTY',count=5)],fixtureLibrary=['Plains']*10)
       c=next(c for c in e.state['battlefield'] if c['name']==parent);a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'] and a['api']=='Token');action(e,'activate_ability',c['forgeId'],abilityId=a['abilityId']);assert next(x for x in e.state['battlefield'] if x['forgeId']==c['forgeId'])['loyalty']==3;resolve(e)
       if name=='illusion':
        token=next(c for c in e.state['battlefield'] if c.get('presentationKey')=='token:u_2_2_illusion_illusory');action(e,'cast_spell',e.state['hand'][0]['forgeId'],[dict(type='targets',name=token['name'],seat=1)]);resolve(e)
        assert not any(c['forgeId']==token['forgeId'] for c in e.state['battlefield']);assert any(t['kind']=='spell-resolved' and t['hasFizzled'] for t in e.state['researchTrace'])
       else:
        action(e,'cast_spell',e.state['hand'][0]['forgeId']);resolve(e,[dict(type='options',index=0)]*3)
        token=next(c for c in e.state['battlefield'] if c.get('presentationKey')=='token:u_2_2_spirit_vigilance_drawcounter');assert token['power']==token['toughness']==4,token;assert next(c for c in e.state['battlefield'] if c['name']==parent)['loyalty']==5
      results.append(dict(id='native-token-trigger-'+name,passed=True,evidence=str(e.ipc)))
     except Exception as ex:results.append(dict(id='native-token-trigger-'+name,passed=False,error=str(ex),evidence=str(e.ipc) if e else ''))
     finally:
      if e:e.close()
     print(json.dumps(results[-1]),flush=True);(E/'generated-token-triggers-native-results.json').write_text(json.dumps(results,indent=2))
    assert all(r['passed'] for r in results),results
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_loyalty_payments():
    results=[]
    for case in ['plus','x','last-loyalty']:
     e=None
     try:
      name='Kaya the Inexorable' if case=='last-loyalty' else 'Chandra, Awakened Inferno';initial=7 if case=='last-loyalty' else 6
      e=Engine('card-family',fixtureHand=[],fixtureLands=[],fixtureBattlefield=[name],fixtureOpponentBattlefield=['Grizzly Bears'],fixtureCounters=[dict(seat=1,cardName=name,occurrence=0,type='LOYALTY',count=initial)],fixtureLibrary=['Plains']*10)
      c=next(c for c in e.state['battlefield'] if c['name']==name);api='DealDamage' if case=='x' else 'Effect';a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId'] and a['api']==api)
      action(e,'activate_ability',c['forgeId'],[dict(type='number',number=3),dict(type='targets',name='Grizzly Bears',seat=2)] if case=='x' else [],abilityId=a['abilityId'])
      actual=next(x for z in ['battlefield','graveyard'] for x in e.state[z] if x['forgeId']==c['forgeId']);expected=0 if case=='last-loyalty' else 3 if case=='x' else 8
      assert actual['loyalty']==expected,(case,actual['loyalty'],expected);assert not any(a['forgeId']==c['forgeId'] for a in e.state['legalActivations'])
      resolve(e)
      if case=='x':assert any(x['name']=='Grizzly Bears' and x['owner']==2 for x in e.state['exile'])
      elif case=='last-loyalty':assert any(x['name']==name for x in e.state['graveyard']) and any(x.get('presentationKey')=='emblem:'+name for x in e.state['command'])
      results.append(dict(id='native-loyalty-payment-'+case,passed=True,evidence=str(e.ipc)))
     except Exception as ex:results.append(dict(id='native-loyalty-payment-'+case,passed=False,error=str(ex),evidence=str(e.ipc) if e else ''))
     finally:
      if e:e.close()
     print(json.dumps(results[-1]),flush=True);(E/'loyalty-payments-native-results.json').write_text(json.dumps(results,indent=2))
    assert all(r['passed'] for r in results),results
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_gemstone_opening():
    attempts=[];result=None
    for seed in [5]:
     e=None;found=False
     try:
      local=dict(name='Gemstone real-start reference',format='arena-brawl',commander=dict(name='Derevi, Empyrial Tactician',count=1),cards=[dict(name='Gemstone Caverns',count=1),dict(name='Forest',count=98)],experimental=True)
      opponent=dict(name='Isamaru reference',format='arena-brawl',commander=dict(name='Isamaru, Hound of Konda',count=1),cards=[dict(name='Plains',count=99)])
      e=Engine('brawl-duel',localDeck=local,opponentDeck=opponent,randomSeed=seed,startingPlayerPolicy='coin-toss')
      for _ in range(16):
       d=e.state.get('decision')
       if not d:
        if e.state['stage']=='Play':break
        time.sleep(.05);e.native_status=e.native_wait(e.native_folder/'status.json');e.state=e.native_status['state'];continue
       kind=d['kind'];fields=dict(decisionToken=d['token'])
       if kind=='starting_player':e.begin('submit_starting_player',assignments=[dict(startingSeat=2)],**fields)
       elif kind=='mulligan':
        if not any(c['name']=='Gemstone Caverns' for c in e.state['hand']):break
        found=True;e.begin('submit_mulligan',assignments=[dict(keep=True)],**fields)
       elif kind=='choice':
        spec=d['choice'];assert found,(kind,spec)
        if spec['type']=='options':chosen=next(o for o in spec['options'] if o['label']=='Gemstone Caverns')
        elif spec['type'] in ['cards-effect','cards-zone','entities']:chosen=next(o for o in spec['options'] if o['label']=='Forest')
        else:raise AssertionError(spec)
        e.begin('submit_choice',assignments=[dict(choiceId=chosen['choiceId'])],**fields)
       else:raise AssertionError(d)
      else:raise AssertionError('Opening sequence bound exceeded')
      attempts.append(dict(seed=seed,gemInOpeningHand=found,evidence=str(e.ipc)))
      if not found:continue
      gem=next(c for c in e.state['battlefield'] if c['name']=='Gemstone Caverns');assert any(c['type']=='LUCK' and c['count']==1 for c in gem['counters']),gem
      assert len([c for c in e.state['exile'] if c['name']=='Forest'])==1
      a=next(a for a in e.state['legalManaOffers'] if a['forgeId']==gem['forgeId']);action(e,'activate_mana',gem['forgeId'],[dict(type='colors',label='green')],abilityId=a['abilityId']);assert e.state['manaTotal']==1 and e.state['mana'][0]['color']==16
      result=dict(id='native-gemstone-normal-shuffle-second-player-opening-exile-luck-mana',passed=True,seed=seed,evidence=str(e.ipc));break
     except Exception as ex:
      result=dict(id='native-gemstone-normal-opening',passed=False,error=str(ex),seed=seed,evidence=str(e.ipc) if e else '');break
     finally:
      if e:e.close()
    if result is None:result=dict(id='native-gemstone-normal-opening',passed=False,error='Seed discovery bound reached; no hand injection performed')
    (E/'gemstone-opening-native-result.json').write_text(json.dumps(dict(result=result,attempts=attempts),indent=2));print(json.dumps(result));assert result['passed'],result
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_mana_combinations():
    results=[]
    for name in ['selvala','beacon']:
     e=None
     try:
      if name=='selvala':settings=dict(fixtureHand=[],fixtureLands=['Forest'],fixtureBattlefield=['Selvala, Heart of the Wilds','Craterhoof Behemoth'],fixtureBattlefieldReady=True,fixtureLibrary=['Plains']*10)
      else:settings=dict(fixtureHand=['Aven Interrupter','Jace, Cunning Castaway'],fixtureLands=['Forest','Island','Plains'],fixtureBattlefield=['Interplanar Beacon'],fixtureLibrary=['Plains']*10)
      e=Engine('card-family',**settings);source='Selvala, Heart of the Wilds' if name=='selvala' else 'Interplanar Beacon';c=next(c for c in e.state['battlefield'] if c['name']==source);offers=[a for a in e.state['legalManaOffers'] if a['forgeId']==c['forgeId']]
      manifest=json.loads((Path(json.loads(Path(os.environ['FORGE_ARENA_CONFIG']).read_text())['privateRoot'])/'native-lab/bridge-card-manifest.json').read_text());ids={v for text,v in manifest['cards'][source]['abilityBindings']['descriptions'].items() if 'Add two mana of different colors' in text}
      if name=='beacon':assert len(ids)==1,ids
      ability=offers[0] if name=='selvala' else next(a for a in offers if a['abilityId']==next(iter(ids)))
      plans=[dict(type='colors',label='green'),dict(type='number',number=3),dict(type='colors',label='blue'),dict(type='number',number=2)] if name=='selvala' else [dict(type='colors',label='white'),dict(type='colors',label='blue')]
      action(e,'activate_mana',c['forgeId'],plans,abilityId=ability['abilityId']);counts={color:sum(x['count'] for x in e.state['mana'] if x['color']==color) for color in [1,2,16]}
      if name=='selvala':assert e.state['manaTotal']==5 and counts[16]==3 and counts[2]==2,counts
      else:
       assert e.state['manaTotal']==2 and counts[1]==counts[2]==1,counts
       forbidden=next(c for c in e.state['hand'] if c['name']=='Aven Interrupter');walker=next(c for c in e.state['hand'] if c['name']=='Jace, Cunning Castaway');assert forbidden['forgeId'] not in e.state['legalCasts'] and walker['forgeId'] in e.state['legalCasts'],e.state['legalCasts']
       action(e,'cast_spell',walker['forgeId']);resolve(e);assert any(c['name']=='Jace, Cunning Castaway' for c in e.state['battlefield'])
      results.append(dict(id='native-mana-combination-'+name,passed=True,evidence=str(e.ipc)))
     except Exception as ex:results.append(dict(id='native-mana-combination-'+name,passed=False,error=str(ex),evidence=str(e.ipc) if e else ''))
     finally:
      if e:e.close()
     print(json.dumps(results[-1]),flush=True);(E/'mana-combinations-native-results.json').write_text(json.dumps(results,indent=2))
    assert all(r['passed'] for r in results),results
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_discard_hand_zero_cost():
    results=[]
    for name in ['diamond','zero-sacrifice']:
     e=None
     try:
      if name=='diamond':settings=dict(fixtureHand=['Divination','Forest'],fixtureLands=[],fixtureBattlefield=["Lion's Eye Diamond"],fixtureLibrary=['Plains']*10)
      else:settings=dict(fixtureHand=[],fixtureLands=['Swamp'],fixtureBattlefield=['Grim Hireling'],fixtureOpponentBattlefield=['Grizzly Bears'],fixtureLibrary=['Plains']*10)
      e=Engine('card-family',**settings);source="Lion's Eye Diamond" if name=='diamond' else 'Grim Hireling';c=next(c for c in e.state['battlefield'] if c['name']==source)
      if name=='diamond':
       a=next(a for a in e.state['legalManaOffers'] if a['forgeId']==c['forgeId']);action(e,'activate_mana',c['forgeId'],[dict(type='confirm',accept=True),dict(type='order',all=True),dict(type='colors',label='green')],abilityId=a['abilityId'])
       assert not e.state['hand'] and e.state['manaTotal']==3 and all(m['color']==16 for m in e.state['mana']);assert {"Lion's Eye Diamond",'Divination','Forest'}<={c['name'] for c in e.state['graveyard']}
      else:
       a=next(a for a in e.state['legalActivations'] if a['forgeId']==c['forgeId']);action(e,'activate_ability',c['forgeId'],[dict(type='targets',name='Grizzly Bears',seat=2)],abilityId=a['abilityId']);resolve(e);target=next(c for c in e.state['battlefield'] if c['name']=='Grizzly Bears');assert target['power']==target['toughness']==2
      results.append(dict(id='native-cost-'+name,passed=True,evidence=str(e.ipc)))
     except Exception as ex:results.append(dict(id='native-cost-'+name,passed=False,error=str(ex),evidence=str(e.ipc) if e else ''))
     finally:
      if e:e.close()
     print(json.dumps(results[-1]),flush=True);(E/'discard-hand-zero-cost-native-results.json').write_text(json.dumps(results,indent=2))
    assert all(r['passed'] for r in results),results
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_mana_pool_choice():
    e=Engine('card-family',fixtureHand=['Dark Ritual','Fatal Push'],fixtureLands=['Swamp'],fixtureBattlefield=['Nurturing Peatland'],fixtureOpponentBattlefield=['Grizzly Bears'],fixtureLibrary=['Plains']*10)
    try:
     swamp=next(c for c in e.state['battlefield'] if c['name']=='Swamp');a=next(a for a in e.state['legalManaOffers'] if a['forgeId']==swamp['forgeId']);action(e,'activate_mana',swamp['forgeId'],abilityId=a['abilityId'])
     action(e,'cast_spell',next(c['forgeId'] for c in e.state['hand'] if c['name']=='Dark Ritual'));resolve(e)
     land=next(c for c in e.state['battlefield'] if c['name']=='Nurturing Peatland');a=next(a for a in e.state['legalManaOffers'] if a['forgeId']==land['forgeId']);action(e,'activate_mana',land['forgeId'],[dict(type='confirm',accept=True),dict(type='colors',label='black')],abilityId=a['abilityId']);assert e.state['manaTotal']==4
     spell=next(c for c in e.state['hand'] if c['name']=='Fatal Push');action(e,'cast_spell',spell['forgeId'],[dict(type='targets',name='Grizzly Bears',seat=2)]);assert e.state['manaTotal']==3 and sum(m['count'] for m in e.state['mana'])==3 and all(m['color']==4 for m in e.state['mana']),e.state['mana'];resolve(e)
     assert not any(c['name']=='Grizzly Bears' for c in e.state['battlefield'])
     r=dict(id='native-original-default-mana-pool-payment-without-extra-prompt',passed=True,evidence=str(e.ipc));(E/'mana-pool-choice-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_tidebinder_token():
    e=Engine('card-family',fixtureHand=['Sunfall','Tishana\'s Tidebinder','Fateful Absence'],fixtureLands=['Plains']*10+['Island']*10,fixtureBattlefield=['Grizzly Bears'],fixtureOpponentBattlefield=['Grizzly Bears'],fixtureLibrary=['Plains']*10)
    try:
     action(e,'cast_spell',next(c['forgeId'] for c in e.state['hand'] if c['name']=='Sunfall'));resolve(e);token=next(c for c in e.state['battlefield'] if c.get('presentationKey')=='token:incubator_c_0_0_a_phyrexian');a=next(a for a in e.state['legalActivations'] if a['forgeId']==token['forgeId']);action(e,'activate_ability',token['forgeId'],abilityId=a['abilityId'])
     action(e,'cast_spell',next(c['forgeId'] for c in e.state['hand'] if c['name']=="Tishana's Tidebinder"));resolve(e,[dict(type='targets',ability=token['name'])])
     current=next(c for c in e.state['battlefield'] if c['forgeId']==token['forgeId']);assert 'Creature' not in current['currentTypes'];assert any(r['all'] for r in current['keywordRemovals']);assert not any(a['forgeId']==token['forgeId'] for a in e.state['legalActivations'])
     action(e,'cast_spell',next(c['forgeId'] for c in e.state['hand'] if c['name']=='Fateful Absence'),[dict(type='targets',name="Tishana's Tidebinder",seat=1)]);resolve(e)
     current=next(c for c in e.state['battlefield'] if c['forgeId']==token['forgeId']);assert not current['keywordRemovals'];a=next(a for a in e.state['legalActivations'] if a['forgeId']==token['forgeId']);action(e,'activate_ability',token['forgeId'],abilityId=a['abilityId']);resolve(e)
     current=next(c for c in e.state['battlefield'] if c['forgeId']==token['forgeId']);assert 'Creature' in current['currentTypes'] and current['power']==current['toughness']==2
     r=dict(id='native-tidebinder-counter-token-ability-removal-and-restoration',passed=True,evidence=str(e.ipc));(E/'tidebinder-token-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()
    if "results" in locals():assert all(r["passed"] for r in results),results

def check_breach_escape():
    e=Engine('card-family',fixtureHand=['Underworld Breach'],fixtureLands=['Mountain','Mountain','Swamp'],fixtureGraveyard=['Dark Ritual','Plains','Forest','Island'],fixtureLibrary=['Plains']*10)
    try:
     action(e,'cast_spell',next(c['forgeId'] for c in e.state['hand'] if c['name']=='Underworld Breach'));resolve(e)
     card=next(c for c in e.state['graveyard'] if c['name']=='Dark Ritual');assert card['forgeId'] in e.state['legalCasts'],e.state['unavailableActions']
     action(e,'cast_spell',card['forgeId'],[dict(type='cards-effect',all=True)]);resolve(e)
     assert e.state['manaTotal']==3 and len(e.state['exile'])==3 and all(c['name'] in ('Plains','Forest','Island') for c in e.state['exile'])
     assert any(c['name']=='Dark Ritual' for c in e.state['graveyard'])
     r=dict(id='native-breach-granted-escape-pay-exile-three-resolve',passed=True,evidence=str(e.ipc));(E/'breach-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()

def check_sprawl_attachment():
    e=Engine('card-family',fixtureHand=['Utopia Sprawl'],fixtureLands=['Forest']*2,fixtureLibrary=['Plains']*10)
    try:
     forest=next(c for c in e.state['battlefield'] if c['name']=='Forest');spell=next(c for c in e.state['hand'] if c['name']=='Utopia Sprawl')
     action(e,'cast_spell',spell['forgeId'],[dict(type='targets',ids=[forest['forgeId']])]);resolve(e,[dict(type='entities',name='Forest'),dict(type='colors',label='blue')])
     aura=next(c for c in e.state['battlefield'] if c['name']=='Utopia Sprawl');assert aura['attachedToForgeId']==forest['forgeId'] and [c.lower() for c in aura['chosenColors']]==['blue']
     # Pick the untouched enchanted Forest explicitly; other mana sources may
     # have paid the Aura's cost. Advance normally if that Forest was tapped.
     for _ in range(80):
      current=next(c for c in e.state['battlefield'] if c['forgeId']==forest['forgeId'])
      if e.state['activeSeat']==1 and e.state['phase']=='MAIN1' and not current['tapped']:break
      action(e,'pass_priority')
     else:raise AssertionError('Did not reach an untapped enchanted Forest')
     offer=next(a for a in e.state['legalManaOffers'] if a['forgeId']==forest['forgeId']);before=e.state['manaTotal'];action(e,'activate_mana',forest['forgeId'],abilityId=offer['abilityId']);resolve(e)
     assert e.state['manaTotal']==before+2 and any(m['color']==2 for m in e.state['mana'])
     r=dict(id='native-sprawl-resolving-aura-color-attachment-extra-mana',passed=True,evidence=str(e.ipc));(E/'sprawl-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()

def check_fetchland_selection():
    e=Engine('card-family',fixtureHand=[],fixtureLands=['Forest'],fixtureBattlefield=['Prismatic Vista'],fixtureLibrary=['Swamp','Forest','Plains'])
    try:
     card=next(c for c in e.state['battlefield'] if c['name']=='Prismatic Vista');a=next(a for a in e.state['legalActivations'] if a['forgeId']==card['forgeId'])
     action(e,'activate_ability',card['forgeId'],[dict(type='confirm',accept=True)],abilityId=a['abilityId']);resolve(e,[dict(type='cards-zone',name='Swamp')])
     assert e.state['life']==19 and any(c['name']=='Prismatic Vista' for c in e.state['graveyard']) and any(c['name']=='Swamp' and not c['tapped'] for c in e.state['battlefield'])
     r=dict(id='native-fetchland-life-sacrifice-library-selection-and-original-ui-classifiers',passed=True,evidence=str(e.ipc));(E/'fetchland-native-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
    finally:e.close()

def check_replacement_labels():
 for first,squirrels in [('Chatterfang, Squirrel General',1),('Peregrin Took',2)]:
  e=Engine('card-family',fixtureHand=['Prosperous Innkeeper'],fixtureLands=['Forest']*2,fixtureBattlefield=['Chatterfang, Squirrel General','Peregrin Took'],fixtureLibrary=['Plains']*10)
  try:
   action(e,'cast_spell',e.state['hand'][0]['forgeId']);resolve(e,[dict(type='options',label=first)]+([dict(type='options',label='Prosperous Innkeeper (#1)')] if squirrels==2 else []))
   counts={n:sum(c['name']==n for c in e.state['battlefield']) for n in ['Treasure Token','Food Token','Squirrel Token']};assert counts=={'Treasure Token':1,'Food Token':1,'Squirrel Token':squirrels},counts
   # Inspect the native translation's actual button strings, not just source text.
   native=[json.loads(x) for x in (e.native_folder/'native-model.jsonl').read_text().splitlines()];labels=[r['value']['labels'] for r in native if r['kind']=='original-choice-ui'];assert ['Chatterfang, Squirrel General','Peregrin Took'] in labels,labels
   print(json.dumps(dict(first=first,passed=True,tokens=counts,evidence=str(e.ipc))),flush=True)
  finally:e.close()

GROUPS=[check_tower_sacrifice_not_automatic,check_autopay_with_tower,check_replacement_labels,check_payments_and_search,check_token_creation,check_nonbasic_mana,check_phyrexian_compleated,check_food,check_card_naming,check_shockland_branches,check_storm,check_creature_types,check_granted_abilities,check_ad_nauseam_stop,check_modal_farewell,check_saga_mana,check_faces,check_rituals,check_cycling,check_fluster,check_fluster_new,check_swat,check_clue,check_incubator,check_orc,check_teferi_emblem,check_jace_emblem,check_emblem_creators,check_mindbreak,check_citadel_library,check_lair,check_chandra_sweeper,check_grim_treasure,check_necropotence,check_dauthi,check_reported_veil,check_context_activation,check_combat_context,check_ivy_oak,check_facebreaker,check_mana_recovery,check_generated_token_triggers,check_loyalty_payments,check_gemstone_opening,check_mana_combinations,check_discard_hand_zero_cost,check_mana_pool_choice,check_tidebinder_token,check_breach_escape,check_sprawl_attachment,check_fetchland_selection]
for group in GROUPS:
 if a.group and group.__name__ not in a.group:continue
 try:group();records.append(dict(group=group.__name__,passed=True))
 except Exception as ex:records.append(dict(group=group.__name__,passed=False,error=str(ex)))
 print(json.dumps(records[-1]),flush=True)
 (E/'progress.json').write_text(json.dumps(dict(groups=records,inputs=inputs,elapsedSeconds=time.time()-started),indent=2))
report=dict(passed=all(r['passed'] for r in records),groups=records,inputs=inputs,elapsedSeconds=time.time()-started,scope=__doc__,binaries={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in a.worker.parent.glob('*.dll')})
(E/'report.json').write_text(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
