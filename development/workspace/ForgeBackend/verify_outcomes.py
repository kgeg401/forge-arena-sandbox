from engine_test_client import Engine
import json
reports=[]
for scenario,winner in [('lethal-win',1),('defend-lethal',2)]:
    e=Engine(scenario)
    try:
        for step in range(24):
            if e.state['gameOver']:break
            r,d=e.pass_or_decision()
            if d:
                dec=e.state['decision'];token=dec['token'];kind=dec['kind']
                if kind=='attackers':
                    r=e.send('select_attackers',decisionToken=token,assignments=[{'forgeId':dec['options'][0]['forgeId'],'targetSeat':2}]);assert r['accepted'],r
                r=e.send('submit_'+kind,decisionToken=token);assert r['accepted'],r
        e.check('Forge ended game through lethal combat',e.state['gameOver'])
        e.check('Forge outcome identifies correct winner',e.state['winnerSeat']==winner)
        e.check('life loss reason comes from Forge',e.state['lossReason']=='LifeReachedZero',e.state['lossReason'])
        r=e.send('pass_priority');e.check('ended game rejects further progression',not r['accepted'])
        reports.append({'scenario':scenario,'evidence':str(e.ipc),'checks':e.checks,'winner':e.state['winnerSeat'],'lossReason':e.state['lossReason']})
    finally:e.close()
print(json.dumps(reports,indent=2))
