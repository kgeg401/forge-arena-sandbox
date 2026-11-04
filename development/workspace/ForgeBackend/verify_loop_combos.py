"""Additional real-card loops through Forge and original native request handlers."""
import argparse,json,time,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

p=argparse.ArgumentParser()
for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--case',choices=['sanctum','bloom','faeburrow','incubation','pemmins','marwyn-staff','circle-staff'],required=True)
p.add_argument('--count',type=int,default=10);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
producer={'sanctum':'Sanctum Weaver','bloom':'Bloom Tender','faeburrow':'Faeburrow Elder','incubation':'Incubation Druid','pemmins':'Zaxara, the Exemplary','marwyn-staff':'Marwyn, the Nurturer','circle-staff':'Circle of Dreams Druid'}[a.case]
staff=a.case.endswith('staff');aura="Pemmin's Aura" if a.case=='pemmins' else 'Freed from the Real';e=None;trace=[]
settings=dict(fixtureHand=[] if staff else [aura],fixtureLands=['Forest'] if staff else ['Island']*3,fixtureBattlefield=[producer,'Staff of Domination']+(['Yoked Ox']*4 if a.case=='circle-staff' else []) if staff else [producer],fixtureBattlefieldReady=True,fixtureLibrary=['Forest']*20,fixtureOpponentLibrary=['Forest']*20,fixtureOpponentPolicy='passive',fixtureLocalLife=40)
if a.case in ('incubation','marwyn-staff'):settings['fixtureCounters']=[dict(seat=1,cardName=producer,occurrence=0,type='P1P1',count=3 if a.case=='incubation' else 4)]
def colors(c,s):
 if c['type']=='colors':return [dict(choiceId=next(o for o in c['options'] if o.get('color','').lower()=='blue')['choiceId'])]
 return None
def targets(d,s):
 ids={c['forgeId'] for c in s['battlefield'] if c['name']==producer};return [o for o in d['options'] if o['forgeId'] in ids][:1]
def act(op,id=0,**kw):execute(e,trace,op,id,_choice_policy=colors,_target_policy=targets,**kw)
def settle():
 for _ in range(24):
  if not e.state['stackOrder']:return
  act('pass_priority')
 raise AssertionError('Stack did not settle within bound')
def activate(name,text='',mana=False,tap=None):
 card=next(c for c in e.state['battlefield'] if c['name']==name)
 offer=next(o for o in e.state['legalManaOffers' if mana else 'legalActivations'] if o['forgeId']==card['forgeId'] and text.lower() in json.dumps(o).lower() and (tap is None or o.get('tap')==tap))
 act('activate_mana' if mana else 'activate_ability',card['forgeId'],abilityId=offer['abilityId'])
def refresh():e.native_status=e.native_wait(e.native_folder/'status.json');e.state=e.native_status['state'];return e.native_status['loop']
def cycle():
 if staff:
  activate('Staff of Domination','Untap',tap=True);settle();activate('Staff of Domination','Untap',tap=False);settle()
 else:activate(aura,'untap');settle()
 activate(producer,mana=True)
try:
 e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7304,**settings)
 if not staff:act('cast_spell',next(c['forgeId'] for c in e.state['hand'] if c['name']==aura));settle()
 activate(producer,mana=True);first=e.state['manaTotal'];cycle();gain=e.state['manaTotal']-first;cycle()
 loop=refresh();(a.output/'detected.json').write_text(json.dumps(e.native_status,indent=2))
 e.check('Two full actual cycles detected: '+a.case,loop['available'] and loop['kind']=='mana')
 e.check('Demonstrated cycles produce positive mana',gain>0)
 before=json.loads(json.dumps(e.state));reply=e.native_call('loop_start',count=a.count);assert reply['accepted'],reply
 end=time.monotonic()+max(60,a.count*2)
 while time.monotonic()<end:
  loop=refresh()
  if loop.get('runId')==reply['loop'].get('runId') and loop['requested']==a.count and not loop['running']:break
  time.sleep(.025)
 e.check('All requested additional cycles finish',not loop['running'] and loop['completed']==a.count)
 e.check('Exact real mana gain with no life/phase/stack change',e.state['manaTotal']==before['manaTotal']+gain*a.count and e.state['life']==before['life'] and e.state['phase']==before['phase'] and not e.state['stackOrder'])
 e.check('Original objects, taps and counters remain',[(c['forgeId'],c['tapped'],c.get('counters')) for c in before['battlefield']]==[(c['forgeId'],c['tapped'],c.get('counters')) for c in e.state['battlefield']])
 e.check('No native fidelity gap',not e.state['fidelityGap'])
 result=dict(passed=True,case=a.case,requested=a.count,completed=loop['completed'],gainPerCycle=gain,checks=e.checks,evidence=str(e.ipc),scope='Seeded real-card combo and original native handlers. No rendered, shuffled-deck or internet claim.')
except Exception as error:result=dict(passed=False,case=a.case,error=repr(error)[:1600],traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
finally:
 if e:e.close()
(a.output/'report.json').write_text(json.dumps(result,indent=2));(a.output/'choices.json').write_text(json.dumps(trace,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('checks','scope','traceback')}));raise SystemExit(0 if result['passed'] else 1)
