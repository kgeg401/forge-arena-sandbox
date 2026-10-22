"""Bounded QA calls into original native client controls; no Forge state injection."""
import json,time,uuid
from pathlib import Path
from runtime_paths import ROOT

LAB=ROOT/'native-lab'


def read(name):
    for attempt in range(20):
        try:return json.loads((LAB/name).read_text(encoding='utf-8-sig'))
        except (PermissionError,json.JSONDecodeError):time.sleep(.05)
    raise RuntimeError('Native output did not settle: '+name)


def wait(predicate,seconds=20,name='client-ui-status.json'):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            value=read(name)
            if predicate(value):return value
        except FileNotFoundError:pass
        time.sleep(.1)
    raise TimeoutError('Native client condition timed out: '+name)


def action(op,**fields):
    path=LAB/'client-ui.request.json'
    if path.exists():raise RuntimeError('A native UI request is still pending; no overwrite sent')
    request_id=uuid.uuid4().hex
    value=dict(op=op,requestId=request_id,**fields)
    pending=path.with_suffix('.pending');pending.write_text(json.dumps(value),encoding='utf8');pending.replace(path)
    result=wait(lambda x:x.get('requestId')==request_id,name='client-ui-result.json')
    if not result['accepted']:raise RuntimeError(result.get('error') or 'Original control rejected the action')
    return result


def click(name,contains=''):
    def observed(value):return [b for b in value['buttons'] if b['name']==name and b['enabled'] and contains in b['path']]
    before=wait(lambda value:len(observed(value))>0,10)
    candidates=observed(before)
    if len(candidates)!=1:raise RuntimeError('Original button is not uniquely enabled: '+name)
    return action('click',path=candidates[0]['path'],expectedScreen=before['screen'])


def capture(destination):
    path=LAB/'native-board.png';before=path.stat().st_mtime_ns if path.exists() else 0
    (LAB/'capture-frame.request').write_text('Native client validation')
    end=time.monotonic()+10
    while time.monotonic()<end:
        if path.exists() and path.stat().st_mtime_ns!=before:
            raw=path.read_bytes()
            if raw.startswith(b'\x89PNG\r\n\x1a\n') and raw.endswith(b'\x00\x00\x00\x00IEND\xaeB`\x82'):
                Path(destination).write_bytes(raw);return str(destination)
        time.sleep(.1)
    raise TimeoutError('Native screenshot did not complete')
