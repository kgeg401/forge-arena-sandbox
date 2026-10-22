"""Exercise actual Forge draw resolution, cleanup and empty-library loss."""
from engine_test_client import Engine
import json

for scenario in ('draw-wrong-color','draw-ready'):
    e=Engine(scenario)
    try:
        spell=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Quick Study')
        library={c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library'}
        if scenario=='draw-wrong-color':
            e.check('three white sources do not offer a blue draw spell',spell not in e.state['legalCasts'])
            r=e.send('cast_spell',spell)
            e.check('direct wrong-color request preserves hand and library',not r['accepted'] and len(e.state['hand'])==7 and len(library)==2 and not e.state['stack'])
        else:
            r=e.send('cast_spell',spell)
            e.check('Forge accepts the three-mana instant without a target choice',r['accepted'] and not e.state.get('decision') and e.state['stack'][0]['forgeId']==spell)
            e.check('casting removes only the spell before resolution',len(e.state['hand'])==6 and {c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library'}==library)
            e.check('actual two generic and one blue payment taps all sources',all(c['tapped'] for c in e.state['battlefield'] if c['owner']==1) and not e.state['manaTotal'])
            e.pass_or_decision()
            e.check('resolution draws both independent original library identities',len(e.state['hand'])==8 and library.issubset({c['forgeId'] for c in e.state['hand']}))
            e.check('the drawn library becomes empty',not any(c['owner']==1 and c['zone']=='Library' for c in e.state['hidden']))
            e.check('resolved instant goes to graveyard and leaves the stack',not e.state['stack'] and any(c['forgeId']==spell for c in e.state['graveyard']))
            e.check('drawing last cards does not itself lose the game',not e.state['gameOver'] and e.state['life']==e.state['opponentLife']==20)
            e.check('opponent hidden identities remain private',all('name' not in c for c in e.state['hidden']))
            for _ in range(40):
                if e.state.get('decision'):break
                e.pass_or_decision()
            d=e.state.get('decision',{})
            e.check('normal cleanup requests exactly one human discard',d.get('kind')=='discard' and d.get('count')==1)
            selected=next(v for v in d['options'] if v['forgeId'] in library)
            r=e.send('select_discard',decisionToken=d['token'],assignments=[selected]);assert r['accepted'],r
            r=e.send('submit_discard',decisionToken=d['token']);assert r['accepted'],r
            e.check('chosen drawn card actually goes to graveyard',len(e.state['hand'])==7 and any(c['forgeId']==selected['forgeId'] for c in e.state['graveyard']))
            for _ in range(50):
                if e.state['gameOver']:break
                e.pass_or_decision()
            e.check('the next required draw loses from the empty library',e.state['gameOver'] and e.state['localLost'] and e.state['lossReason']=='Milled')
            e.check('decking is not fabricated life damage',e.state['life']==e.state['opponentLife']==20 and not e.state['events'])
            e.check('terminal draw loss clears gameplay',not any(e.state[k] for k in ('legalCasts','legalLands','legalMana','canPass')))
        print(json.dumps({'scenario':scenario,'evidence':str(e.ipc),'checks':len(e.checks)}),flush=True)
    finally:e.close()
