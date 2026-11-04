"""A naturally shuffled two-human Forge game through real HTTP/native handlers.

Both scripted test players make explicit original native submissions. The repeat
controller owns only its own inputs. Default transport is HTTP loopback; the
optional pinned tunnel routes the guest through actual public HTTPS. Neither
mode proves rendered multiplayer or two physical PCs.
"""
import argparse,json,os,re,socket,subprocess,sys,threading,time,traceback,uuid
from pathlib import Path
from engine_test_client import Engine
from native_engine_test_client import NativeEngine
from headless_resources import process_flags
from runtime_paths import ROOT
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packaging'))
from client_service import atomic,read
from multiplayer_room import Room,RoomClient,RoomServer
from multiplayer_rules import RulesRoom
from multiplayer_session import Session,TUNNEL_SHA

p=argparse.ArgumentParser()
for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--seconds',type=int,default=480);p.add_argument('--tunnel-binary',type=Path);p.add_argument('--search-opening',action='store_true');p.add_argument('--loop-seat',type=int,choices=(1,2),default=1);a=p.parse_args()
if not a.worker.is_file() or not a.fixture.is_file() or not (a.managed/'Wizards.MDN.GreProtobuf.dll').is_file():p.error('Select existing native worker, board fixture and original managed libraries before starting rules')
if not 1<=a.seconds<=600:p.error('Whole-test bound must be 1–600 seconds; native workers also have a ten-minute limit')
a.output.mkdir(parents=True,exist_ok=False)
combo_role=a.loop_seat;response_role=3-combo_role
deadline=time.monotonic()+a.seconds;engine=None;room=None;server=None;server_thread=None;coordinators=[];clients=[];sessions=[];halt=threading.Event();errors=[];trace=[];checks=[];tunnel=None;tunnel_log=None
AURAS=['Freed from the Real',"Pemmin's Aura"]
TUTORS=['Demonic Tutor','Grim Tutor','Dark Petition']
BOUNCES=['Unsummon','Cyclonic Rift','Winds of Rebuke']
AURA=AURAS[0]
def check(label,value):checks.append(dict(check=label,passed=bool(value)));assert value,label
def maybe(path):
 try:return read(path)
 except (FileNotFoundError,PermissionError,json.JSONDecodeError):return None
class Peer(NativeEngine):
 def __init__(self,role,ipc):
  self.role=role;self.ipc=ipc;self.process=engine.process;self.session=engine.session;self.checks=[];self.native_folder=ipc/'native-worker';self.native_process=None;self.native_log=(ipc/'native-worker.log').open('w',encoding='utf8')
  self.native_process=subprocess.Popen(['dotnet',str(a.worker),str(a.managed),str(ROOT/'native-lab'),str(ipc),str(a.fixture)],stdout=self.native_log,stderr=subprocess.STDOUT,creationflags=process_flags())
  atomic(a.output/('peer-'+str(role)+'-process.json'),dict(pid=self.native_process.pid,role=role,worker=str(a.worker),ipc=str(ipc)))
  try:self.native_status=self.native_wait(self.native_folder/'ready.json',30);self.state=self.native_status['state']
  except BaseException:self.close();raise
 def refresh(self):
  self.native_status=self.native_wait(self.native_folder/'status.json');self.state=self.native_status['state'];return self.native_status
 def close(self):
  if self.native_process:
   (self.native_folder/'stop.request').write_text('Bounded loop multiplayer check complete')
   try:self.native_process.wait(timeout=8)
   except subprocess.TimeoutExpired:self.native_process.terminate();self.native_process.wait(timeout=5)
  self.native_log.close()
def session(role,ipc,client):
 s=Session.__new__(Session);s.root=ROOT;s.ipc=ipc;s.role=role;s.context={};s.room=room if role==1 else None;s.engine=engine.process if role==1 else None;s.broker=RulesRoom(room,engine.ipc) if role==1 else None;s.rules_started=time.monotonic();s.client=client;s.last_revision=-1;s.pending=None;s.ack=0;s.terminal=False
 return s
