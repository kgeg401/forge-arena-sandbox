"""Coordinator/report-worker wiring with authored faults; no game or GitHub writes."""
import copy,hashlib,json,tempfile,threading,time,uuid
from pathlib import Path
from unittest.mock import patch
from client_service import Coordinator,atomic
from failure_reports import Reporter,issue

checks=[]
def check(label,value):assert value,label;checks.append(label)
class Reports:
    def __init__(self):self.codes=[];self.closed=False
    def record(self,code):self.codes.append(code);return True
    def close(self):self.closed=True
class Process:
    pid=999999
    def __init__(self):self.code=None
    def poll(self):return self.code
    def terminate(self):self.code=1
    def wait(self,timeout=None):self.code=0

with tempfile.TemporaryDirectory(prefix='forge-report-wiring-') as temp:
    root=Path(temp);lab=root/'native-lab';lab.mkdir();app=root/'app';app.mkdir()
    session=str(uuid.uuid4());request=str(uuid.uuid4());pid=777777
    atomic(lab/'sandbox-lab.json',dict(schema=1,fixture=True));atomic(lab/'deck-catalog.json',dict(cards=[]))
    atomic(lab/'launch-receipt.json',dict(pid=pid,appContainer=True,capabilityCount=0,networkCapability=False,executable=str(lab/'MTGA.exe')))
    atomic(app/'release-info.json',dict(version='1.2.3'));atomic(app/'release-manifest.json',dict(version='1.2.3',files={'release-info.json':hashlib.sha256((app/'release-info.json').read_bytes()).hexdigest()}))
    config=dict(privateRoot=str(root));report=Reports()
    with patch('failure_reports.Reporter',return_value=report) as make:
        c=Coordinator(config,app,session,pid)
        check('A package-pinned version constructs the reporter',make.call_args.args==(lab,'1.2.3'))
    check('Idle startup does not fabricate an error report',not report.codes)
    c.ipc.mkdir();c.request_id=request
    def live(phase='playing'):
        c.process=Process();c.phase=phase;c.internet=False;c.log=None;c.deadline=time.monotonic()+10;c.error=None
        (c.ipc/'state.json').unlink(missing_ok=True);(c.ipc/'stop.request').unlink(missing_ok=True);report.codes.clear();return c.process
    process=live();process.code=1;atomic(c.ipc/'engine-error.json',dict(reason='SECRET private deck / path #invite'))
    c.tick();check('An actual owner-exit branch records only its fixed code',report.codes==['RULES_ENGINE_EXITED'] and c.phase=='error' and 'SECRET' not in json.dumps(report.codes))
    live('starting');c.deadline=0;c.tick();check('Startup timeout queues its fixed code before graceful stop',report.codes==['RULES_START_TIMEOUT'] and c.phase=='stopping' and (c.ipc/'stop.request').exists())
    live('starting');atomic(c.ipc/'state.json',dict(fidelityGap='SECRET unsupported private card'));c.tick()
    check('A source fidelity gap never uploads its private card message',report.codes==['RULES_FIDELITY_GAP'] and c.phase=='stopping')
    live();c.stop('cancelled');check('An ordinary cancellation creates no failure report',not report.codes and c.phase=='stopping')
    live();atomic(lab/'client-service.request.json',dict(schema=1,session='old',id=str(uuid.uuid4()),action='cancel',matchRequestId=request));c.tick()
    check('A stale client request neither reports nor kills the match',not report.codes and c.phase=='playing' and c.process.poll() is None)
    packet=dict(schema=1,session=session,requestId=request,code='NATIVE_DISPLAY_FAILED')
    for field,value in [('session','other'),('requestId','old'),('schema',True),('code','SECRET private card')]:
        wrong=copy.deepcopy(packet);wrong[field]=value;atomic(lab/'client-failure.json',wrong);c.tick()
        check('Rejects stale/invalid native failure '+field,not report.codes and c.phase=='playing')
    atomic(lab/'client-failure.json',dict(packet,log='SECRET'));c.tick();check('Rejects extra native failure data',not report.codes)
    (lab/'client-failure.json').write_text('x'*4097);c.tick();check('Rejects oversized native failure data',not report.codes)
    atomic(lab/'client-failure.json',packet);c.tick();c.tick()
    check('A matching native display failure is queued once without changing the game',report.codes==['NATIVE_DISPLAY_FAILED'] and c.phase=='playing' and c.process.poll() is None)
    c.request_id=str(uuid.uuid4());c.tick();check('An earlier match failure cannot attach to a later match',len(report.codes)==1)
    c.process=None;c.phase='idle';c.close();check('Coordinator shutdown closes its own reporter',report.closed)
    (app/'release-info.json').write_text('{"version":"1.2.3-private-changed"}')
    with patch('failure_reports.Reporter') as make:
        other=Coordinator(config,app,session,pid);check('Changed/unpinned package metadata disables reporting',other.reporter is None and not make.called)

    entered=threading.Event();release=threading.Event();posts=[];worker_threads=[]
    class GatePublisher:
        def __init__(self,stop=None):self.stop=stop
        def ready(self):worker_threads.append(threading.get_ident());entered.set();release.wait(2);return not self.stop.is_set()
        def find(self,value):return None
        def create(self,value):posts.append(issue(value));return dict(number=1,html_url='https://github.com/kgeg401/forge-arena-sandbox/issues/1',body=issue(value)['body'])
    with patch('failure_reports.GitHub',GatePublisher):
        reporter=Reporter(lab,'1.2.3');start=time.monotonic();check('Report creation is durable and returns promptly',reporter.record('RULES_ENGINE_EXITED') and time.monotonic()-start<.2)
        assert entered.wait(2);start=time.monotonic();reporter.record('RULES_ENGINE_EXITED')
        check('An unavailable publisher never blocks the caller or duplicates the outbox',time.monotonic()-start<.2 and len(reporter.outbox.rows())==1 and worker_threads[0]!=threading.get_ident())
        release.set();end=time.monotonic()+3
        while time.monotonic()<end and reporter.outbox.rows()[0][1]['status']!='sent':time.sleep(.01)
        check('The background publisher records its verified receipt',len(posts)==1 and reporter.outbox.rows()[0][1]['status']=='sent')
        reporter.close();check('Closing the reporter leaves no publishing thread',not reporter.thread.is_alive())
    with patch('failure_reports.write',side_effect=OSError('disk unavailable')):
        check('A failed report write cannot crash the game caller',reporter.record('RULES_START_TIMEOUT') is False)
print(json.dumps(dict(passed=True,checks=len(checks),results=checks,scope='Actual coordinator branches, durable files and real report worker thread with a gated fake publisher. No native UI, real GitHub delivery or save recovery.')))
