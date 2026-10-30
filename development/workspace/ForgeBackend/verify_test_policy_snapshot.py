"""An accepted real land play wins over a lagging shared state-file snapshot."""
import json
from engine_test_client import Engine
from native_test_policy import execute

e=Engine('card-family',fixtureHand=['Fetid Pools'],fixtureLands=['Island']*3)
try:
    before=e.state;source=next(c['forgeId'] for c in before['hand'] if c['name']=='Fetid Pools')
    assert any(v['forgeId']==source for v in before['legalActivations']), 'Starting hand should genuinely offer cycling'
    original=e.wait_json
    def lagged(path,seconds=5):
        return before if path==e.ipc/'state.json' else original(path,seconds)
    e.wait_json=lagged
    execute(e,[],'play_land',source)
    e.check('Accepted land play remains on battlefield despite lagging shared file',any(c['forgeId']==source and c['tapped'] for c in e.state['battlefield']))
    e.check('Old hand cycling offer is never replayed after land play',not any(v['forgeId']==source for v in e.state['legalActivations']))
    e.check('Authoritative parent response preserves the spent land drop',e.state['landsPlayed']==1)
    print(json.dumps(dict(passed=True,checks=len(e.checks),evidence=str(e.ipc))))
finally:e.close()
