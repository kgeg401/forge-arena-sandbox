"""No game launch: accepted input must never become eligible for a resend."""
from contextlib import redirect_stdout
import io
import json
from types import SimpleNamespace
from unittest.mock import patch
import native_ui_client as native

observed = dict(state=1, workflow='ActionsAvailableWorkflow', buttons=[], uiButtons=[], clickable=[])
checks = []
for message, expected in [
    ('Native QA observation changed before publication; inspect again', native.StaleObservation),
    ('Native state not stable; observe again', native.StaleObservation),
    ('Other native action error', RuntimeError),
]:
    result = SimpleNamespace(returncode=1, stderr=message, stdout='')
    with patch.object(native.subprocess, 'run', return_value=result) as run:
        try:
            native.action('button', 'Pass', observed=observed)
        except expected as error:
            assert type(error) == expected and run.call_count == 1
        else:
            raise AssertionError(message)
    checks.append(dict(check=message, passed=True))

result = SimpleNamespace(returncode=0, stdout='accepted', stderr='')
with patch.object(native.subprocess, 'run', return_value=result) as run, \
        patch.object(native, 'inspect', side_effect=RuntimeError('After accepted action: presentation timeout')), \
        redirect_stdout(io.StringIO()):
    try:
        native.action('button', 'Pass', observed=observed)
    except RuntimeError as error:
        assert not isinstance(error, native.StaleObservation) and run.call_count == 1
    else:
        raise AssertionError('Accepted input became eligible for a resend')
checks.append(dict(check='Accepted action plus presentation failure is never retried', passed=True))
print(json.dumps(dict(checks=len(checks), results=checks), indent=2))
