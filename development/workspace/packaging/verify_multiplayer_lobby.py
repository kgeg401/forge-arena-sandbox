"""Native lobby file boundary without Tk, real network or gameplay side effects."""
import json,tempfile
from pathlib import Path
from multiplayer_lobby import lobby,validate_choice

checks=0
def check(ok):
    global checks
    assert ok;checks+=1

for value in [None,[],{}, {'mode':'other'},{'mode':'host','invitation':'secret'},{'mode':'join'},{'mode':'join','invitation':False},{'mode':'join','invitation':''},{'mode':'join','invitation':'x'*2049},{'mode':'join','invitation':' trailing '},{'mode':'join','invitation':'ok','extra':True}]:
    try:validate_choice(value)
    except ValueError:check(True)
    else:raise AssertionError('Malformed room choice accepted')
for mode in ['host','join','cancel','failed']:
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);called=[];context=dict(clientSession='client',requestId='request')
        if mode=='cancel':(root/'stop.request').write_text('cancel')
        else:(root/'network-choice.json').write_text(json.dumps(dict(mode='join',invitation='https://example.test/#private') if mode=='join' else dict(mode='host')))
        def run(choice):
            called.append(choice)
            if mode=='failed':raise RuntimeError('transport failed')
        try:lobby(root,'Saved deck',run,context=context)
        except RuntimeError:check(mode=='failed')
        else:check(mode!='failed')
        status=json.loads((root/'network-status.json').read_text())
        check(status['clientSession']=='client' and status['requestId']=='request' and status['lobbyPhase']=='choose')
        check(len(called)==(0 if mode=='cancel' else 1))
        check('invitation' not in status and 'https://example.test/#private' not in json.dumps(status))
print(json.dumps(dict(passed=True,checks=checks,scope='Choice validation, context propagation, one attempt, cancellation and failure propagation only; no rendered or internet acceptance.')))
