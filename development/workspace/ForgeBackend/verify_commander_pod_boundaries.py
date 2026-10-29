"""Native London mulligans, first-player draw, and graceful local elimination."""
from pathlib import Path
import argparse,os,json,time,traceback
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
a.output.mkdir(parents=True,exist_ok=False);reports=[]
deck=dict(name='Pod boundary validation',format='commander-40',commander=dict(name='Isamaru, Hound of Konda',count=1),cards=[dict(name='Plains',count=99)],experimental=True)
def start(opponent=None,local=None,seed=7274):return NativeEngine('commander-pod',worker=a.worker,managed=a.managed,fixture=a.fixture,localDeck=local or deck,opponentDecks=[opponent or deck]*3,randomSeed=seed,startingPlayerPolicy='local-first')
for case in ['two-mulligans-and-first-draw','concede-opening-hand','concede-main-phase','natural-human-elimination']:
 e=None;trace=[]
 try:
  if case=='natural-human-elimination':
   # Real life payment reaches zero without relying on AI threat assessment
   # to choose a particular defender. No life total or intermediate state is
   # injected. Seed 14 normally shuffles Necropotence into the opening hand.
   local={**deck,'commander':dict(name='Chatterfang, Squirrel General',count=1),'cards':[dict(name='Swamp',count=98),dict(name='Necropotence',count=1)]}
   opponent={**deck,'commander':dict(name='Derevi, Empyrial Tactician',count=1)}
   e=start(opponent,local,14)
  else:e=start()
  if case=='two-mulligans-and-first-draw':
   for count in [1,2]:
    d=e.state['decision'];assert d['kind']=='mulligan',d
    r=e.send('submit_mulligan',decisionToken=d['token'],assignments=[dict(keep=False)]);assert r['accepted'],r['reason']
    assert len(e.state['hand'])==7 and e.state['mulligans']==count
   d=e.state['decision'];r=e.send('submit_mulligan',decisionToken=d['token'],assignments=[dict(keep=True)]);assert r['accepted'],r['reason']
   d=e.state['decision'];assert d['kind']=='mulligan_bottom' and d['count']==1,d
   execute(e,trace,'submit_mulligan_bottom',decisionToken=d['token'],assignments=[dict(forgeId=d['options'][0]['forgeId'])])
   assert len(e.state['hand'])==6,(e.state['phase'],len(e.state['hand']))
   for _ in range(16):
    if e.state['phase']=='MAIN1':break
    execute(e,trace,'pass_priority')
   assert e.state['activeSeat']==1 and e.state['turn']==1 and len(e.state['hand'])==7,'Multiplayer first player must draw'
   assert all(p['kept'] for p in e.state['players'])
   reports.append(dict(case=case,passed=True,keptCards=6,firstTurnHand=7,freeMulligans=1,evidence=str(e.ipc)))
  elif case=='natural-human-elimination':
   execute(e,trace,'submit_mulligan',decisionToken=e.state['decision']['token'],assignments=[dict(keep=True)])
   deadline=time.monotonic()+180;source=0;payments=0
   for _ in range(600):
    assert time.monotonic()<deadline,'Natural elimination test exceeded time budget'
    if e.state['localLost']:break
    card=next((c for z in ['hand','battlefield','stack'] for c in e.state[z] if c['owner']==1 and c['name']=='Necropotence'),None)
    if card:source=card['forgeId']
    offer=next((o for o in e.state['legalActivations'] if o['forgeId']==source),None)
    if offer:
     execute(e,trace,'activate_ability',source,abilityId=offer['abilityId']);payments+=1
    elif e.state['legalLands']:execute(e,trace,'play_land',e.state['legalLands'][0])
    elif source in e.state['legalCasts']:execute(e,trace,'cast_spell',source)
    else:execute(e,trace,'pass_priority')
   assert e.state['localLost'] and not e.state['gameOver'] and e.state['winnerSeat']==0
   assert e.state['life']<=0 or next(p for p in e.state['players'] if p['seat']==1)['lossReason']=='CommanderDamage'
   assert not e.state['canPass'] and not e.state.get('decision')
   assert payments==40,payments
   reports.append(dict(case=case,passed=True,turn=e.state['turn'],life=e.state['life'],realLifePayments=payments,lossReason=next(p for p in e.state['players'] if p['seat']==1)['lossReason'],evidence=str(e.ipc)))
  else:
   if case=='concede-main-phase':
    execute(e,trace,'submit_mulligan',decisionToken=e.state['decision']['token'],assignments=[dict(keep=True)])
    for _ in range(16):
     if e.state['phase']=='MAIN1':break
     execute(e,trace,'pass_priority')
   started=time.monotonic();r=e.send('concede');elapsed=time.monotonic()-started
   assert r['accepted'] and e.state['localLost'] and not e.state['gameOver'] and e.state['winnerSeat']==0
   assert not e.state['canPass'] and not e.state.get('decision')
   assert all(not p['lost'] for p in e.state['players'] if p['seat']!=1)
   assert elapsed<5,elapsed
   reports.append(dict(case=case,passed=True,seconds=round(elapsed,3),noFabricatedWinner=True,evidence=str(e.ipc)))
 except BaseException as ex:reports.append(dict(case=case,passed=False,error=str(ex),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None))
 finally:
  if e:e.close()
  print(json.dumps(reports[-1]),flush=True)
report=dict(passed=all(r['passed'] for r in reports),cases=reports);(a.output/'report.json').write_text(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
