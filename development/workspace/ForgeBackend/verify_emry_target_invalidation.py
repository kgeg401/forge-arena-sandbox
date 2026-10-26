"""Use a real Crypt activation to remove Emry's target before resolution."""
import json
from deck_import import parse_deck
from emry_test_client import EmryGame,EMRY,BOMB,TAP,DRAW

CRYPT="Tormod's Crypt"
deck=parse_deck("24 Island\n12 Emry, Lurker of the Loch\n8 Aether Spellbomb\n8 Ornithopter\n8 Tormod's Crypt\n",'Emry target invalidation practice')
g=EmryGame(deck_override=deck)
try:
    g.lands(3);crypt=g.ensure_hand(CRYPT);g.cast(crypt);emry=g.ensure_hand(EMRY);g.cast(emry);g.next_main();g.optional_land()
    artifacts=[c for c in g.cards('graveyard') if c['name'] in (BOMB,CRYPT,'Ornithopter')]
    if not artifacts:
        bomb=g.ensure_hand(BOMB);g.cast(bomb);g.activation(bomb,DRAW);artifacts=[g.one('graveyard',BOMB)]
    target=artifacts[0];g.activation(emry,TAP,target,False)
    g.send('activate_ability',crypt['forgeId'],abilityId=12870);d=g.s['decision']
    g.check('Crypt offers real players with collision-free references',{o['targetSeat'] for o in d['options']}=={1,2} and all(o['targetKind']=='player' and o['forgeId']<-1000000 for o in d['options']))
    g.reject('A card cannot replace a player target','select_targets',decisionToken=d['token'],assignments=[{'forgeId':emry['forgeId']}])
    own=next(o for o in d['options'] if o['targetSeat']==1)
    g.send('select_targets',decisionToken=d['token'],assignments=[{'forgeId':own['forgeId']}]);g.answer('targets')
    g.check('Crypt sacrificed as a real cost',bool(g.cards('graveyard',CRYPT)) and not g.cards('battlefield',CRYPT))
    g.check('Crypt stack ability identifies chosen player',any(a['abilityId']==12870 and a['targetSeats']==[1] for a in g.s['stackAbilities']))
    gy={c['forgeId'] for c in g.cards('graveyard')};g.step()
    for _ in range(4):
        if not g.shared_observation():break
    else:raise AssertionError('Exile ordering observation bound exceeded')
    g.check('Crypt really exiles the selected graveyard',gy<={c['forgeId'] for c in g.cards('exile')} and not g.cards('graveyard'))
    g.check('Emry is still on stack after its target leaves',any(a['abilityId']==TAP for a in g.s['stackAbilities']))
    g.resolve()
    g.check('Invalid target gives no casting permission',target['forgeId'] not in g.s['legalCasts'])
    g.reject('The exiled former target cannot be cast','cast_spell',target['forgeId'])
    g.check('Emry tap cost remains spent after fizzle',g.one('battlefield',EMRY)['tapped'])
    g.next_main()
    g.check('Empty graveyard does not offer Emry activation',not any(a['abilityId']==TAP for a in g.s['legalActivations']))
    g.reject('No-target Emry activation is rejected','activate_ability',emry['forgeId'],abilityId=TAP)
    r=dict(checks=len(g.e.checks),evidence=str(g.e.ipc),scope='Only real spells, target decisions, priority and cost payments; no direct zone edits')
    (g.e.ipc/'emry-invalidation-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
finally:g.close()
