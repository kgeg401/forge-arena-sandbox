"""One private internet match. Native clients stay isolated; this worker owns I/O."""
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,json,os,re,subprocess,threading,time,uuid
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from urllib.request import urlopen
from client_service import atomic,read,NativeLifetime
from multiplayer_room import Room,RoomClient,RoomServer,RoomError
from multiplayer_rules import RulesRoom
from multiplayer_view import project_view,restore_action
from profile_identity import selected_identity,public_identity

TUNNEL_VERSION='2026.10.7'
TUNNEL_SHA='2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def maybe(path):
    try:return read(path)
    except (FileNotFoundError,PermissionError,json.JSONDecodeError):return None
def invite(value):
    p=urlsplit(value.strip());url=urlunsplit((p.scheme,p.netloc,p.path,p.query,''))
    RoomClient(url,p.fragment)
    return url,p.fragment

def compatibility(root):
    root=Path(root);lab=root/'native-lab';manifest=read(lab/'bridge-card-manifest.json')
    from arena_compat import validated_family
    family,build=validated_family(lab)
    if manifest['sourceDatabaseSha256']!=build['databaseSha256']:raise ValueError('Multiplayer catalogue does not match the validated installed Arena build')
    semantic={k:manifest[k] for k in ('cards','keywordAbilityIds','typeEnumIds','sourceForgeScriptsSha256','policySha256')}
    classes={p.name:digest(p) for p in sorted((root/'build/ForgeBackend/classes').glob('ForgeLandEngine*.class'))}
    if not classes:raise ValueError('Missing two-player rules build')
    transport={name:digest(Path(__file__).with_name(name)) for name in ('multiplayer_session.py','multiplayer_room.py','multiplayer_rules.py','multiplayer_view.py','profile_identity.py','client_service.py')}
    managed={'reviewedArenaFamily':family}
    return dict(protocol=1,rules=hashlib.sha256(json.dumps(classes,sort_keys=True).encode()).hexdigest(),forge=digest(root/'forge-runtime/forge.jar'),gson=digest(root/'forge-runtime/gson.jar'),native=digest(lab/'BepInEx/plugins/ForgeArenaSandbox/NativeHost.dll'),catalogue=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest(),transport=hashlib.sha256(json.dumps(transport,sort_keys=True).encode()).hexdigest(),managed=hashlib.sha256(json.dumps(managed,sort_keys=True).encode()).hexdigest(),humanChoices=manifest.get('fullHumanChoices') is True)

def validated_deck(value):
    from deck_import import parse_commander
    if not isinstance(value,dict) or set(value)-{'name','format','commander','cards','experimental'}:raise ValueError('Invalid Commander deck')
    lines=['Commander',str(value['commander']['count'])+' '+value['commander']['name'],'Deck']
    lines.extend(str(c['count'])+' '+c['name'] for c in value['cards'])
    result=parse_commander('\n'.join(lines),value['name']);result.pop('experimental',None)
    return result

def native_action(native,session,role):
    if not re.fullmatch(r'(?:arena|rules)_[a-f0-9]{32}',native.get('id','')) or native.get('session')!=session or type(native.get('seat')) is not int or native['seat']!=1:raise ValueError('Wrong native match input')
    return restore_action({k:native[k] for k in ('op','forgeId','abilityId','assignments','autoOrderTriggers','autoChooseReplacementEffects') if k in native},role)

