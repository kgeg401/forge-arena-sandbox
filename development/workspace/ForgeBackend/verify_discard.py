from engine_test_client import Engine
import json
e=Engine('discard')
try:
    d=None
    for _ in range(16):
        r,d=e.pass_or_decision()
        if d:break
    dec=e.state['decision'];token=dec['token'];count=dec['count'];options=dec['options']
    e.check('Forge cleanup requests exactly two discards from nine-card hand',dec['kind']=='discard' and count==2 and len(e.state['hand'])==9)
    before=e.state
    for label,ids in [('too few',[options[0]['forgeId']]),('duplicate',[options[0]['forgeId']]*2),('unoffered',[999999,options[0]['forgeId']])]:
        r=e.send('submit_discard',decisionToken=token,assignments=[{'forgeId':i} for i in ids]);e.check(label+' rejected without changing zones',not r['accepted'] and len(e.state['hand'])==9 and not e.state['graveyard'])
    ids=[o['forgeId'] for o in options if o['forgeId']!=3][:count]
    r=e.send('submit_discard',decisionToken=token,assignments=[{'forgeId':i} for i in ids]);e.check('Forge discards the exact human choices and leaves seven cards',r['accepted'] and len(e.state['hand'])==7 and {c['forgeId'] for c in e.state['graveyard']}==set(ids))
    print(json.dumps({'evidence':str(e.ipc),'checks':e.checks},indent=2))
finally:e.close()
