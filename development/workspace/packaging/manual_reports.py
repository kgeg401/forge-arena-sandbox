"""Player-requested, allowlisted session diagnostics and a GitHub issue draft.

Raw logs contain invitations and hidden cards. Construct a technical timeline
instead of attempting to redact arbitrary log text after the fact.
"""
import collections,json,os,subprocess,threading,time,uuid,webbrowser
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from failure_reports import REPOSITORY,packaged_version,write

PHASES=frozenset(('UNTAP','UPKEEP','DRAW','MAIN1','COMBAT_BEGIN','COMBAT_DECLARE_ATTACKERS',
    'COMBAT_DECLARE_BLOCKERS','COMBAT_FIRST_STRIKE_DAMAGE','COMBAT_DAMAGE','COMBAT_END','MAIN2','END_OF_TURN','CLEANUP'))
SERVICE_PHASES=frozenset(('idle','starting','ready','playing','stopping','cancelled','error','closed'))


def read_bounded(path,limit=8*1024*1024):
    with Path(path).open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('Diagnostic source too large')
    value=json.loads(data.decode('utf-8-sig'))
    if not isinstance(value,dict):raise ValueError('Diagnostic source is not an object')
    return value


def projection(state):
    result={}
    if state.get('phase') in PHASES:result['phase']=state['phase']
    if state.get('stage') in ('Mulligan','Play','GameOver'):result['stage']=state['stage']
    for name in ('turn','activeSeat','prioritySeat','inputSeat','viewerSeat','playerCount','viewRevision','networkRevision'):
        value=state.get(name)
        if type(value) is int and 0<=value<=10**9:result[name]=value
    for name in ('gameOver','canPass','networkMatch','pod','attackLeft','spectating'):
        if type(state.get(name)) is bool:result[name]=state[name]
    for name in ('stackOrder','battlefield','unavailableActions'):
        if isinstance(state.get(name),list):result[name+'Count']=len(state[name])
    if isinstance(state.get('decision'),dict):result['choicePending']=True
    result['rulesGap']=bool(state.get('fidelityGap'))
    return result


def issue_url(version,report_id,latest):
    # Keep the OS browser handoff below Windows' legacy URL length limit.
    summary=json.dumps(latest,separators=(',',':'),ensure_ascii=True)
    evidence=('## Screenshots and session log\nDrag screenshots and session-report.txt here before submitting. '
          'Review screenshots for hidden cards or private information.\n\n'
          '## Automatic diagnostics\nVersion: '+version+'\nReport: '+report_id+'\n```json\n'+summary+'\n```\n')
    url='https://github.com/'+REPOSITORY+'/issues/new?'+urlencode(dict(template='bug_report.yml',title='Client bug report ('+version+')',version=version,evidence=evidence))
    if len(url)>1900:raise ValueError('Issue draft exceeds browser handoff limit')
    return url


class ManualReports:
    def __init__(self,lab,app,session):
        self.lab=Path(lab);self.session=str(uuid.UUID(session));self.version=packaged_version(app) or 'unverified'
        self.history=collections.deque(maxlen=120);self.last=None;self.next_sample=0.;self.thread=None
        self.seen=set();self.next_report=0.;self.started=datetime.now(timezone.utc).isoformat()

    def sample(self,phase,internet,engine_session):
        now=time.monotonic()
        if now<self.next_sample:return
        self.next_sample=now+1
        value=dict(servicePhase=phase if phase in SERVICE_PHASES else 'unknown',internet=internet is True)
        if engine_session and phase in ('starting','ready','playing','error'):
            try:
                state=read_bounded(self.lab/'forge-ipc/state.json')
                if state.get('session')==engine_session:value.update(projection(state))
            except (OSError,ValueError,TypeError):value['stateUnavailable']=True
        if value!=self.last:
            self.last=value;self.history.append(dict(utc=datetime.now(timezone.utc).isoformat(),**value))

    def poll(self,phase,internet,engine_session):
        try:self.sample(phase,internet,engine_session)
        except (OSError,ValueError,TypeError):pass
        request=self.lab/'manual-report.request.json'
        if not request.exists():return
        # Only the native session can request a draft. No caller-controlled URL,
        # filesystem path, issue body, shell command or free-form log is accepted.
        try:
            packet=read_bounded(request,4096)
            if set(packet)!={'schema','session','id'} or type(packet['schema']) is not int or packet['schema']!=1 or packet['session']!=self.session:raise ValueError('Invalid report request')
            report_id=str(uuid.UUID(packet['id']))
            if report_id!=packet['id']:raise ValueError('Noncanonical report ID')
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            try:request.unlink(missing_ok=True)
            except OSError:pass
            return
        try:request.unlink()
        except OSError:return
        if report_id in self.seen:return
        if len(self.seen)>=64:self.status(report_id,'busy');return
        self.seen.add(report_id)
        if self.thread and self.thread.is_alive() or time.monotonic()<self.next_report:
            self.status(report_id,'busy');return
        self.next_report=time.monotonic()+10
        history=list(self.history)
        self.thread=threading.Thread(target=self.prepare,args=(report_id,history),daemon=True)
        self.thread.start()

    def status(self,report_id,status,**extra):
        try:write(self.lab/'manual-report-status.json',dict(schema=1,session=self.session,id=report_id,status=status,**extra))
        except OSError:pass

    def prepare(self,report_id,history):
        try:
            folder=self.lab/'bug-reports'/report_id;folder.mkdir(parents=True,exist_ok=False)
            latest={k:v for k,v in (history[-1] if history else {}).items() if k!='utc'}
            url=issue_url(self.version,report_id,latest)
            report=dict(schema=1,report=report_id,version=self.version,sessionStartedUtc=self.started,
                        capturedUtc=datetime.now(timezone.utc).isoformat(),history=history,
                        scope='Last 120 changed technical samples, at most once per second. No raw logs, private cards, deck lists, names, invitations, paths or credentials.')
            (folder/'session-report.txt').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
            (folder/'GitHub issue.url').write_text('[InternetShortcut]\nURL='+url+'\n',encoding='utf8')
            (folder/'README.txt').write_text('Add details and screenshots in the GitHub draft. Drag session-report.txt into its description to attach the full technical timeline. Review it before submitting. Nothing is posted until you submit on GitHub. If the browser did not open, double-click GitHub issue.url.\n',encoding='utf8')
            opened=False;shown=False
            try:opened=webbrowser.open(url) is True
            except (OSError,webbrowser.Error):pass
            try:
                subprocess.Popen(['explorer.exe',str(folder)],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));shown=True
            except OSError:pass
            self.status(report_id,'ready',browserOpened=opened,folderOpened=shown)
        except (OSError,ValueError,TypeError):self.status(report_id,'failed')

    def close(self):
        if self.thread:self.thread.join(timeout=2)
