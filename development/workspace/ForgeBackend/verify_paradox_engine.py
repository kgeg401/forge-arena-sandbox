"""Real Paradox/Emry/Crypt casting loops, priority, exclusions and legend rule."""
import json
from pathlib import Path
from deck_import import read_deck
from emry_test_client import EmryGame,EMRY,TAP,ORNITHOPTER

ENGINE='Paradox Engine'
CRYPT="Tormod's Crypt"
SEAT='Seat of the Synod'
UNTAP=76767
g=EmryGame(deck_override=read_deck(Path(__file__).resolve().parent/'draft_policies/Paradox-Emry-Practice.txt'))
def triggers():return [a for a in g.s['stackAbilities'] if a['abilityId']==UNTAP]
def lands():return {c['forgeId']:c['tapped'] for c in g.cards('battlefield') if c['name'] in ('Island',SEAT)}
def crypt_sacrifice(crypt,resolve=True):
    g.activation(crypt,12870,{'forgeId':-1000002},False)
    g.check('An activated ability does not trigger Engine',not triggers())
    if resolve:g.resolve()
def resolve_untap(spell,expected_tapped):
    g.check('Exactly one source-bound cast trigger is on stack',len(triggers())==1 and triggers()[0]['triggered'] and triggers()[0]['sourceForgeId']==engine['forgeId'])
    g.check('The cast spell is still pending below its trigger',any(c['forgeId']==spell['forgeId'] for c in g.s['stack']))
    g.check('Untap is not applied before trigger resolution',all(next(c for c in g.cards('battlefield') if c['forgeId']==i)['tapped'] for i in expected_tapped))
    before_lands=lands();before_mana=g.s['manaTotal'];g.step()
    g.check('Untap resolves before the spell',not triggers() and any(c['forgeId']==spell['forgeId'] for c in g.s['stack']))
    g.check('All expected nonlands really untap',all(not next(c for c in g.cards('battlefield') if c['forgeId']==i)['tapped'] for i in expected_tapped))
    g.check('Basic and artifact lands stay in their prior tap state',lands()==before_lands)
    g.check('The trigger does not create mana',g.s['manaTotal']==before_mana)
    g.resolve()
try:
    g.lands(5)
    if not g.cards('battlefield',SEAT):
        seat=g.ensure_hand(SEAT)
        if not g.s['legalLands']:g.next_main()
        g.send('play_land',seat['forgeId'])
    crypt=g.ensure_hand(CRYPT);g.cast(crypt);emry=g.ensure_hand(EMRY);g.cast(emry)
    g.next_main();engine=g.ensure_hand(ENGINE)
    g.check('Engine offers its real generic five cost',g.cost(engine)==[{'color':'Generic','count':5}])
    before=sum(lands().values());g.cast(engine,False)
    g.check('Engine does not trigger on its own first cast',not triggers())
    g.check('Five real lands pay for Engine',sum(lands().values())-before==5)
    g.resolve();g.check('Engine entered as a real permanent',bool(g.cards('battlefield',ENGINE)))
    g.next_main();seat=g.one('battlefield',SEAT);g.send('activate_mana',seat['forgeId'])
    g.check('Playing and activating lands does not trigger Engine',not triggers())
    crypt_sacrifice(crypt);crypt=g.one('graveyard',CRYPT)
    g.activation(emry,TAP,crypt)
    g.check('Emry activation grants permission without an Engine trigger',not triggers())
    turn=g.s['turn'];initial_mana=g.s['manaTotal'];loop_count=6
    for index in range(loop_count):
        crypt=g.one('graveyard',CRYPT);g.cast(crypt,False)
        resolve_untap(crypt,[emry['forgeId']])
        crypt=g.one('battlefield',CRYPT);crypt_sacrifice(crypt)
        crypt=g.one('graveyard',CRYPT);g.activation(emry,TAP,crypt)
        g.check('Same-turn loop '+str(index+1)+' preserves mana and turn',g.s['turn']==turn and g.s['manaTotal']==initial_mana)
        g.check('Untap permits a new paid tap activation each loop',g.one('battlefield',EMRY)['tapped'] and crypt['forgeId'] in g.s['legalCasts'])

    # Opponent spells must not fire the local Engine. Traverse the actual AI turn.
    saw_opponent_spell=False
    for _ in range(100):
        if g.s['activeSeat']==2 and g.s['stack']:
            saw_opponent_spell|=any(c['owner']==2 for c in g.s['stack'])
            g.check('Opponent casting does not trigger your Engine',not triggers())
        if g.s['turn']>turn and g.s['activeSeat']==1 and g.s['phase']=='MAIN1' and not g.s.get('decision'):break
        g.step()
    else:raise AssertionError('Opponent-turn traversal bound exceeded')
    g.check('Observed a real opponent spell for the negative trigger check',saw_opponent_spell)

    # Establish two independently tapped nonlands through real attacks and costs.
    orn=g.ensure_hand(ORNITHOPTER);g.cast(orn);g.next_main()
    for _ in range(60):
        if (g.s.get('decision') or {}).get('kind')=='attackers':break
        g.step()
    else:raise AssertionError('No real attack decision')
    d=g.s['decision'];g.send('select_attackers',decisionToken=d['token'],assignments=[{'forgeId':orn['forgeId'],'targetSeat':2}]);g.answer('attackers')
    for _ in range(70):
        if g.s['activeSeat']==1 and g.s['phase']=='MAIN2' and not g.s.get('decision') and not g.s['stack'] and not g.s['stackAbilities']:break
        g.step()
    else:raise AssertionError('Postcombat main bound exceeded')
    g.check('The real attack tapped Ornithopter',next(c for c in g.cards('battlefield') if c['forgeId']==orn['forgeId'])['tapped'])
    crypt=g.one('graveyard',CRYPT);g.activation(emry,TAP,crypt);seat=g.one('battlefield',SEAT);g.send('activate_mana',seat['forgeId'])
    g.cast(crypt,False);resolve_untap(crypt,[emry['forgeId'],orn['forgeId']])

    # A second legendary Engine is a spell: the old one triggers before legend SBA.
    g.next_main();second=g.ensure_hand(ENGINE);g.cast(second,False)
    g.check('Existing Engine triggers on a second Engine cast',len(triggers())==1 and triggers()[0]['sourceForgeId']==engine['forgeId'])
    for _ in range(30):
        if (g.s.get('decision') or {}).get('kind')=='legend_rule':break
        g.step()
    else:raise AssertionError('No Engine legend choice')
    d=g.s['decision'];g.check('Legend choice offers the two real Engines',{o['forgeId'] for o in d['options']}=={engine['forgeId'],second['forgeId']})
    g.answer('legend_rule',[{'forgeId':engine['forgeId']}]);g.resolve()
    g.check('Chosen Engine survives and the other goes to graveyard',g.one('battlefield',ENGINE)['forgeId']==engine['forgeId'] and any(c['forgeId']==second['forgeId'] for c in g.cards('graveyard',ENGINE)))
    result=dict(checks=len(g.e.checks),loops=loop_count,loopTurn=turn,evidence=str(g.e.ipc),scope='Normal shuffled match, real spells/abilities/attack/legend choices; no injected states or native rendering claim')
    (g.e.ipc/'paradox-engine-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
finally:g.close()
