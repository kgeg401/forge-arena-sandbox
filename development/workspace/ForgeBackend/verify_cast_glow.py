"""Check native cast affordability against actual Forge timing, targets and mana."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute
p=argparse.ArgumentParser()
for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[];observations=[]
try:
 e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,fixtureHand=['Savannah Lions','Opt','Divination','Grizzly Bears','Hired Blade','Negate','Torment of Hailfire','Plains'],fixtureLands=['Plains','Island','Island','Swamp','Swamp','Swamp'],fixtureBattlefield=[],fixtureOpponentBattlefield=[],fixtureOpponentHand=[],fixtureOpponentPolicy='passive',fixtureLibrary=['Forest']*20)
 def check(label,ok):e.check(label,ok)
 def offered():return {c['name'] for c in e.state['hand'] if c['forgeId'] in e.state['legalCasts']}
 def observe(label):
  rows=e.native_status['castAvailability'];legal=set(e.state['legalCasts']);cards={c['forgeId']:c for c in e.state['hand']}
  check(label+': every actual native cast offer is affordable',len(rows)==len(legal) and all(r['forgeAffordable'] and r['effectiveAffordable'] for r in rows))
  check(label+': foreign instances, printings and action types stay rejected',all(not any(r[k] for k in ('foreignInstanceOverride','wrongPrintingOverride','activationOverride')) for r in rows))
  observations.append(dict(label=label,phase=e.state['phase'],activeSeat=e.state['activeSeat'],offered=sorted(offered()),native=rows))
 def act(op,id=0,**kw):execute(e,trace,op,id,**kw)
 def advance(predicate):
  for _ in range(70):
   if predicate():return
   act('pass_priority',_attack_policy=lambda d,s:[])
  raise AssertionError('Phase bound exceeded')
 check('Main phase offers payable creatures, sorceries, instants and flash',{'Savannah Lions','Divination','Opt','Hired Blade'}<=offered())
 check('Wrong-colored mana and absent legal targets do not offer casts',not {'Grizzly Bears','Negate'}&offered())
 check('Normal land play remains available',bool(e.state['legalLands']))
 observe('main')
 check('Paid native casts reproduce the missing auto-tap-plan condition',any(not r['nativeAffordable'] for r in e.native_status['castAvailability']))
 advance(lambda:e.state['phase']=='COMBAT_BEGIN');check('Combat offers only instant-speed cards',offered()=={'Opt','Hired Blade'});observe('combat')
 advance(lambda:e.state['activeSeat']==2);check('Opponent turn offers only instant-speed cards',offered()=={'Opt','Hired Blade'});observe('opponent turn')
 opt=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Opt');act('cast_spell',opt)
 check('An actual spell on the stack makes Negate available','Negate' in offered());observe('stack response')
 for _ in range(30):
  if not e.state['stackOrder']:break
  act('pass_priority')
 check('Negate stops being available when its legal target disappears','Negate' not in offered());observe('resolved instant')
 advance(lambda:e.state['activeSeat']==1 and e.state['phase']=='MAIN1')
 def x4(choice,state):
  if choice['type']=='number' and 'Choose X' in choice.get('prompt',''):return [dict(number=4)]
  return None
 torment=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Torment of Hailfire');act('cast_spell',torment,_choice_policy=x4)
 check('The real X=4 cast spends all six lands',sum(c['tapped'] for c in e.state['battlefield'] if c['name'] in ('Plains','Island','Swamp'))==6 and e.state['manaTotal']==0)
 check('Paid spells lose availability after the resources are spent',not offered());observe('mana spent')
 result=dict(passed=True,checks=e.checks,observations=observations,evidence=str(e.ipc),scope='Seeded native-handler/Forge timing, target and payment checks. The actual Unity patch and rendered blue outline require a separate native test.')
except Exception as error:result=dict(passed=False,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
finally:
 if e:e.close()
(a.output/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(passed=result['passed'],checks=len(result.get('checks',[])),error=result.get('error','')[:400],evidence=result.get('evidence'))));raise SystemExit(0 if result['passed'] else 1)
