"""Protocol/ownership regression fixtures; native gameplay is verified separately."""
import copy,json,os,sys,tempfile,time,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
APP=Path(__file__).resolve().parent
if not (APP/'ForgeBackend').is_dir():APP=APP.parent
sys.path.insert(0,str(APP/'ForgeBackend'))
from client_service import Coordinator,NativeLifetime,RequestRejected,atomic,parse_local_deck,service_lock

# This checker uses authored baseline deck/protocol fixtures only. A public
# checkout includes a pinned experimental recipe, whose production loader must
# require owned game files. Keep that integration check separate from this test
# instead of weakening the loader or requiring game assets on the CI runner.
with patch('experimental_cards.load_experimental',return_value=dict(cards={},blockedCards={},enabled=False)):
    import deck_import

checks=[]
def check(label,condition):
    if not condition:raise AssertionError(label)
    checks.append(label)
def reject(label,operation):
    try:operation()
    except (ValueError,RuntimeError,OSError):check(label,True)
    else:raise AssertionError('Unexpected acceptance: '+label)
catalog={'1':dict(name='Plains'),'2':dict(name='Island'),'3':dict(name='Savannah Lions'),'4':dict(name='Isamaru, Hound of Konda'),'5':dict(name='Emry, Lurker of the Loch'),'6':dict(name='Liliana, Death Mage'),'7':dict(name='Savannah Lions')}
def deck(main,commander=None):return dict(id=str(uuid.uuid4()),name='Fixture deck',main=main,commander=commander or {},sideboard={},companion={})
practice=deck({'1':24,'3':16});brawl=deck({'1':98,'3':1},{'4':1})
check('Practice preserves the exact admitted name counts',parse_local_deck(practice,catalog,'SandboxPractice')['cards']==[dict(name='Plains',count=24),dict(name='Savannah Lions',count=16)])
check('Brawl retains the commander and 99 main cards',sum(c['count'] for c in parse_local_deck(brawl,catalog,'SandboxBrawl')['cards'])==99)
check('Four-player Commander independently enforces the Commander deck policy',parse_local_deck(brawl,catalog,'SandboxCommanderPod')['format']=='commander-40')
reject('Commander pod rejects a deck without a commander',lambda:parse_local_deck(practice,catalog,'SandboxCommanderPod'))
reject('Practice cannot silently drop a commander',lambda:parse_local_deck(brawl,catalog,'SandboxPractice'))
reject('Unknown local queues are rejected',lambda:parse_local_deck(practice,catalog,'OnlineRanked'))
reject('Unknown saved printing IDs are rejected',lambda:parse_local_deck(deck({'999':60}),catalog,'SandboxPractice'))
reject('Boolean quantities cannot become card counts',lambda:parse_local_deck(deck({'1':True}),catalog,'SandboxPractice'))
reject('An unverified Arena card is rejected explicitly',lambda:parse_local_deck(deck({'1':59,'6':1}),catalog,'SandboxPractice'))
reject('Brawl singleton is checked across different saved printings',lambda:parse_local_deck(deck({'1':97,'3':1,'7':1},{'4':1}),catalog,'SandboxBrawl'))
reject('Brawl color identity is independently checked',lambda:parse_local_deck(deck({'1':97,'2':1,'3':1},{'4':1}),catalog,'SandboxBrawl'))
reject('Brawl requires the full 100-card deck',lambda:parse_local_deck(deck({'1':59},{'4':1}),catalog,'SandboxBrawl'))

class Engine:
    def __init__(self,pid):self.pid=pid;self.code=None;self.terminated=0
    def poll(self):return self.code
    def terminate(self):self.terminated+=1;self.code=-1
    def wait(self,timeout=None):self.code=0;return self.code

