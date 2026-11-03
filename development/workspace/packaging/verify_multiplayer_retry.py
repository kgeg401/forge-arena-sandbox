"""Fault-after-acceptance tests against real HTTP; fixture views are not Magic rules."""
import json,tempfile,threading,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from client_service import atomic,read
from multiplayer_room import Room,RoomClient,RoomServer,RoomError
from multiplayer_session import Session

checks=[]
def check(name,value):assert value,name;checks.append(name)

class FaultClient:
    def __init__(self,client,stage):self.client=client;self.drop=True;self.commands=[];self.stage=stage
    def call(self,path,value=None):
        if path=='/v1/command':
            self.commands.append(json.loads(json.dumps(value)))
            if self.drop and self.stage=='before':self.drop=False;raise ConnectionResetError('Fixture dropped unsent request')
        response=self.client.call(path,value)
        if path=='/v1/command':
            if self.drop:self.drop=False;raise ConnectionResetError('Fixture dropped accepted response')
        return response

def case(accepted,stage):
    room=Room(dict(test='uncertain-send'),require_presentation=True);server=RoomServer(room);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='http://127.0.0.1:'+str(server.server_port);host=RoomClient(url,room.host_token)
    joined=RoomClient(url,room.invite).call('/v1/join',dict(id=str(uuid.uuid4()),protocol=1,compatibility=room.compatibility));guest=RoomClient(url,joined['token'])
    session=str(uuid.uuid4())
    def views():return {role:dict(session=session,viewerSeat=role,playerCount=2,inputSeat=2,gameOver=False,players=[dict(seat=1,name='Host'),dict(seat=2,name='Guest')]) for role in (1,2)}
    try:
        room.publish(session,views(),2)
        with tempfile.TemporaryDirectory() as folder:
            ipc=Path(folder);(ipc/'requests').mkdir();(ipc/'responses').mkdir()
            native=dict(id='arena_'+uuid.uuid4().hex,session=session,seat=1,op='pass_priority');path=ipc/'requests'/(native['id']+'.json');atomic(path,native)
            client=FaultClient(guest,stage);worker=Session.__new__(Session)
            worker.room=None;worker.client=client;worker.ipc=ipc;worker.role=2;worker.pending=None;worker.last_revision=-1;worker.ack=0;worker.context={};worker.terminal=False
            try:worker.tick()
            except ConnectionResetError:pass
            else:raise AssertionError('Fixture fault did not fire')
            check('Uncertain input retains its envelope and native request',worker.pending is not None and path.exists())
            check('Initial fault has the declared delivery boundary',len(room.requests)==(1 if stage=='after' else 0))
            worker.tick()
            check('Queued retry waits for both real presentation acknowledgements',room.take_command() is None and not (ipc/'responses'/(native['id']+'.json')).exists())
            for client in (host,guest):client.call('/v1/ack',dict(session=session,revision=room.revision))
            command=room.take_command();check('Acknowledged input dispatches once',command is not None and room.take_command() is None)
            room.complete(2,command['id'],accepted,'Fixture engine result')
            room.publish(session,views(),2)
            worker.tick()
            check('Retry keeps exact original command envelope',len(worker.client.commands)==3 and all(v==worker.client.commands[0] for v in worker.client.commands))
            check('Retry cannot queue a second action at the next revision',room.take_command() is None and len(room.requests)==1)
            response=read(ipc/'responses'/(native['id']+'.json'))
            check('Native receives the actual original acceptance or rejection',response['accepted'] is accepted and response['reason']=='Fixture engine result' and response['id']==native['id'])
            check('Only reconciled input is consumed',not path.exists() and worker.pending is None)
            worker.tick();check('Reconciled input never reappears',len(worker.client.commands)==3 and len(room.requests)==1)
    finally:server.shutdown();server.server_close();thread.join(timeout=3)

for accepted in (True,False):
    for stage in ('before','after'):case(accepted,stage)

