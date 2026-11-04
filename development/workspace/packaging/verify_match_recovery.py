"""Explicit recovery handoff guards; native replay/gameplay is checked separately."""
import copy,hashlib,json,tempfile,time,uuid
from pathlib import Path
from unittest.mock import patch
from client_service import Coordinator,RequestRejected,atomic

checks=[]
with tempfile.TemporaryDirectory(prefix='forge-recovery-') as folder:
    lab=Path(folder);ipc=lab/'forge-ipc';ipc.mkdir()
    state=dict(session=str(uuid.uuid4()),scenario='commander-duel',gameOver=False,decision=dict(kind='choice'),fidelityGap='')
    atomic(ipc/'state.json',state)
    receipt=dict(schema=1,clientSession=str(uuid.uuid4()),expires=time.time()+300,ipc=str(ipc),engineSession=state['session'],stateSha256=hashlib.sha256((ipc/'state.json').read_bytes()).hexdigest())
    def setup(value):
        c=Coordinator.__new__(Coordinator);c.lab=lab;c.ipc=ipc;c.session=receipt['clientSession'];c.process=None;c.seen=set();c.request_id=None;c.error=None
        c.publish=lambda phase,message,**kw:setattr(c,'result',dict(phase=phase,**kw))
        atomic(lab/'match-recovery.json',value)
        request=dict(schema=1,session=c.session,id=str(uuid.uuid4()),action='resume')
        return c,request
    for field,value in [('schema',2),('clientSession',str(uuid.uuid4())),('expires',0),('ipc',str(lab/'other')),('engineSession',str(uuid.uuid4())),('stateSha256','0'*64)]:
        wrong=copy.deepcopy(receipt);wrong[field]=value;c,request=setup(wrong)
        with patch('client_service.RecoveredRulesProcess') as owner:
            try:c.handle(request)
            except RequestRejected:pass
            else:raise AssertionError('Accepted changed '+field)
            assert not owner.called
        checks.append('Rejects changed '+field+' before adopting any process')
    c,request=setup(receipt)
    with patch('client_service.RecoveredRulesProcess') as owner:
        c.handle(request);assert owner.call_count==1 and c.result['phase']=='ready' and c.result['recovered'] and c.request_id==request['id']
        c.handle(request);assert owner.call_count==1
    assert not (lab/'match-recovery.json').exists()
    assert (lab/'enable-forge-land-test.flag').is_file()
    assert (lab/('match-recovery-consumed-'+request['id']+'.json')).exists()
    checks.append('A verified handoff is consumed once and cannot be re-adopted by a repeated request')
    for label,position,accepted in [
        ('ordinary local priority',dict(decision=None,canPass=True,prioritySeat=1),True),
        ('other player priority',dict(decision=None,canPass=True,prioritySeat=2),False),
        ('no actionable boundary',dict(decision=None,canPass=False,prioritySeat=1),False),
        ('nonboolean readiness',dict(decision=None,canPass=1,prioritySeat=1),False),
        ('finished game',dict(decision=None,canPass=True,prioritySeat=1,gameOver=True),False),
        ('rules gap',dict(decision=None,canPass=True,prioritySeat=1,fidelityGap='unmapped'),False),
    ]:
        updated={**state,**position};atomic(ipc/'state.json',updated)
        handoff={**receipt,'stateSha256':hashlib.sha256((ipc/'state.json').read_bytes()).hexdigest()};c,request=setup(handoff)
        with patch('client_service.RecoveredRulesProcess') as owner:
            try:c.handle(request)
            except RequestRejected:assert not accepted and not owner.called,label
            else:assert accepted and owner.call_count==1,label
        checks.append('Recovery boundary: '+label)
print(json.dumps(dict(passed=True,checks=checks),indent=2))