def coordinate(s):
 try:
  while not halt.is_set():
   s.tick()
   time.sleep(.005)
 except BaseException as error:errors.append(repr(error));halt.set()
def stable():
 while time.monotonic()<deadline:
  if errors:raise RuntimeError('Coordinator: '+str(errors))
  if engine.process.poll() is not None:raise RuntimeError('Rules exited')
  with room.lock:revision=room.revision;actor=room.actor;pending=room.pending is not None
  statuses=[c.refresh() for c in clients]
  if actor in (1,2) and not pending and all(s['state'].get('networkRevision')==revision and not s.get('gap') for s in statuses):return actor,clients[actor-1]
  if any(s.get('gap') for s in statuses):raise RuntimeError('Native fidelity gap: '+str([s.get('gap') for s in statuses]))
  time.sleep(.015)
 raise TimeoutError('Stable paired boundary exceeded whole-test bound')
def command(c,op,id=0,**fields):
 c.refresh();reply=c.native_call(op,id,**fields)
 if not reply.get('accepted'):raise RuntimeError('Native action rejected '+op+': '+str(reply.get('reason') or reply.get('gap')))
 trace.append(dict(role=c.role,op=op,forgeId=id,nativeState=reply['nativeStateId'],revision=reply['state'].get('networkRevision')))
 return reply
def choose(c):
 for _ in range(24):
  c.refresh();d=c.state.get('decision')
  if not d or c.state.get('inputSeat')!=1:return
  kind=d['kind'];token=d['token']
  if kind=='mulligan':
   wanted=AURAS+TUTORS if c.role==combo_role else BOUNCES;keep=not a.search_opening or c.state['mulligans']>=4 or any(v['name'] in wanted for v in c.state['hand']);command(c,'submit_mulligan',decisionToken=token,assignments=[dict(keep=keep)])
  elif kind=='starting_player':command(c,'submit_starting_player',decisionToken=token,assignments=[dict(startingSeat=1)])
  elif kind in ('discard','mulligan_bottom'):
   names={v['forgeId']:v['name'] for v in c.state['hand']};wanted=AURAS+TUTORS if c.role==combo_role else BOUNCES;options=sorted(d['options'],key=lambda o:names.get(o['forgeId']) in wanted);command(c,'submit_'+kind,decisionToken=token,assignments=[dict(forgeId=o['forgeId']) for o in options[:d['count']]])
  elif kind=='commander_return':command(c,'submit_commander_return',decisionToken=token,assignments=[dict(returnToCommand=True)])
  elif kind in ('attackers','blockers'):command(c,'submit_'+kind,decisionToken=token)
  elif kind=='order_cards':command(c,'submit_order_cards',decisionToken=token,assignments=[dict(forgeId=o['forgeId']) for o in d['options']])
  elif kind=='choice' and d['choice']['type']=='colors':command(c,'submit_choice',decisionToken=token,assignments=[dict(choiceId=next(o for o in d['choice']['options'] if o.get('color','').lower()=='blue')['choiceId'])])
  elif kind=='choice' and d['choice']['type']=='confirm':command(c,'submit_choice',decisionToken=token,assignments=[dict(accept=False)])
  elif kind=='choice' and d['choice']['type']=='options' and d['choice']['prompt'].startswith('Choose how to cast Cyclonic Rift'):
   option=next(o for o in d['choice']['options'] if 'Overload' not in o['label']);command(c,'submit_choice',decisionToken=token,assignments=[dict(choiceId=option['choiceId'])])
  elif kind=='choice' and d['choice']['type'] in ('cards-order','abilities-order'):command(c,'submit_choice',decisionToken=token,assignments=[dict(choiceId=o['choiceId']) for o in d['choice']['options']])
  elif kind=='choice' and d['choice']['type'] in ('cards-zone','cards-effect','entities'):
   desired=AURAS if c.role==combo_role else BOUNCES;options=d['choice']['options'];picked=next((o for name in desired for o in options if o.get('label')==name),None)
   if picked is None:raise AssertionError('No actual offered tutor target: '+json.dumps(d)[:500])
   command(c,'submit_choice',decisionToken=token,assignments=[dict(choiceId=picked['choiceId'])])
  elif kind=='targets':
   cards={v['forgeId']:v for z in ('hand','battlefield','stack','command','stackAbilities') for v in c.state.get(z,[])}
   target=next(o for o in d['options'] if cards.get(o['forgeId'],{}).get('name')=='Zaxara, the Exemplary')
   command(c,'select_targets',decisionToken=token,assignments=[dict(forgeId=target['forgeId'])]);command(c,'submit_targets',decisionToken=token)
  else:raise AssertionError('Unimplemented explicit network policy '+kind+': '+json.dumps(d)[:500])
 raise AssertionError('Native nested-choice bound')
