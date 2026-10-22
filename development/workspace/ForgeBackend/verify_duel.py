from engine_test_client import Engine
import json,sys
scenario=sys.argv[1] if len(sys.argv)>1 else 'duel'
e=Engine(scenario)
try:
    seen=set(); declarations=0
    for step in range(1000):
        state=e.state
        if state['gameOver']:break
        if state['legalLands']:e.send('play_land',state['legalLands'][0]);continue
        if state['legalCasts']:e.send('cast_spell',state['legalCasts'][0]);continue
        r,d=e.pass_or_decision()
        if d:
            dec=e.state['decision'];kind=dec['kind'];token=dec['token'];assignments=[]
            if kind=='attackers':assignments=[{'forgeId':c['forgeId'],'targetSeat':2} for c in dec['options']]
            elif kind=='blockers':
                used=set()
                for c in dec['options']:
                    target=next((i for i in c['attackerIds'] if i not in used),None)
                    if target is not None:assignments.append({'forgeId':c['forgeId'],'attackerIds':[target]});used.add(target)
            if assignments:
                r=e.send('select_'+kind,decisionToken=token,assignments=assignments);assert r['accepted'],r
            r=e.send('submit_'+kind,decisionToken=token);assert r['accepted'],r;declarations+=1
        for c in e.state['battlefield']+e.state['graveyard']+e.state['stack']:
            if c['owner']==2:seen.add(c['name'])
        if step%100==0:print(step,e.state['turn'],e.state['phase'],e.state['life'],e.state['opponentLife'],len(e.state['hand']),flush=True)
    expected={'Plains','Savannah Lions','Yoked Ox','Oreskos Swiftclaw'} if scenario=='mixed-duel' else {'Plains','Savannah Lions'}
    e.check('Forge AI played all admitted identities',seen==expected,seen)
    e.check('human choices span repeated combats',declarations>=3,declarations)
    e.check('hidden zones contain no future card identities',all('name' not in c for c in e.state['hidden']))
    e.check('bounded game reaches Forge outcome',e.state['gameOver'])
    e.check('final state disallows further passing',not e.state['canPass'])
    print(json.dumps({'evidence':str(e.ipc),'checks':len(e.checks),'winner':e.state['winnerSeat'],'lossReason':e.state['lossReason'],'turn':e.state['turn'],'life':[e.state['life'],e.state['opponentLife']]},indent=2))
finally:e.close()
