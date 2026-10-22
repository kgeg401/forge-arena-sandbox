"""Own local client coordinator. One bounded Forge process for one native session.

The isolated game cannot start subprocesses or contact a match server. This
coordinator accepts only local deck IDs and two fixed queue identifiers; all
decks are revalidated independently before Forge sees them.
"""
import sys
sys.dont_write_bytecode=True
import argparse,ctypes,json,os,subprocess,time,uuid
from ctypes import wintypes
from datetime import datetime,timezone
from pathlib import Path
from contextlib import contextmanager


class RequestRejected(ValueError):
    """A stale/duplicate request must not cancel a healthy queued or live game."""


@contextmanager
def service_lock(path,wait_seconds=15):
    import msvcrt
    with Path(path).open('a+b') as handle:
        handle.seek(0)
        if not handle.read(1):handle.write(b'0');handle.flush()
        handle.seek(0)
        deadline=time.monotonic()+wait_seconds
        while True:
            try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:
                if time.monotonic()>=deadline:raise RuntimeError('A local match coordinator already owns this client')
                time.sleep(.15)
        try:yield
        finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)


def read(path):
    with Path(path).open(encoding='utf-8-sig') as file:return json.load(file)


def atomic(path,value):
    path=Path(path);pending=path.with_suffix(path.suffix+'.pending')
    with pending.open('w',encoding='utf8') as file:
        json.dump(value,file,ensure_ascii=False,indent=2);file.flush();os.fsync(file.fileno())
    # Native readers allow replacement. A transient scan must not lose the state.
    for attempt in range(12):
        try:pending.replace(path);return
        except PermissionError:
            if attempt==11:raise
            time.sleep(.025)


def parse_local_deck(deck,catalog,queue):
    from deck_import import parse_brawl,parse_deck
    if queue not in ('SandboxPractice','SandboxBrawl'):raise ValueError('Unknown local bot queue')
    if not isinstance(deck,dict) or not isinstance(deck.get('name'),str):raise ValueError('Invalid saved deck')
    lines=[]
    for pile,title in (('commander','Commander'),('companion','Companion'),('main','Deck'),('sideboard','Sideboard')):
        cards=deck.get(pile)
        if not isinstance(cards,dict):raise ValueError('Saved deck is missing '+pile)
        if pile!='main' and not cards:continue
        lines.append(title)
        for key,count in cards.items():
            if key not in catalog or type(count) is not int or not 1<=count<=999:raise ValueError('Unknown or invalid saved printing: '+str(key))
            lines.append(str(count)+' '+catalog[key]['name'])
    parser=parse_brawl if queue=='SandboxBrawl' else parse_deck
    return parser('\n'.join(lines),deck['name'])


class NativeLifetime:
    """An open kernel handle prevents PID recycling from extending ownership."""
    def __init__(self,pid,executable,allow_termination=False):
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];api.OpenProcess.restype=wintypes.HANDLE
        api.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
        api.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];api.WaitForSingleObject.restype=wintypes.DWORD
        api.CloseHandle.argtypes=[wintypes.HANDLE]
        api.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT];api.TerminateProcess.restype=wintypes.BOOL
        handle=api.OpenProcess(0x100000|0x1000|(1 if allow_termination else 0),False,pid)
        if not handle:raise RuntimeError('Native client is not running')
        try:
            buf=ctypes.create_unicode_buffer(32768);length=wintypes.DWORD(len(buf))
            if not api.QueryFullProcessImageNameW(handle,0,buf,ctypes.byref(length)) or Path(buf.value).resolve()!=Path(executable).resolve():raise ValueError('Native process path differs from the isolated client')
        except Exception:api.CloseHandle(handle);raise
        self.api=api;self.handle=handle;self.allow_termination=allow_termination
    def alive(self):return self.api.WaitForSingleObject(self.handle,0)==258
    def terminate(self):
        if not self.allow_termination:raise RuntimeError('This lifetime handle is read-only')
        if self.alive() and not self.api.TerminateProcess(self.handle,1):raise ctypes.WinError(ctypes.get_last_error())
    def close(self):self.api.CloseHandle(self.handle)


