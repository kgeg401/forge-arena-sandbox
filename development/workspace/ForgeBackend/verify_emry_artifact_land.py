"""Artifact-land affinity, real blue mana, and a legal but uncastable land target."""
import json
from deck_import import parse_deck
from emry_test_client import EmryGame,EMRY,TAP

SEAT='Seat of the Synod'
deck=parse_deck('8 Island\n16 Seat of the Synod\n8 Emry, Lurker of the Loch\n8 Ornithopter\n','Artifact land boundary practice')
g=EmryGame(deck_override=deck)
try:
    seat=g.ensure_hand(SEAT);g.send('play_land',seat['forgeId']);g.send('activate_mana',seat['forgeId'])
    g.check('Seat produces actual blue mana',g.s['manaTotal']==1 and g.s['mana'][0]['color']==2 and g.s['mana'][0]['sourceForgeId']==seat['forgeId'])
    g.next_main();nextseat=g.ensure_hand(SEAT);g.send('play_land',nextseat['forgeId']);emry=g.ensure_hand(EMRY)
    g.check('Two artifact lands reduce Emry generic cost to zero',g.cost(emry)==[{'color':'Blue','count':1}])
    before=sum(c['tapped'] for c in g.cards('battlefield'));g.cast(emry)
    g.check('Blue cost remains and is actually paid',sum(c['tapped'] for c in g.cards('battlefield'))-before==1)
    for _ in range(3):
        if g.cards('graveyard',SEAT):break
        g.next_main();g.optional_land();copy=g.ensure_hand(EMRY);g.cast(copy,False)
        for _ in range(20):
            if not g.s['stack'] and not g.s['stackAbilities'] and not g.s.get('decision'):break
            if g.s.get('decision'):
                assert g.s['decision']['kind']=='legend_rule';g.answer('legend_rule',[{'forgeId':emry['forgeId']}])
            else:g.step()
    land=g.one('graveyard',SEAT);g.next_main()
    g.send('activate_ability',emry['forgeId'],abilityId=TAP);d=g.s['decision']
    g.check('An artifact land is a legal Emry target',any(o['forgeId']==land['forgeId'] for o in d['options']))
    g.send('select_targets',decisionToken=d['token'],assignments=[{'forgeId':land['forgeId']}]);g.answer('targets');g.resolve()
    g.check('Targeting an artifact land does not let it be cast',land['forgeId'] not in g.s['legalCasts'])
    g.check('Emry does not grant a graveyard land play',land['forgeId'] not in g.s['legalLands'])
    g.reject('Cannot cast the selected artifact land','cast_spell',land['forgeId'])
    r=dict(checks=len(g.e.checks),evidence=str(g.e.ipc));(g.e.ipc/'emry-artifact-land-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
finally:g.close()
