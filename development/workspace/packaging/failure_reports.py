"""Bounded, version/code-only reports using the player's own GitHub CLI sign-in."""
import hashlib,json,os,re,shutil,subprocess,threading,time,uuid
from pathlib import Path

REPOSITORY='kgeg401/forge-arena-sandbox'
CODES=frozenset({'RULES_ENGINE_EXITED','NETWORK_SESSION_FAILED','RULES_START_TIMEOUT','RULES_FIDELITY_GAP','NATIVE_DISPLAY_FAILED','REPORTER_SELF_TEST'})

def event(version,code):
    if not isinstance(version,str) or len(version)>64 or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?',version):raise ValueError('Invalid report version')
    if not isinstance(code,str) or code not in CODES:raise ValueError('Unknown failure code')
    return dict(version=version,code=code)

def key(value):return hashlib.sha256((value['version']+'\n'+value['code']).encode('ascii')).hexdigest()

def issue(value):
    value=event(**value)
    return dict(title='Client report: '+value['code']+' ('+value['version']+')',
                body='Automatic technical report.\n\nVersion: '+value['version']+'\nFailure code: '+value['code']+'\n\n<!-- forge-client-report:'+key(value)+' -->')

def write(path,value):
    pending=path.with_name(path.name+'.'+uuid.uuid4().hex+'.pending')
    try:
        with pending.open('x',encoding='utf8') as f:json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(pending,path)
    finally:pending.unlink(missing_ok=True)

def packaged_version(app):
    app=Path(app)
    try:
        manifest=json.loads((app/'release-manifest.json').read_text(encoding='utf8'))
        raw=(app/'release-info.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=manifest['files']['release-info.json']:return None
        version=json.loads(raw)['version']
        if version!=manifest['version']:return None
        return event(version,'RULES_ENGINE_EXITED')['version']
    except (OSError,ValueError,KeyError,TypeError):return None

class GitHub:
    def __init__(self,stop=None):self.executable=shutil.which('gh');self.stop=stop
    def call(self,*args,payload=None):
        if self.stop is not None and self.stop.is_set():raise InterruptedError('Report publisher closed')
        if not self.executable:raise OSError('GitHub CLI is not installed')
        result=subprocess.run([self.executable,'api','--hostname','github.com',*args],input=json.dumps(payload) if payload is not None else None,
                              text=True,capture_output=True,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode:raise OSError('GitHub request did not complete')
        return json.loads(result.stdout) if result.stdout.strip() else None
    def ready(self):
        if not self.executable:return False
        try:self.call('user','--silent');return True
        except (OSError,ValueError,subprocess.TimeoutExpired):return False
    def find(self,value):
        expected=issue(value);deadline=time.monotonic()+15
        for page in range(1,11):
            if time.monotonic()>deadline:raise OSError('Issue lookup exceeded its time bound')
            rows=self.call('repos/'+REPOSITORY+'/issues?state=all&per_page=100&page='+str(page))
            if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):raise ValueError('Invalid GitHub issue list')
            matches=[r for r in rows if not r.get('pull_request') and r.get('body')==expected['body'] and r.get('title')==expected['title']]
            if matches:return matches[0]
            if len(rows)<100:return None
        # An incomplete lookup must never authorize another issue creation.
        raise OSError('Issue reconciliation exceeded its bounded history')
    def create(self,value):return self.call('repos/'+REPOSITORY+'/issues','--method','POST','--input','-',payload=issue(value))

class FailureOutbox:
    def __init__(self,folder,version):
        self.folder=Path(folder);self.version=event(version,'RULES_ENGINE_EXITED')['version']
        self.folder.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock();self.delivery=threading.Lock()
    def record(self,code):
        value=event(self.version,code);path=self.folder/(key(value)+'.json')
        with self.lock:
            if path.exists():return False
            if len(list(self.folder.glob('*.json')))>=64:return False
            write(path,dict(schema=1,event=value,status='queued',created=time.time()))
        return True
    def rows(self):
        result=[]
        for path in sorted(self.folder.glob('*.json')):
            row=json.loads(path.read_text(encoding='utf8'));value=row['event']
            if type(row.get('schema')) is not int or row['schema']!=1 or value!=event(**value) or value['version']!=self.version or path.stem!=key(value) or row['status'] not in ('queued','attempted','sent'):raise ValueError('Invalid report outbox')
            result.append((path,row))
        return result
    @staticmethod
    def receipt(value,row):
        number=value.get('number') if isinstance(value,dict) else None
        if type(number) is not int or number<=0 or value.get('html_url')!='https://github.com/'+REPOSITORY+'/issues/'+str(number) or value.get('body')!=issue(row['event'])['body']:raise ValueError('Invalid issue receipt')
        return value['html_url']
    def flush(self,publisher,*,now=None):
        if not self.delivery.acquire(blocking=False):return 'busy'
        try:
            with self.lock:rows=self.rows()
            pending=[(p,r) for p,r in rows if r['status']!='sent']
            if not pending:return 'empty'
            if not publisher.ready():return 'publisher-unavailable'
            now=time.time() if now is None else now
            deadline=time.monotonic()+20
            attempts=[r['attempted'] for _,r in rows if 'attempted' in r]
            for path,row in pending:
                if time.monotonic()>deadline:return 'budget-limited'
                found=publisher.find(row['event'])
                if found:
                    row.update(status='sent',issueUrl=self.receipt(found,row))
                    with self.lock:write(path,row)
                    continue
                if row['status']=='attempted':continue
                if sum(t>now-86400 for t in attempts)>=3 or any(t>now-600 for t in attempts):return 'rate-limited'
                # Commit uncertainty BEFORE POST. An unknown outcome is reconciled,
                # never automatically replayed, even if the first send never arrived.
                row.update(status='attempted',attempted=now)
                with self.lock:write(path,row)
                attempts.append(now)
                result=publisher.create(row['event'])
                row.update(status='sent',issueUrl=self.receipt(result,row))
                with self.lock:write(path,row)
            return 'checked'
        finally:self.delivery.release()

class Reporter:
    """All network/CLI work stays off the native coordinator's polling thread."""
    def __init__(self,lab,version):
        self.outbox=FailureOutbox(Path(lab)/'failure-reports'/version,version);self.status=Path(lab)/'failure-report-status.json'
        self.stop=threading.Event();self.wake=threading.Event()
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def record(self,code):
        try:
            value=event(self.outbox.version,code)
            accepted=self.outbox.record(code) or (self.outbox.folder/(key(value)+'.json')).exists()
            if accepted:self.wake.set()
            return accepted
        except (OSError,ValueError,TypeError):return False
    def run(self):
        publisher=GitHub(self.stop)
        while not self.stop.is_set():
            self.wake.wait(60);self.wake.clear()
            if self.stop.is_set():break
            try:status=self.outbox.flush(publisher)
            except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired):status='delivery-unconfirmed'
            try:
                with self.outbox.lock:rows=self.outbox.rows()
                write(self.status,dict(schema=1,status=status,
                      queued=sum(r['status']=='queued' for _,r in rows),unconfirmed=sum(r['status']=='attempted' for _,r in rows),sent=sum(r['status']=='sent' for _,r in rows)))
            except (OSError,ValueError,KeyError,TypeError):pass
            # Repeated failures cannot turn a wakeup storm into GitHub traffic.
            self.stop.wait(30)
    def close(self):self.stop.set();self.wake.set();self.thread.join(timeout=11)
