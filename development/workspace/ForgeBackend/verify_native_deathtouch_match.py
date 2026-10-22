"""Bounded normal-match QA through observed original Arena controls only.

Uses the deathtouch practice deck, so spell targeting is not needed. Chooses all
legal attackers, no blockers, and the original automatic damage assignment.
No requests are written to Forge IPC and no native intermediate states are fed.
"""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import re
import shutil
import time
import native_ui_client as native
from native_client_ui import capture
from runtime_paths import ROOT


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=int, default=600)
    p.add_argument('--resume', action='store_true', help='Continue observing the same live match without repeating accepted inputs')
    a = p.parse_args()
    if (a.output.exists() and not a.resume) or not 30 <= a.seconds <= 900:
        raise ValueError('Select a new output folder and a bounded 30–900 second run')
    a.output.mkdir(parents=True, exist_ok=a.resume)
    lab = ROOT/'native-lab'
    checks = []
    actions = 0
    stale_observations = 0
    deferred_snapshots = 0
    seen_native_damage = False

    def state():
        return json.loads((lab/'forge-ipc/state.json').read_text())

    def check(label, passed):
        checks.append(dict(check=label, passed=bool(passed)))
        assert passed, label

    s = state()
    session = s['session']
    if a.resume:
        initial = json.loads((a.output/'initial-state.json').read_text())
        check('Resume keeps the exact live session', initial['session'] == session)
        actions = len(re.findall(r'"requestId"\s*:', (a.output/'native-actions.log').read_text()))
        initial_turn = initial['turn']
        seen_native_damage = any('assignDamageResp' in line for line in (lab/'forge-ipc/native-wire.jsonl').read_text().splitlines())
    else:
        initial_turn = s['turn']
        (a.output/'initial-state.json').write_text(json.dumps(s, indent=2))
    check('Actual normally shuffled custom match', s['scenario'] == 'custom-duel' and not any(k.startswith('fixture') for k in json.loads((lab/'forge-ipc/scenario.json').read_text())))
    check('Starting deck includes the tested deathtouch family', 'Vampire Nighthawk' in {c['name'] for c in s['localDeck']['cards']})
    if not a.resume:
        capture(a.output/'opening.png')
    deadline = time.monotonic()+a.seconds
    with (a.output/'native-actions.log').open('a' if a.resume else 'w', encoding='utf8') as log, redirect_stdout(log):
        while time.monotonic() < deadline:
            s = state()
            check('Same native match session, no fidelity gap', s['session'] == session and not s['fidelityGap'])
            if s['gameOver']:
                break
            try:
                observed = native.inspect()
                # Normal clients automatically yield empty priority windows.
                # Read Forge after observing the native screen, then require
                # agreement before choosing an operation from that snapshot.
                s = state()
                if s['gameOver']:
                    break
                kind = (s.get('decision') or {}).get('kind')
                expected = {'attackers':'DeclareAttackersWorkflow', 'blockers':'DeclareBlockersWorkflow', 'assign_damage':'AssignDamageWorkflow'}
                if (kind in expected and observed['workflow'] != expected[kind]) or (not kind and observed['workflow'] != 'ActionsAvailableWorkflow'):
                    deferred_snapshots += 1
                    time.sleep(.1)
                    continue
                buttons = [b for b in observed['buttons'] if b['enabled']]
                primary = [b for b in buttons if b['tag'] == 'Primary']
                advance = [b for b in buttons if b['text'] in ('Pass', 'Resolve')]
                if kind == 'starting_player':
                    native.action('play', observed=observed)
                elif kind == 'mulligan':
                    native.action('keep', observed=observed)
                elif kind == 'attackers':
                    if any(b['text'] == 'All Attack' for b in buttons):
                        native.action('button', 'All Attack', observed=observed)
                    elif len(primary) == 1:
                        native.action('button', primary[0]['text'], observed=observed)
                    elif any(b['text'] == 'No Attacks' for b in buttons):
                        native.action('button', 'No Attacks', observed=observed)
                    else:
                        raise AssertionError(observed)
                elif kind == 'blockers':
                    no_blocks = [b for b in buttons if b['text'] == 'No Blocks']
                    if len(no_blocks) != 1:
                        raise AssertionError(observed)
                    native.action('button', 'No Blocks', observed=observed)
                elif kind == 'assign_damage':
                    capture(a.output/'damage-assignment.png')
                    done = [b for b in observed['uiButtons'] if b['enabled'] and b['key'] == 'DuelScene/KeywordSelection/KeywordSelection_Done']
                    check('Real original damage allocation browser', observed['workflow'] == 'AssignDamageWorkflow' and len(done) == 1)
                    native.action('ui', done[0]['key'], observed=observed)
                    seen_native_damage = True
                elif kind in ('discard', 'mulligan_bottom'):
                    decision = s['decision']
                    selected = {v['forgeId'] for v in decision['assignments']}
                    if len(selected) < decision['count']:
                        identity = next(v['forgeId'] for v in decision['options'] if v['forgeId'] not in selected)
                        native.card(identity)
                    elif len(primary) == 1:
                        native.action('button', primary[0]['text'], observed=observed)
                    else:
                        raise AssertionError(observed)
                elif kind:
                    raise AssertionError('No native choice adapter in this QA driver: '+kind)
                elif s['legalLands']:
                    native.card(s['legalLands'][0])
                elif s['legalCasts']:
                    native.card(s['legalCasts'][0])
                elif observed['workflow'] == 'ActionsAvailableWorkflow' and len(primary) == 1:
                    native.action('button', primary[0]['text'], observed=observed)
                elif len(advance) == 1:
                    native.action('button', advance[0]['text'], observed=observed)
                else:
                    raise AssertionError(observed)
            except native.StaleObservation:
                stale_observations += 1
                continue  # QA rejected before publication; no accepted input is resent.
            actions += 1
            (a.output/'progress.json').write_text(json.dumps(dict(session=session, actions=actions, turn=s['turn'], phase=s['phase']), indent=2))
            if actions % 20 == 0:
                print(json.dumps(dict(actions=actions, turn=s['turn'], phase=s['phase'], life=[s['life'], s['opponentLife']])), flush=True)
    s = state()
    if not s['gameOver']:
        capture(a.output/'bounded-checkpoint.png')
        (a.output/'incomplete-checkpoint.json').write_text(json.dumps(dict(session=session, actions=actions, turn=s['turn'], phase=s['phase'], life=[s['life'], s['opponentLife']],
            status='bounded-timeout', scope='Original match remains live; no accepted action was resent and no completed-game claim.'), indent=2))
    check('Normal native match reaches a real game outcome before deadline', s['gameOver'])
    check('Many original gameplay controls exercised', actions >= 30)
    check('No gameplay actions remain after outcome', not any(s[k] for k in ('legalLands', 'legalCasts', 'legalMana', 'canPass')))
    capture(a.output/'outcome.png')
    for name in ('state.json', 'native-wire.jsonl', 'engine-journal.jsonl', 'scenario.json'):
        shutil.copy2(lab/'forge-ipc'/name, a.output/name)
    (a.output/'report.json').write_text(json.dumps(dict(checks=len(checks), results=checks, actions=actions,
        sawNativeDamageBrowser=seen_native_damage, rejectedStaleObservations=stale_observations, deferredSnapshots=deferred_snapshots, seed=s.get('randomSeed'), initialTurn=initial_turn, turn=s['turn'], winner=s['winnerSeat'], life=[s['life'], s['opponentLife']],
        scope='Normally shuffled independent Forge match through original native controls. QA deliberately chooses no blocks and native automatic allocation; not optimal play, physical mouse input or complete animation parity.'), indent=2))
    print(json.dumps(dict(checks=len(checks), actions=actions, turn=s['turn'], winner=s['winnerSeat'], report=str(a.output/'report.json'))))


if __name__ == '__main__':
    main()
