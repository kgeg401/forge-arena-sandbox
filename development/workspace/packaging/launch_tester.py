"""Launch the selected local release; retain user profiles outside versions."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, os, shutil, subprocess, sys, time, uuid
from tester_common import verify_tree, sha, no_links, within, metadata_recipe
from dependencies import match_forge

def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def win_processes():
    script="@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'MTGA.exe' -or $_.Name -eq 'java.exe'} | Select-Object ProcessId,ExecutablePath,CommandLine) | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',script],capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    rows=json.loads(result.stdout) if result.stdout.strip() else []
    return rows if isinstance(rows,list) else [rows]

def focus_native(pid):
    import ctypes
    from ctypes import wintypes
    api=ctypes.WinDLL('user32',use_last_error=True)
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    api.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    api.IsWindowVisible.argtypes=[wintypes.HWND];api.IsWindowVisible.restype=wintypes.BOOL
    api.EnumWindows.argtypes=[callback,wintypes.LPARAM];api.EnumWindows.restype=wintypes.BOOL
    api.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int];api.SetForegroundWindow.argtypes=[wintypes.HWND]
    handles=[]
    def visit(handle,_):
        owner=wintypes.DWORD();api.GetWindowThreadProcessId(handle,ctypes.byref(owner))
        if owner.value==pid and api.IsWindowVisible(handle):handles.append(handle)
        return True
    api.EnumWindows(callback(visit),0)
    if handles:api.ShowWindow(handles[0],9);api.SetForegroundWindow(handles[0])
    return bool(handles)

def wait_state(lab,receipt,predicate,description,seconds=45):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if not any(p['ProcessId']==receipt['pid'] for p in win_processes()):raise RuntimeError('Native client exited; inspect '+str(lab/'unity-lab.log'))
        try:
            state=read_json(lab/'native-host-status.json')
            if state['utc']>receipt['utc']:
                if state.get('gap'):raise RuntimeError(state['gap'])
                if predicate(state):return state
        except (OSError,json.JSONDecodeError):pass
        time.sleep(.5)
    raise TimeoutError(description+' did not become ready; inspect '+str(lab/'native-host-status.json'))

def close_failed_launch(lifetime,pid):
    # The open process handle was acquired and path-checked immediately after
    # our isolated launch. No process-name kill or recycled PID is used.
    import ctypes
    from ctypes import wintypes
    api=ctypes.WinDLL('user32',use_last_error=True)
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    api.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    api.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    api.EnumWindows.argtypes=[callback,wintypes.LPARAM]
    def visit(handle,_):
        owner=wintypes.DWORD();api.GetWindowThreadProcessId(handle,ctypes.byref(owner))
        if owner.value==pid:api.PostMessageW(handle,0x0010,0,0)
        return True
    api.EnumWindows(callback(visit),0)
    deadline=time.monotonic()+8
    while lifetime.alive() and time.monotonic()<deadline:time.sleep(.1)
    if lifetime.alive():lifetime.terminate()


def start(args):
    owned={}
    try:return start_client(args,owned)
    except BaseException:
        if owned.get('lifetime'):
            try:close_failed_launch(owned['lifetime'],owned['pid'])
            except OSError as cleanup:print('The failed client could not close automatically: '+str(cleanup),file=sys.stderr)
        raise
    finally:
        if owned.get('lifetime'):owned['lifetime'].close()


def start_client(args,owned):
    install=Path(args.install_root).resolve();no_links(install)
    if (install/'installation-incomplete.txt').exists():raise ValueError('Finish installation before starting the sandbox')
    configpath=install/'sandbox-install.json';config=read_json(configpath);active=read_json(install/'active-version.json')
    from tester_common import version
    version(active['version']);app=install/'versions'/active['version'];manifest=verify_tree(app)
    if config['profileSchema']!=manifest['profileSchema'] or active['profileSchema']!=manifest['profileSchema']:raise ValueError('Profile migration required; existing profile preserved')
    data=Path(config['privateRoot']);lab=data/'native-lab'
    if data.resolve()!=install/'data' or not within(lab,install):raise ValueError('Install paths escaped configured sandbox data tree')
    requirements=read_json(app/'requirements.json')
    for rel,digest in requirements['arenaFiles'].items():
        if sha(lab/rel)!=digest:raise ValueError('This release does not support the copied Arena build: '+rel)
    if not args.check_only:
        from rules_runtime import ensure_rules_runtime
        ensure_rules_runtime(app,config)
    match_forge(data/'forge-runtime',requirements,runtime=True)
    for rel,digest in requirements['loaderFiles'].items():
        if sha(lab/rel)!=digest:raise ValueError('Copied loader changed: '+rel)
    if args.deck or args.opponent:raise ValueError('Import or choose your deck inside the client Play panel.')
    os.environ['FORGE_ARENA_CONFIG']=str(configpath)
    env={**os.environ,'FORGE_ARENA_CONFIG':str(configpath),'FORGE_ARENA_LAB_ROOT':str(lab),'PYTHONDONTWRITEBYTECODE':'1'}
    # A new release may add verified cards. Regenerate only derived metadata;
    # decks/collection remain separate. Do this before stopping a running client
    # so an incompatible mapping cannot turn a good session into a failed start.
    expected_policy=sha(app/'ForgeBackend/bridge_support.json')
    recipe=metadata_recipe(app);recipe_path=lab/'derived-metadata-receipt.json'
    try:recipe_changed=read_json(recipe_path).get('recipeSha256')!=recipe
    except (OSError,json.JSONDecodeError):recipe_changed=True
    for relative,script in (('bridge-card-manifest.json','ForgeBackend/build_card_coverage.py'),('deck-catalog.json','DeckBackend/build_deck_catalog.py')):
        try:
            existing=read_json(lab/relative);current_policy=existing.get('policySha256')
            if relative=='bridge-card-manifest.json' and existing.get('admissionSchema')!=1:current_policy=None
        except (OSError,json.JSONDecodeError):current_policy=None
        if current_policy!=expected_policy or recipe_changed:
            if args.check_only:raise ValueError('Derived card metadata needs a normal launch to refresh for this release')
            subprocess.run([sys.executable,str(app/script)],env=env,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if recipe_changed:
        pending=recipe_path.with_suffix('.pending')
        pending.write_text(json.dumps(dict(recipeSha256=recipe,policySha256=expected_policy),indent=2))
        pending.replace(recipe_path)
    procs=win_processes()
    for proc in procs:
        if proc['ExecutablePath'] and Path(proc['ExecutablePath']).name.lower()=='mtga.exe' and Path(proc['ExecutablePath']).resolve()!=lab/'MTGA.exe':raise ValueError('Another Arena client is open. Close it before starting this sandbox.')
    if args.check_only:return dict(ready=True,version=manifest['version'],mode=args.mode,isolatedLaunchRequired=True)
    running=next((p for p in procs if p['ExecutablePath'] and Path(p['ExecutablePath']).resolve()==lab/'MTGA.exe'),None)
    if running:
        focus_native(int(running['ProcessId']))
        return dict(ready=True,reused=True,version=manifest['version'],mode='client',nativePid=running['ProcessId'])
    ipc=lab/'forge-ipc'
    if (ipc/'backend-process.json').exists():
        old=read_json(ipc/'backend-process.json');running=next((p for p in procs if p['ProcessId']==old['pid']),None)
        if running:
            command=running.get('CommandLine') or ''
            if 'ForgeLandEngine' not in command or str(ipc).casefold() not in command.casefold():raise ValueError('Stale backend PID; refusing to stop an unrelated process')
            (ipc/'stop.request').write_text('Fresh isolated sandbox requested')
            end=time.monotonic()+12
            while time.monotonic()<end and any(p['ProcessId']==old['pid'] for p in win_processes()):time.sleep(.2)
            if any(p['ProcessId']==old['pid'] for p in win_processes()):raise TimeoutError('Prior Forge engine did not stop; no second engine started')
    if ipc.exists():ipc.rename(lab/('forge-ipc-evidence-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
    for name,subdir in (('NativeHost.dll','plugins/ForgeArenaSandbox'),('LocalTransport.dll','plugins/ForgeArenaSandbox'),('PreferencePatcher.dll','patchers'),('LabPreferences.dll','core')):shutil.copy2(app/'binaries'/name,lab/'BepInEx'/subdir/name)
    shutil.copy2(app/'third-party/gson/gson.jar',data/'forge-runtime/gson.jar')
    classes=data/'build/ForgeBackend/classes'
    if classes.exists():classes.rename(classes.with_name('classes-prior-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
    shutil.copytree(app/'backend',classes)
    for name in ('prepare-local-assets.request','start-board.request','start-decks.request','start-packs.request','deck-action.request.json','pack-action.request.json','native-action.request.json','incoming-messages.request.json','full-control-test.flag','enable-forge-land-test.flag','client-ui.request.json','start-client.request'):
        path=lab/name
        if path.exists():path.unlink()
    # Native menus start independently of the rules engine. The coordinator
    # creates a fresh authoritative Forge game only when the user clicks Play.
    session=str(uuid.uuid4())
    release_info=read_json(app/'release-info.json')
    (lab/'client-session.json').write_text(json.dumps(dict(schema=1,session=session,version=manifest['version'],displayVersion=release_info.get('displayVersion',manifest['version']))))
    for name in ('client-service.request.json','client-service-status.json','client-ui.request.json','start-client.request'):(lab/name).unlink(missing_ok=True)
    seeds=lab/'local-deck-seeds';seeds.mkdir(exist_ok=True)
    for path in (app/'decks').glob('*.txt'):shutil.copy2(path,seeds/path.name)
    if (app/'starter-decks.json').is_file():shutil.copy2(app/'starter-decks.json',seeds/'starter-decks.json')
    launcher=app/'binaries/launcher/LabLauncher.dll'
    result=subprocess.run([config['dotnet'],str(launcher),str(lab)],env=env,capture_output=True,text=True,check=True)
    receipt=read_json(lab/'launch-receipt.json')
    if not receipt['appContainer'] or receipt['capabilityCount']!=0 or receipt['networkCapability'] or Path(receipt['executable']).resolve()!=lab/'MTGA.exe':raise ValueError('Isolated launch receipt failed')
    from client_service import NativeLifetime
    owned['lifetime']=NativeLifetime(receipt['pid'],lab/'MTGA.exe',allow_termination=True);owned['pid']=receipt['pid']
    wait_state(lab,receipt,lambda s:s.get('papa'),'Native application context',30)
    (lab/'prepare-local-assets.request').write_text('Use locally installed native assets')
    wait_state(lab,receipt,lambda s:s.get('phase')=='local-assets-ready-render-unverified','Owned card database',60)
    print('Preparing local pack and deck menus…',flush=True)
    subprocess.run([sys.executable,'-B',str(app/'PackBackend/build_pack_catalog.py')],env=env,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    service_log=install/'logs'/('client-service-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.log')
    with service_log.open('w',encoding='utf8') as log:
        service=subprocess.Popen([config['python'],'-B',str(app/'client_service.py'),'--config',str(configpath),'--native-pid',str(receipt['pid']),'--session',session],env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (lab/'client-service-process.json').write_text(json.dumps(dict(pid=service.pid,nativePid=receipt['pid'],session=session,log=str(service_log)),indent=2))
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        if service.poll() is not None:raise RuntimeError('Local match coordinator could not start. See '+str(service_log))
        try:
            status=read_json(lab/'client-service-status.json')
            if status.get('session')==session and status.get('phase')=='idle':break
        except (OSError,json.JSONDecodeError):pass
        time.sleep(.1)
    else:raise TimeoutError('Local match coordinator did not become ready')
    print('Opening Home…',flush=True)
    (lab/'start-client.request').write_text('Open the persistent native sandbox client')
    state=wait_state(lab,receipt,lambda s:s.get('phase')=='native-local-client','Native Home menu',45)
    if args.mode=='decks':(lab/'client-ui.request.json').write_text(json.dumps(dict(op='decks')))
    record=dict(version=manifest['version'],mode=args.mode,launch=receipt,nativeState=state,scope='Native readiness; rendered/manual gameplay needs separate checks')
    (install/'last-start.json').write_text(json.dumps(record,indent=2));return record

def parser():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--install-root',required=True);p.add_argument('--mode',choices=('client','practice','hares','decks'),default='client');p.add_argument('--deck');p.add_argument('--opponent');p.add_argument('--check-only',action='store_true');return p
if __name__=='__main__':
    try:print(json.dumps(start(parser().parse_args()),indent=2))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('Sandbox startup stopped: '+str(e))
