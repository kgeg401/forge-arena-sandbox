"""Real paid Staff life cycles; never synthesize mana, life or stack effects."""
import argparse,json,time,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute
p=argparse.ArgumentParser()
for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--chain',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[]
def act(op,id=0,**fields):execute(e,trace,op,id,**fields)
def settle():
 for _ in range(8):
  if not e.state['stackOrder']:return
  act('pass_priority')
 raise AssertionError('Stack bound')
def staff(api,tap=None):
 card=next(c for c in e.state['battlefield'] if c['name']=='Staff of Domination');o=next(o for o in e.state['legalActivations'] if o['forgeId']==card['forgeId'] and o['api']==api and (tap is None or o['tap']==tap));act('activate_ability',card['forgeId'],abilityId=o['abilityId']);settle()
def marwyn():
 card=next(c for c in e.state['battlefield'] if c['name']=='Marwyn, the Nurturer');o=next(o for o in e.state['legalManaOffers'] if o['forgeId']==card['forgeId']);act('activate_mana',card['forgeId'],abilityId=o['abilityId'])
def refresh():e.native_status=e.native_wait(e.native_folder/'status.json');e.state=e.native_status['state'];return e.native_status['loop']
def run(count):
 refresh();reply=e.native_call('loop_start',count=count);assert reply['accepted'],reply;end=time.monotonic()+max(90,count)
 while time.monotonic()<end:
  loop=refresh()
  if loop['runId']==reply['loop']['runId'] and not loop['running']:return loop
  time.sleep(.025)
 raise TimeoutError('Life loop bound')
try:
 settings=dict(fixtureHand=[],fixtureLands=[] if a.chain else ['Forest']*40,fixtureBattlefield=['Staff of Domination']+(['Marwyn, the Nurturer'] if a.chain else []),fixtureBattlefieldReady=True,fixtureLibrary=['Forest']*20,fixtureOpponentLibrary=['Forest']*20,fixtureOpponentPolicy='passive',fixtureLocalLife=40)
 if a.chain:settings['fixtureCounters']=[dict(seat=1,cardName='Marwyn, the Nurturer',occurrence=0,type='P1P1',count=4)]
 e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7351,**settings)
 if a.chain:
  marwyn()
  for _ in range(2):staff('Untap',True);staff('Untap',False);marwyn()
  refresh();e.check('Real Marwyn/Staff mana cycle is detected before conversion',e.native_status['loop']['kind']=='mana')
  loop=run(300);e.check('Three hundred real mana cycles produce the life-payment pool',loop['completed']==300 and e.state['manaTotal']==307)
 else:
  for card in list(e.state['battlefield']):
   if card['name']=='Forest':act('activate_mana',card['forgeId'],abilityId=next(o['abilityId'] for o in e.state['legalManaOffers'] if o['forgeId']==card['forgeId']))
  e.check('Forty real basic-land mana activations produced the starting pool',e.state['manaTotal']==40)
 for _ in range(2):staff('GainLife');staff('Untap')
 loop=refresh();e.check('Two paid gain-life/untap cycles are recognized',loop['available'] and loop['kind']=='life' and loop['lifeGainPerCycle']==1 and e.state['life']==42 and e.state['manaTotal']==(301 if a.chain else 34))
 (a.output/'detected.json').write_text(json.dumps(e.native_status,indent=2));before=e.state['life'];count=100 if a.chain else 10;loop=run(count);first_run=loop['runId']
 e.check('Real life cycles gain exact life and pay every cost',loop['completed']==count and e.state['life']==before+count and e.state['manaTotal']==(1 if a.chain else 4) and not e.state['stackOrder'])
 if a.chain:
  reply=e.native_call('loop_start',count=100);e.check('Exhausted resources reject a new batch without spending life or mana',not reply['accepted'] and e.state['life']==142 and e.state['manaTotal']==1 and not e.state['fidelityGap'])
 else:
  loop=run(10);e.check('A new same-count batch has a distinct identity',loop['runId']!=first_run)
  e.check('Insufficient mana stops after one more complete paid cycle',loop['completed']==1 and e.state['life']==53 and e.state['manaTotal']==1 and not e.state['stackOrder'] and not loop['running'] and not e.state['fidelityGap'])
 e.check('The actual source is untapped at the last complete boundary',not next(c for c in e.state['battlefield'] if c['name']=='Staff of Domination')['tapped'])
 result=dict(passed=True,checks=e.checks,evidence=str(e.ipc),loop=loop,scope='Seeded real original native-handler/Forge life loops and resource exhaustion, not a rendered or internet claim.')
except BaseException as error:result=dict(passed=False,error=repr(error)[:1600],traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
finally:
 if e:e.close()
(a.output/'report.json').write_text(json.dumps(result,indent=2));(a.output/'choices.json').write_text(json.dumps(trace,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('checks','scope','traceback')}));raise SystemExit(0 if result['passed'] else 1)