def act(c,op,id=0,**fields):command(c,op,id,**fields);choose(c)
def by_name(c,name):return next(v for z in ('hand','battlefield','command') for v in c.state.get(z,[]) if v['name']==name)
def offer(c,name,mana=False):
 c.refresh();card=by_name(c,name);offers=c.state['legalManaOffers' if mana else 'legalActivations'];return card,next(v for v in offers if v['forgeId']==card['forgeId'] and (mana or v['api']=='Untap'))
def activate(c,name,mana=False):
 card,o=offer(c,name,mana);act(c,'activate_mana' if mana else 'activate_ability',card['forgeId'],abilityId=o['abilityId'])
def settle():
 for _ in range(20):
  actor,c=stable();choose(c)
  if not c.state['stackOrder']:return
  act(c,'pass_priority')
 raise AssertionError('Paired stack settle bound')
try:
 deck=lambda commander,rows:dict(name='Explicit loop test '+commander,format='commander-40',commander=dict(name=commander,count=1),cards=[dict(name=name,count=count) for name,count in rows])
 combo_deck=deck('Zaxara, the Exemplary',[('Forest',18),('Swamp',18),('Island',58)]+[(name,1) for name in AURAS+TUTORS]);response_deck=deck('Emry, Lurker of the Loch',[('Island',96)]+[(name,1) for name in BOUNCES])
 engine=Engine('commander-human-duel',localDeck=combo_deck if combo_role==1 else response_deck,opponentDeck=response_deck if combo_role==1 else combo_deck,startingPlayerPolicy='local-first',randomSeed=7306777)
 atomic(a.output/'rules-process.json',dict(pid=engine.process.pid,ipc=str(engine.ipc),runtime=str(ROOT)))
 room=Room(dict(test='same frozen rules and native build'),require_presentation=True);server=RoomServer(room);server_thread=threading.Thread(target=server.serve_forever,daemon=True);server_thread.start();url='http://127.0.0.1:'+str(server.server_port)
 guest_url=url
 if a.tunnel_binary:
  import hashlib
  check('Internet helper matches the exact shipped pin',hashlib.sha256(a.tunnel_binary.read_bytes()).hexdigest()==TUNNEL_SHA);tunnel_log=(a.output/'tunnel.log').open('w',encoding='utf8');tunnel=subprocess.Popen([str(a.tunnel_binary),'tunnel','--no-autoupdate','--protocol','http2','--url',url],stdout=tunnel_log,stderr=subprocess.STDOUT,creationflags=process_flags());atomic(a.output/'tunnel-process.json',dict(pid=tunnel.pid,exe=str(a.tunnel_binary)))
  end=min(deadline,time.monotonic()+120)
  while time.monotonic()<end:
   if tunnel.poll() is not None:raise RuntimeError('Owned internet helper exited')
   text=(a.output/'tunnel.log').read_text(encoding='utf8',errors='replace');match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',text)
   if match and 'Registered tunnel connection' in text:guest_url=match.group();break
   time.sleep(.25)
  else:raise TimeoutError('Owned internet endpoint did not become ready')
  from urllib.parse import urlsplit
  end=min(deadline,time.monotonic()+120);attempts=0
  while time.monotonic()<end:
   attempts+=1
   try:socket.getaddrinfo(urlsplit(guest_url).hostname,443,type=socket.SOCK_STREAM);break
   except OSError as error:atomic(a.output/'dns-preflight.json',dict(ready=False,attempts=attempts,error=repr(error)));time.sleep(.5)
  else:raise TimeoutError('Registered tunnel hostname did not resolve within the bounded preflight')
  atomic(a.output/'dns-preflight.json',dict(ready=True,attempts=attempts))
 join_request=dict(id=str(uuid.uuid4()),protocol=1,compatibility=room.compatibility);end=min(deadline,time.monotonic()+60)
 while True:
  try:joined=RoomClient(guest_url,room.invite).call('/v1/join',join_request);break
  except OSError:
   if time.monotonic()>=end:raise
   time.sleep(.5)
 for role,token in ((1,room.host_token),(2,joined['token'])):
  ipc=ROOT/'research'/(a.output.name+'-peer-'+str(role));ipc.mkdir();(ipc/'requests').mkdir();(ipc/'responses').mkdir();atomic(ipc/'scenario.json',dict(scenario='commander-human-duel'));sessions.append(session(role,ipc,RoomClient(url if role==1 else guest_url,token)))
 for s in sessions:
  thread=threading.Thread(target=coordinate,args=(s,),daemon=True);coordinators.append(thread);thread.start()
 for role in (1,2):
  ipc=sessions[role-1].ipc;end=time.monotonic()+35
  while not (ipc/'state.json').exists() and time.monotonic()<end:
   if errors:raise RuntimeError(str(errors))
   time.sleep(.025)
  clients.append(Peer(role,ipc))
 check('Both original native parsers attached to separate real human views',len(clients)==2)
 first=clients[combo_role-1];second=clients[response_role-1];actions=0
 while time.monotonic()<deadline:
  actor,c=stable();actions+=1;assert actions<2400,'Natural-draw setup action bound'
  if c.state.get('decision'):choose(c);continue
  c.refresh()
  if c.state['gameOver']:raise AssertionError('Normal game ended before setup')
  first.refresh();second.refresh()
  ready=any(v['name'] in AURAS for v in first.state['hand']) and any(v['name'] in BOUNCES for v in second.state['hand']) and any(v['name']=='Zaxara, the Exemplary' for v in first.state['battlefield']) and any(o['forgeId']==by_name(first,'Zaxara, the Exemplary')['forgeId'] for o in first.state.get('legalManaOffers',[]))
  if actor==combo_role and ready and any(v['name'] in AURAS and v['forgeId'] in first.state['legalCasts'] for v in first.state['hand']):AURA=next(v['name'] for v in first.state['hand'] if v['name'] in AURAS and v['forgeId'] in first.state['legalCasts']);break
  if c.state.get('decision'):continue
  if c.state['legalLands']:
   lands=[v for v in c.state['hand'] if v['forgeId'] in c.state['legalLands']];present={v['name'] for v in c.state['battlefield']};missing=[name for name in ('Forest','Swamp','Island') if name not in present];preferred=next((v for name in missing for v in lands if v['name']==name),None) if actor==combo_role else None;act(c,'play_land',(preferred or lands[0])['forgeId'])
  elif actor==combo_role and not any(v['name'] in AURAS for v in c.state['hand']) and any(v['name'] in TUTORS and v['forgeId'] in c.state['legalCasts'] for v in c.state['hand']):act(c,'cast_spell',next(v['forgeId'] for v in c.state['hand'] if v['name'] in TUTORS and v['forgeId'] in c.state['legalCasts']))
  elif actor==combo_role and any(v['name']=='Zaxara, the Exemplary' and v['forgeId'] in c.state['legalCasts'] for v in c.state['command']):act(c,'cast_spell',by_name(c,'Zaxara, the Exemplary')['forgeId'])
  elif c.state.get('canPass'):act(c,'pass_priority')
  else:raise AssertionError('No scripted setup action')
 else:raise TimeoutError('Natural draws did not assemble the test cards within bound')
 check('Real shuffled decks draw combo and response cards without fixtures',ready)
 act(first,'cast_spell',by_name(first,AURA)['forgeId']);settle();activate(first,'Zaxara, the Exemplary',True)
 for _ in range(2):activate(first,AURA);settle();activate(first,'Zaxara, the Exemplary',True)
 stable();first.refresh();loop=first.native_status['loop'];check('Two-human mana loop is recognized',loop['available'] and loop['kind']=='mana');before=first.state['manaTotal'];start=command(first,'loop_start',count=10);passes=0
 while time.monotonic()<deadline:
  first.refresh();loop=first.native_status['loop']
  if loop.get('runId')==start['loop'].get('runId') and not loop['running']:break
  actor,c=stable()
  if actor==response_role:act(c,'pass_priority');passes+=1
  else:time.sleep(.015)
 check('Ten real network cycles complete with exact mana gain',loop['completed']==10 and first.state['manaTotal']==before+10)
 check('The other human explicitly receives and passes real response windows',passes>=10)
 stable();start=command(first,'loop_start',count=20);cancelled=False
 while time.monotonic()<deadline:
  actor,c=stable();first.refresh()
  if actor==response_role:
   check('Waiting player has no original gameplay response request',first.native_status['nativeMessageId'] is None)
   rejected=first.native_call('loop_stop',loopRunId='older-batch');check('An old batch cannot cancel the current one',not rejected['accepted'])
   stop=command(first,'loop_stop');check('Stop works while the other human owns priority',not stop['loop']['running'] and stop['loop']['runId']==start['loop']['runId']);cancelled=True;break
  time.sleep(.015)
 check('Cancellation reached an actual other-player window',cancelled)
 settle();activate(first,'Zaxara, the Exemplary',True)
 for _ in range(2):activate(first,AURA);settle();activate(first,'Zaxara, the Exemplary',True)
 stable();start=command(first,'loop_start',count=20);interrupted=False
 while time.monotonic()<deadline:
  first.refresh();loop=first.native_status['loop']
  if loop.get('runId')==start['loop'].get('runId') and not loop['running']:break
  actor,c=stable()
  if actor==response_role:
   if loop['completed']>=2 and any(v['name'] in BOUNCES and v['forgeId'] in c.state['legalCasts'] for v in c.state['hand']):act(c,'cast_spell',next(v['forgeId'] for v in c.state['hand'] if v['name'] in BOUNCES and v['forgeId'] in c.state['legalCasts']));interrupted=True
   else:act(c,'pass_priority')
  else:time.sleep(.015)
 check('A real opposing response stops the repeat without inventing passes',interrupted and not loop['running'] and loop['completed']<20)
 settle();first.refresh();check('Real opposing bounce removes the original mana creature',not any(v['name']=='Zaxara, the Exemplary' for v in first.state['battlefield']) and not first.state['fidelityGap'])
 result=dict(passed=True,checks=checks,evidence=str(a.output),rulesEvidence=str(engine.ipc),setupActions=actions,responsePasses=passes,loopSeat=combo_role,transport='actual HTTPS quick tunnel' if a.tunnel_binary else 'HTTP loopback',scope=__doc__)
except BaseException as error:result=dict(passed=False,error=repr(error)[:1800],traceback=traceback.format_exc(),checks=checks,coordinatorErrors=errors,rulesEvidence=str(engine.ipc) if engine else None,scope=__doc__)
finally:
 halt.set()
 for thread in coordinators:thread.join(timeout=15)
 for c in clients:c.close()
 if room:room.close()
 if server:server.shutdown();server.server_close();server_thread.join(timeout=5)
 if engine:engine.close()
 if tunnel and tunnel.poll() is None:tunnel.terminate();tunnel.wait(timeout=8)
 if tunnel_log:tunnel_log.close()
 atomic(a.output/'report.json',result);atomic(a.output/'actions.json',trace);atomic(a.output/'cleanup.json',dict(coordinatorStopped=all(not t.is_alive() for t in coordinators),nativeWorkersExited=all(c.native_process.poll() is not None for c in clients),rulesExited=engine is None or engine.process.poll() is not None,tunnelExited=tunnel is None or tunnel.poll() is not None))
print(json.dumps({k:v for k,v in result.items() if k not in ('checks','scope','traceback')}));raise SystemExit(0 if result['passed'] else 1)
