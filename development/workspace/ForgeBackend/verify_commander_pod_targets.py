"""Player targets and private-zone changes at seats three and four, through GRE."""
from pathlib import Path
import argparse,os,json,time,traceback
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--seed',type=int,default=14)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[];report={}
def deck(commander,land):return dict(name='Pod target validation',format='commander-40',commander=dict(name=commander,count=1),cards=[dict(name=land,count=99)],experimental=True)
try:
 local=deck('Emry, Lurker of the Loch','Island');local['cards']=[dict(name='Island',count=98),dict(name='Jace, Wielder of Mysteries',count=1)];bot=deck('Derevi, Empyrial Tactician','Plains')
 e=NativeEngine('commander-pod',worker=a.worker,managed=a.managed,fixture=a.fixture,localDeck=local,opponentDecks=[bot,bot,bot],randomSeed=a.seed,startingPlayerPolicy='local-first')
 execute(e,trace,'submit_mulligan',decisionToken=e.state['decision']['token'],assignments=[dict(keep=True)])
 commander=0;deadline=time.monotonic()+360;cases=[]
 for target in [3,4]:
  for i in range(1800):
   assert time.monotonic()<deadline,'Player target test exceeded time budget'
   assert not e.state['fidelityGap'],e.state['fidelityGap']
   source=next((c for zone in ['hand','battlefield','stack'] for c in e.state[zone] if c['owner']==1 and c['name']=='Jace, Wielder of Mysteries'),None)
   if source:commander=source['forgeId']
   offer=next((o for o in e.state['legalActivations'] if o['forgeId']==commander and o['api']=='Mill'),None)
   if offer:break
   if e.state['legalLands']:execute(e,trace,'play_land',e.state['legalLands'][0])
   elif commander in e.state['legalCasts']:execute(e,trace,'cast_spell',commander)
   else:execute(e,trace,'pass_priority')
  else:raise AssertionError('Jace mill activation was not offered')
  before={seat:len([c for c in e.state['graveyard'] if c['owner']==seat]) for seat in [2,3,4]};hand=len(e.state['hand'])
  execute(e,trace,'activate_ability',commander,abilityId=offer['abilityId'],_target_seat=target)
  for i in range(24):
   if len([c for c in e.state['graveyard'] if c['owner']==target])==before[target]+2:break
   execute(e,trace,'pass_priority',_target_seat=target)
  assert len([c for c in e.state['graveyard'] if c['owner']==target])==before[target]+2
  assert all(len([c for c in e.state['graveyard'] if c['owner']==seat])==before[seat] for seat in [2,3,4] if seat!=target)
  assert len(e.state['hand'])==hand+1,'Jace did not draw for the local player'
  cases.append(dict(targetSeat=target,milled=2,localDraw=1,nativeState=e.native_status['nativeStateId']))
 report=dict(passed=True,cases=cases,evidence=str(e.ipc),turn=e.state['turn'])
except BaseException as ex:report=dict(passed=False,error=str(ex),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
finally:
 if e:e.close()
 (a.output/'trace.json').write_text(json.dumps(trace,indent=2));(a.output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
raise SystemExit(0 if report.get('passed') else 1)
