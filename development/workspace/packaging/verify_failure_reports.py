"""Actual local HTTP receipt-loss tests; never contacts GitHub or sends game data."""
import copy,json,socket,tempfile,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import Request,urlopen
from unittest.mock import patch
from types import SimpleNamespace
from failure_reports import FailureOutbox,event,issue,key,GitHub,packaged_version,REPOSITORY

checks=[]
def check(label,value):
    assert value,label
    checks.append(label)
def rejects(label,fn):
    try:fn()
    except (ValueError,TypeError,UnicodeError):check(label,True)
    else:raise AssertionError(label)

taint='private-name C:/Users/person/decks SECRET#invite-token'
for version in [taint,'1.2.3\n'+taint,'１.２.３',None,'x'*65]:rejects('Rejects non-version report input '+str(len(checks)),lambda v=version:event(v,'RULES_ENGINE_EXITED'))
rejects('Arbitrary error text cannot become a failure code',lambda:event('1.2.3',taint))
rejects('Unexpected event fields cannot become issue text',lambda:issue(dict(version='1.2.3',code='RULES_ENGINE_EXITED',log=taint)))
value=event('1.2.3','RULES_ENGINE_EXITED');payload=issue(value)
check('Only version and allowlisted code enter the fixed public issue',set(value)=={'version','code'} and taint not in json.dumps(payload) and key(value) in payload['body'])

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def answer(self,value):
        raw=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):self.answer(self.server.rows)
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));self.server.received.append(data)
        row=dict(number=len(self.server.rows)+1,html_url='https://github.com/'+REPOSITORY+'/issues/'+str(len(self.server.rows)+1),**data)
        self.server.rows.append(row)
        if self.server.drop:self.server.drop=False;self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
        self.answer(row)

class FakeHTTP:
    available=True
    def __init__(self,url):self.url=url
    def ready(self):return self.available
    def find(self,value):
        with urlopen(self.url,timeout=2) as r:rows=json.load(r)
        return next((r for r in rows if r['body']==issue(value)['body']),None)
    def create(self,value):
        with urlopen(Request(self.url,data=json.dumps(issue(value)).encode(),headers={'Content-Type':'application/json'}),timeout=2) as r:return json.load(r)

server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.rows=[];server.received=[];server.drop=True
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    with tempfile.TemporaryDirectory(prefix='forge-reports-') as temp:
        root=Path(temp);out=FailureOutbox(root/'outbox','1.2.3');publisher=FakeHTTP('http://127.0.0.1:'+str(server.server_port))
        check('First failure is durably queued',out.record('RULES_ENGINE_EXITED'))
        check('Repeated same version/code is locally deduplicated',not out.record('RULES_ENGINE_EXITED') and len(out.rows())==1)
        publisher.available=False;check('Missing sign-in preserves pending reports',out.flush(publisher)=='publisher-unavailable' and out.rows()[0][1]['status']=='queued')
        publisher.available=True
        try:out.flush(publisher)
        except OSError:pass
        else:raise AssertionError('Expected actual HTTP receipt loss')
        check('POST uncertainty is durable before its receipt is known',out.rows()[0][1]['status']=='attempted' and len(server.rows)==1)
        restarted=FailureOutbox(root/'outbox','1.2.3');restarted.flush(publisher)
        check('Restart reconciles the accepted issue without another POST',len(server.received)==1 and restarted.rows()[0][1]['status']=='sent')
        check('Repeated flush does not resend a delivered issue',restarted.flush(publisher)=='empty' and len(server.received)==1)
        second=FailureOutbox(root/'second-install','1.2.3');second.record('RULES_ENGINE_EXITED');second.flush(publisher)
        check('An existing identical public issue deduplicates another local installation',second.rows()[0][1]['status']=='sent' and len(server.received)==1)
        class NotReceived(FakeHTTP):
            def create(self,value):raise OSError('No receipt, no known delivery')
        unknown=FailureOutbox(root/'unknown','1.2.4');unknown.record('RULES_ENGINE_EXITED')
        try:unknown.flush(NotReceived(publisher.url))
        except OSError:pass
        unknown.flush(publisher)
        check('Uncertain delivery is never blindly resent even when no issue is found',unknown.rows()[0][1]['status']=='attempted' and len(server.received)==1)
        rate=FailureOutbox(root/'rate','1.2.5')
        for i,code in enumerate(['RULES_ENGINE_EXITED','RULES_START_TIMEOUT','RULES_FIDELITY_GAP']):rate.record(code);rate.flush(publisher,now=100000+i*601)
        check('Three sufficiently spaced reports can be delivered',sum(r['status']=='sent' for _,r in rate.rows())==3)
        rate.record('NATIVE_DISPLAY_FAILED');before=len(server.received)
        check('Daily cap preserves fourth report without posting',rate.flush(publisher,now=102000)=='rate-limited' and len(server.received)==before)
        spaced=FailureOutbox(root/'spaced','1.2.6');spaced.record('RULES_ENGINE_EXITED');spaced.flush(publisher,now=100000);spaced.record('RULES_START_TIMEOUT');before=len(server.received)
        check('Ten-minute interval prevents a failure burst',spaced.flush(publisher,now=100001)=='rate-limited' and len(server.received)==before)
        bounded=FailureOutbox(root/'bounded','1.0.0')
        for i in range(64):(bounded.folder/(str(i)+'.json')).write_text('preserved foreign evidence')
        check('Outbox storage is bounded without deleting old evidence',not bounded.record('RULES_ENGINE_EXITED') and len(list(bounded.folder.glob('*.json')))==64)
        wrong=FailureOutbox(root/'wrong-version','1.2.3');wrong.record('RULES_ENGINE_EXITED');wrong.version='1.2.3-'+taint.replace(' ','-').replace('/','-').replace(':','-').replace('#','-')
        rejects('An outbox cannot upload a version other than its package-pinned version',wrong.rows)
        check('Actual HTTP bodies contain no local report bookkeeping',all(set(r)=={'title','body'} and taint not in json.dumps(r) and 'created' not in r['body'] for r in server.received))
        rejects('Unexpected issue URLs are rejected',lambda:FailureOutbox.receipt(dict(number=1,html_url='https://example.test/private',body=payload['body']),dict(event=value)))
        app=root/'package';app.mkdir();(app/'release-info.json').write_text(json.dumps(dict(version='1.2.3')))
        import hashlib
        manifest=dict(version='1.2.3',files={'release-info.json':hashlib.sha256((app/'release-info.json').read_bytes()).hexdigest()});(app/'release-manifest.json').write_text(json.dumps(manifest))
        check('Only matching package-pinned version is selected',packaged_version(app)=='1.2.3')
        (app/'release-info.json').write_text(json.dumps(dict(version=taint)));check('Altered release metadata is not used for reports',packaged_version(app) is None)
        calls=[]
        with patch('failure_reports.shutil.which',return_value='gh.exe'),patch('failure_reports.subprocess.run',side_effect=lambda args,**kw:(calls.append((args,kw)) or SimpleNamespace(returncode=0,stdout='{}'))):GitHub().create(value)
        args,kwargs=calls[0]
        check('CLI uses fixed GitHub host/repository and sanitized stdin JSON',args[:4]==['gh.exe','api','--hostname','github.com'] and 'repos/'+REPOSITORY+'/issues' in args and json.loads(kwargs['input'])==payload and kwargs.get('shell') is None)
finally:server.shutdown();server.server_close();thread.join(timeout=3)
print(json.dumps(dict(passed=True,checks=len(checks),results=checks,scope='Actual local HTTP receipt loss/reconciliation and bounded private fixtures; no real GitHub delivery or game installation.')))