class GatewayFixture(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        raw=b'{"error":"Fixture HTTP failure"}'
        self.send_response(self.server.failure_status);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

server=ThreadingHTTPServer(('127.0.0.1',0),GatewayFixture);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    client=RoomClient('http://127.0.0.1:'+str(server.server_port),'a'*43)
    for status in (502,503,504,401,409):
        server.failure_status=status
        try:client.call('/v1/state')
        except OSError:check('Gateway failure remains uncertain transport input',status in (502,503,504))
        except RoomError as error:check('Definite access or board rejection stays explicit',status in (401,409) and error.status==status)
        else:raise AssertionError('HTTP fault not delivered')
finally:server.shutdown();server.server_close();thread.join(timeout=3)

# Every startup POST is idempotent, including a deck receipt lost after rules start.
room=Room(dict(test='startup-receipt'));server=RoomServer(room);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
url='http://127.0.0.1:'+str(server.server_port);dropped=set();joined_ids=[]
deck=dict(name='Fixture',format='commander-40',commander=dict(name='Isamaru, Hound of Konda',count=1),cards=[dict(name='Plains',count=99)])
class StartupFault:
    def __init__(self,url,token):self.client=RoomClient(url,token)
    def call(self,path,value=None):
        response=self.client.call(path,value)
        if path=='/v1/join':joined_ids.append(value['id'])
        if path not in dropped:
            dropped.add(path)
            if path=='/v1/deck':
                session=str(uuid.uuid4());room.publish(session,{role:dict(session=session,viewerSeat=role) for role in (1,2)},2)
            raise ConnectionResetError('Fixture lost accepted startup receipt')
        return response
try:
    with tempfile.TemporaryDirectory() as folder:
        worker=Session.__new__(Session);worker.compat=room.compatibility;worker.join_id=str(uuid.uuid4());worker.identity=dict(name='Guest',avatar='Avatar_Basic_Sparky');worker.deck=deck;worker.ipc=Path(folder);worker.context={}
        with patch('multiplayer_session.RoomClient',StartupFault):worker.join(url+'#'+room.invite)
        check('Startup survives lost join, identity and deck receipts',dropped=={'/v1/join','/v1/profile','/v1/deck'})
        check('Every join retry keeps its original guest identity',len(joined_ids)>=2 and set(joined_ids)=={worker.join_id} and room.join_id==worker.join_id)
        check('Startup locks one authenticated identity and original deck',room.profiles=={2:worker.identity} and room.decks=={2:deck})
        check('An accepted deck receipt remains valid after actual room publication',room.session is not None and worker.role==2)
        for token,value in [(room.guest_token,{**deck,'name':'Replacement'}),(room.host_token,deck)]:
            try:room.deck(token,value)
            except RoomError as error:check('Started room still refuses changed or previously unlocked decks',error.status==409)
            else:raise AssertionError('Post-start deck changed')
        try:worker.join(url+'#'+'a'*43)
        except RoomError as error:check('Startup authentication failure is not retried',error.status==401)
        else:raise AssertionError('Invalid invitation joined')
finally:server.shutdown();server.server_close();thread.join(timeout=3)

class UnreachableStartup:
    calls=0
    def __init__(self,url,token):RoomClient(url,token)
    def call(self,*args):UnreachableStartup.calls+=1;raise ConnectionError('Fixture unavailable')

for outcome in ('timeout','cancel'):
    with tempfile.TemporaryDirectory() as folder:
        worker=Session.__new__(Session);worker.ipc=Path(folder);worker.context={};worker.join_id=str(uuid.uuid4());worker.compat={'fixture':'bounded'}
        clock=iter((0,100)) if outcome=='timeout' else iter((0,1))
        def sleep(_):
            (worker.ipc/'stop.request').write_text('Fixture user cancelled')
        UnreachableStartup.calls=0
        with patch('multiplayer_session.RoomClient',UnreachableStartup),patch('multiplayer_session.time',SimpleNamespace(monotonic=lambda:next(clock),sleep=sleep)):
            try:worker.join('http://127.0.0.1:1#'+'a'*43)
            except TimeoutError:check('Startup has a bounded timeout without replacing identity',outcome=='timeout' and UnreachableStartup.calls==1)
            except InterruptedError:check('Cancellation stops startup without another network attempt',outcome=='cancel' and UnreachableStartup.calls==1)
            else:raise AssertionError('Startup bound not enforced')
print(json.dumps(dict(passed=True,checks=len(checks),scope=__doc__,results=checks)))
