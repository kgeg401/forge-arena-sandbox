from engine_test_client import Engine
import json
e=Engine('starter')
try:
    r=e.send('cast_spell',3);e.check('insufficient mana rejects creature',not r['accepted'])
    r=e.send('play_land',1);e.check('land enables mana source',r['accepted'])
    r=e.send('activate_mana',1);e.check('mana available',r['accepted'] and e.state['manaTotal']==1)
    r=e.send('cast_spell',3);e.check('Forge pays creature cost and retains real stack',r['accepted'] and e.state['manaTotal']==0 and len(e.state['stack'])==1)
    r=e.send('pass_priority');e.check('passing resolves creature through Forge',r['accepted'] and not e.state['stack'] and any(c['forgeId']==3 for c in e.state['battlefield']))
    r=e.send('cast_spell',3);e.check('battlefield creature cannot be recast',not r['accepted'])
    d=None
    for _ in range(20):
        r,d=e.pass_or_decision()
        if d:break
        if e.state['turn']>=2:break
    e.check('Forge skips the unavailable attack for a summoning-sick creature',d is None and e.state['turn']==2 and e.state['opponentLife']==20)
    e.check('no unsupported combat gap during normal turn progression',not e.state['fidelityGap'])
    print(json.dumps({'evidence':str(e.ipc),'checks':e.checks},indent=2))
finally:e.close()
