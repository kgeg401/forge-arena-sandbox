"""Explicit bounded test-only decision policy; never used by the player client."""
import json,time
def execute(e,trace,op,card=0,_attack_seat=None,_target_seat=2,_choice_policy=None,**fields):
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
    options=sorted(options,key=lambda o:0 if o.get('targetSeat')==_target_seat or cards.get(o['forgeId'],{}).get('controller')==_target_seat else 1);selected=options[:required]
    trace.append(dict(kind='target-assignments',selected=selected))
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
    if _choice_policy is not None:
     selected=_choice_policy(c,e.state)
     if selected is not None:values=selected
    trace.append(dict(kind='choice-assignments',prompt=c.get('prompt'),selected=values))
    pending.append(e.begin('submit_choice',assignments=values,**fields))
   elif kind=='order_cards':pending.append(e.begin('submit_order_cards',assignments=[dict(forgeId=o['forgeId']) for o in spec['options']],**fields))
   elif kind=='attackers':
    assignments=[]
    for o in spec['options']:
     seat=_attack_seat.get(o['forgeId'],0) if isinstance(_attack_seat,dict) else _attack_seat
     if isinstance(_attack_seat,dict) and seat==0:assignments.append(dict(forgeId=o['forgeId'],targetSeat=0));continue
     recipient=next((r for r in o.get('attackTargets',[]) if r['targetSeat']==seat and not r.get('targetForgeId')),None) if seat else None
     if isinstance(_attack_seat,dict):assert recipient is not None,'Requested split-attack recipient was not offered by Forge'
     assignments.append(dict(forgeId=o['forgeId'],targetSeat=recipient['targetSeat'] if recipient else o['targetSeat']))
    trace.append(dict(kind='attacker-assignments',assignments=assignments))
    reply=e.send('select_attackers',assignments=assignments,**fields);assert reply['accepted'],reply['reason'];pending.append(e.begin('submit_attackers',**fields))
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
