"""Preserve existing card presentation when composing one new binding change.

Uses explicit private source metadata; no game data is embedded in this test.
This verifies reconstruction and rejection boundaries, not gameplay coverage.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
for name in ('base', 'rebuilt', 'experimental', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
tool = Path(__file__).with_name('prepare_human_choice_overlay.py')
inputs = [a.base, a.rebuilt, a.experimental, tool]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
before = {str(path): sha(path) for path in inputs}
checks = []

def run(label, *, base=a.base, rebuilt=a.rebuilt, experimental=a.experimental,
        incremental=True, expected_error=None, output=None):
    target = output or a.output / (label + '.json')
    prior = target.read_bytes() if target.exists() else None
    command = [sys.executable, '-B', str(tool), '--base', str(base),
               '--rebuilt', str(rebuilt), '--experimental', str(experimental),
               '--output', str(target)]
    if incremental:
        command.append('--incremental')
    result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    (a.output / (label + '.log')).write_text(result.stdout + result.stderr)
    if expected_error:
        assert result.returncode != 0 and expected_error in result.stderr, result.stderr
        assert (target.read_bytes() if target.exists() else None) == prior
    else:
        assert result.returncode == 0, result.stderr
        value = json.loads(target.read_text())
        old = json.loads(a.experimental.read_text())
        assert value['cards'] == old['cards'] and value['blockedCards'] == old['blockedCards']
        assert set(old['humanChoices']['cardOverrides']) <= set(value['humanChoices']['cardOverrides'])
        assert all(value['humanChoices']['presentationObjects'].get(k) == v
                   for k, v in old['humanChoices']['presentationObjects'].items())
    checks.append(dict(check=label, passed=True))
    return target

positive = run('preserve-existing-bindings')
run('reject-implicit-drop', incremental=False, expected_error='drop existing bindings')
bad = json.loads(a.experimental.read_text())
name = next(iter(bad['humanChoices']['cardOverrides']))
bad['humanChoices']['cardOverrides'][name]['grpId'] += 1
path = a.output / 'bad-parent.json'; path.write_text(json.dumps(bad))
run('reject-wrong-parent', experimental=path, expected_error='missing an existing binding')
base = json.loads(a.base.read_text())
old = json.loads(a.experimental.read_text())
del base['cards'][next(iter(old['humanChoices']['presentationObjects']))]
path = a.output / 'missing-object.json'; path.write_text(json.dumps(base))
run('reject-missing-object', base=path, expected_error='missing an existing presentation object')
rebuilt = json.loads(a.rebuilt.read_text())
name = next(n for n, c in rebuilt['cards'].items() if c.get('admitted'))
rebuilt['cards'][name]['admitted'] = False
path = a.output / 'admission-change.json'; path.write_text(json.dumps(rebuilt))
run('reject-admission-change', rebuilt=path, expected_error='complete expected card presentation')
run('preserve-existing-output', output=positive, expected_error='preserve existing evidence')
assert before == {str(path): sha(path) for path in inputs}
report = dict(passed=True, checks=checks, inputsSHA256=before,
              scope=__doc__, gameplayVerified=False)
(a.output / 'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps(dict(passed=True, checks=len(checks), gameplayVerified=False)))
