"""Exact post-prevention damage reaches original Arena handlers without marking loyalty loss as creature damage."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

CASES=('bolt-walker','shield-walker','loyalty-is-not-damage')
def run(a,key):
 e=None;trace=[];report={};walker_name='Jace, Wielder of Mysteries'
 try:
  own=key=='loyalty-is-not-damage';shield=key=='shield-walker'
  counters=[dict(seat=1 if own else 2,cardName=walker_name,occurrence=0,type='LOYALTY',count=4)]
  if shield:counters.append(dict(seat=2,cardName=walker_name,occurrence=0,type='SHIELD',count=1))
  e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,fixtureHand=[] if own else ['Lightning Bolt'],fixtureLands=['Mountain'],fixtureBattlefield=[walker_name] if own else [],fixtureOpponentBattlefield=[] if own else [walker_name],fixtureCounters=counters,fixtureLibrary=['Forest']*20)
  walker=next(c['forgeId'] for c in e.state['battlefield'] if c['name']==walker_name)
  def targets(d,s):return [v for v in d['options'] if v.get('targetSeat')==1] if own else [v for v in d['options'] if v['forgeId']==walker]
  if own:
   offers=[v for v in e.state['legalActivations'] if v['forgeId']==walker];offer=next(v for v in offers if v['api']=='Mill')
   execute(e,trace,'activate_ability',walker,abilityId=offer['abilityId'],_target_policy=targets)
  else:
   spell=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Lightning Bolt');execute(e,trace,'cast_spell',spell,_target_policy=targets)
  for _ in range(20):
   if not e.state['stackOrder']:break
   execute(e,trace,'pass_priority',_target_policy=targets)
  else:raise AssertionError('Actual effect failed to resolve')
  e.check('Actual opposing player life remains unchanged',e.state['opponentLife']==20)
  card=next(c for c in e.state['battlefield'] if c['forgeId']==walker)
  e.check('Loyalty follows the actual paid or prevented effect',card['loyalty']==(5 if own else 4 if shield else 1))
  if shield:e.check('Actual shield is consumed instead of fabricating damage',not any(c['type']=='SHIELD' for c in card['counters']))
  damage=[v for v in e.state['events'] if v['kind']=='damage' and v.get('targetForgeId')==walker];expected=3 if not own and not shield else 0
  e.check('Only actual unprevented damage creates an impact event',len(damage)==int(expected>0) and sum(v['amount'] for v in damage)==expected)
  e.check('Noncombat impact is unmarked, exact, and not inferred from a loyalty cost',all(not v['combat'] and v.get('markDamage') is False for v in damage))
  native=[json.loads(v)['value'] for v in (e.native_folder/'native-model.jsonl').read_text().splitlines() if json.loads(v)['kind']=='native-update']
  hits=[v for row in native for v in row['damageEvents'] if v['target']==1000+walker]
  e.check('Original parser observes exactly the actual direct-damage event',len(hits)==int(expected>0) and sum(v['amount'] for v in hits)==expected and all(v['type']=='Direct' for v in hits))
  e.check('Original walker never has creature-style marked damage',all(c['damage']==0 for row in native for c in row['cards'] if c['id']==1000+walker))
  e.check('No unresolved or unsupported native decision remains',not e.state.get('decision') and not e.state['fidelityGap'])
  report=dict(case=key,passed=True,checks=e.checks,evidence=str(e.ipc))
 except Exception as error:report=dict(case=key,passed=False,error=repr(error)[:1400],traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
 finally:
  if e:e.close()
 (a.output/(key+'.json')).write_text(json.dumps(report,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps({k:report.get(k) for k in ('case','passed','error','evidence')}),flush=True);return report['passed']

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('worker','managed','fixture','output'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--case',choices=CASES,action='append');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 ok=[run(a,key) for key in a.case or CASES];raise SystemExit(0 if all(ok) else 1)
