"""Real Forge cycles and original native submissions; explicit seeded position."""
import argparse,json,time,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute
p=argparse.ArgumentParser()
for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--case',choices=['mana','stack','short'],required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
e=None;trace=[]
def choices(c,s):
 if c['type']=='colors':return [dict(choiceId=next(o for o in c['options'] if o.get('color','').lower()=='blue')['choiceId'])]
 return None
def targets(d,s):
 ids={c['forgeId'] for c in s['battlefield'] if c['name']=='Zaxara, the Exemplary'}
 return [o for o in d['options'] if o['forgeId'] in ids][:1]
def act(op,id=0,**kw):execute(e,trace,op,id,_choice_policy=choices,_target_policy=targets,**kw)
def settle():
 for _ in range(20):
  if not e.state['stackOrder']:return
  act('pass_priority')
 raise AssertionError('stack bound')
def activate(name,text='',mana=False):
 card=next(c for c in e.state['battlefield'] if c['name']==name)
 offer=next(o for o in e.state['legalManaOffers' if mana else 'legalActivations'] if o['forgeId']==card['forgeId'] and text.lower() in json.dumps(o).lower())
 act('activate_mana' if mana else 'activate_ability',card['forgeId'],abilityId=offer['abilityId'])
def refresh():
 e.native_status=e.native_wait(e.native_folder/'status.json');e.state=e.native_status['state'];return e.native_status['loop']
def run(count,timeout=100):
 refresh();reply=e.native_call('loop_start',count=count);assert reply['accepted'],reply
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  loop=refresh()
  if loop.get('runId')==reply['loop'].get('runId') and loop['requested']==count and not loop['running']:return loop
  time.sleep(.03)
 raise TimeoutError('loop bound')
try:
 e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,fixtureHand=['Freed from the Real'],fixtureLands=['Island']*3,fixtureBattlefield=[],fixtureBattlefieldReady=True,fixtureCommander='Zaxara, the Exemplary',fixtureCommanderInPlay=True,fixtureLibrary=['Forest']*20,fixtureOpponentLibrary=['Forest']*20,fixtureOpponentPolicy='passive',fixtureLocalLife=40)
 act('cast_spell',next(c['forgeId'] for c in e.state['hand'] if c['name']=='Freed from the Real'));settle()
 activate('Zaxara, the Exemplary',mana=True)
 for _ in range(2):activate('Freed from the Real','untap');settle();activate('Zaxara, the Exemplary',mana=True)
 loop=refresh();(a.output/'detected.json').write_text(json.dumps(e.native_status,indent=2))
 e.check('Two actual equal net-blue cycles are detected',loop['available'] and loop['kind']=='mana')
 before=e.state['manaTotal'];initial=json.loads(json.dumps(e.state))
 for count in (0,-1,1001):
  reply=e.native_call('loop_start',count=count);e.check('Out-of-range count rejected: '+str(count),not reply['accepted'] and e.state['manaTotal']==before)
 count=5 if a.case=='short' else 100
 loop=run(count);(a.output/'after-repeat.json').write_text(json.dumps(e.native_status,indent=2))
 e.check(str(count)+' additional cycles finish',loop['completed']==count and not loop['running'])
 e.check(str(count)+' actual additional blue mana, no life/phase change',e.state['manaTotal']==before+count and e.state['life']==initial['life'] and e.state['phase']==initial['phase'] and not e.state['stackOrder'])
 e.check('Original physical board objects remain',[(c['forgeId'],c['tapped']) for c in e.state['battlefield']]==[(c['forgeId'],c['tapped']) for c in initial['battlefield']])
 if a.case in ('mana','short'):
  refresh();reply=e.native_call('loop_start',count=1000);assert reply['accepted'],reply;time.sleep(.2)
  for _ in range(12):
   refresh();reply=e.native_call('loop_stop')
   if reply['accepted']:break
   assert reply.get('reason')=='Stale or foreign native worker request',reply
  assert reply['accepted'],reply
  loop=refresh();completed=loop['completed'];time.sleep(.3);loop=refresh()
  e.check('Stop prevents another cycle without rolling back actual actions',not loop['running'] and loop['completed']==completed and completed<1000)
 else:
  activate('Freed from the Real','untap');loop=refresh();e.check('Actual activation held on stack is repeatable',loop['available'] and loop['kind']=='stack')
  before=e.state['manaTotal'];stack=len(e.state['stackOrder']);loop=run(100)
  e.check('One hundred additional paid activations stay on real stack',loop['completed']==100 and len(e.state['stackOrder'])==stack+100 and e.state['manaTotal']==before-100)
  loop=run(100);e.check('Insufficient mana stops safely',not loop['running'] and loop['completed']<100 and e.state['manaTotal']>=0 and not e.state['fidelityGap'])
 result=dict(passed=True,case=a.case,checks=e.checks,evidence=str(e.ipc),loop=refresh(),scope='Seeded real Forge cycles through shipped native request handlers; no universal or multiplayer-loop certification.')
except Exception as error:result=dict(passed=False,case=a.case,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
finally:
 if e:e.close()
(a.output/'report.json').write_text(json.dumps(result,indent=2));(a.output/'choices.json').write_text(json.dumps(trace,indent=2));print(json.dumps(dict(passed=result['passed'],case=a.case,error=result.get('error','')[:1200],checks=len(result['checks']),evidence=result['evidence'])));raise SystemExit(0 if result['passed'] else 1)
