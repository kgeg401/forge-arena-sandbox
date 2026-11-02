"""Host-side adapter between a private room and one two-human Forge owner.

The ordinary solo engine does not export paired views and cannot use this adapter.
It never starts processes or chooses gameplay actions for either player.
"""
import json,time
from pathlib import Path
from multiplayer_room import MAX_STATE_BYTES,decode


def read_object(path):
    try:
        with path.open('rb') as file:raw=file.read(MAX_STATE_BYTES+1)
    except (FileNotFoundError,PermissionError):return None
    if len(raw)>MAX_STATE_BYTES:raise ValueError('Rules view exceeds room limit')
    value=decode(raw)
    if not isinstance(value,dict):raise ValueError('Rules response must be an object')
    return value


def offered_action(view,action):
    op=action['op'];card=action.get('forgeId')
    if op=='concede':return True
    decision=view.get('decision')
    if decision is not None:
        kind=decision.get('kind')
        return op in ('select_'+str(kind),'submit_'+str(kind),'cancel_'+str(kind))
    if op=='pass_priority':return view.get('canPass') is True
    if op=='play_land':return card in view.get('legalLands',[])
    if op=='cast_spell':return card in view.get('legalCasts',[])
    offers=view.get('legalActivations',[]) if op=='activate_ability' else view.get('legalManaOffers',[]) if op=='activate_mana' else []
    return any(offer.get('forgeId')==card and offer.get('abilityId')==action.get('abilityId') for offer in offers)


class RulesRoom:
    def __init__(self,room,ipc):
        self.room=room;self.ipc=Path(ipc)
        if not (self.ipc/'requests').is_dir() or not (self.ipc/'responses').is_dir():raise ValueError('Missing private rules IPC')
        self.pending=None;self.generation=-1;self.dispatched_generation=-1
        self.wait_started=0.

    def tick(self):
        """Call on the sole host coordinator thread; never from HTTP handlers."""
        completed=None
        if self.pending is not None:
            reply=read_object(self.ipc/'responses'/(self.pending['id']+'.json'))
            if reply is not None:
                if reply.get('id')!=self.pending['id'] or reply.get('session')!=self.pending['session']:raise ValueError('Rules result identity changed')
                if type(reply.get('accepted')) is not bool or not isinstance(reply.get('reason'),str):raise ValueError('Invalid rules result')
                self.room.complete(self.pending['seat'],self.pending['id'],reply['accepted'],reply['reason'][:2048])
                completed=dict(seat=self.pending['seat'],id=self.pending['id'],op=self.pending['action']['op'],accepted=reply['accepted'])
                self.pending=None
                # Rejection need not produce a new engine generation. Reopen
                # the same actual decision, with a new transport revision.
                if not reply['accepted']:self.generation=-1;self.dispatched_generation=-1

        views={role:read_object(self.ipc/('state-'+str(role)+'.json')) for role in (1,2)}
        if all(views.values()):
            a,b=views[1],views[2]
            if a.get('viewRevision')==b.get('viewRevision') and a.get('session')==b.get('session'):
                generation=a.get('viewRevision');actor=a.get('inputSeat')
                if type(generation) is not int or generation<0 or type(actor) is not int or actor not in (0,1,2) or actor!=b.get('inputSeat'):raise ValueError('Invalid paired rules boundary')
                if self.pending is None and generation>self.generation and generation>self.dispatched_generation:
                    decision=views[actor].get('decision') if actor else None
                    if decision is not None and (not isinstance(decision,dict) or decision.get('seat')!=actor):raise ValueError('Rules decision does not belong to its input owner')
                    if any(view.get('decision') is not None for role,view in views.items() if role!=actor):raise ValueError('Private decision appeared in another player view')
                    # Lock spans publication and command pickup: an HTTP input
                    # cannot slip between the queued-state test and publication.
                    with self.room.lock:
                        if self.room.pending is None:
                            self.room.publish(a['session'],views,actor,decision.get('token') if decision else None)
                            self.generation=generation

        if self.pending is None:
            command=self.room.take_command()
            if command is not None:
                if not offered_action(self.room.views[command['seat']],command['action']):
                    # Never probe a hidden card through the rules engine's
                    # availability helpers or expose its diagnostic exception.
                    self.room.complete(command['seat'],command['id'],False,'Action is not offered by the current player view')
                    self.generation=-1;self.dispatched_generation=-1
                    return dict(seat=command['seat'],id=command['id'],op=command['action']['op'],accepted=False)
                self.pending=command;self.dispatched_generation=self.generation;self.wait_started=time.monotonic()
                request=dict(id=command['id'],session=command['session'],seat=command['seat'],forgeId=0)
                request.update(command['action'])
                if command['decisionToken'] is not None:request['decisionToken']=command['decisionToken']
                path=self.ipc/'requests'/(command['id']+'.json')
                temporary=path.with_suffix('.pending')
                with temporary.open('x',encoding='utf8') as file:json.dump(request,file,allow_nan=False)
                temporary.replace(path)
        return completed
