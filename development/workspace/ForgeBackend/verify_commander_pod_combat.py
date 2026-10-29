"""Split one human combat across two opponents through native attack handlers."""
from pathlib import Path
import argparse,os,json,time,traceback
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--seed',type=int,default=5)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[];report={}
try:
 local=dict(name='Pod split attack test',format='commander-40',commander=dict(name='Isamaru, Hound of Konda',count=1),cards=[dict(name='Plains',count=98),dict(name='Savannah Lions',count=1)],experimental=True)
 bot={**local,'commander':dict(name='Derevi, Empyrial Tactician',count=1),'cards':[dict(name='Plains',count=99)]}
 e=NativeEngine('commander-pod',worker=a.worker,managed=a.managed,fixture=a.fixture,localDeck=local,opponentDecks=[bot]*3,randomSeed=a.seed,startingPlayerPolicy='local-first')
 assert any(c['name']=='Savannah Lions' for c in e.state['hand']),'Seed must normally shuffle Savannah Lions into the opening hand'
 execute(e,trace,'submit_mulligan',decisionToken=e.state['decision']['token'],assignments=[dict(keep=True)])
 deadline=time.monotonic()+180
 for step in range(600):
  s=e.state;assert time.monotonic()<deadline,'Split combat exceeded time budget'
  creatures={c['name']:c for c in s['battlefield'] if c['controller']==1 and c['name'] in ['Isamaru, Hound of Konda','Savannah Lions']}
  ready=len(creatures)==2 and all(not c['sick'] for c in creatures.values())
  targets={c['forgeId']:0 for c in creatures.values()}
  if ready:targets={creatures['Isamaru, Hound of Konda']['forgeId']:3,creatures['Savannah Lions']['forgeId']:4}
  if next(p for p in s['players'] if p['seat']==3)['life']==38 and next(p for p in s['players'] if p['seat']==4)['life']==38:break
  if s['legalLands']:execute(e,trace,'play_land',s['legalLands'][0],_attack_seat=targets)
  elif s['legalCasts']:execute(e,trace,'cast_spell',s['legalCasts'][0],_attack_seat=targets)
  else:execute(e,trace,'pass_priority',_attack_seat=targets)
 else:raise AssertionError('Split combat action budget exceeded')
 assert next(p for p in s['players'] if p['seat']==2)['life']==40,'Unattacked player took damage'
 split=next(t['assignments'] for t in trace if t.get('kind')=='attacker-assignments' and {x['targetSeat'] for x in t['assignments']}=={3,4})
 commander=creatures['Isamaru, Hound of Konda']['forgeId']
 assert any(d['seat']==3 and d['commanderForgeId']==commander and d['amount']==2 for d in s['commanderDamage'])
 assert not any(d['seat']==4 and d['commanderForgeId']==commander for d in s['commanderDamage'])
 report=dict(passed=True,turn=s['turn'],assignments=split,lifeBySeat={p['seat']:p['life'] for p in s['players']},commanderDamage=s['commanderDamage'],nativeState=e.native_status['nativeStateId'],evidence=str(e.ipc))
except BaseException as error:report=dict(passed=False,error=repr(error),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
finally:
 if e:e.close()
 (a.output/'trace.json').write_text(json.dumps(trace,indent=2));(a.output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
raise SystemExit(0 if report.get('passed') else 1)
