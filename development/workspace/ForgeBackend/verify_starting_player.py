from engine_test_client import Engine
import json

for seat in (1,2,0):
    e=Engine('opening-duel',randomSeed=1)
    try:
        d=e.state['decision'];token=d['token']
        e.check('local coin winner receives real starting-player callback',d['kind']=='starting_player' and e.state['stage']=='BeforeMulligan' and len(e.state['hand'])==0)
        e.check('both complete libraries exist before opening draw',len(e.state['hidden'])==120 and all(c['zone']=='Library' for c in e.state['hidden']))
        for label,fields in [('unoffered seat',{'assignments':[{'startingSeat':3}]}),('wrong player',{'seat':2,'assignments':[{'startingSeat':1}]}),('stale token',{'decisionToken':'stale','assignments':[{'startingSeat':1}]})]:
            r=e.send('submit_starting_player',decisionToken=token,**{k:v for k,v in fields.items() if k!='decisionToken'}) if 'decisionToken' not in fields else e.send('submit_starting_player',**fields)
            e.check('reject '+label,not r['accepted'] and e.state['decision']['token']==token)
        if seat==0:
            r=e.send('concede');e.check('concession during play/draw settles before hands are drawn',r['accepted'] and e.state['gameOver'] and not e.state['hand'])
        else:
            r=e.send('submit_starting_player',decisionToken=token,assignments=[{'startingSeat':seat}])
            e.check('starting seat selected through Forge callback',r['accepted'] and e.state['startingSeat']==seat and e.state['decision']['kind']=='mulligan' and len(e.state['hand'])==7)
            d=e.state['decision'];r=e.send('submit_mulligan',decisionToken=d['token'],assignments=[{'keep':True}]);assert r['accepted'],r
            for _ in range(100):
                s=e.state
                if s['activeSeat']==1 and s['phase']=='MAIN1':break
                r,d=e.pass_or_decision();assert not d,(d,e.state)
            e.check('first local main has correct normal draw',e.state['activeSeat']==1 and e.state['phase']=='MAIN1' and e.state['turn']==(1 if seat==1 else 2) and len(e.state['hand'])==(7 if seat==1 else 8))
            e.send('concede')
        print(json.dumps({'choice':seat,'checks':len(e.checks),'evidence':str(e.ipc)}),flush=True)
    finally:e.close()
