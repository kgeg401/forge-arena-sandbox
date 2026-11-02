"""Private two-player room transport. No rules simulation or game-file access."""
import sys
sys.dont_write_bytecode=True
import copy,hashlib,hmac,json,re,secrets,threading,time,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError

PROTOCOL=1
MAX_COMMAND_BYTES=64*1024
MAX_STATE_BYTES=4*1024*1024
DECISIONS={'targets','starting_player','mulligan','mulligan_bottom','discard','legend_rule','order_cards','attackers','blockers','assign_damage','commander_return','choice'}
OPS={'pass_priority','play_land','cast_spell','activate_mana','activate_ability','cancel_targets','cancel_assign_damage','concede'}|{'submit_'+kind for kind in DECISIONS}|{'select_'+kind for kind in DECISIONS-{'choice','assign_damage','order_cards'}}

class RoomError(ValueError):
    def __init__(self,status,message):super().__init__(message);self.status=status

def exact_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON field')
        result[key]=value
    return result

def encoded(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf8')

def decode(raw):return json.loads(raw.decode('utf8'),object_pairs_hook=exact_object,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Invalid JSON number')))

def identity(value):
    return isinstance(value,str) and str(uuid.UUID(value))==value

class Room:
    """Only the local rules adapter publishes views and completes commands."""
    def __init__(self,compatibility,require_presentation=False):
        if not isinstance(compatibility,dict) or not compatibility or len(encoded(compatibility))>2048:raise ValueError('Missing pinned compatibility')
        self.compatibility=copy.deepcopy(compatibility)
        self.invite=secrets.token_urlsafe(32);self.host_token=secrets.token_urlsafe(32);self.guest_token=secrets.token_urlsafe(32)
        self.lock=threading.RLock();self.join_id=None;self.closed=False;self.revision=0;self.session=None;self.actor=None;self.views={};self.decision=None
        self.seen={1:time.monotonic(),2:0.0};self.requests={};self.pending=None;self.dispatched=False
        self.require_presentation=require_presentation;self.acknowledged={1:0,2:0};self.decks={}

    def alive(self):
        if self.closed:raise RoomError(410,'Room closed')

    def role(self,token):
        self.alive()
        if not isinstance(token,str) or len(token)>128:raise RoomError(401,'Invalid player access')
        if hmac.compare_digest(token,self.host_token):return 1
        if self.join_id and hmac.compare_digest(token,self.guest_token):return 2
        raise RoomError(401,'Invalid player access')

    def join(self,token,value):
        with self.lock:
            self.alive()
            if not isinstance(token,str) or len(token)>128 or not hmac.compare_digest(token,self.invite):raise RoomError(401,'Invalid invitation')
            if not isinstance(value,dict) or set(value)!={'id','protocol','compatibility'}:raise RoomError(400,'Invalid join request')
            try:
                if not identity(value['id']):raise ValueError()
            except (ValueError,TypeError,AttributeError):raise RoomError(400,'Invalid join identity')
            if type(value['protocol']) is not int or value['protocol']!=PROTOCOL or value['compatibility']!=self.compatibility:raise RoomError(409,'Both clients need the same tested build and catalogue')
            if self.join_id is not None and self.join_id!=value['id']:raise RoomError(409,'This private room already has its second player')
            self.join_id=value['id'];self.seen[2]=time.monotonic()
            return dict(protocol=PROTOCOL,player=2,token=self.guest_token)

    def state(self,token):
        with self.lock:
            role=self.role(token);now=time.monotonic();self.seen[role]=now
            return dict(protocol=PROTOCOL,player=role,revision=self.revision,session=self.session,inputPlayer=self.actor or 0,pendingAction=self.pending is not None,peerConnected=self.join_id is not None and now-self.seen[3-role]<30,
                        readyPlayers=sorted(self.decks),phase='waiting-for-player' if self.join_id is None else 'waiting-for-rules' if self.session is None else 'match',state=copy.deepcopy(self.views.get(role)))

    def deck(self,token,value):
        with self.lock:
            role=self.role(token)
            if self.session is not None:raise RoomError(409,'The match has already started')
            if not isinstance(value,dict) or set(value)!={'name','format','commander','cards'} or not isinstance(value['name'],str) or len(value['name'])>200 or value['format']!='commander-40':raise RoomError(400,'A Commander deck is required')
            entries=[value['commander']]+value['cards'] if isinstance(value['cards'],list) else []
            if not 2<=len(entries)<=100 or any(not isinstance(c,dict) or set(c)!={'name','count'} or not isinstance(c['name'],str) or not 1<=len(c['name'])<=200 or type(c['count']) is not int or not 1<=c['count']<=99 for c in entries):raise RoomError(400,'Invalid deck entries')
            if entries[0]['count']!=1 or sum(c['count'] for c in entries)!=100:raise RoomError(400,'Use 99 cards and one commander')
            if role in self.decks and self.decks[role]!=value:raise RoomError(409,'Deck already locked for this room')
            self.decks[role]=copy.deepcopy(value);return dict(ready=True)

    def acknowledge(self,token,value):
        with self.lock:
            role=self.role(token)
            if not isinstance(value,dict) or set(value)!={'session','revision'} or value['session']!=self.session or type(value['revision']) is not int or not 0<value['revision']<=self.revision:raise RoomError(409,'Wrong presented view')
            self.acknowledged[role]=max(self.acknowledged[role],value['revision']);self.seen[role]=time.monotonic()
            return dict(acknowledged=value['revision'])

    def publish(self,session,views,actor,decision_token=None):
        # Host-only Python API; there is deliberately no network publish route.
        with self.lock:
            self.alive()
            if not self.join_id:raise ValueError('Second player has not joined')
            if self.pending is not None:raise ValueError('Complete the queued rules command before replacing its view')
            if not identity(session):raise ValueError('Invalid match identity')
            if self.session is not None and session!=self.session:raise ValueError('An existing room cannot change matches')
            if type(actor) is not int or actor not in (0,1,2) or set(views)!={1,2}:raise ValueError('Publish both private views and the real input owner')
            if decision_token is not None and (not isinstance(decision_token,str) or not 1<=len(decision_token)<=128):raise ValueError('Invalid decision identity')
            for role,view in views.items():
                if not isinstance(view,dict) or type(view.get('viewerSeat')) is not int or view['viewerSeat']!=role or view.get('session')!=session:raise ValueError('Private view ownership differs')
                if set(view)&{'localDeck','opponentDeck','randomSeed','researchControls','researchTrace'}:raise ValueError('Private deck or diagnostic metadata is not a network view')
                if len(encoded(view))>MAX_STATE_BYTES:raise ValueError('Private view exceeds room limit')
            self.session=session;self.views=copy.deepcopy(views);self.actor=actor;self.decision=decision_token;self.revision+=1

    def command(self,token,value):
        with self.lock:
            role=self.role(token);self.seen[role]=time.monotonic()
            if not isinstance(value,dict) or set(value)!={'id','session','revision','decisionToken','action'}:raise RoomError(400,'Invalid command envelope')
            try:
                if not identity(value['id']):raise ValueError()
            except (ValueError,TypeError,AttributeError):raise RoomError(400,'Invalid command identity')
            action=value['action']
            if not isinstance(action,dict) or not isinstance(action.get('op'),str) or action['op'] not in OPS or set(action)-{'op','forgeId','abilityId','assignments','autoOrderTriggers','autoChooseReplacementEffects'}:raise RoomError(400,'Unknown gameplay action or fields')
            if any(type(action[k]) is not bool for k in ('autoOrderTriggers','autoChooseReplacementEffects') if k in action):raise RoomError(400,'Invalid player preferences')
            if any(type(action[key]) is not int or not 0<=action[key]<=2147483647 for key in ('forgeId','abilityId') if key in action):raise RoomError(400,'Invalid gameplay identity')
            if 'assignments' in action and (not isinstance(action['assignments'],list) or len(action['assignments'])>4096 or any(not isinstance(item,dict) for item in action['assignments'])):raise RoomError(400,'Invalid gameplay assignments')
            raw=encoded(value)
            if len(raw)>MAX_COMMAND_BYTES:raise RoomError(413,'Command exceeds room limit')
            key=(role,value['id']);digest=hashlib.sha256(raw).digest()
            if key in self.requests:
                old,reply=self.requests[key]
                if not hmac.compare_digest(digest,old):raise RoomError(409,'Command identity reused with different input')
                return copy.deepcopy(reply)
            if value['session']!=self.session or self.session is None:raise RoomError(409,'Match identity changed')
            if type(value['revision']) is not int or value['revision']!=self.revision:raise RoomError(409,'The board changed; observe it before acting')
            if action['op']!='concede' and value['decisionToken']!=self.decision:raise RoomError(409,'Decision identity changed')
            if self.actor!=role and action['op']!='concede':raise RoomError(409,'Waiting for the other player')
            if time.monotonic()-self.seen[3-role]>=30:raise RoomError(409,'Other player disconnected; reconnect before acting')
            if self.pending is not None:raise RoomError(409,'An action is already awaiting the rules engine')
            if len(self.requests)>=10000:raise RoomError(409,'Room action limit reached; start a new room')
            reply=dict(id=value['id'],status='queued')
            self.requests[key]=(digest,reply);self.pending=dict(id=value['id'],session=self.session,seat=role,decisionToken=self.decision,action=copy.deepcopy(action));self.dispatched=False
            return copy.deepcopy(reply)

    def take_command(self):
        with self.lock:
            self.alive()
            if self.pending is None or self.dispatched or any(time.monotonic()-seen>=30 for seen in self.seen.values()):return None
            if self.require_presentation and any(value<self.revision for value in self.acknowledged.values()):return None
            self.dispatched=True;return copy.deepcopy(self.pending)

    def complete(self,seat,command_id,accepted,reason):
        with self.lock:
            self.alive()
            if not self.dispatched or self.pending is None or (seat,command_id)!=(self.pending['seat'],self.pending['id']):raise ValueError('Rules result does not own the pending command')
            if type(accepted) is not bool or not isinstance(reason,str) or len(reason)>2048:raise ValueError('Invalid rules result')
            key=(seat,command_id);digest,_=self.requests[key];self.requests[key]=(digest,dict(id=command_id,status='completed',accepted=accepted,reason=reason))
            self.pending=None;self.dispatched=False;self.actor=0

    def close(self):
        with self.lock:self.closed=True;self.pending=None;self.views.clear()

class RoomServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,room):
        self.room=room;self.slots=threading.BoundedSemaphore(8)
        super().__init__(('127.0.0.1',0),RoomHandler)
    def process_request(self,request,address):
        if not self.slots.acquire(False):request.close();return
        try:super().process_request(request,address)
        except BaseException:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()

class RoomHandler(BaseHTTPRequestHandler):
    server_version='ForgeRoom/1';sys_version=''
    def setup(self):super().setup();self.connection.settimeout(8)
    def log_message(self,*args):pass # Invitation/player tokens never enter request logs.
    def do_GET(self):self.dispatch()
    def do_POST(self):self.dispatch()
    def dispatch(self):
        status=200
        try:
            if self.headers.get('Origin') or sum(len(k)+len(v) for k,v in self.headers.items())>8192:raise RoomError(403,'Browser or oversized request rejected')
            auth=self.headers.get_all('Authorization',[])
            if len(auth)!=1 or not auth[0].startswith('Bearer '):raise RoomError(401,'Player access required')
            token=auth[0][7:]
            if self.command=='GET' and self.path=='/v1/state':result=self.server.room.state(token)
            elif self.command=='POST' and self.path in ('/v1/join','/v1/command','/v1/deck','/v1/ack','/v1/leave'):
                lengths=self.headers.get_all('Content-Length',[])
                if self.headers.get('Transfer-Encoding') or len(lengths)!=1 or not lengths[0].isdigit():raise RoomError(400,'Exact JSON length required')
                size=int(lengths[0])
                if size>MAX_COMMAND_BYTES:raise RoomError(413,'Request exceeds room limit')
                if self.headers.get_content_type()!='application/json':raise RoomError(415,'JSON required')
                raw=self.rfile.read(size)
                if len(raw)!=size:raise RoomError(400,'Incomplete JSON request')
                value=decode(raw)
                if self.path=='/v1/leave':
                    with self.server.room.lock:self.server.room.role(token);self.server.room.close();result=dict(closed=True)
                else:result={'/v1/join':self.server.room.join,'/v1/command':self.server.room.command,'/v1/deck':self.server.room.deck,'/v1/ack':self.server.room.acknowledge}[self.path](token,value)
            else:raise RoomError(404,'Unknown room operation')
        except RoomError as error:status=error.status;result=dict(error=str(error))
        except (ValueError,TypeError,KeyError,RecursionError,UnicodeError):status=400;result=dict(error='Invalid room request')
        except (TimeoutError,ConnectionError,OSError):return
        raw=encoded(result);self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('Connection','close');self.end_headers()
        try:self.wfile.write(raw)
        except (ConnectionError,OSError):pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):raise ValueError('Room redirects are not allowed')

