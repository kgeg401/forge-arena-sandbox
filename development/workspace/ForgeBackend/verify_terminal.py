"""A terminal session must reject all new gameplay operations without mutation."""
from engine_test_client import Engine
import json

e = Engine('starter')
try:
    e.send('play_land', e.state['legalLands'][0])
    land = next(c['forgeId'] for c in e.state['battlefield'] if c['name'] == 'Plains')
    lion = next(c['forgeId'] for c in e.state['hand'] if c['name'] == 'Savannah Lions')
    hand_land = next(c['forgeId'] for c in e.state['hand'] if c['name'] == 'Plains')
    e.check('concession reaches terminal state', e.send('concede')['accepted'] and e.state['gameOver'])
    e.check('terminal state exposes no legal actions', not any(e.state[k] for k in ('legalLands', 'legalMana', 'legalCasts', 'canPass')))
    before = json.dumps(e.state, sort_keys=True)
    for op, card in (('play_land', hand_land), ('activate_mana', land), ('cast_spell', lion), ('pass_priority', 0), ('concede', 0)):
        reply = e.send(op, card)
        e.check(f'terminal {op} rejected unchanged', not reply['accepted'] and 'game is over' in reply['reason'] and json.dumps(e.state, sort_keys=True) == before)
    e.check('terminal snapshot remains readable', e.send('snapshot')['accepted'] and json.dumps(e.state, sort_keys=True) == before)
    print(json.dumps({'evidence': str(e.ipc), 'checks': len(e.checks)}, indent=2))
finally:
    e.close()
