"""Real HTTP guest->host code relay; no game simulation or GitHub writes."""
import json,tempfile,threading,uuid
from pathlib import Path
from unittest.mock import patch
from client_service import Coordinator,atomic
from multiplayer_room import Room,RoomServer,RoomClient,RoomError
from multiplayer_session import Session

checks=[]
def check(label,value):assert value,label;checks.append(label)
def rejected(label,client,payload,status):
    try:client.call('/v1/report',payload)
    except RoomError as error:check(label,error.status==status)
    else:raise AssertionError(label)

with tempfile.TemporaryDirectory(prefix='forge-peer-reports-') as temp:
    root=Path(temp);host_lab=root/'host';host_lab.mkdir();ipc=host_lab/'forge-ipc';ipc.mkdir();guest_root=root/'guest';(guest_root/'native-lab').mkdir(parents=True)
    room=Room({'build':'peer-report-contract'});server=RoomServer(room);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        url='http://127.0.0.1:'+str(server.server_port);host=RoomClient(url,room.host_token)
        joined=RoomClient(url,room.invite).call('/v1/join',dict(id=str(uuid.uuid4()),protocol=1,compatibility=room.compatibility));guest=RoomClient(url,joined['token'])
        payload=dict(code='NATIVE_DISPLAY_FAILED');rejected('Invitation is not authenticated player access',RoomClient(url,room.invite),payload,401)
        rejected('Host cannot impersonate guest report routing',host,payload,403)
        rejected('No report is accepted before a match exists',guest,payload,409)
        fixture_session=str(uuid.uuid4());room.publish(fixture_session,{seat:dict(viewerSeat=seat,session=fixture_session) for seat in (1,2)},1)
        for value in [{},dict(code='PRIVATE raw message'),dict(code='NATIVE_DISPLAY_FAILED',log='SECRET'),dict(code='NATIVE_DISPLAY_FAILED',version='1.0.0-private')]:rejected('Rejects extra/private/unlisted report fields '+str(len(checks)),guest,value,400)
        check('An unconfigured host does not falsely accept a report',guest.call('/v1/report',payload)==dict(queued=False))
        context=dict(clientSession=str(uuid.uuid4()),requestId=str(uuid.uuid4()));seen=[]
        host_session=Session.__new__(Session);host_session.context=context;host_session.ipc=ipc
        def capture(code):seen.append(code);host_session.queue_peer_failure(code)
        room.failure_callback=lambda _:(_ for _ in ()).throw(OSError('disk unavailable'))
        check('A failed host write is safely retryable',guest.call('/v1/report',payload)==dict(queued=False) and not room.reported_failures)
        room.failure_callback=capture
        client=Session.__new__(Session);client.role=2;client.context=dict(clientSession=str(uuid.uuid4()),requestId=str(uuid.uuid4()));client.root=guest_root;client.client=guest
        packet=dict(schema=1,session=client.context['clientSession'],requestId=client.context['requestId'],code='NATIVE_DISPLAY_FAILED')
        for field,value in [('session','old'),('requestId','old'),('code','PRIVATE'),('schema',True)]:
            wrong=dict(packet);wrong[field]=value;atomic(guest_root/'native-lab/client-failure.json',wrong);client._failure_poll_at=0;client.relay_failure()
            check('Guest refuses stale/invalid local report '+field,not seen)
        atomic(guest_root/'native-lab/client-failure.json',packet);client._failure_poll_at=0;client.relay_failure();client.relay_failure()
        check('Actual guest relay emits one fixed code and deduplicates the receipt',seen==['NATIVE_DISPLAY_FAILED'] and client._failure_relayed)
        check('Direct duplicate HTTP sends remain idempotent',guest.call('/v1/report',payload)==dict(queued=True) and len(seen)==1)
        received=json.loads((ipc/'peer-failure.json').read_text())
        check('Host context is locally supplied; no guest version/name/deck travels',received==dict(schema=1,**context,code='NATIVE_DISPLAY_FAILED'))
        class Reports:
            codes=[]
            def record(self,code):self.codes.append(code);return True
        owner=Coordinator.__new__(Coordinator);owner.reporter=Reports();owner.lab=host_lab;owner.ipc=ipc;owner.session=context['clientSession'];owner.request_id=context['requestId'];owner.phase='playing';owner.internet=True;owner.last_failures=set()
        owner.poll_native_failure();owner.poll_native_failure()
        check('Real coordinator accepts the qualified host packet once',owner.reporter.codes==['NATIVE_DISPLAY_FAILED'])
        owner.internet=False;owner.last_failures.clear();owner.reporter.codes.clear();owner.poll_native_failure()
        check('A solo coordinator cannot adopt an internet peer packet',not owner.reporter.codes)
        owner.internet=True;owner.request_id=str(uuid.uuid4());owner.poll_native_failure()
        check('A prior room packet cannot attach to a new match',not owner.reporter.codes)
        class Unavailable:
            def call(self,*args):raise OSError('offline')
        client.client=Unavailable();client._failure_relayed=False;client._failure_poll_at=0;client.relay_failure()
        check('Relay failure never raises into gameplay or claims delivery',not client._failure_relayed)
        check('Reporting leaves the original room view/actor/revision intact',room.revision==1 and room.actor==1 and room.session==fixture_session)
    finally:server.shutdown();server.server_close();thread.join(timeout=3)
print(json.dumps(dict(passed=True,checks=len(checks),results=checks,scope='Actual local HTTP authentication/idempotence/host-context relay and production coordinator handoff. Transport fixtures only, not a rendered internet failure or real GitHub delivery.')))