class RoomClient:
    def __init__(self,url,token):
        parsed=urlsplit(url)
        local=parsed.hostname in ('127.0.0.1','localhost','::1')
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/') or not parsed.hostname or parsed.scheme!='https' and not (parsed.scheme=='http' and local):raise ValueError('Use HTTPS for an internet room; HTTP is limited to loopback tests')
        if not local and parsed.port not in (None,443):raise ValueError('Internet rooms use HTTPS port443')
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,128}',token):raise ValueError('Invalid invitation or player access')
        self.url=url.rstrip('/');self.token=token;self.opener=build_opener(NoRedirect())
    def call(self,path,value=None):
        if path not in ('/v1/state','/v1/join','/v1/command','/v1/deck','/v1/ack','/v1/leave'):raise ValueError('Unknown room operation')
        req=Request(self.url+path,data=None if value is None else encoded(value),headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json','User-Agent':'ForgeArenaSandbox-Room/1'})
        try:
            with self.opener.open(req,timeout=15) as response:
                raw=response.read(MAX_STATE_BYTES+8193)
                if len(raw)>MAX_STATE_BYTES+8192:raise ValueError('Room response exceeds limit')
                return decode(raw)
        except HTTPError as error:
            raw=error.read(8192)
            try:message=decode(raw)['error']
            except (ValueError,KeyError,TypeError):message='Room request rejected'
            raise RoomError(error.code,message) from None
