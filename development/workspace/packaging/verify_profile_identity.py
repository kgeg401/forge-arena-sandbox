"""Cosmetic alias privacy and authenticated real HTTP room boundaries."""
import json,tempfile,uuid,threading
from pathlib import Path
from profile_identity import selected_identity,public_identity
from multiplayer_room import Room,RoomClient,RoomServer,RoomError
from multiplayer_session import Session

checks=0
def check(value):
    global checks
    assert value;checks+=1
for value in [None,{},dict(name='x',avatar='unknown'),dict(name='<b>fake</b>',avatar='Avatar_Basic_Sparky'),dict(name='x\ny',avatar='Avatar_Basic_Sparky'),dict(name='x'*33,avatar='Avatar_Basic_Sparky'),dict(name='😀'*17,avatar='Avatar_Basic_Sparky'),dict(name='x',avatar='Avatar_Basic_Sparky',profileId='private')]:
    try:public_identity(value)
    except ValueError:check(True)
    else:raise AssertionError('Invalid public profile accepted')
with tempfile.TemporaryDirectory() as temp:
    lab=Path(temp);check(selected_identity(lab)==dict(name='Local Player',avatar='Avatar_Basic_AjaniGoldmane'))
    folder=lab/'local-profile';folder.mkdir();path=folder/'identities.json';identity=str(uuid.uuid4())
    row=dict(id=identity,name='Friend',avatar='Avatar_Basic_Sparky');saved=dict(schema=1,revision=1,activeId=identity,profiles=[row]);path.write_text(json.dumps(saved));before=path.read_bytes()
    selected=selected_identity(lab);check(selected==dict(name='Friend',avatar='Avatar_Basic_Sparky') and 'id' not in selected);check(path.read_bytes()==before)
    saved['activeId']=str(uuid.uuid4());path.write_text(json.dumps(saved));bad=path.read_bytes()
    try:selected_identity(lab)
    except ValueError:check(path.read_bytes()==bad)
    else:raise AssertionError('Missing profile silently defaulted')
room=Room({'build':'cosmetic-contract'});server=RoomServer(room);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    url='http://127.0.0.1:'+str(server.server_port);host=RoomClient(url,room.host_token)
    host.call('/v1/profile',dict(name='Host',avatar='Avatar_Basic_AjaniGoldmane'))
    joined=RoomClient(url,room.invite).call('/v1/join',dict(id=str(uuid.uuid4()),protocol=1,compatibility=room.compatibility));guest=RoomClient(url,joined['token'])
    guest.call('/v1/profile',selected);view=host.call('/v1/state')
    check(view['profiles']=={'1':dict(name='Host',avatar='Avatar_Basic_AjaniGoldmane'),'2':selected})
    check(all(set(v)=={'name','avatar'} for v in view['profiles'].values()))
    check(identity not in json.dumps(view['profiles']))
    check(guest.call('/v1/profile',selected)==dict(ready=True))
    for client,value,code in [(guest,dict(name='Changed',avatar='Avatar_Basic_Sparky'),409),(guest,dict(name='x',avatar='Avatar_Basic_Sparky',seat=1),400),(RoomClient(url,'z'*43),selected,401)]:
        try:client.call('/v1/profile',value)
        except RoomError as error:check(error.status==code)
        else:raise AssertionError('Invalid profile update accepted')
    check(host.call('/v1/state')['profiles']==view['profiles'])
    for role in [1,2]:
        session=Session.__new__(Session);session.role=role
        packet=dict(revision=1,profiles=view['profiles'],state=dict(viewerSeat=role,playerCount=2,decision=None,players=[dict(seat=1,name='Original host'),dict(seat=2,name='Original guest')]))
        projected=session.projected(packet);players={p['seat']:p for p in projected['players']}
        check(players[1]['name']==('Host' if role==1 else 'Friend') and players[1]['avatar']==('Avatar_Basic_AjaniGoldmane' if role==1 else 'Avatar_Basic_Sparky'))
        check(players[2]['name']==('Friend' if role==1 else 'Host') and projected['networkRevision']==1)
finally:server.shutdown();server.server_close();thread.join(timeout=3)
print(json.dumps(dict(passed=True,checks=checks,scope='Cosmetic file validation and two real local HTTP roles; no native rendered peer avatars or internet gameplay certification.')))
