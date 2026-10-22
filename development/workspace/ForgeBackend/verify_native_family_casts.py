"""Verify bounded source-family casts via original native card/button callbacks."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import shutil
import native_ui_client as native
from native_client_ui import capture
from runtime_paths import ROOT


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scenario-json', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Select a new evidence folder')
    a.output.mkdir(parents=True)
    lab = ROOT/'native-lab'
    manifest = json.loads((lab/'bridge-card-manifest.json').read_text())
    if not manifest.get('researchOnly'):
        raise ValueError('Native family fixtures require a research manifest')
    names = json.loads(a.scenario_json.read_text())['fixtureHand']
    checks = []

    def state():
        return json.loads((lab/'forge-ipc/state.json').read_text())

    def check(label, passed):
        checks.append(dict(check=label, passed=bool(passed)))
        assert passed, label

    capture(a.output/'initial-hand.png')
    with (a.output/'native-actions.log').open('w', encoding='utf8') as log, redirect_stdout(log):
        for name in names:
            s = state()
            card = next(c for c in s['hand'] if c['name'] == name)
            check('Original card offered for cast '+name, card['forgeId'] in s['legalCasts'])
            native.card(card['forgeId'])
            check('Original card callback puts spell on stack '+name,
                  any(c['forgeId'] == card['forgeId'] for c in state()['stack']))
            observed = native.inspect()
            buttons = [b for b in observed['buttons'] if b['enabled'] and b['text'] in ('Resolve', 'Pass')]
            check('One original resolution control '+name, len(buttons) == 1)
            native.action('button', buttons[0]['text'], observed=observed)
            s = state()
            check('Forge resolution reaches native battlefield '+name,
                  not s['stack'] and any(c['forgeId'] == card['forgeId'] for c in s['battlefield']))
            check('No fidelity gap '+name, not s['fidelityGap'])
        capture(a.output/'resolved-family.png')
    for name in ('state.json', 'native-wire.jsonl'):
        shutil.copy2(lab/'forge-ipc'/name, a.output/name)
    (a.output/'report.json').write_text(json.dumps(dict(cards=names, checks=len(checks), results=checks,
        scope='Original owned native client card/Resolve callbacks and rendered board. Fixture starting hand only; no physical-mouse or animation parity claim.'), indent=2))
    print(json.dumps(dict(cards=len(names), checks=len(checks), report=str(a.output/'report.json'))))


if __name__ == '__main__':
    main()
