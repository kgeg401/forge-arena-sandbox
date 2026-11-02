"""Grow a real token army from one initial permanent, then attack on its next natural turn."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

def run(a):
 e=None;trace=[];checks=[];report={}
 try:
  e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,fixtureHand=['Raise the Alarm','Second Harvest','Second Harvest'],fixtureLands=['Plains']*2+['Forest']*8,fixtureBattlefield=['Doubling Season'],fixtureOpponentBattlefield=[],fixtureBattlefieldReady=True,fixtureLibrary=['Forest']*20)
  old=set();stages=[]
  for name,expected in [('Raise the Alarm',4),('Second Harvest',12),('Second Harvest',36)]:
   c=next(c for c in e.state['hand'] if c['name']==name);execute(e,trace,'cast_spell',c['forgeId'])
   for _ in range(15):
    if not e.state['stackOrder']:break
    execute(e,trace,'pass_priority')
   army=[c for c in e.state['battlefield'] if c['token'] and c['controller']==1];current={c['forgeId'] for c in army}
   e.check('Actual '+name+' resolution grows the army to '+str(expected),len(army)==expected and old<=current and len(current)==expected)
   e.check('Original Soldier characteristics remain one-one and summoning sick',all(c['power']==1 and c['toughness']==1 and c['sick'] for c in army))
   stages.append(dict(spell=name,count=expected,ids=sorted(current)));old=current
  for _ in range(120):
   if e.state['turn']==3 and e.state['phase']=='MAIN1':break
   execute(e,trace,'pass_priority',_attack_policy=lambda d,s:[])
  else:raise AssertionError('Natural next local turn did not arrive')
  e.check('The same thirty-six original tokens become ready on the actual next turn',old=={c['forgeId'] for c in e.state['battlefield'] if c['token']} and all(not c['sick'] for c in e.state['battlefield'] if c['token']))
  for _ in range(60):
   if e.state['gameOver']:break
   execute(e,trace,'pass_priority',_attack_seat=2)
  else:raise AssertionError('Actual token combat did not finish')
  hits=[v for v in e.state['events'] if v['kind']=='damage' and v.get('sourceForgeId') in old and v.get('targetSeat')==2]
  e.check('Each of the original thirty-six attackers deals exactly one actual damage',len(hits)==36 and {v['sourceForgeId'] for v in hits}==old and all(v['amount']==1 and v['combat'] for v in hits))
  e.check('Actual combat wins from twenty life without manufactured life or readiness',e.state['gameOver'] and e.state['opponentLife']==-16 and next(p for p in e.state['players'] if p['seat']==1)['won'])
  native=[json.loads(v)['value'] for v in (e.native_folder/'native-model.jsonl').read_text().splitlines() if json.loads(v)['kind']=='native-update'];impacts=[v for row in native for v in row['damageEvents'] if v['target']==2]
  e.check('Original Arena parser receives exactly thirty-six real combat damage events',len(impacts)==36 and sum(v['amount'] for v in impacts)==36 and all(v['type']=='Combat' for v in impacts))
  e.check('No unsupported callback or orphaned choice remains',not e.state['fidelityGap'] and not e.state.get('decision'))
  report=dict(passed=True,checks=e.checks,evidence=str(e.ipc),stages=stages,scope=__doc__)
 except Exception as error:report=dict(passed=False,error=repr(error)[:1400],traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
 finally:
  if e:e.close()
 a.output.write_text(json.dumps(report,indent=2));print(json.dumps({k:report.get(k) for k in ('passed','error','evidence')}));return report['passed']

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('worker','managed','fixture','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();assert not a.output.exists();raise SystemExit(0 if run(a) else 1)
