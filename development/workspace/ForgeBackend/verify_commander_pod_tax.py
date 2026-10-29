"""Normal four-player cast, self-bounce, command return and taxed recast."""
from pathlib import Path
import argparse,os,json,time,traceback
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--seed',type=int,default=14)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[];report={}
try:
 local=dict(name='Pod commander tax test',format='commander-40',commander=dict(name='Emry, Lurker of the Loch',count=1),cards=[dict(name='Island',count=98),dict(name='Unsummon',count=1)],experimental=True)
 bot={**local,'commander':dict(name='Derevi, Empyrial Tactician',count=1),'cards':[dict(name='Plains',count=99)]}
 e=NativeEngine('commander-pod',worker=a.worker,managed=a.managed,fixture=a.fixture,localDeck=local,opponentDecks=[bot]*3,randomSeed=a.seed,startingPlayerPolicy='local-first')
 assert any(c['name']=='Unsummon' for c in e.state['hand']),'Seed must normally shuffle Unsummon into the opening hand'
 commander=next(c['forgeId'] for c in e.state['command'] if c['owner']==1)
 execute(e,trace,'submit_mulligan',decisionToken=e.state['decision']['token'],assignments=[dict(keep=True)])
 deadline=time.monotonic()+180;bounced=False;return_record=None
 for step in range(700):
  s=e.state;assert time.monotonic()<deadline,'Commander recast exceeded time budget'
  command=next((c for c in s['command'] if c['forgeId']==commander),None)
  permanent=next((c for c in s['battlefield'] if c['forgeId']==commander),None)
  if permanent and permanent.get('commandCasts')==2:break
  if bounced and command and return_record is None:
   assert command['commandCasts']==1 and command['commanderTax']==2,command
   assert any(t.get('kind')=='commander_return' for t in trace),'The actual command-zone choice was not exercised'
   return_record=dict(turn=s['turn'],tax=command['commanderTax'],nativeState=e.native_status['nativeStateId'])
  if s['legalLands']:execute(e,trace,'play_land',s['legalLands'][0],_attack_seat={commander:0})
  elif permanent and not bounced:
   spell=next(c['forgeId'] for c in s['hand'] if c['name']=='Unsummon')
   if spell in s['legalCasts']:execute(e,trace,'cast_spell',spell,_target_seat=1,_attack_seat={commander:0});bounced=True
   else:execute(e,trace,'pass_priority',_attack_seat={commander:0})
  elif commander in s['legalCasts']:execute(e,trace,'cast_spell',commander,_attack_seat={commander:0})
  else:execute(e,trace,'pass_priority',_attack_seat={commander:0})
 else:raise AssertionError('Commander recast action budget exceeded')
 assert return_record is not None and bounced
 tapped=[c for c in s['battlefield'] if c['controller']==1 and c['name']=='Island' and c['tapped']]
 assert len(tapped)==5,('An artifact-free Emry recast must pay 2U plus two generic tax',len(tapped))
 assert all(p['life']==40 and not p['lost'] for p in s['players'])
 report=dict(passed=True,turn=s['turn'],returnToCommand=return_record,secondCastCount=permanent['commandCasts'],secondCastTappedIslands=len(tapped),nativeState=e.native_status['nativeStateId'],evidence=str(e.ipc))
except BaseException as error:report=dict(passed=False,error=repr(error),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
finally:
 if e:e.close()
 (a.output/'trace.json').write_text(json.dumps(trace,indent=2));(a.output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
raise SystemExit(0 if report.get('passed') else 1)
