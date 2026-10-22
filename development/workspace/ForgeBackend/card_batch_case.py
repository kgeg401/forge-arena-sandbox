"""One declarative, input-driven Forge case. Called by run_card_batches.py.

Expected values are authored rules assertions, never copied from an observed
result. Initial fixtures seed environments only; all spell effects use Forge.
"""
import argparse
import json
from pathlib import Path
import traceback


class CaseFailure(AssertionError):
    def __init__(self, category, label):
        self.category = category
        super().__init__(label)


def execute(case, engine_factory=None):
    from engine_test_client import Engine
    e = None
    try:
        e = (engine_factory or Engine)('card-family', randomSeed=case.get('seed', 7274), **case['fixture'])

        def check(category, label, condition):
            # Save the exact failing assertion even when the case aborts.
            e.checks.append(dict(check=label, passed=bool(condition), category=category))
            if not condition:
                raise CaseFailure(category, label)

        def advance(phase):
            for _ in range(16):
                if e.state['phase'] == phase:
                    return
                check('controller', 'No unhandled decision while advancing', not e.state.get('decision') and not e.state['fidelityGap'])
                e.pass_or_decision()
            raise CaseFailure('timing', 'Did not reach phase '+phase)

        check('controller','Research human callback guard is enabled',e.state.get('researchControls',{}).get('strictHumanCallbacks') is True)

        for step in case['steps']:
            if step['op'] == 'phase':
                advance(step['phase'])
                continue
            name = step['card']
            cards = [c for c in e.state['hand'] if c['name'] == name]
            check('identity', name+' is in the real hand', bool(cards))
            identity = cards[0]['forgeId']
            before = e.state
            before_hand = {c['forgeId'] for c in before['hand']}
            before_library = {c['forgeId'] for c in before['hidden'] if c['owner'] == 1 and c['zone'] == 'Library'}
            before_life = before['life']
            if step['op'] == 'deny':
                check('legality', name+' is not offered under illegal conditions', identity not in before['legalCasts'])
                reply = e.send('cast_spell', identity)
                check('legality', name+' direct illegal cast is rejected unchanged', not reply['accepted'] and e.state['hand'] == before['hand'] and not e.state['stack'] and e.state['life'] == before_life and e.state['battlefield'] == before['battlefield'] and e.state['hidden'] == before['hidden'])
                continue
            offer = next((o for o in before['castOffers'] if o['forgeId'] == identity), None)
            check('cost', name+' has a legal cost offer', offer is not None)
            cost = sum(c['count'] for c in offer['manaCost'])
            check('cost', name+' keeps the authored printed mana cost', cost == step['mana'])
            tapped = sum(c['tapped'] for c in before['battlefield'] if c['owner'] == 1)
            reply = e.send('cast_spell', identity)
            check('controller', name+' has no unmapped human callback', not e.state.get('fidelityGap'))
            check('casting', name+' enters stack from accepted input', reply['accepted'] and any(c['forgeId'] == identity for c in e.state['stack']))
            check('controller', name+' has no unmapped human decision', not e.state.get('decision') and not e.state['fidelityGap'])
            check('cost', name+' pays with actual sources', sum(c['tapped'] for c in e.state['battlefield'] if c['owner'] == 1)-tapped == cost)
            check('resolution', name+' effects wait for resolution', e.state['life'] == before_life and {c['forgeId'] for c in e.state['hand']} == before_hand-{identity} and {c['forgeId'] for c in e.state['hidden'] if c['owner'] == 1 and c['zone'] == 'Library'} == before_library)
            e.pass_or_decision()
            check('controller', name+' resolves without an unhandled choice', not e.state.get('decision') and not e.state['fidelityGap'])
            after_hand = {c['forgeId'] for c in e.state['hand']}
            after_library = {c['forgeId'] for c in e.state['hidden'] if c['owner'] == 1 and c['zone'] == 'Library'}
            drawn = after_hand-(before_hand-{identity})
            check('draw', name+' draws the exact expected original library objects', len(drawn) == step['draw'] and drawn == before_library-after_library and after_library <= before_library)
            check('life', name+' gains the expected life', e.state['life']-before_life == step['life'])
            check('resolution', name+' finishes in its expected zone', not e.state['stack'] and any(c['forgeId'] == identity for c in e.state[step.get('zone', 'graveyard')]))
            check('privacy', 'Opponent hidden objects remain anonymous', all('name' not in c for c in e.state['hidden']))
            check('outcome', 'Case does not end unexpectedly', not e.state['gameOver'] and e.state['opponentLife'] == before['opponentLife'])
        return dict(status='passed', checks=len(e.checks), evidence=str(e.ipc))
    except Exception as error:
        if e:e._case_failed=True
        gap = e.state.get('fidelityGap') if e else None
        return dict(status='failed', category=getattr(error, 'category', 'controller' if gap else 'infrastructure'), error=str(error),
                    fidelityGap=gap,
                    traceback=traceback.format_exc(), checks=len(e.checks) if e else 0,
                    evidence=str(e.ipc) if e else None)
    finally:
        if e:
            e.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite', type=Path, required=True)
    p.add_argument('--case', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    case = next(c for c in json.loads(a.suite.read_text(encoding='utf8'))['cases'] if c['id'] == a.case)
    if json.loads(a.suite.read_text(encoding='utf8'))['schema']==2:
        from card_batch_scenario import execute as execute_scenario
        result=execute_scenario(case)
    else:result = execute(case)
    a.output.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(dict(case=a.case, **result)), flush=True)
    raise SystemExit(0 if result['status'] == 'passed' else 1)
