"""Four authoritative Commander seats through the shipped Arena parser/handlers.

The full-match fixture intentionally gives the bots only Plains for a multicolor
commander. This bounds combat/elimination tests; it is not an AI-strength test.
"""
from pathlib import Path
import argparse,os,json,time,traceback
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--full-match',action='store_true')
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[];report={}
def deck(commander):return dict(name='Pod rules validation',format='commander-40',commander=dict(name=commander,count=1),cards=[dict(name='Plains',count=99)],experimental=True)
try:
 local=deck('Isamaru, Hound of Konda');bot=deck('Derevi, Empyrial Tactician')
 e=NativeEngine('commander-pod',worker=a.worker,managed=a.managed,fixture=a.fixture,localDeck=local,opponentDecks=[bot,bot,bot],randomSeed=7274,startingPlayerPolicy='local-first')
 assert [p['seat'] for p in e.state['players']]==[1,2,3,4]
 assert all(p['life']==p['startingLifeTotal']==40 for p in e.state['players'])
 assert sorted(c['owner'] for c in e.state['command'])==[1,2,3,4]
 assert all(p['commanders'] for p in e.state['players'])
 assert '40 starting life' in e.native_status['podDetails']
 commander=next(c['forgeId'] for c in e.state['command'] if c['owner']==1)
 execute(e,trace,'submit_mulligan',decisionToken=e.state['decision']['token'],assignments=[dict(keep=False)])
 assert len(e.state['hand'])==7 and e.state['freeMulliganCount']==1
 seen=set();eliminated=[];attacks=set();deadline=time.monotonic()+(1200 if a.full_match else 150)
 for i in range(2200 if a.full_match else 180):
  assert time.monotonic()<deadline,'Pod test exceeded time budget'
  assert not e.state['fidelityGap'],e.state['fidelityGap']
  assert [p['seat'] for p in e.state['players']]==[1,2,3,4],'Seat identities changed after elimination'
  seen.add(e.state['activeSeat'])
  for player in e.state['players']:
   if player['lost'] and player['seat'] not in eliminated:
    eliminated.append(player['seat']);print(json.dumps(dict(eliminated=player,turn=e.state['turn'])),flush=True)
  if e.state['gameOver'] or not a.full_match and e.state['turn']>=5 and e.state['activeSeat']==1:break
  target=next((seat for seat in [3,4,2] if not next(p for p in e.state['players'] if p['seat']==seat)['lost']),2)
  if e.state['legalLands']:execute(e,trace,'play_land',e.state['legalLands'][0],_attack_seat=target)
  elif e.state['legalCasts']:execute(e,trace,'cast_spell',e.state['legalCasts'][0],_attack_seat=target)
  else:execute(e,trace,'pass_priority',_attack_seat=target)
 else:raise AssertionError('Pod test exceeded action budget')
 assert seen=={1,2,3,4},seen
 if a.full_match:
  assert e.state['gameOver'] and e.state['winnerSeat']==1,e.state.get('lossReason')
  assert eliminated==[3,4,2],eliminated
  for seat in [3,4,2]:
   player=next(p for p in e.state['players'] if p['seat']==seat)
   assert player['lossReason']=='CommanderDamage' and player['life']>0,player
   damage=sum(event['amount'] for event in e.state['events'] if event['kind']=='damage' and event.get('combat') and event.get('targetSeat')==seat and event['sourceForgeId']==commander)
   assert damage>=21,(seat,damage)
  assert e.native_status['podDetails'].count('22/21')==3,e.native_status['podDetails']
  assert 'Commander #' not in e.native_status['podDetails'],e.native_status['podDetails']
 report=dict(passed=True,fullMatch=a.full_match,seenSeats=sorted(seen),eliminationOrder=eliminated,turn=e.state['turn'],winnerSeat=e.state['winnerSeat'],nativeState=e.native_status['nativeStateId'],evidence=str(e.ipc),players=e.state['players'],podDetails=e.native_status['podDetails'])
except BaseException as ex:report=dict(passed=False,error=str(ex),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
finally:
 if e:e.close()
 (a.output/'trace.json').write_text(json.dumps(trace,indent=2));(a.output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
raise SystemExit(0 if report.get('passed') else 1)