class Session:
    def __init__(self,config,ipc,deck):
        self.config=config;self.root=Path(config['privateRoot']);self.ipc=Path(ipc);self.deck=validated_deck(deck)
        self.identity=selected_identity(self.root/'native-lab')
        self.children=[];self.logs=[];self.room=None;self.server=None;self.server_thread=None;self.client=None
        self.broker=None;self.engine=None;self.last_revision=-1;self.pending=None;self.ack=0;self.terminal=False
        self.closed=False;self.context={};self.reports_enabled=False
        context=maybe(self.ipc/'network-context.json')
        if context is not None:
            if not isinstance(context,dict) or set(context) not in ({'schema','clientSession','requestId'},{'schema','clientSession','requestId','reportsEnabled'}) or type(context.get('reportsEnabled',False)) is not bool or type(context['schema']) is not int or context['schema']!=1 or any(not isinstance(context[k],str) or str(uuid.UUID(context[k]))!=context[k] for k in ('clientSession','requestId')):raise ValueError('Invalid native room context')
            self.context={k:context[k] for k in ('clientSession','requestId')}
            self.reports_enabled=context.get('reportsEnabled',False)
        self.compat=compatibility(self.root);self.started=time.monotonic();self.join_id=str(uuid.uuid4())
        atomic(self.ipc/'network-build.json',self.compat)
        for name in ('requests','responses'):(self.ipc/name).mkdir(exist_ok=True)
    def stopped(self):return (self.ipc/'stop.request').exists()
    def check_stop(self):
        if self.stopped():raise InterruptedError('Room closed by this player')
    def status(self,message,**extra):atomic(self.ipc/'network-status.json',dict(message=message,**self.context,**extra))
    def child(self,args,log):
        handle=log.open('w',encoding='utf8');self.logs.append(handle)
        process=subprocess.Popen(args,stdout=handle,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        self.children.append(process)
        owner=NativeLifetime(process.pid,args[0]);birth=owner.creation_ticks();owner.close()
        previous=maybe(self.ipc/'network-children.json') or {'children':[]}
        previous['children'].append(dict(pid=process.pid,executable=str(args[0]),creationTicks=birth))
        atomic(self.ipc/'network-children.json',previous);return process
    def tunnel_binary(self):
        target=self.root/'network-tools'/('cloudflared-'+TUNNEL_VERSION+'.exe');target.parent.mkdir(exist_ok=True)
        if target.exists():
            if digest(target)!=TUNNEL_SHA:raise ValueError('Internet helper checksum differs; file preserved')
            return target
        self.status('Downloading the verified internet connection helper…')
        pending=target.with_suffix('.download')
        url='https://github.com/cloudflare/cloudflared/releases/download/'+TUNNEL_VERSION+'/cloudflared-windows-amd64.exe'
        with urlopen(url,timeout=15) as response,pending.open('wb') as output:
            total=0
            while True:
                self.check_stop();chunk=response.read(1024*1024)
                if not chunk:break
                total+=len(chunk)
                if total>80*1024*1024:raise ValueError('Internet helper exceeds its download limit')
                output.write(chunk)
        if digest(pending)!=TUNNEL_SHA:raise ValueError('Internet helper download failed checksum verification')
        pending.replace(target);return target
    def host(self):
        self.room=Room(self.compat,require_presentation=True);self.room.profile(self.room.host_token,self.identity);self.room.deck(self.room.host_token,self.deck)
        if self.context and self.reports_enabled:self.room.failure_callback=self.queue_peer_failure
        self.server=RoomServer(self.room);self.server_thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.server_thread.start()
        binary=self.tunnel_binary();log=self.ipc/'tunnel.log';process=self.child([str(binary),'tunnel','--no-autoupdate','--protocol','http2','--url','http://127.0.0.1:'+str(self.server.server_port)],log)
        self.status('Creating a private internet room…');deadline=time.monotonic()+120;url=None
        while time.monotonic()<deadline:
            self.check_stop()
            if process.poll() is not None:raise RuntimeError('Internet helper exited; see the match connection log')
            text=log.read_text(encoding='utf8',errors='replace');match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',text)
            if match and 'Registered tunnel connection' in text:
                url=match.group()
                try:
                    if RoomClient(url,self.room.host_token).call('/v1/state')['phase']=='waiting-for-player':break
                except OSError:pass
            time.sleep(.3)
        else:raise TimeoutError('The private internet address did not become ready; create a new room')
        self.role=1;self.client=RoomClient('http://127.0.0.1:'+str(self.server.server_port),self.room.host_token)
        self.status('Copy the invitation to your brother. Keep this PC and client open.',invitation=url+'#'+self.room.invite)
    def join(self,code):
        url,token=invite(code);self.status('Joining the private room…')
        deadline=time.monotonic()+90
        while True:
            self.check_stop()
            try:
                response=RoomClient(url,token).call('/v1/join',dict(id=self.join_id,protocol=1,compatibility=self.compat))
                self.role=2;self.client=RoomClient(url,response['token']);self.client.call('/v1/profile',self.identity);self.client.call('/v1/deck',self.deck)
                self.status('Deck locked. Waiting for the host to start the match…');return
            except OSError:
                if time.monotonic()>=deadline:raise TimeoutError('The room could not finish joining. Ask the host to create a new room.') from None
                self.status('Connection interrupted while joining. Keeping your invitation and trying again…');time.sleep(.5)
    def start_rules(self):
        decks={role:validated_deck(self.room.decks[role]) for role in (1,2)}
        rules=self.ipc/'host-rules';rules.mkdir();atomic(rules/'scenario.json',dict(scenario='commander-human-duel',localDeck=decks[1],opponentDeck=decks[2],startingPlayerPolicy='coin-toss'))
        classes=self.root/'build/ForgeBackend/classes';runtime=self.root/'forge-runtime'
        cp=';'.join(str(p) for p in (classes,runtime/'forge.jar',runtime/'gson.jar'))
        self.engine=self.child([str(Path(self.config['javaHome'])/'bin/java.exe'),'-Xmx1024m','-XX:ActiveProcessorCount=2','-Djava.awt.headless=false','-Dfile.encoding=UTF-8','-cp',cp,'ForgeLandEngine',str(runtime),str(rules)],rules/'engine.log')
        self.rules_started=time.monotonic();self.status('Both decks are ready. Starting Commander…')
    def projected(self,packet):
        state=project_view(packet['state'],self.role);state['networkMatch']=True;state['networkRevision']=packet['revision']
        profiles={int(k):public_identity(v) for k,v in packet.get('profiles',{}).items()}
        if set(profiles)-{1,2}:raise ValueError('Unknown cosmetic player seat')
        for player in state.get('players',[]):
            original=self.role if player['seat']==1 else 3-self.role
            if original in profiles:player.update(profiles[original])
        return state
    def tick(self):
        if self.room:
            if self.engine is None and set(self.room.decks)=={1,2}:self.start_rules()
            if self.engine is not None:
                if self.engine.poll() is not None:raise RuntimeError('The host rules engine exited; match log was retained')
                rules=self.ipc/'host-rules'
                if self.broker is None and (rules/'requests').is_dir():self.broker=RulesRoom(self.room,rules)
                if self.broker:self.broker.tick()
                if self.room.session is None and time.monotonic()-self.rules_started>100:raise TimeoutError('Two-player rules startup did not finish')
        packet=self.client.call('/v1/state')
        if packet['state'] is None:return
        state=self.projected(packet);self.terminal=state['gameOver']
        if packet['revision']>self.last_revision:
            atomic(self.ipc/'state.json',state)
            if self.last_revision>=0:atomic(self.ipc/'network-view.json',state)
            self.last_revision=packet['revision']
            self.status('Connected — Commander match in progress',boardReady=True)
        presented=maybe(self.ipc/'network-presented.json')
        if presented and presented.get('session')==packet['session'] and self.ack<presented.get('revision',0)<=packet['revision']:
            self.client.call('/v1/ack',presented);self.ack=presented['revision']
        if self.pending is None:
            paths=sorted((self.ipc/'requests').glob('*.json'))
            if paths:
                path=paths[0];native=read(path)
                action=native_action(native,packet['session'],self.role)
                command=dict(id=str(uuid.uuid4()),session=packet['session'],revision=packet['revision'],decisionToken=(packet['state'].get('decision') or {}).get('token'),action=action)
                # Retain the same envelope before I/O: a lost reply is not a new action.
                self.pending=(native,command,path)
        if self.pending is not None:
            native,command,path=self.pending
            try:response=self.client.call('/v1/command',command)
            except RoomError as error:response=dict(status='completed',accepted=False,reason=str(error))
            if response['status']=='completed' and (not response['accepted'] or packet['revision']>command['revision']):
                atomic(self.ipc/'responses'/(native['id']+'.json'),dict(id=native['id'],session=native['session'],accepted=response['accepted'],reason=response['reason'],state=state))
                path.unlink(missing_ok=True);self.pending=None
    def run(self,choice):
        try:
            if choice['mode']=='host':self.host()
            elif choice['mode']=='join':self.join(choice['invitation'])
            else:raise ValueError('Choose Host or Join')
            missing_since=None
            while not self.stopped():
                if self.terminal and self.pending is None and self.ack>=self.last_revision:
                    self.wait_for_home();break
                try:self.relay_failure();self.tick();missing_since=None
                except RoomError as error:
                    if self.terminal:self.wait_for_home();break
                    raise
                except OSError:
                    if self.terminal:self.wait_for_home();break
                    missing_since=missing_since or time.monotonic();self.status('Connection interrupted. Keeping this match; trying to reconnect…')
                    if time.monotonic()-missing_since>90:raise TimeoutError('The room could not reconnect. Both players should create a new room.')
                time.sleep(.08)
        except InterruptedError:pass
        finally:self.close()
    def queue_peer_failure(self,code):
        atomic(self.ipc/'peer-failure.json',dict(schema=1,**self.context,code=code))
    def relay_failure(self):
        if getattr(self,'role',None)!=2 or not getattr(self,'context',None) or getattr(self,'_failure_relayed',False):return
        if time.monotonic()<getattr(self,'_failure_poll_at',0):return
        self._failure_poll_at=time.monotonic()+1
        try:
            path=self.root/'native-lab/client-failure.json'
            if path.stat().st_size>4096:return
            value=read(path)
            if not isinstance(value,dict) or set(value)!={'schema','session','requestId','code'} or type(value['schema']) is not int or value['schema']!=1 or value['session']!=self.context['clientSession'] or value['requestId']!=self.context['requestId'] or value['code']!='NATIVE_DISPLAY_FAILED':return
            result=self.client.call('/v1/report',dict(code='NATIVE_DISPLAY_FAILED'))
            self._failure_relayed=isinstance(result,dict) and result.get('queued') is True
        except (OSError,ValueError,KeyError,TypeError):pass
    def wait_for_home(self):
        # The finished result remains usable after the host closes its tunnel.
        self.status('Match finished. Return Home to play again.',boardReady=True)
        while not self.stopped():time.sleep(.2)
    def close(self):
        if self.closed:return
        self.closed=True
        if self.client:
            try:self.client.call('/v1/leave',{})
            except (OSError,ValueError):pass
        if self.room:self.room.close()
        if self.server:self.server.shutdown();self.server.server_close();self.server_thread.join(timeout=3)
        rules=self.ipc/'host-rules'
        if rules.is_dir():(rules/'stop.request').write_text('Private room closed')
        for child in reversed(self.children):
            if child.poll() is None:
                try:child.wait(timeout=5 if child==self.engine else .1)
                except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5)
        for handle in self.logs:handle.close()
        atomic(self.ipc/'network-cleanup.json',dict(childrenExited=all(p.poll() is not None for p in self.children)))

def main(args):
    config=read(args.config);os.environ['FORGE_ARENA_CONFIG']=str(Path(args.config).resolve())
    app=Path(__file__).parent;backend=app/'ForgeBackend'
    if not backend.is_dir():backend=app.parent/'ForgeBackend'
    sys.path.insert(0,str(backend));ipc=Path(args.ipc)
    if ipc.resolve()!=(Path(config['privateRoot'])/'native-lab/forge-ipc').resolve():raise ValueError('Wrong private match directory')
    session=None
    try:
        from multiplayer_lobby import lobby
        session=Session(config,ipc,read(ipc/'network-deck.json'))
        lobby(ipc,session.deck['name'],session.run,context=session.context)
    except Exception as error:
        category='ROOM_CLOSED' if isinstance(error,RoomError) and error.status==410 else 'NETWORK_SESSION_FAILED'
        try:
            atomic(ipc/'engine-error.json',dict(reason=str(error),category=category))
            atomic(ipc/'network-status.json',dict(message=str(error),error=True,**(session.context if session else {})))
        except OSError:pass
        raise
    finally:
        if session:session.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--ipc',required=True);main(parser.parse_args())
