"""Real optional exert decisions and extra combat through original native handlers.

Only the initial objects are seeded. Forge declares attackers, handles exert,
creates its trigger/extra combat and performs untap steps. No intermediate
game-state edits or native card-admission promotion are performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import traceback


def run(case, args):
    from native_engine_test_client import NativeEngine
    from native_test_policy import execute
    engine = None
    trace = []
    exert_decisions = []
    combats = []
    checks_after_rejection = []
    attack_enabled = True
    accepting = case != 'decline'
    try:
        engine = NativeEngine('card-family', worker=args.worker, managed=args.managed,
                              fixture=args.fixture, fixtureHand=[], fixtureLands=[],
                              fixtureBattlefield=['Combat Celebrant', 'Grizzly Bears'],
                              fixtureBattlefieldReady=True, fixtureOpponentBattlefield=[],
                              fixtureOpponentLands=[], fixtureLibrary=['Forest'] * 20)
        def card(name):
            return next(c for c in engine.state['battlefield'] if c['name'] == name and c['controller'] == 1)
        celebrant = card('Combat Celebrant')['forgeId']
        bears = card('Grizzly Bears')['forgeId']
        original_ids = {celebrant, bears}
        def attackers(spec, state):
            if not attack_enabled:
                return []
            offered = {o['forgeId'] for o in spec['options']}
            # Attack in both combats when accepting exert. There is no forced
            # main phase between those combats and Celebrant remains tapped.
            chosen = [i for i in (celebrant, bears) if i in offered]
            combats.append(chosen)
            return [dict(forgeId=i, targetSeat=2) for i in chosen]
        def choice(spec, state):
            if spec.get('context') != 'exert-attackers':
                raise AssertionError('Unexpected optional decision: ' + str(spec))
            options = spec['options']
            engine.check('Only the eligible attacking Celebrant is offered',
                         {o['forgeId'] for o in options} == {celebrant})
            engine.check('Exert is optional and bounded', spec['min'] == 0 and spec['max'] == 1)
            exert_decisions.append(dict(type=spec['type'], context=spec['context'], options=options))
            if case == 'invalid-then-accept':
                token = engine.state['decision']['token']
                def position():
                    return json.dumps({k: engine.state[k] for k in
                                       ['battlefield', 'hand', 'graveyard', 'stackOrder', 'decision', 'life', 'opponentLife', 'phase']}, sort_keys=True)
                before = position()
                for label, supplied_token, values in [
                    ('stale-token', token + '-stale', [dict(choiceId=options[0]['choiceId'])]),
                    ('foreign-choice', token, [dict(choiceId=987654321)]),
                    ('duplicate-choice', token, [dict(choiceId=options[0]['choiceId'])] * 2)]:
                    reply = engine.native_call('submit_choice', decisionToken=supplied_token, assignments=values)
                    engine.check(label + ' is rejected without changing combat or exert selection',
                                 not reply['accepted'] and position() == before)
                    checks_after_rejection.append(dict(kind=label, rejected=True))
            return [dict(choiceId=options[0]['choiceId'])] if accepting else []
        deadline = time.monotonic() + 100
        for _ in range(90):
            if engine.state['phase'] == 'MAIN2':
                break
            assert time.monotonic() < deadline, 'Exert combat deadline exceeded'
            execute(engine, trace, 'pass_priority', _attack_policy=attackers, _choice_policy=choice)
        else:
            raise AssertionError('Combat did not finish')
        engine.check('Actual optional exert decision occurred', len(exert_decisions) == 1)
        engine.check('Original creature identities were retained',
                     {c['forgeId'] for c in engine.state['battlefield'] if c['controller'] == 1} == original_ids)
        engine.check('Expected native attacker declarations occurred',
                     combats == ([list((celebrant, bears)), [bears]] if accepting else [list((celebrant, bears))]))
        engine.check('Forge applied the exact combat damage', engine.state['opponentLife'] == (12 if accepting else 14))
        engine.check('Exert never untapped its own source', card('Combat Celebrant')['tapped'])
        attack_enabled = False
        untap_results = []
        for cycle in [1, 2]:
            prior_turn = engine.state['turn']
            for _ in range(140):
                if (engine.state['activeSeat'] == 1 and engine.state['phase'] == 'MAIN1'
                        and engine.state['turn'] > prior_turn):
                    break
                assert time.monotonic() < deadline, 'Exert untap-step deadline exceeded'
                execute(engine, trace, 'pass_priority', _attack_policy=attackers, _choice_policy=choice)
            else:
                raise AssertionError('Next actual human untap did not complete')
            expected_tapped = accepting and cycle == 1
            engine.check('Exert skips exactly the next untap, cycle ' + str(cycle),
                         card('Combat Celebrant')['tapped'] == expected_tapped and not card('Grizzly Bears')['tapped'])
            untap_results.append(dict(cycle=cycle, turn=engine.state['turn'], celebrantTapped=card('Combat Celebrant')['tapped']))
        engine.check('Combat ended without a gap or pending decision',
                     not engine.state['fidelityGap'] and not engine.state.get('decision'))
        return dict(case=case, passed=True, checks=len(engine.checks), combats=combats,
                    exertDecisions=exert_decisions, opponentLife=engine.state['opponentLife'],
                    untapResults=untap_results, invalidChoices=checks_after_rejection,
                    evidence=str(engine.ipc), trace=trace)
    except Exception as error:
        return dict(case=case, passed=False, error=repr(error), traceback=traceback.format_exc(),
                    evidence=str(engine.ipc) if engine else None, trace=trace)
    finally:
        if engine:
            engine.close()


def run_multiple(case, args):
    """Exercise the real 0..N choice with two distinct copies of one card."""
    from native_engine_test_client import NativeEngine
    from native_test_policy import execute
    engine = None
    trace, offered_combats, decisions = [], [], []
    amount = {'multiple-none': 0, 'multiple-one': 1, 'multiple-both': 2}[case]
    try:
        engine = NativeEngine('card-family', worker=args.worker, managed=args.managed,
                              fixture=args.fixture, fixtureHand=[], fixtureLands=[],
                              fixtureBattlefield=['Combat Celebrant', 'Combat Celebrant', 'Grizzly Bears'],
                              fixtureBattlefieldReady=True, fixtureOpponentBattlefield=[],
                              fixtureOpponentLands=[], fixtureLibrary=['Forest'] * 20)
        original = {c['forgeId'] for c in engine.state['battlefield'] if c['controller'] == 1}
        celebrants = {c['forgeId'] for c in engine.state['battlefield'] if c['name'] == 'Combat Celebrant'}
        chosen = set(sorted(celebrants)[:amount])
        def attackers(spec, state):
            eligible = {o['forgeId'] for o in spec['options']}
            offered_combats.append(sorted(eligible))
            # Later extra combats are deliberately declined: this isolates the
            # two-source cost/trigger interaction without ending the duel.
            return [dict(forgeId=i, targetSeat=2) for i in sorted(celebrants)] if len(offered_combats) == 1 else []
        def choice(spec, state):
            engine.check('The two-source exert choice has the original exact bounds',
                         spec.get('context') == 'exert-attackers' and spec['min'] == 0 and spec['max'] == 2)
            engine.check('Only the two declared eligible attackers can be exerted',
                         {o['forgeId'] for o in spec['options']} == celebrants)
            decisions.append(spec)
            return [dict(choiceId=o['choiceId']) for o in spec['options'] if o['forgeId'] in chosen]
        deadline = time.monotonic() + 100
        for _ in range(120):
            if engine.state['phase'] == 'MAIN2':
                break
            assert time.monotonic() < deadline, 'Multiple-source combat deadline exceeded'
            execute(engine, trace, 'pass_priority', _attack_policy=attackers, _choice_policy=choice)
        else:
            raise AssertionError('Multiple-source combat did not finish')
        engine.check('One optional subset decision was made', len(decisions) == 1)
        engine.check('Each selected source produced exactly one extra combat', len(offered_combats) == 1 + amount)
        engine.check('Nonattacking Bears were excluded from the exert choice',
                     len(celebrants) == 2 and len(original) == 3)
        engine.check('Only the first combat dealt damage', engine.state['opponentLife'] == 12)
        cards = {c['forgeId']: c for c in engine.state['battlefield'] if c['controller'] == 1}
        engine.check('All three original physical cards survived', set(cards) == original)
        expected_tapped = celebrants if amount == 0 else chosen if amount == 1 else set()
        engine.check('Each trigger untapped the other source but never itself',
                     {i for i in celebrants if cards[i]['tapped']} == expected_tapped)
        engine.check('Multiple-source combat completed without a rules or native gap',
                     not engine.state['fidelityGap'] and not engine.state.get('decision'))
        return dict(case=case, passed=True, checks=len(engine.checks), selected=sorted(chosen),
                    offeredCombats=offered_combats, exertDecisions=decisions,
                    opponentLife=engine.state['opponentLife'], evidence=str(engine.ipc), trace=trace)
    except Exception as error:
        return dict(case=case, passed=False, error=repr(error), traceback=traceback.format_exc(),
                    evidence=str(engine.ipc) if engine else None, trace=trace)
    finally:
        if engine:
            engine.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'worker', 'managed', 'fixture', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--case', choices=('accept', 'decline', 'invalid-then-accept', 'multiple-none', 'multiple-one', 'multiple-both'), action='append')
    args = parser.parse_args()
    os.environ['FORGE_ARENA_CONFIG'] = str(args.config)
    assert not args.output.exists(), 'Preserve the original failed evidence'
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    root = Path(config['privateRoot'])
    inputs = [Path(__file__), args.config, args.fixture, args.worker,
              root / 'native-lab/bridge-card-manifest.json', root / 'forge-runtime/forge.jar',
              *sorted((root / 'build/ForgeBackend/classes').glob('ForgeLandEngine*.class'))]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    rows = []
    for case in args.case or ['accept', 'decline', 'invalid-then-accept', 'multiple-none', 'multiple-one', 'multiple-both']:
        row = run_multiple(case, args) if case.startswith('multiple-') else run(case, args)
        rows.append(row)
        stable = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
        args.output.write_text(json.dumps(dict(passed=stable and all(r['passed'] for r in rows),
                                              cases=rows, inputsSHA256=hashes, artifactDrift=not stable,
                                              scope=__doc__), indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in row.items() if k not in ('trace', 'traceback')}), flush=True)
    raise SystemExit(0 if stable and all(row['passed'] for row in rows) else 1)
