"""Only transient response reads retry; a gameplay request is never resubmitted."""
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
from engine_test_client import Engine

checks=[]
def check(label,ok):
    assert ok,label
    checks.append(label)

with tempfile.TemporaryDirectory(prefix='arena-poll-check-') as folder:
    e=Engine.__new__(Engine);e.ipc=Path(folder);e.process=Mock();e.process.poll.return_value=None
    path=e.ipc/'response.json'
    for error in (PermissionError('file being replaced'),FileNotFoundError('not published'),json.JSONDecodeError('partial document','',0)):
        with patch.object(Path,'read_text',side_effect=[error,'{"accepted":true}']) as read:
            result=e.wait_json(path,seconds=.5)
            check('Transient read is retried '+type(error).__name__,result['accepted'] and read.call_count==2)
    with patch.object(Path,'read_text',side_effect=PermissionError('persistent lock')):
        try:e.wait_json(path,seconds=.06)
        except TimeoutError as error:check('Persistent lock fails within the bounded wait','persistent lock' in str(error))
        else:raise AssertionError('Persistent lock accepted')
    e.process.poll.return_value=1
    (e.ipc/'engine.log').write_text('engine failure fixture')
    try:e.wait_json(path,seconds=.5)
    except RuntimeError as error:check('Engine exit stops retries and preserves its error','engine failure fixture' in str(error))
    else:raise AssertionError('Dead engine was ignored')
print(json.dumps(dict(checks=len(checks),passed=checks),indent=2))
