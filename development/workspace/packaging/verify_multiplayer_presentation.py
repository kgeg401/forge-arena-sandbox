"""Render acknowledgements and deck exchange: protocol fixtures, not native UI."""
import copy,json,uuid
from multiplayer_room import Room,RoomError
from multiplayer_session import Session,invite,native_action
checks=[]
def check(label,ok):assert ok,label;checks.append(label)
def reject(label,call):
    try:call()
    except (ValueError,RoomError):checks.append(label)
    else:raise AssertionError(label)
r=Room(dict(build='fixture'),require_presentation=True)
guest=r.join(r.invite,dict(id=str(uuid.uuid4()),protocol=1,compatibility=r.compatibility))['token']
deck=dict(name='Fixture',format='commander-40',commander=dict(name='Isamaru, Hound of Konda',count=1),cards=[dict(name='Plains',count=99)])
r.deck(r.host_token,deck);r.deck(guest,deck);deck['cards'][0]['count']=2
check('Locked deck cannot be changed through caller alias',r.decks[1]['cards'][0]['count']==99)
reject('Deck replacement requires a new room',lambda:r.deck(guest,deck))
check('Private deck names/lists do not enter state response','commander' not in json.dumps(r.state(guest)) and 'Isamaru' not in json.dumps(r.state(guest)))
session=str(uuid.uuid4());views={role:dict(session=session,viewerSeat=role) for role in (1,2)}
r.publish(session,views,1)
command=dict(id=str(uuid.uuid4()),session=session,revision=1,decisionToken=None,action=dict(op='pass_priority'))
r.command(r.host_token,command)
check('Even submitted input waits for both actual rendered views',r.take_command() is None)
r.acknowledge(r.host_token,dict(session=session,revision=1));check('The actor acknowledgement alone cannot advance the match',r.take_command() is None)
reject('Wrong-match view acknowledgements fail',lambda:r.acknowledge(guest,dict(session=str(uuid.uuid4()),revision=1)))
r.acknowledge(guest,dict(session=session,revision=1));check('Both acknowledgements release one input',r.take_command()['id']==command['id'] and r.take_command() is None)
r.complete(1,command['id'],True,'Fixture boundary');r.publish(session,views,2)
r.command(guest,{**command,'id':str(uuid.uuid4()),'revision':2})
check('Old render acknowledgements do not release the next view',r.take_command() is None)
url,token=invite('https://private.example#'+r.invite)
check('Invitation secret stays out of the HTTP URL',url=='https://private.example' and token==r.invite)
reject('Insecure internet invitation rejected',lambda:invite('http://private.example#'+r.invite))
r.close()
for prefix in ('arena_','rules_'):
    request=dict(id=prefix+uuid.uuid4().hex,session=session,seat=1,op='pass_priority',forgeId=0)
    check('Native clicked/automatic request accepted: '+prefix,native_action(request,session,2)==dict(op='pass_priority',forgeId=0))
reject('Native request cannot select the other authenticated actor',lambda:native_action({**request,'seat':2},session,2))
reject('Native stale-session input stays rejected',lambda:native_action(request,str(uuid.uuid4()),2))
r=Room(dict(build='fixture'));guest=r.join(r.invite,dict(id=str(uuid.uuid4()),protocol=1,compatibility=r.compatibility))['token']
r.publish(session,views,2,'private-other-decision')
r.command(r.host_token,dict(id=str(uuid.uuid4()),session=session,revision=1,decisionToken=None,action=dict(op='concede')))
check('A player may concede without reading the other private decision',r.take_command()['seat']==1)
r.close()
class FinishedSession(Session):
    def __init__(self,error,terminal):
        self.error=error;self.terminal=terminal;self.pending=None;self.ack=0;self.last_revision=1;self.waited=False;self.closed=False
    def join(self,code):pass
    def stopped(self):return False
    def tick(self):raise self.error
    def wait_for_home(self):self.waited=True
    def close(self):self.closed=True
for error in (RoomError(410,'Closed'),RoomError(502,'Tunnel stopped'),OSError('Connection closed')):
    s=FinishedSession(error,True);s.run(dict(mode='join',invitation='fixture'))
    check('Finished result survives transport closure '+type(error).__name__,s.waited and s.closed)
s=FinishedSession(RoomError(401,'Invalid access'),False)
reject('Pre-result authentication error still fails',lambda:s.run(dict(mode='join',invitation='fixture')))
r=Room(dict(build='new-source'));reject('Mismatched source build cannot join',lambda:r.join(r.invite,dict(id=str(uuid.uuid4()),protocol=1,compatibility=dict(build='old-source'))));r.close()
print(json.dumps(dict(passed=True,checks=len(checks),results=checks,scope=__doc__),indent=2))
