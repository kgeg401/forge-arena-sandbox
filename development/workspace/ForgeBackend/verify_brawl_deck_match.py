"""Bounded normal Brawl match through original native handlers.
Explicit test-only choices are a robustness policy, not a competitive bot.
"""
from pathlib import Path
import os,sys,json,time,argparse
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','deck','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--seed',type=int,default=7274)
a=p.parse_args();E=a.output;E.mkdir(parents=True,exist_ok=False);os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
R=Path(json.loads(a.config.read_text())['privateRoot'])
piles={'commander':[],'cards':[]};pile='cards'
for line in a.deck.read_text().splitlines():
 line=line.strip()
 if not line or line.startswith('#'):continue
 if line=='Commander':pile='commander';continue
 if line=='Deck':pile='cards';continue
 count,name=line.split(' ',1);piles[pile].append(dict(name=name,count=int(count)))
assert len(piles['commander'])==1 and piles['commander'][0]['count']==1 and sum(c['count'] for c in piles['cards'])==99
name=a.deck.stem;d=dict(commander=piles['commander'][0]['name'],cards=piles['cards']);trace=[];e=None
local=dict(name=name,format='arena-brawl',commander=piles['commander'][0],cards=piles['cards'],experimental=True)
opponent=dict(name='Isamaru and 99 Plains: bounded robustness opponent',format='arena-brawl',commander=dict(name='Isamaru, Hound of Konda',count=1),cards=[dict(name='Plains',count=99)])
def execute(op,card=0,**fields):
 old=e.state.get('decision') or {};seen={old.get('token')} if op.startswith('submit_') else set();root=e.begin(op,card,**fields);pending=[root];deadline=time.monotonic()+35
 while time.monotonic()<deadline:
  if e.process.poll() is not None:raise RuntimeError((e.ipc/'engine.log').read_text()[-2500:])
  for key in pending[:]:
   p=e.ipc/'responses'/(key+'.json')
   if p.exists():
    r=json.loads(p.read_text());e.state=r['state'];pending.remove(key)
    if not r['accepted']:raise RuntimeError(r['reason'])
  p=e.ipc/'decision.json'
  if p.exists():
   try:d=json.loads(p.read_text())
   except (FileNotFoundError,PermissionError,json.JSONDecodeError):continue
   spec=d['state'].get('decision',{});e.state=d['state']
   if d['token'] in seen:time.sleep(.02);continue
   seen.add(d['token']);assert len(seen)<30,'Test decision budget exceeded';kind=spec['kind'];fields=dict(decisionToken=d['token']);trace.append(dict(op=op,kind=kind,type=spec.get('choice',{}).get('type')))
   if kind=='targets':
    options=spec['options'];required=spec['minTargets'] or (1 if spec['maxTargets'] and options else 0)
    cards={c['forgeId']:c for z in ['hand','battlefield','stack','graveyard','command','exile'] for c in e.state.get(z,[])}
    options=sorted(options,key=lambda o:0 if o.get('targetSeat')==2 or cards.get(o['forgeId'],{}).get('controller')==2 else 1);selected=options[:required]
    for o in selected:
     reply=e.send('select_targets',assignments=[dict(forgeId=o['forgeId'])],**fields);assert reply['accepted'],reply['reason']
    pending.append(e.begin('submit_targets',**fields))
   elif kind=='choice':
    c=spec['choice'];typ=c['type'];opts=c['options'];minimum=c.get('min',0)
    if typ=='confirm':values=[dict(accept=c.get('context') in ('life-payment','phyrexian-payment','pay-cost') or c.get('prompt','').startswith('Cancel Search?'))]
    elif typ=='number':values=[dict(number=c['min'])]
    elif typ=='partition':values=[dict(choiceId=o['choiceId'],group='top') for o in opts]
    else:
     n=c.get('count',minimum)
     if n==0 and c.get('max',0)>0 and typ in ('options','cards-zone'):n=1
     if typ in ['cards-order','abilities-order']:n=len(opts)
     values=[dict(choiceId=o['choiceId']) for o in opts[:n]]
    pending.append(e.begin('submit_choice',assignments=values,**fields))
   elif kind=='order_cards':pending.append(e.begin('submit_order_cards',assignments=[dict(forgeId=o['forgeId']) for o in spec['options']],**fields))
   elif kind=='attackers':
    reply=e.send('select_attackers',assignments=[dict(forgeId=o['forgeId'],targetSeat=o['targetSeat']) for o in spec['options']],**fields);assert reply['accepted'],reply['reason'];pending.append(e.begin('submit_attackers',**fields))
   elif kind=='blockers':pending.append(e.begin('submit_blockers',**fields))
   elif kind=='mulligan':pending.append(e.begin('submit_mulligan',assignments=[dict(keep=True)],**fields))
   elif kind=='starting_player':pending.append(e.begin('submit_starting_player',assignments=[dict(startingSeat=1)],**fields))
   elif kind=='commander_return':pending.append(e.begin('submit_commander_return',assignments=[dict(returnToCommand=True)],**fields))
   elif kind in ['discard','mulligan_bottom']:pending.append(e.begin('submit_'+kind,assignments=[dict(forgeId=o['forgeId']) for o in spec['options'][:spec['count']]],**fields))
   elif kind=='assign_damage':pending.append(e.begin('submit_assign_damage',assignments=[dict(forgeId=o['forgeId'],amount=o['assignedDamage']) for o in spec['options']],**fields))
   elif kind=='legend_rule':pending.append(e.begin('submit_legend_rule',forgeId=spec['options'][0]['forgeId'],**fields))
   else:raise RuntimeError('Unhandled test decision '+kind)
  elif not pending:
   e.state=json.loads((e.ipc/'state.json').read_text());assert not e.state['fidelityGap'],e.state['fidelityGap'];return
  time.sleep(.02)
 raise TimeoutError('Action did not reach a stable boundary')


