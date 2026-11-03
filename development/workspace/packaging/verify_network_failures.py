"""Setup/room-close error contracts. Real local HTTP, authored process fixtures."""
import argparse,json,tempfile,uuid,threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from multiplayer_session import main
from multiplayer_room import Room,RoomServer,RoomClient
from client_service import Coordinator,atomic

parser=argparse.ArgumentParser();parser.add_argument('--case',choices=['startup','room','all'],default='all');args=parser.parse_args();checks=[]
def check(label,value):assert value,label;checks.append(label)
class Reports:
    def __init__(self):self.codes=[]
    def record(self,code):self.codes.append(code);return True
    def close(self):pass
class Ended:
    pid=888888
    def poll(self):return 1

with tempfile.TemporaryDirectory(prefix='forge-network-failure-') as temp:
    root=Path(temp);assert root.resolve().parent==Path(tempfile.gettempdir()).resolve()
    lab=root/'native-lab';ipc=lab/'forge-ipc';ipc.mkdir(parents=True);config=root/'config.json';atomic(config,dict(privateRoot=str(root)));atomic(ipc/'network-deck.json',dict(name='fixture'))
    argv=SimpleNamespace(config=str(config),ipc=str(ipc));secret='PRIVATE local setup detail / not for GitHub'
    if args.case in ('startup','all'):
        with patch('multiplayer_session.Session',side_effect=ValueError(secret)):
            try:main(argv)
            except ValueError as e:check('Setup preserves the original exception',str(e)==secret)
            else:raise AssertionError('Expected constructor failure')
        check('Constructor failure gets an explicit private error receipt',(ipc/'engine-error.json').exists())
        error=json.loads((ipc/'engine-error.json').read_text());check('Raw setup detail stays in its local diagnostic',error['reason']==secret and error['category']=='NETWORK_SESSION_FAILED')
        (ipc/'engine-error.json').unlink();(ipc/'network-status.json').unlink()
        original=ValueError(secret)
        with patch('multiplayer_session.Session',side_effect=original),patch('multiplayer_session.atomic',side_effect=OSError('disk unavailable')):
            try:main(argv)
            except ValueError as error:check('A failed diagnostic write preserves the original setup error',error is original)
            else:raise AssertionError('Expected original failure')
    if args.case in ('room','all'):
        room=Room(dict(build='closed-room-contract'));server=RoomServer(room);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url='http://127.0.0.1:'+str(server.server_port);host=RoomClient(url,room.host_token)
            joined=RoomClient(url,room.invite).call('/v1/join',dict(id=str(uuid.uuid4()),protocol=1,compatibility=room.compatibility));guest=RoomClient(url,joined['token']);host.call('/v1/leave',{})
            class SessionFixture:
                deck=dict(name='fixture');context=dict(clientSession=str(uuid.uuid4()),requestId=str(uuid.uuid4()));closed=0
                def run(self,choice):guest.call('/v1/state')
                def close(self):self.closed+=1
            session=SessionFixture()
            with patch('multiplayer_session.Session',return_value=session),patch('multiplayer_lobby.lobby',side_effect=lambda ipc,deck,run,**kw:run(dict(mode='join'))):
                try:main(argv)
                except ValueError:pass
                else:raise AssertionError('Expected actual HTTP410 closure')
            check('Closed HTTP room still closes its owned session',session.closed==1)
            atomic(lab/'sandbox-lab.json',dict(schema=1,fixture=True));atomic(lab/'deck-catalog.json',dict(cards=[]));atomic(lab/'launch-receipt.json',dict(pid=777777,executable=str(lab/'MTGA.exe'),appContainer=True,capabilityCount=0,networkCapability=False))
            app=root/'app';app.mkdir();owner=Coordinator(dict(privateRoot=str(root)),app,str(uuid.uuid4()),777777);owner.reporter=Reports();owner.process=Ended();owner.phase='playing';owner.internet=True
            owner.tick();check('A normal explicit room closure does not create a bug report',not owner.reporter.codes)
            check('The player gets a clear room-closure explanation',owner.phase=='error' and 'private room' in owner.last_snapshot['message'].lower())
            local_status=json.loads((ipc/'network-status.json').read_text());check('A running session error keeps its validated local context',all(local_status[k]==v for k,v in session.context.items()))
            owner.phase='starting';owner.tick();check('A room closed during startup is also not a bug report',not owner.reporter.codes and owner.phase=='error')
            atomic(ipc/'engine-error.json',dict(reason=secret,category='NETWORK_SESSION_FAILED'));owner.phase='playing';owner.tick()
            check('Other network-owner failures use a fixed network code',owner.reporter.codes==['NETWORK_SESSION_FAILED'])
            check('Local diagnostic detail never enters the report payload',secret not in json.dumps(owner.reporter.codes))
            (ipc/'engine-error.json').write_text('not JSON');owner.phase='playing';owner.tick()
            check('A malformed diagnostic cannot crash the coordinator',owner.phase=='error' and owner.reporter.codes[-1]=='NETWORK_SESSION_FAILED' and 'connection' in owner.last_snapshot['message'])
            owner.close()
            (ipc/'engine-error.json').unlink();(ipc/'network-status.json').unlink()
            class Cancelled(SessionFixture):
                def run(self,choice):return
            cancelled=Cancelled()
            with patch('multiplayer_session.Session',return_value=cancelled),patch('multiplayer_lobby.lobby',side_effect=lambda ipc,deck,run,**kw:run(dict(mode='join'))):main(argv)
            check('Cooperative cancellation creates no error receipt',not (ipc/'engine-error.json').exists() and cancelled.closed==1)
        finally:server.shutdown();server.server_close();thread.join(timeout=3)
print(json.dumps(dict(passed=True,checks=len(checks),results=checks,scope='Constructor fault injection, actual authenticated local HTTP410 and production coordinator with authored process metadata. No native gameplay, crash restoration or GitHub sends.')))