with tempfile.TemporaryDirectory(prefix='forge-coordinator-') as temp:
    root=Path(temp);lab=root/'native-lab';(lab/'local-profile').mkdir(parents=True)
    native=lab/'MTGA.exe';session=str(uuid.uuid4());pid=987654
    atomic(lab/'sandbox-lab.json',dict(schema=1,fixture=True))
    receipt=dict(pid=pid,executable=str(native),appContainer=True,capabilityCount=0,networkCapability=False)
    atomic(lab/'launch-receipt.json',receipt)
    atomic(lab/'deck-catalog.json',dict(schema=1,cards=[dict(grpId=int(k),**v) for k,v in catalog.items()]))
    atomic(lab/'local-profile/decks.json',dict(schema=1,revision=0,decks=[practice,brawl]));original=(lab/'local-profile/decks.json').read_bytes()
    app=root/'app';(app/'decks').mkdir(parents=True)
    (app/'decks/White-Lifegain.txt').write_text('Deck\n24 Plains\n36 Savannah Lions\n')
    (app/'decks/Brawl-Isamaru-Bot.txt').write_text('Commander\n1 Isamaru, Hound of Konda\nDeck\n98 Plains\n1 Savannah Lions\n')
    config=dict(privateRoot=str(root),javaHome=str(root/'java'))
    engines=[]
    def spawn(*args,**kwargs):e=Engine(800000+len(engines));engines.append(e);return e
    with patch('client_service.subprocess.Popen',side_effect=spawn),patch('client_service.subprocess.run',return_value=SimpleNamespace(stdout='')):
        c=Coordinator(config,app,session,pid)
        def request(action,**values):return dict(schema=1,session=session,id=str(uuid.uuid4()),action=action,**values)
        def submit(value):atomic(lab/'client-service.request.json',value);c.tick()
        first=request('start',queue='SandboxBrawl',deckId=brawl['id'],localDeck=dict(cards=[dict(name='Forbidden injected card',count=99)]))
        submit(first)
        check('A valid queue creates exactly one engine',len(engines)==1 and c.phase=='starting')
        scenario=json.loads((c.ipc/'scenario.json').read_text())
        check('The engine receives saved deck data rather than injected request cards',scenario['localDeck']['cards'][0]['name']=='Plains' and 'Forbidden' not in json.dumps(scenario))
        submit(first);check('A repeated request ID is idempotent',len(engines)==1 and c.request_id==first['id'])
        submit(request('start',queue='SandboxPractice',deckId=practice['id']))
        check('A duplicate start cannot cancel a pending game',len(engines)==1 and c.phase=='starting' and c.process.poll() is None and c.request_id==first['id'])
        submit(dict(request('cancel',matchRequestId=first['id']),session=str(uuid.uuid4())))
        check('A stale client session cannot stop the game',c.phase=='starting' and not (c.ipc/'stop.request').exists())
        atomic(c.ipc/'state.json',dict(session='fixture-engine-1',scenario='brawl-duel',decision=dict(kind='mulligan')));c.tick()
        check('Ready is published only after a matching engine exposes an input decision',c.phase=='ready' and json.loads(c.state_path.read_text())['engineSession']=='fixture-engine-1')
        submit(request('cancel',matchRequestId=str(uuid.uuid4())))
        check('A stale match ID cannot cancel a ready game',c.phase=='ready' and not (c.ipc/'stop.request').exists())
        submit(request('match-started',matchRequestId=first['id']));check('The native acknowledgment enters playing',c.phase=='playing')
        submit(request('match-ended',matchRequestId=first['id']));check('Match end requests graceful shutdown',c.phase=='stopping' and (c.ipc/'stop.request').exists())
        engines[0].code=0;c.tick();check('Engine shutdown releases the coordinator for another game',c.phase=='idle' and c.process is None)
        second=request('start',queue='SandboxPractice',deckId=practice['id']);submit(second)
        check('A second match archives the first session evidence',len(engines)==2 and any(lab.glob('forge-ipc-evidence-*/state.json')))
        check('Old state cannot mark a newly queued match ready',c.phase=='starting' and not (c.ipc/'state.json').exists())
        submit(request('cancel',matchRequestId=second['id']));deadline=c.deadline
        submit(request('cancel',matchRequestId=second['id']));check('Repeated cancel cannot extend the shutdown deadline',c.deadline==deadline)
        engines[1].code=0;c.tick();check('Cancelled startup returns to a reusable state',c.phase=='cancelled')
        bad=request('start',queue='SandboxBrawl',deckId=practice['id']);submit(bad)
        check('Deck rejection reports the requesting match ID instead of stranding its UI',c.phase=='error' and c.request_id==bad['id'] and len(engines)==2)
        c.heartbeat_at=0;before=json.loads(c.state_path.read_text())['utc'];time.sleep(.002);c.tick()
        check('A fresh heartbeat is observable while idle/error',json.loads(c.state_path.read_text())['utc']!=before)
        check('All queue operations preserve the saved deck library byte for byte',(lab/'local-profile/decks.json').read_bytes()==original)
        c.close()
        check('Closing an idle coordinator leaves no engine',c.phase=='closed' and c.process is None)
    receipt['capabilityCount']=1;atomic(lab/'launch-receipt.json',receipt)
    reject('A receipt with network capabilities is rejected before any engine starts',lambda:Coordinator(config,app,session,pid))
    with service_lock(lab/'lock-test',wait_seconds=0):
        reject('Only one coordinator can own an installation',lambda:service_lock(lab/'lock-test',wait_seconds=0).__enter__())
    with service_lock(lab/'lock-test',wait_seconds=0):check('The coordinator lock releases after shutdown',True)

life=NativeLifetime(os.getpid(),sys.executable)
try:check('A real kernel handle tracks the exact executable lifetime',life.alive())
finally:life.close()
reject('An unrelated executable cannot satisfy native ownership',lambda:NativeLifetime(os.getpid(),Path(sys.executable).with_name('MTGA.exe')))
with tempfile.TemporaryDirectory(prefix='forge-engine-failure-') as temp:
    c=Coordinator.__new__(Coordinator);c.ipc=Path(temp)
    check('An unreported engine exit keeps the recovery instruction','Return Home' in c.engine_failure())
    atomic(c.ipc/'engine-error.json',dict(session=str(uuid.uuid4()),reason='Unmapped triggered target from Bojuka Bog',recoverable=False))
    check('A reported rules failure reaches the client with its actual source','Unmapped triggered target from Bojuka Bog' in c.engine_failure())
    (c.ipc/'engine-error.json').write_text('{unfinished')
    check('An incomplete failure receipt cannot break the coordinator','Return Home' in c.engine_failure())
    (c.ipc/'engine-error.json').write_text('[]')
    check('A non-object failure receipt cannot break the coordinator','Return Home' in c.engine_failure())
print(json.dumps(dict(checks=len(checks),passed=checks,scope='Authored protocol/deck fixtures, file/process ownership checks. No simulated result is counted as native gameplay.'),indent=2))
