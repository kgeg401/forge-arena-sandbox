from engine_test_client import Engine
import json
all_reports=[]
for scenario in ['attack-blocked','defend']:
 e=Engine(scenario)
 try:
  chosen=False
  for i in range(32):
   r,d=e.pass_or_decision()
   if d:
    dec=e.state['decision'];kind=dec['kind'];token=dec['token'];opt=dec['options'][0]
    if kind=='attackers':assignment={'forgeId':opt['forgeId'],'targetSeat':2}
    else:assignment={'forgeId':opt['forgeId'],'attackerIds':[opt['attackerIds'][0]]}
    r=e.send('select_'+kind,decisionToken=token,assignments=[assignment]);e.check('valid '+kind+' selection',r['accepted'])
    r=e.send('submit_'+kind,decisionToken=token);e.check('Forge accepts submitted '+kind,r['accepted']);chosen=True
   if len(e.state['graveyard'])>=2:break
  e.check('controller decision reached',chosen)
  e.check('Forge moves both 2/1 creatures to their owners graveyards',len(e.state['graveyard'])==2)
  e.check('blocked damage leaves both players at 20',e.state['life']==20 and e.state['opponentLife']==20)
  e.check('damage events captured from engine',len(e.state['events'])>=2)
  all_reports.append({'scenario':scenario,'evidence':str(e.ipc),'checks':len(e.checks),'state':e.state})
 finally:e.close()
print(json.dumps(all_reports,indent=2))
