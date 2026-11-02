import pathlib,json,subprocess,time,uuid
from runtime_paths import ROOT as root,JAVA_HOME
from headless_resources import java_options,process_flags
ipc=root/'research'/('mana-check-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]);ipc.mkdir()
java=str(JAVA_HOME/'bin/java.exe');cp=';'.join(str(root/p) for p in ['build/ForgeBackend/classes','forge-runtime/forge.jar','forge-runtime/gson.jar'])
with (ipc/'engine.log').open('w') as log:p=subprocess.Popen([java,*java_options(),'-cp',cp,'ForgeLandEngine',str(root/'forge-runtime'),str(ipc)],cwd=root/'forge-runtime',stdout=log,stderr=subprocess.STDOUT,creationflags=process_flags())
try:
 for _ in range(120):
  if (ipc/'state.json').exists():break
  if p.poll() is not None:raise RuntimeError((ipc/'engine.log').read_text()[-3000:])
  time.sleep(.25)
 state=json.loads((ipc/'state.json').read_text());session=state['session'];checks=[]
 def send(op,forgeid=1,seat=1,reqid=None,sessionid=None,abilityid=None):
  global state
  req={'id':reqid or uuid.uuid4().hex,'session':sessionid or session,'op':op,'seat':seat,'forgeId':forgeid}
  if op=='activate_mana':
   offered=next((v['abilityId'] for v in state.get('legalManaOffers',[]) if v['forgeId']==forgeid),None)
   if abilityid is not None or offered is not None:req['abilityId']=abilityid if abilityid is not None else offered
  path=ipc/'requests'/(req['id']+'.json');tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(req));tmp.rename(path)
  response=ipc/'responses'/path.name
  for _ in range(100):
   if response.exists():
    result=json.loads(response.read_text());state=result['state'];return req,result
   time.sleep(.05)
  raise RuntimeError('response timed out')
 def check(label,response,accepted,mana,tapped=None):
  assert response['accepted']==accepted,(label,response)
  assert response['state']['manaTotal']==mana,(label,response)
  if tapped is not None:assert response['state']['battlefield'][0]['tapped']==tapped
  checks.append({'check':label,'passed':True,'response':response})
 _,r=send('activate_mana');check('cannot tap a hand card',r,False,0)
 _,r=send('play_land');check('Forge land play',r,True,0,False)
 _,r=send('play_land',2);check('second land rejected',r,False,0,False)
 _,r=send('activate_mana',seat=2);check('wrong player rejected',r,False,0,False)
 _,r=send('activate_mana',sessionid='stale');check('stale session rejected',r,False,0,False)
 request,r=send('activate_mana');check('Forge tap cost and white mana production',r,True,1,True);original_activation=r
 (ipc/'responses'/(request['id']+'.json')).unlink()
 _,r=send('activate_mana',reqid=request['id'],abilityid=request.get('abilityId'));check('exact replay is idempotent',r,True,1,True)
 (ipc/'responses'/(request['id']+'.json')).unlink()
 _,r=send('play_land',2,reqid=request['id']);check('conflicting request ID rejected',r,False,1,True)
 _,r=send('activate_mana');check('already tapped land rejected',r,False,1,True)
 phase_trace=[]
 for i in range(40):
  _,r=send('pass_priority');assert r['accepted'],r
  phase_trace.append({'phase':r['state']['phase'],'turn':r['state']['turn'],'active':r['state']['activeSeat'],'mana':r['state']['manaTotal'],'lands':r['state']['landsPlayed'],'transitions':r.get('phaseTransitions')})
  if r['state']['turn']>=3 and r['state']['activeSeat']==1 and r['state']['phase']=='MAIN1':break
 else:raise AssertionError('did not reach local next main phase')
 assert r['state']['manaTotal']==0 and r['state']['landsPlayed']==0 and not r['state']['battlefield'][0]['tapped'],r
 checks.append({'check':'normal Forge phase loop returns to local next turn with untap/mana cleanup/land reset','passed':True,'trace':phase_trace,'state':r['state']})
 (ipc/'responses'/(request['id']+'.json')).unlink()
 _,replay=send('activate_mana',reqid=request['id'],abilityid=request.get('abilityId'))
 assert replay==original_activation,'Historical replay lost its exact original answer after later turns/conflict'
 checks.append({'check':'historical completed request replays its original response after later turns and a conflicting reuse','passed':True})
 _,r=send('snapshot')
 assert r['accepted'] and r['state']['manaTotal']==0 and not r['state']['battlefield'][0]['tapped'],'Historical request executed again instead of replaying'
 checks.append({'check':'historical replay does not retap an untapped land or produce fresh mana','passed':True})
 _,upper=send('snapshot',reqid='Case')
 (ipc/'responses'/'Case.json').unlink()
 _,lower=send('snapshot',reqid='case')
 assert upper['id']=='Case' and lower['id']=='case','Request IDs were case-folded'
 checks.append({'check':'case-distinct request IDs each receive their own answer on Windows','passed':True})
 (ipc/'responses'/'case.json').unlink()
 _,upper_replay=send('snapshot',reqid='Case')
 (ipc/'responses'/'Case.json').unlink()
 _,lower_replay=send('snapshot',reqid='case')
 assert upper_replay==upper and lower_replay==lower,'Case-distinct completed archives overwrote one another'
 checks.append({'check':'case-distinct historical answers replay independently without archive collision','passed':True})
 (ipc/'checks.json').write_text(json.dumps(checks,indent=2));print(json.dumps({'evidence':str(ipc),'passed':len(checks),'final':r['state']},indent=2))
finally:
 (ipc/'stop.request').write_text('stop bounded regression scenario')
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
