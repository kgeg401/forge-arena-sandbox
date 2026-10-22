"""Normally registered Emry Brawl: actual discount, combat death and taxed recast."""
import json
from emry_test_client import EmryGame,EMRY,ORNITHOPTER

g=EmryGame(seed=5,brawl=True)
try:
    g.check('Both Brawl players start at25',g.s['life']==25 and g.s['opponentLife']==25)
    g.check('One registered Emry commander',len(g.cards('command',EMRY))==1)
    g.land();g.cast(g.one('hand',ORNITHOPTER))
    g.next_main();g.land();emry=g.one('command',EMRY)
    g.check('First command cast with one artifact costs1U',g.cost(emry)==[{'color':'Generic','count':1},{'color':'Blue','count':1}])
    before=g.tapped_lands();g.cast(emry)
    g.check('Actual first command payment is two lands',g.tapped_lands()-before==2)
    g.check('First command cast history is1',g.one('battlefield',EMRY)['commandCasts']==1)
    for _ in range(100):
        d=g.s.get('decision')
        if d and d['kind']=='blockers':
            option=next(o for o in d['options'] if o['forgeId']==emry['forgeId'])
            g.send('select_blockers',decisionToken=d['token'],assignments=[{'forgeId':emry['forgeId'],'attackerIds':[option['attackerIds'][0]]}]);g.answer('blockers');break
        g.step()
    else:raise AssertionError('No real Isamaru combat block was offered')
    for _ in range(30):
        d=g.s.get('decision')
        if d and d['kind']=='commander_return':break
        g.step()
    else:raise AssertionError('Combat death did not offer commander return')
    g.check('Dead Emry is really in graveyard before decision',bool(g.cards('graveyard',EMRY)))
    g.answer('commander_return',[{'returnToCommand':True}])
    commander=g.one('command',EMRY)
    g.check('Returned Emry accumulates2tax',commander['commanderTax']==2 and commander['commandCasts']==1)
    g.to_main(5);g.optional_land()
    g.reject('Three lands cannot pay discounted taxed cost4','cast_spell',emry['forgeId'])
    g.next_main();g.optional_land();commander=g.one('command',EMRY)
    g.check('Affinity applies after adding commander tax',g.cost(commander)==[{'color':'Generic','count':3},{'color':'Blue','count':1}])
    before=g.tapped_lands();g.cast(commander)
    g.check('Actual discounted taxed recast pays4lands',g.tapped_lands()-before==4)
    g.check('Recast commander history becomes2',g.one('battlefield',EMRY)['commandCasts']==2)
    g.check('Artifact remains a real counted permanent',len(g.cards('battlefield',ORNITHOPTER))==1)
    result=dict(checks=len(g.e.checks),turn=g.s['turn'],evidence=str(g.e.ipc),scope='Real 100-card registration, shuffle, combat and command choices; input only')
    (g.e.ipc/'emry-brawl-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
finally:g.close()
