"""Confirm the original Arena Assign Damage/Done interaction and Forge outcome.

Begin at the isolated Vampire Nighthawk / two-reach-blockers fixture's original
damage browser. Only observed native button callbacks are invoked.
"""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import shutil
import native_ui_client as native
from native_client_ui import capture
from runtime_paths import ROOT

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--verify-outcome-only', action='store_true', help='Inspect a previously accepted native action; never resend it')
a = p.parse_args()
if a.output.exists() and not a.verify_outcome_only:
    raise ValueError('Select a new evidence folder')
a.output.mkdir(parents=True, exist_ok=a.verify_outcome_only)
lab = ROOT/'native-lab'
checks = []


def state():
    return json.loads((lab/'forge-ipc/state.json').read_text())


def check(label, passed):
    checks.append(dict(check=label, passed=bool(passed)))
    assert passed, label


s = json.loads((a.output/'before-state.json').read_text()) if a.verify_outcome_only else state()
check('Current session matches the retained native evidence', s['session'] == state()['session'])
check('Explicit research manifest', json.loads((lab/'bridge-card-manifest.json').read_text()).get('researchOnly'))
d = s['decision']
check('Real deathtouch damage assignment pending', d['kind'] == 'assign_damage' and d['totalDamage'] == 2 and [v['assignedDamage'] for v in d['options']] == [1, 1])
source = d['sourceForgeId']
victims = {v['forgeId'] for v in d['options']}
check('Source is exact Vampire Nighthawk', next(c['name'] for c in s['battlefield'] if c['forgeId'] == source) == 'Vampire Nighthawk')
if not a.verify_outcome_only:
    (a.output/'before-state.json').write_text(json.dumps(s, indent=2))
    capture(a.output/'assign-damage.png')
with (a.output/'native-actions.log').open('a' if a.verify_outcome_only else 'w', encoding='utf8') as log, redirect_stdout(log):
    if not a.verify_outcome_only:
        observed = native.inspect()
        check('Original damage browser applied', observed['workflow'] == 'AssignDamageWorkflow')
        done = [b for b in observed['uiButtons'] if b['enabled'] and b['key'] == 'DuelScene/KeywordSelection/KeywordSelection_Done']
        check('One original enabled Done control', len(done) == 1)
        native.action('ui', done[0]['key'], observed=observed)
        for _ in range(8):
            s = state()
            if s['phase'] == 'MAIN2':
                break
            observed = native.inspect()
            buttons = [b for b in observed['buttons'] if b['enabled'] and b['text'] == 'Pass']
            check('Original Pass control available', len(buttons) == 1)
            native.action('button', 'Pass', observed=observed)
s = state()
check('Native Done drives real combat to second main', s['phase'] == 'MAIN2' and not s.get('decision'))
wire = [json.loads(line) for line in (lab/'forge-ipc/native-wire.jsonl').read_text().splitlines()]
responses = [r['message']['assignDamageResp']['assigners'] for r in wire if r['direction'] == 'outgoing' and r['session'] == s['session'] and 'assignDamageResp' in r['message']]
check('Exactly one original native damage response was submitted', len(responses) == 1 and len(responses[0]) == 1)
assigner = responses[0][0]
_, native_to_forge = native.mapping()
check('Original native damage response preserves chosen source and recipients', native_to_forge[assigner['instanceId']] == source and assigner['totalDamage'] == 2 and {native_to_forge[v['instanceId']]: v['assignedDamage'] for v in assigner['assignments']} == {v: 1 for v in victims})
hits = {v['targetForgeId']: v['amount'] for v in s['events'] if v['kind'] == 'damage' and v['sourceForgeId'] == source and v['amount'] > 0}
check('Native damage response applies one to each blocker', hits == {v: 1 for v in victims})
dead = {c['forgeId'] for c in s['graveyard']}
check('Both reach blockers die to deathtouch', victims <= dead)
check('Nighthawk dies to three return damage', source in dead)
check('Lifelink gains only the two points dealt', s['life'] == 22 and s['opponentLife'] == 20)
check('No fidelity gap after native allocation', not s['fidelityGap'])
capture(a.output/'resolved-combat.png')
for name in ('state.json', 'native-wire.jsonl'):
    shutil.copy2(lab/'forge-ipc'/name, a.output/name)
(a.output/'report.json').write_text(json.dumps(dict(checks=len(checks), results=checks,
    scope='Observed original damage browser Done callback, native wire response, Forge damage/deaths/lifelink and rendered outcome. Not a physical-mouse or exhaustive interaction claim.'), indent=2))
print(json.dumps(dict(checks=len(checks), report=str(a.output/'report.json'))))
