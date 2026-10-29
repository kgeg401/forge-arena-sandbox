"""A real Crypt exiles a dead Emry commander; exercise both owner choices."""
import json
from deck_import import parse_brawl
from emry_test_client import EmryGame,EMRY

CRYPT="Tormod's Crypt"
deck=parse_brawl("Commander\n1 Emry, Lurker of the Loch\n\nDeck\n98 Island\n1 Tormod's Crypt\n",'Emry commander exile boundary')
results=[]
for return_to_command in (False,True):
    g=EmryGame(seed=5,brawl=True,deck_override=deck)
    try:
        crypt=g.one('hand',CRYPT);g.lands(2);g.cast(crypt)
        emry=g.one('command',EMRY);g.cast(emry)
        for _ in range(100):
            d=g.s.get('decision')
            if d and d['kind']=='blockers':
                option=next(o for o in d['options'] if o['forgeId']==emry['forgeId'])
                g.send('select_blockers',decisionToken=d['token'],assignments=[{'forgeId':emry['forgeId'],'attackerIds':[option['attackerIds'][0]]}]);g.answer('blockers');break
            g.step()
        else:raise AssertionError('No real Isamaru attack to block')
        for _ in range(30):
            if (g.s.get('decision') or {}).get('kind')=='commander_return':break
            g.step()
        else:raise AssertionError('No graveyard commander choice after combat death')
        g.check('First return choice follows actual combat death',g.s['decision']['choiceZone']=='Graveyard' and bool(g.cards('graveyard',EMRY)))
        g.answer('commander_return',[{'returnToCommand':False}]);g.to_main(g.s['turn']+1)
        g.send('activate_ability',crypt['forgeId'],abilityId=12870)
        d=g.s['decision'];own=next(o for o in d['options'] if o['targetSeat']==1)
        g.send('select_targets',decisionToken=d['token'],assignments=[{'forgeId':own['forgeId']}]);g.answer('targets')
        for _ in range(20):
            if g.s.get('decision'):
                if g.shared_observation():continue
                break
            g.step()
        else:raise AssertionError('Crypt did not expose commander exile choice')
        d=g.s['decision']
        g.check('Second choice follows actual exile and uses the exile prompt',d['kind']=='commander_return' and d['choiceZone']=='Exile' and d['fromZone']=='Exile' and bool(g.cards('exile',EMRY)),d)
        g.answer('commander_return',[{'returnToCommand':return_to_command}])
        g.resolve()
        zone='command' if return_to_command else 'exile'
        commander=g.one(zone,EMRY)
        g.check('Owner chooses commander '+zone,commander['forgeId']==emry['forgeId'])
        g.check('Crypt really sacrificed and exiled itself',bool(g.cards('exile',CRYPT)) and not g.cards('battlefield',CRYPT))
        g.check('Exile does not increment command casts',commander['commandCasts']==1)
        g.check('Tax is offered only for a commander in command',commander['commanderTax']==(2 if return_to_command else 0))
        if return_to_command:
            g.lands(5);commander=g.one('command',EMRY)
            g.check('No artifact remains to discount the taxed recast',g.cost(commander)==[{'color':'Generic','count':4},{'colors':['Blue'],'count':1}])
            before=g.tapped_lands();g.cast(commander)
            g.check('Actual command recast pays five after Crypt leaves',g.tapped_lands()-before==5 and g.one('battlefield',EMRY)['commandCasts']==2)
        else:g.reject('Declined exiled commander cannot be cast','cast_spell',emry['forgeId'])
        r=dict(returnToCommand=return_to_command,checks=len(g.e.checks),evidence=str(g.e.ipc),scope='Normal shuffled Brawl; combat death, real Crypt costs/targets/exile, explicit owner choices; no state injection')
        (g.e.ipc/'emry-commander-exile-result.json').write_text(json.dumps(r,indent=2));results.append(r)
    finally:g.close()
print(json.dumps(results,indent=2))