class Coordinator:
    def __init__(self,config,app,session,pid):
        self.config=config;self.app=Path(app).resolve();self.root=Path(config['privateRoot']).resolve();self.lab=self.root/'native-lab'
        self.session=str(uuid.UUID(session));self.pid=pid
        boundary=read(self.lab/'sandbox-lab.json');receipt=read(self.lab/'launch-receipt.json')
        if receipt['pid']!=pid or not receipt.get('appContainer') or receipt.get('capabilityCount')!=0 or receipt.get('networkCapability') or Path(receipt['executable']).resolve()!=self.lab/'MTGA.exe':raise ValueError('Coordinator requires the current isolated native launch')
        if not boundary:raise ValueError('Isolated lab boundary is missing')
        self.process=None;self.log=None;self.request_id=None;self.phase='idle';self.deadline=0.;self.after_stop='idle';self.seen=set();self.error=None
        self.last_snapshot=None;self.heartbeat_at=0.
        self.ipc=self.lab/'forge-ipc';self.state_path=self.lab/'client-service-status.json'
        self.catalog={str(c['grpId']):c for c in read(self.lab/'deck-catalog.json')['cards']}
        self.publish('idle','Ready for a local bot match')
    def publish(self,phase,message,**extra):
        self.phase=phase
        value=dict(schema=1,session=self.session,nativePid=self.pid,utc=datetime.now(timezone.utc).isoformat(),requestId=self.request_id,phase=phase,message=message,enginePid=self.process.pid if self.process else None,**extra)
        self.last_snapshot=value;self.heartbeat_at=time.monotonic()+3
        atomic(self.state_path,value)
    def start(self,request):
        if self.process and self.process.poll() is None:raise RequestRejected('A local match is already running. Finish or cancel it first.')
        queue=request.get('queue');deck_id=str(uuid.UUID(request.get('deckId','')))
        library=read(self.lab/'local-profile/decks.json')
        matches=[d for d in library['decks'] if str(uuid.UUID(d['id']))==deck_id]
        if len(matches)!=1:raise ValueError('The selected saved deck no longer exists')
        deck=parse_local_deck(matches[0],self.catalog,queue)
        from deck_import import read_deck
        opponent=read_deck(self.app/'decks'/('Brawl-Isamaru-Bot.txt' if queue=='SandboxBrawl' else 'White-Lifegain.txt'),'arena-brawl' if queue=='SandboxBrawl' else 'practice')
        self.request_id=request['id'];self.error=None
        self.publish('starting','Starting the local Forge bot…',queue=queue,deckName=deck['name'])
        if self.ipc.exists():
            metadata=self.ipc/'backend-process.json'
            if metadata.exists():
                old=read(metadata)
                check=subprocess.run(['powershell.exe','-NoProfile','-Command',f"Get-CimInstance Win32_Process -Filter 'ProcessId={int(old['pid'])}' | Select-Object -ExpandProperty CommandLine"],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
                if 'ForgeLandEngine' in check.stdout and str(self.ipc).casefold() in check.stdout.casefold():raise RuntimeError('A previous rules engine is still running; close the client and retry')
            archived=self.lab/('forge-ipc-evidence-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            self.ipc.rename(archived)
        self.ipc.mkdir()
        atomic(self.ipc/'scenario.json',dict(scenario='brawl-duel' if queue=='SandboxBrawl' else 'custom-duel',localDeck=deck,opponentDeck=opponent))
        (self.lab/'enable-forge-land-test.flag').write_text('Authoritative local Forge match')
        cp=';'.join(str(self.root/p) for p in ('build/ForgeBackend/classes','forge-runtime/forge.jar','forge-runtime/gson.jar'))
        self.log=(self.ipc/'engine.log').open('w',encoding='utf8')
        self.process=subprocess.Popen([str(Path(self.config['javaHome'])/'bin/java.exe'),'-Xmx1024m','-XX:ActiveProcessorCount=2','-Djava.awt.headless=false','-cp',cp,'ForgeLandEngine',str(self.root/'forge-runtime'),str(self.ipc)],cwd=self.root/'forge-runtime',stdout=self.log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        atomic(self.ipc/'backend-process.json',dict(pid=self.process.pid,**{'class':'ForgeLandEngine'},ipc=str(self.ipc),started=time.time(),clientSession=self.session,requestId=self.request_id))
        self.deadline=time.monotonic()+90
    def stop(self,after='idle'):
        if self.phase=='stopping':return
        self.after_stop=after
        if self.process and self.process.poll() is None:
            (self.ipc/'stop.request').write_text('Client session finished or cancelled')
            self.deadline=time.monotonic()+12;self.publish('stopping','Closing the local match…')
        else:self.stopped()
    def stopped(self):
        if self.log:self.log.close();self.log=None
        self.process=None
        self.publish(self.after_stop,self.error if self.after_stop=='error' and self.error else 'Match cancelled' if self.after_stop=='cancelled' else 'Ready for another local bot match')
    def handle(self,request):
        if request.get('schema')!=1 or request.get('session')!=self.session:raise RequestRejected('Stale client session request rejected')
        try:request_id=str(uuid.UUID(request.get('id','')))
        except (ValueError,TypeError,AttributeError):raise RequestRejected('Invalid local request identity')
        if request_id in self.seen:return
        self.seen.add(request_id)
        if len(self.seen)>4096:raise ValueError('Client request limit reached; restart the client')
        action=request.get('action')
        if action=='start':
            if not self.process or self.process.poll() is not None:self.request_id=request_id
            self.start(request)
        elif action in ('cancel','match-ended'):
            if request.get('matchRequestId')!=self.request_id:raise RequestRejected('Stale match cancellation rejected')
            self.stop('cancelled' if action=='cancel' else 'idle')
        elif action=='match-started':
            if request.get('matchRequestId')!=self.request_id or self.phase!='ready':raise RequestRejected('Stale match acknowledgment rejected')
            self.publish('playing','Local Forge bot match in progress')
        else:raise RequestRejected('Unknown client action')
    def tick(self,process_requests=True):
        if time.monotonic()>=self.heartbeat_at and self.last_snapshot:
            self.last_snapshot['utc']=datetime.now(timezone.utc).isoformat();atomic(self.state_path,self.last_snapshot);self.heartbeat_at=time.monotonic()+3
        request_path=self.lab/'client-service.request.json'
        if process_requests and request_path.exists():
            try:
                if request_path.stat().st_size>65536:raise ValueError('Local request exceeds 64 KB')
                request=read(request_path);request_path.unlink();self.handle(request)
            except RequestRejected as error:
                request_path.unlink(missing_ok=True);atomic(self.lab/'client-service-rejection.json',dict(utc=datetime.now(timezone.utc).isoformat(),reason=str(error)))
            except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:
                request_path.unlink(missing_ok=True)
                # Do not destroy a healthy match because of an invalid request.
                if self.process and self.phase in ('playing','ready'):atomic(self.lab/'client-service-rejection.json',dict(utc=datetime.now(timezone.utc).isoformat(),reason=str(error)))
                elif self.process and self.process.poll() is None:
                    self.error=str(error);self.stop('error')
                else:self.publish('error',str(error))
        if self.phase=='starting':
            if self.process.poll() is not None:
                self.publish('error','Forge could not start. See '+str(self.ipc/'engine.log'));self.stopped_log()
            elif time.monotonic()>self.deadline:
                self.error='Forge startup timed out; the engine was stopped';self.stop('error')
            elif (self.ipc/'state.json').exists():
                try:
                    state=read(self.ipc/'state.json')
                    if state.get('fidelityGap'):raise ValueError(state['fidelityGap'])
                    if state.get('session') and state.get('decision'):
                        self.publish('ready','Bot ready — opening the Arena board',engineSession=state['session'],scenario=state['scenario'])
                except (OSError,json.JSONDecodeError):pass
                except ValueError as error:self.error=str(error);self.stop('error')
        elif self.phase=='stopping':
            if not self.process or self.process.poll() is not None:self.stopped()
            elif time.monotonic()>self.deadline:
                # This Popen object is the exact process created by this coordinator.
                self.process.terminate();self.process.wait(timeout=10);self.stopped()
        elif self.phase in ('ready','playing') and self.process and self.process.poll() is not None:
            self.publish('error','The local rules engine exited. Return Home and start another match.');self.stopped_log()
    def stopped_log(self):
        if self.log:self.log.close();self.log=None
    def close(self):
        self.stop('closed');end=time.monotonic()+15
        while self.phase=='stopping' and time.monotonic()<end:self.tick(process_requests=False);time.sleep(.1)
        self.stopped_log()


def main(args):
    config=read(args.config);os.environ['FORGE_ARENA_CONFIG']=str(Path(args.config).resolve())
    app=Path(__file__).resolve().parent
    backend=app/'ForgeBackend'
    if not backend.is_dir():backend=app.parent/'ForgeBackend'
    sys.path.insert(0,str(backend))
    lab=Path(config['privateRoot'])/'native-lab'
    lifetime=NativeLifetime(args.native_pid,lab/'MTGA.exe')
    coordinator=None
    try:
        with service_lock(lab/'client-service.lock'):
            coordinator=Coordinator(config,backend.parent,args.session,args.native_pid)
            try:
                while lifetime.alive():coordinator.tick();time.sleep(.15)
            finally:coordinator.close();coordinator=None
    finally:
        if coordinator:coordinator.close()
        lifetime.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--native-pid',required=True,type=int);parser.add_argument('--session',required=True)
    main(parser.parse_args())
