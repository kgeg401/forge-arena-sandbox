"""Real Forge casts and trigger resolution; no injected intermediate token state."""
from engine_test_client import Engine
import json

e=Engine('hare-chain')
try:
    for index in range(3):
        hare=next(c for c in e.state['hand'] if c['name']=='Hare Apparent')
        r=e.send('cast_spell',hare['forgeId']);e.check('Hare casting cost paid '+str(index),r['accepted'])
        e.check('Hare is the actual creature spell on stack '+str(index),e.state['stackOrder']==[hare['forgeId']])
        e.pass_or_decision()
        e.check('ETB trigger has independent identity '+str(index),len(e.state['stackAbilities'])==1 and e.state['stackAbilities'][0]['sourceForgeId']==hare['forgeId'] and e.state['stackAbilities'][0]['triggered'])
        e.pass_or_decision()
        tokens=[c for c in e.state['battlefield'] if c['token']]
        e.check('Sequential Hare creates 0 then 1 then 2 new Rabbits '+str(index),len(tokens)==index*(index+1)//2)
        e.check('Real token stats, ownership, color and sickness '+str(index),all(c['power']==1 and c['toughness']==1 and c['owner']==1 and c['controller']==1 and c['colorMask']==1 and c['sick'] for c in tokens))
        e.check('No extra stack ability or fidelity gap '+str(index),not e.state['stackAbilities'] and not e.state['fidelityGap'])
    bounced=tokens[0]['forgeId'];spell=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Unsummon')
    e.check('An unused blue source keeps the token-removal test legal',spell in e.state['legalCasts'])
    parent=e.begin('cast_spell',spell);p=e.wait_json(e.ipc/'decision.json');e.state=p['state'];d=e.state['decision'];fields={'decisionToken':d['token']}
    e.check('Real Rabbit token is an offered creature target',bounced in {v['forgeId'] for v in d['options']})
    e.send('select_targets',assignments=[{'forgeId':bounced}],**fields);e.send('submit_targets',**fields);e.finish(parent);e.pass_or_decision()
    e.check('Bounced token ceases to exist after real Forge state-based action',not any(c['forgeId']==bounced for k in ('hand','battlefield','graveyard','hidden') for c in e.state[k]))
    e.check('Other two Rabbit tokens and all Hares survive',sum(c['token'] for c in e.state['battlefield'])==2 and sum(c['name']=='Hare Apparent' for c in e.state['battlefield'])==3)
    print(json.dumps({'evidence':str(e.ipc),'checks':len(e.checks),'createdTokens':3,'tokensAfterBounce':2},indent=2))
finally:e.close()