try:
 e=NativeEngine('brawl-duel',worker=a.worker,managed=a.managed,fixture=a.fixture,localDeck=local,opponentDeck=opponent,randomSeed=a.seed,startingPlayerPolicy='local-first')
 if e.state.get('decision'):
  dec=e.state['decision'];assert dec['kind']=='mulligan',dec;execute('submit_mulligan',decisionToken=dec['token'],assignments=[dict(keep=True)])
 activated=set();rejected=set();commands=0;end=time.monotonic()+480
 for step in range(1800):
  if e.state['gameOver']:break
  assert time.monotonic()<end,'Bounded match elapsed-time budget reached'
  state=e.state;turn=state['turn'];key=(turn,state['phase'],len(state['battlefield']),len(state['hand']),len(state['stack']))
  command=None
  if state['legalLands']:
   card=next((c for c in state['legalLands'] if (key,'land',c) not in rejected),None)
   if card:command=('play_land',card,{})
  if command is None and state['legalCasts']:
   card=next((c['forgeId'] for c in state['command'] if c['owner']==1 and c['name']==d['commander'] and c['forgeId'] in state['legalCasts'] and (key,'cast',c['forgeId']) not in rejected),None) or next((c for c in state['legalCasts'] if (key,'cast',c) not in rejected),None)
   if card:command=('cast_spell',card,{})
  if command is None and state['phase']=='MAIN2' and not state['stack'] and not state['stackAbilities']:
   a=next((a for a in state['legalActivations'] if (turn,a['forgeId'],a['abilityId']) not in activated),None)
   if a:activated.add((turn,a['forgeId'],a['abilityId']));command=('activate_ability',a['forgeId'],dict(abilityId=a['abilityId']))
  if command is None:command=('pass_priority',0,{})
  try:execute(command[0],command[1],**command[2]);commands+=1
  except RuntimeError as ex:
   # A declined original payment is an accepted test-policy outcome, not a crash.
   if (str(ex).startswith('Native request rejected: Forge rejected action: Forge human') or str(ex).startswith('Native request rejected: Forge rejected action: Human play was canceled')) and not e.state['fidelityGap']:
    rejected.add((key,'land' if command[0]=='play_land' else 'cast',command[1]));continue
   raise
 else:raise AssertionError('Bounded match action budget reached')
 assert e.state['gameOver'] and not e.state['fidelityGap'];result=dict(deck=name,passed=True,turn=e.state['turn'],winnerSeat=e.state['winnerSeat'],commands=commands,coverage='One exact Arena deck, one seed, normally started native-handler match in explicit full-control test mode; automatic pacing tested separately',evidence=str(e.ipc))
except BaseException as ex:result=dict(deck=name,passed=False,error=str(ex)[-2500:],evidence=str(e.ipc) if e else '')
finally:
 if e:(e.ipc/'test-policy-trace.json').write_text(json.dumps(trace,indent=2));e.close()
(E/'report.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)

raise SystemExit(0 if result["passed"] else 1)
