from engine_test_client import Engine
import json
reports=[]
for scenario in ['starter','attack-open','discard']:
    e=Engine(scenario)
    try:
        if scenario!='starter':
            for _ in range(18):
                r,d=e.pass_or_decision()
                if d:break
            e.check('controller decision pending',e.state.get('decision') is not None)
        before=(e.state['life'],e.state['opponentLife'])
        r=e.send('concede',seat=2);e.check('wrong seat cannot concede local game',not r['accepted'] and not e.state['gameOver'])
        r=e.send('concede');e.check('concede accepted by Forge',r['accepted'])
        e.check('correct terminal winner and reason',e.state['gameOver'] and e.state['winnerSeat']==2 and e.state['lossReason']=='Conceded')
        e.check('concede does not invent life loss',before==(e.state['life'],e.state['opponentLife']))
        r=e.send('concede');e.check('repeated new concession rejected',not r['accepted'])
        reports.append({'scenario':scenario,'evidence':str(e.ipc),'checks':len(e.checks)})
    finally:e.close()
print(json.dumps(reports,indent=2))
