"""Launch a pinned private research preview without replacing a parked client.

This is a developer checkpoint launcher, not the public installer. Immutable
owned assets must already have been prepared in a separate AppContainer lab.
"""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,time,uuid,traceback

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
 digest=hashlib.sha256()
 with Path(path).open('rb') as handle:
  for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
 return digest.hexdigest()
def processes():
 command="@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'MTGA.exe' -or $_.Name -eq 'java.exe'} | Select-Object ProcessId,ExecutablePath,CommandLine) | ConvertTo-Json -Compress"
 result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
 value=json.loads(result.stdout) if result.stdout.strip() else []
 return value if isinstance(value,list) else [value]
def wait(lab,pid,predicate,seconds=65):
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  if not any(p['ProcessId']==pid for p in processes()):raise RuntimeError('The preview client exited during startup')
  try:
   state=read(lab/'native-host-status.json')
   if state.get('gap'):raise RuntimeError(state['gap'])
   if predicate(state):return state
  except (OSError,json.JSONDecodeError):pass
  time.sleep(.2)
 raise TimeoutError('The preview did not become ready; inspect native-host-status.json')
def launch(spec_path):
 spec=read(spec_path);root=Path(spec['privateRoot']).resolve();lab=root/'native-lab';release=Path(spec['releaseRoot']).resolve()
 if spec.get('schema')!=1 or read(lab/'sandbox-lab.json').get('researchOnly') is not True:raise ValueError('A schema-1 private research lab is required')
 config=read(spec['runtimeConfig'])
 if Path(config['privateRoot']).resolve()!=root:raise ValueError('Preview configuration names a different private root')
 required={'NativeHost.dll','LocalTransport.dll','backend/ForgeLandEngine.class','launcher/LabLauncher.dll','app/client_service.py','app/ForgeBackend/bridge_support.json','app/ForgeBackend/experimental-admission.json','app/ForgeBackend/card-support-index.json','app/decks/Brawl-Isamaru-Bot.txt'}
 if not required.issubset(spec['files']):raise ValueError('Incomplete preview release: '+', '.join(sorted(required-set(spec['files']))))
 for name,digest in spec['files'].items():
  path=(release/name).resolve()
  if release not in path.parents or sha(path)!=digest:raise ValueError('Preview release file changed: '+name)
 for name,digest in spec['nativeRequirements'].items():
  path=(lab/name).resolve()
  if lab not in path.parents or sha(path)!=digest:raise ValueError('Pinned Arena preview build changed: '+name)
 env={**os.environ,'FORGE_ARENA_LAB_ROOT':str(lab),'FORGE_ARENA_CONFIG':str(Path(spec['runtimeConfig']).resolve()),'PYTHONDONTWRITEBYTECODE':'1'}
 # Import the pinned policy before starting Unity. Missing admission data or
 # a changed catalogue must fail here rather than strand the native queue.
 preflight=subprocess.run([config['python'],'-B','-c','import sys;sys.path.insert(0,sys.argv[1]);import deck_import',str(release/'app/ForgeBackend')],env=env,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
 if preflight.returncode:raise RuntimeError('Preview card-policy preflight failed: '+preflight.stderr[-1500:])
 sys.path.insert(0,str(release/'app'));from client_service import NativeLifetime,service_lock
 with service_lock(lab/'preview-launch.lock',wait_seconds=15):
  running=[p for p in processes() if p.get('ExecutablePath') and Path(p['ExecutablePath']).resolve()==lab/'MTGA.exe']
  if len(running)>1:raise RuntimeError('More than one preview client is open')
  if running:
   # Reuse this lab only. Other Arena processes, including the parked match,
   # have different executable paths and are never closed or controlled here.
   if read(lab/'client-session.json').get('version')!=spec['version']:raise RuntimeError('A different preview build is open. Close that preview window and try again. Your other client can stay open.')
   for name in ['NativeHost.dll','LocalTransport.dll']:
    if sha(lab/'BepInEx/plugins/ForgeArenaSandbox'/name)!=spec['files'][name]:raise RuntimeError('The open preview has different bridge files; close its window before updating')
   import ctypes
   pid=int(running[0]['ProcessId']);owned=NativeLifetime(pid,lab/'MTGA.exe')
   try:
    if not owned.alive():raise RuntimeError('The existing preview exited; launch it again')
    api=ctypes.WinDLL('user32');api.AllowSetForegroundWindow(pid)
    subprocess.run(['powershell.exe','-NoProfile','-Command',f"(New-Object -ComObject WScript.Shell).AppActivate({pid}) | Out-Null"],creationflags=subprocess.CREATE_NO_WINDOW)
   finally:owned.close()
   return dict(reused=True,pid=pid)
  prior=lab/'forge-ipc/backend-process.json'
  if prior.exists():
   old=read(prior);candidate=next((p for p in processes() if p['ProcessId']==old['pid']),None)
   if candidate:
    command=candidate.get('CommandLine') or ''
    if 'ForgeLandEngine' not in command or str(lab/'forge-ipc').casefold() not in command.casefold():raise RuntimeError('Stale preview engine identity; no unrelated process was stopped')
    (lab/'forge-ipc/stop.request').write_text('Preview client was closed')
    deadline=time.monotonic()+15
    while time.monotonic()<deadline and any(p['ProcessId']==old['pid'] for p in processes()):time.sleep(.2)
    if any(p['ProcessId']==old['pid'] for p in processes()):raise RuntimeError('The previous preview rules process did not stop')
  for name in ['NativeHost.dll','LocalTransport.dll']:shutil.copy2(release/name,lab/'BepInEx/plugins/ForgeArenaSandbox'/name)
  classes=root/'build/ForgeBackend/classes';classes.mkdir(parents=True,exist_ok=True)
  for path in (release/'backend').glob('*.class'):shutil.copy2(path,classes/path.name)
  for name in ['start-client.request','prepare-local-assets.request','client-ui.request.json','native-host-status.json','client-ui-status.json','start-board.request','native-action.request.json','incoming-messages.request.json','client-service.request.json','client-service-status.json','full-control-test.flag','enable-forge-land-test.flag','pod-probe.request.json']:(lab/name).unlink(missing_ok=True)
  session=str(uuid.uuid4());(lab/'client-session.json').write_text(json.dumps(dict(schema=1,session=session,version=spec['version'],displayVersion='Commander Pod Preview')))
  result=subprocess.run([config['dotnet'],str(release/'launcher/LabLauncher.dll'),str(lab)],env=env,capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
  receipt=read(lab/'launch-receipt.json');pid=receipt['pid']
  if not (receipt.get('appContainer') and receipt.get('capabilityCount')==0 and not receipt.get('networkCapability') and Path(receipt['executable']).resolve()==lab/'MTGA.exe'):raise RuntimeError('Preview launch did not return the expected isolated executable receipt')
  owned=NativeLifetime(pid,lab/'MTGA.exe',allow_termination=True)
  try:
   wait(lab,pid,lambda s:s.get('papa'),30)
   (lab/'prepare-local-assets.request').write_text('Use the pinned owned local assets')
   wait(lab,pid,lambda s:s.get('phase')=='local-assets-ready-render-unverified')
   logs=root/'preview-logs';logs.mkdir(exist_ok=True)
   log=logs/('coordinator-'+time.strftime('%Y%m%d-%H%M%S')+'.log')
   with log.open('w',encoding='utf8') as output:
    coordinator=subprocess.Popen([config['python'],'-B',str(release/'app/client_service.py'),'--config',str(spec['runtimeConfig']),'--native-pid',str(pid),'--session',session],stdout=output,stderr=subprocess.STDOUT,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
   (lab/'preview-coordinator.json').write_text(json.dumps(dict(pid=coordinator.pid,nativePid=pid,session=session,log=str(log))))
   deadline=time.monotonic()+25
   while time.monotonic()<deadline:
    if coordinator.poll() is not None:raise RuntimeError('Preview coordinator exited; see '+str(log))
    try:
     status=read(lab/'client-service-status.json')
     if status.get('session')==session and status.get('phase')=='idle':break
    except (OSError,json.JSONDecodeError):pass
    time.sleep(.1)
   else:raise RuntimeError('Preview coordinator did not become ready')
   (lab/'start-client.request').write_text('Open the dedicated Commander pod preview')
   deadline=time.monotonic()+30
   while time.monotonic()<deadline:
    try:
     ui=read(lab/'client-ui-status.json')
     if ui.get('screen')=='home' and not ui.get('error'):return dict(reused=False,pid=pid,coordinatorPid=coordinator.pid,session=session)
     if ui.get('error'):raise RuntimeError(ui['error'])
    except (OSError,json.JSONDecodeError):pass
    time.sleep(.2)
   raise RuntimeError('Preview Home did not become ready')
  except BaseException:
   if owned.alive():owned.terminate()
   raise
  finally:owned.close()
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',type=Path,required=True);args=p.parse_args()
 try:
  result=launch(args.spec);Path(args.spec).with_name('preview-launch-result.json').write_text(json.dumps(result,indent=2))
  if sys.stdout:print(json.dumps(result),flush=True)
 except BaseException as error:
  details=Path(args.spec).with_name('preview-launch-error.log');details.write_text(traceback.format_exc(),encoding='utf8')
  if sys.stderr:print(str(error),file=sys.stderr)
  if sys.stderr is None:
   import tkinter as tk
   from tkinter import messagebox
   w=tk.Tk();w.withdraw();messagebox.showerror('Commander Pod Preview',str(error)+'\n\nDetails: '+str(details));w.destroy()
  raise
