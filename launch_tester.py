"""Launch the selected local release; retain user profiles outside versions."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, os, shutil, subprocess, sys, time
from tester_common import verify_tree, sha, no_links, within, metadata_recipe

def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def win_processes():
    script="@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'MTGA.exe' -or $_.Name -eq 'java.exe'} | Select-Object ProcessId,ExecutablePath,CommandLine) | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',script],capture_output=True,text=True,check=True)
    rows=json.loads(result.stdout) if result.stdout.strip() else []
    return rows if isinstance(rows,list) else [rows]

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

def start(args):
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
    if sha(data/'forge-runtime/forge.jar')!=requirements['forgeFiles'][requirements['forgeJar']]:raise ValueError('Copied Forge engine changed')
    for rel,digest in requirements['forgeFiles'].items():
        if rel.startswith('res/') and sha(data/'forge-runtime'/rel)!=digest:raise ValueError('Copied Forge scripts changed: '+rel)
    for rel,digest in requirements['loaderFiles'].items():
        if sha(lab/rel)!=digest:raise ValueError('Copied loader changed: '+rel)
    # Preflight deck admission before disrupting any running private client.
    sys.path.insert(0,str(app/'ForgeBackend'));from deck_import import read_deck
    decks=None
    if args.mode!='decks':
        local=read_deck(Path(args.deck).resolve() if args.deck else app/'decks'/('Hare-Apparent-Practice.txt' if args.mode=='hares' else 'White-Blue-Study.txt'))
        opponent=read_deck(Path(args.opponent).resolve() if args.opponent else app/'decks/White-Lifegain.txt');decks=dict(localDeck=local,opponentDeck=opponent)
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
    for proc in procs:
        if proc['ExecutablePath'] and Path(proc['ExecutablePath']).resolve()==lab/'MTGA.exe':
            subprocess.run(['powershell.exe','-NoProfile','-Command','Stop-Process -Id '+str(int(proc['ProcessId']))+' -ErrorAction Stop'],check=True)
    ipc=lab/'forge-ipc'
    if (ipc/'backend-process.json').exists():
        old=read_json(ipc/'backend-process.json');running=next((p for p in procs if p['ProcessId']==old['pid']),None)
        if running:
            command=running.get('CommandLine') or ''
            if 'ForgeLandEngine' not in command or str(data).casefold() not in command.casefold():raise ValueError('Stale backend PID; refusing to stop an unrelated process')
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
    for name in ('prepare-local-assets.request','start-board.request','start-decks.request','start-packs.request','deck-action.request.json','pack-action.request.json','native-action.request.json','incoming-messages.request.json','full-control-test.flag','enable-forge-land-test.flag'):
        path=lab/name
        if path.exists():path.unlink()
    if decks:
        ipc.mkdir();(ipc/'scenario.json').write_text(json.dumps(dict(scenario='custom-duel',**decks)))
        (lab/'enable-forge-land-test.flag').write_text('Forge is authoritative; no fixture gameplay')
        subprocess.run([sys.executable,str(app/'ForgeBackend/start_backend.py')],env=env,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    launcher=app/'binaries/launcher/LabLauncher.dll'
    result=subprocess.run([config['dotnet'],str(launcher),str(lab)],env=env,capture_output=True,text=True,check=True)
    receipt=read_json(lab/'launch-receipt.json')
    if not receipt['appContainer'] or receipt['capabilityCount']!=0 or receipt['networkCapability'] or Path(receipt['executable']).resolve()!=lab/'MTGA.exe':raise ValueError('Isolated launch receipt failed')
    wait_state(lab,receipt,lambda s:s.get('papa'),'Native application context',30)
    (lab/'prepare-local-assets.request').write_text('Use locally installed native assets')
    wait_state(lab,receipt,lambda s:s.get('phase')=='local-assets-ready-render-unverified','Owned card database',60)
    if args.mode=='decks':
        (lab/'start-decks.request').write_text('Open native local deck browser')
        state=wait_state(lab,receipt,lambda s:s.get('phase')=='native-local-deck-editor','Native deck browser',45)
    else:
        (lab/'start-board.request').write_text('Open Forge-backed native board')
        state=wait_state(lab,receipt,lambda s:s.get('nativeState') and 'DuelScene' in s.get('scenes',[]) and 'PreGameScene' not in s.get('scenes',[]),'Native Forge board',60)
    record=dict(version=manifest['version'],mode=args.mode,launch=receipt,nativeState=state,scope='Native readiness; rendered/manual gameplay needs separate checks')
    (install/'last-start.json').write_text(json.dumps(record,indent=2));return record

def parser():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--install-root',required=True);p.add_argument('--mode',choices=('practice','hares','decks'),default='practice');p.add_argument('--deck');p.add_argument('--opponent');p.add_argument('--check-only',action='store_true');return p
if __name__=='__main__':
    try:print(json.dumps(start(parser().parse_args()),indent=2))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('Sandbox startup stopped: '+str(e))
