"""Real commander hand replacement choices; no direct zone edits."""
from pathlib import Path
import json
from deck_import import parse_brawl
from engine_test_client import Engine,ROOT
from emry_test_client import EmryGame,EMRY

deck=parse_brawl('Commander\n1 Emry, Lurker of the Loch\n\nDeck\n98 Island\n1 Unsummon\n','Emry commander bounce boundary')
other=parse_brawl('Commander\n1 Isamaru, Hound of Konda\n\nDeck\n98 Plains\n1 Yoked Ox\n')
seed_path=ROOT/'research/emry-mechanics/bounce-seed.json'
seed_path.parent.mkdir(parents=True,exist_ok=True)
if seed_path.exists():seed=json.loads(seed_path.read_text())['seed']
else:
    for seed in range(40):
        e=Engine('brawl-duel',localDeck=deck,opponentDeck=other,randomSeed=seed,startingPlayerPolicy='local-first')
        try:
            if any(c['name']=='Unsummon' for c in e.state['hand']):
                seed_path.write_text(json.dumps(dict(seed=seed,evidence=str(e.ipc)),indent=2));break
        finally:e.close()
    else:raise AssertionError('No initial bounce card in the bounded real-shuffle seed search')
results=[]
for command in (False,True):
    g=EmryGame(seed=seed,brawl=True,deck_override=deck)
    try:
        g.lands(4);emry=g.one('command',EMRY);g.cast(emry)
        bounce=g.one('hand','Unsummon');g.send('cast_spell',bounce['forgeId'])
        d=g.s['decision'];g.send('select_targets',decisionToken=d['token'],assignments=[{'forgeId':emry['forgeId']}]);g.answer('targets')
        for _ in range(20):
            if g.s.get('decision'):break
            g.step()
        d=g.s['decision']
        g.check('Bounce asks an actual commander replacement choice',d['kind']=='commander_return' and d['choiceZone']=='Hand' and d['fromZone']=='Battlefield',d)
        g.answer('commander_return',[{'returnToCommand':command}])
        zone='command' if command else 'hand';g.check('Emry reaches chosen '+zone,any(c['forgeId']==emry['forgeId'] for c in g.cards(zone,EMRY)))
        g.next_main();g.optional_land();card=g.one(zone,EMRY)
        expected=5 if command else 3
        g.check('Tax only applies to command cast',g.cost(card)==[{'color':'Generic','count':expected-1},{'colors':['Blue'],'count':1}])
        before=g.tapped_lands();g.cast(card)
        g.check('Recast really pays chosen-zone cost',g.tapped_lands()-before==expected)
        g.check('Only command cast increments commander history',g.one('battlefield',EMRY)['commandCasts']==(2 if command else 1))
        r=dict(returnToCommand=command,checks=len(g.e.checks),paid=expected,evidence=str(g.e.ipc),seed=seed)
        (g.e.ipc/'emry-bounce-result.json').write_text(json.dumps(r,indent=2));results.append(r)
    finally:g.close()
print(json.dumps(results,indent=2))
