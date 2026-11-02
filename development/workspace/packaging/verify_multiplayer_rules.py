"""File-IPC contract checks; fixture replies never count as playable Magic."""
import json,tempfile,uuid
from pathlib import Path
from multiplayer_room import Room
from multiplayer_rules import RulesRoom,offered_action

checks=[]
def check(label,ok):assert ok,label;checks.append(label)
def rejects(label,call):
    try:call()
    except ValueError:checks.append(label)
    else:raise AssertionError(label)

with tempfile.TemporaryDirectory(prefix='forge-room-check-') as temp:
    ipc=Path(temp)
    for name in ('requests','responses'):(ipc/name).mkdir()
    room=Room(dict(rules='fixture'))
    guest=room.join(room.invite,dict(id=str(uuid.uuid4()),protocol=1,compatibility=room.compatibility))['token']
    session=str(uuid.uuid4());broker=RulesRoom(room,ipc)
    def pair(generation,actor=2):
        for role in (1,2):
            view=dict(session=session,viewerSeat=role,viewRevision=generation,inputSeat=actor,hand=[],decision=dict(seat=2,token='actual-choice',kind='choice') if role==actor==2 else None)
            (ipc/('state-'+str(role)+'.json')).write_text(json.dumps(view))
    pair(1)
    broker.tick();check('Actual paired boundary publishes its real input owner',room.state(guest)['inputPlayer']==2)
    def submit(action):
        packet=room.state(guest)
        command=dict(id=str(uuid.uuid4()),session=session,revision=packet['revision'],decisionToken='actual-choice',action=action)
        room.command(guest,command);return command
    command=submit(dict(op='submit_choice',assignments=[dict(choiceId=7)]))
    broker.tick();request=json.loads((ipc/'requests'/(command['id']+'.json')).read_text())
    check('Rules file uses authenticated seat and exact choice token',request['seat']==2 and request['decisionToken']=='actual-choice' and request['assignments']==[dict(choiceId=7)])
    check('Queued is not reported as engine acceptance',room.command(guest,command)['status']=='queued')
    pair(2,1);broker.tick()
    check('A new snapshot cannot clear an outstanding rules command',room.revision==1 and broker.pending is not None)
    response=ipc/'responses'/(command['id']+'.json')
    response.write_text(json.dumps(dict(id=command['id'],session=str(uuid.uuid4()),accepted=True,reason='wrong match')))
    rejects('Wrong-session acknowledgement cannot consume player input',broker.tick)
    response.write_text(json.dumps(dict(id=command['id'],session=session,accepted=True,reason='actual fixture boundary')))
    completed=broker.tick()
    check('Only actual engine response completes the command',completed['accepted'] and room.command(guest,command)['accepted'])
    check('Next real boundary gives the other player input',room.state(room.host_token)['inputPlayer']==1 and room.revision==2)
    pair(3);broker.tick();command=submit(dict(op='submit_choice',assignments=[dict(choiceId=99)]));broker.tick()
    (ipc/'responses'/(command['id']+'.json')).write_text(json.dumps(dict(id=command['id'],session=session,accepted=False,reason='Not an offered choice')))
    old=room.revision;completed=broker.tick()
    check('Engine rejection is preserved and same decision can be answered again',completed['accepted'] is False and room.state(guest)['inputPlayer']==2 and room.revision>old)
    command=submit(dict(op='cast_spell',forgeId=99001));completed=broker.tick()
    check('A guessed hidden card is never passed to engine availability helpers',completed['accepted'] is False and not (ipc/'requests'/(command['id']+'.json')).exists())
    broker.tick()
    (ipc/'state-1.json').write_text(json.dumps(dict(session=session,viewerSeat=1,viewRevision=4,inputSeat=1,hand=[],decision=None)))
    old=room.revision;broker.tick();check('Half-written paired generations are not published',room.revision==old)
    pair(4);v=json.loads((ipc/'state-1.json').read_text());v['decision']=dict(seat=2,token='secret');(ipc/'state-1.json').write_text(json.dumps(v))
    rejects('Another player chooser cannot be published as a private view',broker.tick)
    room.close()
view=dict(canPass=True,legalLands=[11],legalCasts=[12],legalActivations=[dict(forgeId=13,abilityId=7)],legalManaOffers=[dict(forgeId=14,abilityId=8)])
for action in (dict(op='pass_priority'),dict(op='play_land',forgeId=11),dict(op='cast_spell',forgeId=12),dict(op='activate_ability',forgeId=13,abilityId=7),dict(op='activate_mana',forgeId=14,abilityId=8)):
    check('Offered network input passes validation: '+action['op'],offered_action(view,action))
check('A hidden object cannot borrow another offered ability',not offered_action(view,dict(op='activate_ability',forgeId=99,abilityId=7)))
check('Ordinary pass cannot answer a private chooser',not offered_action(dict(decision=dict(kind='choice')),dict(op='pass_priority')))
print(json.dumps(dict(passed=True,checks=len(checks),results=checks,scope=__doc__),indent=2))
