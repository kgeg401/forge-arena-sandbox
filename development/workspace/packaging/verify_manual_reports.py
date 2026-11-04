"""Manual reports: real files/worker, fake OS handoff; no public issue created."""
import json,tempfile,time,uuid
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
from manual_reports import ManualReports,projection,issue_url
from failure_reports import write

checks=[]
def check(label,value):assert value,label;checks.append(label)
secret='SECRET-CARD-PRIVATE-INVITE-ACCOUNT'
state=dict(session=str(uuid.uuid4()),phase='MAIN1',stage='Play',turn=6,activeSeat=1,prioritySeat=2,
    inputSeat=1,viewerSeat=1,playerCount=10,viewRevision=200,networkRevision=200,
    gameOver=False,canPass=True,networkMatch=True,pod=True,attackLeft=True,spectating=False,
    stackOrder=[secret]*304,battlefield=[secret],unavailableActions=[dict(message=secret)],decision=dict(prompt=secret),
    fidelityGap=secret,hand=[secret],events=[secret],name=secret,deck=secret,token=secret,path='C:/Users/'+secret)
projected=projection(state)
check('Allowlisted counts retain stack size and priority without private content',projected['stackOrderCount']==304 and projected['prioritySeat']==2 and secret not in json.dumps(projected))
check('No unbounded phase or forged numeric text enters diagnostics','phase' not in projection(dict(phase=secret,turn=secret)) and 'turn' not in projection(dict(turn=True)))
url=issue_url('0.2.0-beta.1',str(uuid.uuid4()),projected)
check('Largest supported context fits a browser URL',len(url)<=1900)
query=parse_qs(urlsplit(url).query)
check('Fixed GitHub form includes version and screenshot/diagnostic fields',url.startswith('https://github.com/kgeg401/forge-arena-sandbox/issues/new?') and query['template']==['bug_report.yml'] and query['version']==['0.2.0-beta.1'] and 'Screenshots' in query['evidence'][0] and '304' in query['evidence'][0])

with tempfile.TemporaryDirectory(prefix='forge-manual-report-') as temp:
    root=Path(temp);lab=root/'native-lab';lab.mkdir();(lab/'forge-ipc').mkdir();app=root/'app';app.mkdir()
    session=str(uuid.uuid4());report=ManualReports(lab,app,session)
    write(lab/'forge-ipc/state.json',state)
    report.sample('playing',True,state['session'])
    check('Live session sample records actual stack/turn',report.history[-1]['stackOrderCount']==304 and report.history[-1]['turn']==6)
    report.next_sample=0;report.sample('playing',True,str(uuid.uuid4()))
    check('Another rules owner cannot contribute stale state','stackOrderCount' not in report.history[-1])
    for i in range(150):
        report.next_sample=0;report.sample('playing' if i%2 else 'ready',False,None)
    check('Session history has a fixed memory/storage bound',len(report.history)==120)
    report.next_sample=0;report.sample('playing',True,state['session'])
    request=lab/'manual-report.request.json'
    for wrong in (dict(schema=1,session='old',id=str(uuid.uuid4())),dict(schema=True,session=session,id=str(uuid.uuid4())),dict(schema=1,session=session,id='../../outside'),dict(schema=1,session=session,id=str(uuid.uuid4()),url='https://evil.example')):
        write(request,wrong);report.poll('playing',True,state['session'])
        check('Invalid request cannot open a browser or write a report',report.thread is None and not (lab/'bug-reports').exists())
    request.write_text('x'*4097);report.poll('playing',False,None)
    check('Oversized native command is rejected without disturbing gameplay',report.thread is None and not request.exists())
    rid=str(uuid.uuid4());write(request,dict(schema=1,session=session,id=rid));opened=[];folders=[]
    with patch('manual_reports.webbrowser.open',side_effect=lambda u:(opened.append(u) or True)),patch('manual_reports.subprocess.Popen',side_effect=lambda a,**k:folders.append(a)):
        report.poll('playing',True,state['session']);report.thread.join(3)
    status=json.loads((lab/'manual-report-status.json').read_text());folder=lab/'bug-reports'/rid
    check('Explicit click creates durable log and confirmed OS draft handoffs',status['status']=='ready' and status['browserOpened'] and status['folderOpened'] and len(opened)==len(folders)==1)
    text=(folder/'session-report.txt').read_text()
    check('Saved report includes technical history but no secret/deck/path/token',secret not in text and 'stackOrderCount' in text and '304' in text and len(text)<100000)
    check('Offline fallback is a real GitHub shortcut plus instructions',(folder/'GitHub issue.url').read_text().startswith('[InternetShortcut]\nURL=https://github.com/') and (folder/'README.txt').is_file())
    write(request,dict(schema=1,session=session,id=rid));report.poll('playing',True,state['session'])
    check('Repeated command is never replayed',len(list((lab/'bug-reports').iterdir()))==1)
    rid2=str(uuid.uuid4());write(request,dict(schema=1,session=session,id=rid2));report.poll('playing',True,state['session'])
    check('Rapid clicks are throttled and acknowledged',json.loads((lab/'manual-report-status.json').read_text())['status']=='busy')
    report.next_report=0;rid3=str(uuid.uuid4());write(request,dict(schema=1,session=session,id=rid3))
    with patch('manual_reports.webbrowser.open',side_effect=OSError('offline')),patch('manual_reports.subprocess.Popen',side_effect=OSError('unavailable')):
        report.poll('playing',True,state['session']);report.thread.join(3)
    status=json.loads((lab/'manual-report-status.json').read_text())
    check('Failed browser/folder handoff preserves the saved report for manual opening',status['status']=='ready' and not status['browserOpened'] and not status['folderOpened'] and (lab/'bug-reports'/rid3/'session-report.txt').is_file())
    report.close();check('Owned report worker exits',not report.thread.is_alive())
    from client_service import Coordinator
    write(lab/'sandbox-lab.json',dict(schema=1,fixture=True));write(lab/'deck-catalog.json',dict(cards=[]))
    write(lab/'launch-receipt.json',dict(pid=999999,appContainer=True,capabilityCount=0,networkCapability=False,executable=str(lab/'MTGA.exe')))
    c=Coordinator(dict(privateRoot=str(root)),app,session,999999)
    match=str(uuid.uuid4());c.request_id=match;c.process=SimpleNamespace(pid=999998,poll=lambda:None)
    c.publish('ready','Ready',engineSession=state['session']);c.publish('playing','Playing')
    check('Entering playing retains the matching rules identity for diagnostics',c.last_snapshot['engineSession']==state['session'])
    rid4=str(uuid.uuid4());write(request,dict(schema=1,session=session,id=rid4))
    with patch('manual_reports.webbrowser.open',return_value=True),patch('manual_reports.subprocess.Popen'):
        c.tick();c.manual_reports.thread.join(3);c.tick()
    check('Reporting during a match preserves the rules owner, match and priority',c.phase=='playing' and c.request_id==match and c.process.poll() is None and json.loads((lab/'forge-ipc/state.json').read_text())==state)
    saved=json.loads((lab/'bug-reports'/rid4/'session-report.txt').read_text())
    check('A running coordinator produces real scoped stack diagnostics',saved['history'][-1]['stackOrderCount']==304 and saved['history'][-1]['prioritySeat']==2)
    c.manual_reports.close()
    c.request_id=str(uuid.uuid4());c.publish('starting','Starting next match')
    check('A new match cannot inherit a previous rules identity','engineSession' not in c.last_snapshot)
print(json.dumps(dict(passed=True,checks=len(checks),results=checks,scope='Real bounded files and worker; OS browser/folder launch mocked, no live upload.')))
