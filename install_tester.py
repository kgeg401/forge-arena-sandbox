"""Prepare a separate local sandbox from the recipient's own installations."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, os, shutil, subprocess, sys
from tester_common import sha, within, no_links, verify_tree, repository_name
from board_template import board_template
from dependencies import match_forge

HERE=Path(__file__).resolve().parent
ARENA_PARTS=('MTGA.exe','UnityPlayer.dll','MonoBleedingEdge','MTGA_Data','D3D12','Contents')

def check_destination(destination):
    """A new folder or our own launcher-only install; preserve all profiles."""
    destination=Path(destination);no_links(destination)
    if not destination.exists():return False
    try:config=json.loads((destination/'sandbox-install.json').read_text())
    except (OSError,ValueError):raise ValueError('Choose a new folder or an existing launcher-only sandbox. Existing unrelated files were preserved.')
    if config.get('installationMode')!='launcher-only' or config.get('profileSchema')!=1 or Path(config['privateRoot']).resolve()!=destination.resolve()/'data':raise ValueError('This sandbox already has game files. Use its updater or choose a NEW folder.')
    if (destination/'installation-incomplete.txt').exists():raise ValueError('An interrupted setup is preserved here. Choose a new folder; do not remove your saved profile.')
    profile=destination/'data/native-lab/local-profile'
    for path in (destination/'data').rglob('*'):
        no_links(path)
        if path.is_file() and not within(path,profile):raise ValueError('Unexpected files in launcher data; no existing files were overwritten.')
    return True

def install_launchers(destination,app):
    """Stable entry points load the active version; never change saved data."""
    destination=Path(destination);app=Path(app);no_links(destination)
    config=json.loads((destination/'sandbox-install.json').read_text())
    if Path(config['privateRoot']).resolve()!=destination.resolve()/'data':raise ValueError('Unexpected bootstrap destination')
    shutil.copy2(app/'client_bootstrap.py',destination/'client_bootstrap.py')
    # Locally created shortcuts target the recipient's own interpreter. No
    # global execution-policy change and no unsigned PowerShell file is needed.
    shortcut_script='''$ErrorActionPreference='Stop'
$shell=New-Object -ComObject WScript.Shell
$root=$env:FORGE_ARENA_SHORTCUT_ROOT
$modes=@{'Start Sandbox'='hub';'Start Practice'='practice';'Start Hares'='hares';'Open Decks'='decks';'Check Updates'='check';'Install Update'='update';'Rollback Sandbox'='rollback'}
foreach($name in $modes.Keys){
  $shortcut=$shell.CreateShortcut((Join-Path $root ($name+'.lnk')))
  $shortcut.TargetPath=$env:FORGE_ARENA_SHORTCUT_PYTHON
  $shortcut.Arguments='-B "'+(Join-Path $root 'client_bootstrap.py')+'" '+$modes[$name]
  $shortcut.WorkingDirectory=$root
  $shortcut.Description='Forge Arena local sandbox'
  $shortcut.Save()
}'''
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',shortcut_script],check=True,
                   env={**os.environ,'FORGE_ARENA_SHORTCUT_ROOT':str(destination),'FORGE_ARENA_SHORTCUT_PYTHON':config['python']},creationflags=subprocess.CREATE_NO_WINDOW)
    shutil.copy2(app/'Start-Client.ps1',destination/'Start-Client.ps1')
    for mode in ('practice','hares','decks'):
        (destination/('Start-'+mode.title()+'.cmd')).write_text('@echo off\r\npowershell.exe -NoProfile -File "%~dp0Start-Client.ps1" -Mode '+mode+'\r\nif errorlevel 1 pause\r\n')
    shutil.copy2(app/'Manage-Updates.ps1',destination/'Manage-Updates.ps1')
    for filename,action in (('Check-Updates','Check'),('Install-Update','Install'),('Rollback-Sandbox','Rollback')):
        (destination/(filename+'.cmd')).write_text('@echo off\r\npowershell.exe -NoProfile -File "%~dp0Manage-Updates.ps1" -Action '+action+'\r\npause\r\n')

def inspect_install(arena,forge,java,loader,destination,package,dotnet=None):
    manifest=verify_tree(package);requirements=json.loads((package/'requirements.json').read_text())
    for p in (arena,forge,java,loader):
        no_links(p)
        if not p.is_dir():raise ValueError('Missing prerequisite directory: '+str(p))
        if within(destination,p) or within(p,destination):raise ValueError('Destination must be separate from Arena, Forge, Java and the loader')
    no_links(destination)
    complete_launcher=check_destination(destination)
    existing_app=destination/'versions'/manifest['version']
    if existing_app.exists() and verify_tree(existing_app)!=manifest:raise ValueError('Existing adapter version differs; no files were copied')
    checks=[]
    variant=match_forge(forge,requirements)
    for base,entries in ((arena,requirements['arenaFiles']),(forge,variant['files']),(loader,requirements['loaderFiles'])):
        for rel,digest in entries.items():
            path=base/rel;no_links(path)
            if not path.is_file() or sha(path)!=digest:raise ValueError('Unsupported or changed prerequisite: '+str(path))
            checks.append(str(path))
    if os.name!='nt':raise ValueError('This native client requires 64-bit Windows')
    if sys.version_info<(3,10):raise ValueError('Python 3.10 or newer is required')
    java_version=subprocess.run([str(java/'bin/java.exe'),'-version'],capture_output=True,text=True,check=True).stderr
    if not __import__('re').search(r'version "17[.\"]',java_version):raise ValueError('Use the tested Java 17 runtime')
    dotnet=dotnet or shutil.which('dotnet')
    if not dotnet:raise ValueError('Install the .NET 8 x64 runtime first')
    runtimes=subprocess.run([dotnet,'--list-runtimes'],capture_output=True,text=True,check=True).stdout
    if 'Microsoft.NETCore.App 8.' not in runtimes:raise ValueError('Install the .NET 8 x64 runtime first')
    files=[]
    for name in ARENA_PARTS:
        p=arena/name
        if p.is_file():files.append(p)
        elif p.is_dir():files.extend(x for x in p.rglob('*') if x.is_file() and 'Logs' not in x.parts and x.suffix.lower()!='.log')
    for p in files:no_links(p)
    forge_resources=[p for p in (forge/'res').rglob('*') if p.is_file()]
    for p in forge_resources:no_links(p)
    forge_bytes=sum(p.stat().st_size for p in forge_resources)+(forge/variant['jar']).stat().st_size
    required=sum(p.stat().st_size for p in files)+forge_bytes
    anchor=destination.parent
    while not anchor.exists():anchor=anchor.parent
    if shutil.disk_usage(anchor).free<required+2*1024**3:raise ValueError('Not enough free space for an independent Arena copy plus a 2 GB reserve')
    return dict(manifest=manifest,requirements=requirements,forgeVariant=variant,completeLauncher=complete_launcher,sourceFiles=files,forgeResources=forge_resources,checks=checks,estimatedArenaBytes=required-forge_bytes,estimatedForgeBytes=forge_bytes,estimatedTotalBytes=required,dotnet=dotnet,javaVersion=java_version.splitlines()[0])

def install(args):
    if args.repository:repository_name(args.repository)
    paths=[Path(getattr(args,n)).absolute() for n in ('arena','forge','java','loader','destination')]
    arena,forge,java,loader,destination=paths;package=Path(args.package).resolve()
    plan=inspect_install(arena,forge,java,loader,destination,package,getattr(args,'dotnet',None))
    report=dict(compatible=True,version=plan['manifest']['version'],destination=str(destination),estimatedArenaBytes=plan['estimatedArenaBytes'],estimatedForgeBytes=plan['estimatedForgeBytes'],estimatedTotalBytes=plan['estimatedTotalBytes'],sourceFiles=len(plan['sourceFiles']),prerequisiteChecks=len(plan['checks']),checkOnly=args.check_only)
    print(json.dumps(report,indent=2),flush=True)
    if args.check_only:return report
    if plan['completeLauncher']:
        backup=destination/'profile-backups'/('before-game-setup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        source_profile=destination/'data/native-lab/local-profile'
        if source_profile.exists():shutil.copytree(source_profile,backup/'local-profile')
        else:backup.mkdir(parents=True)
        shutil.copy2(destination/'sandbox-install.json',backup/'sandbox-install.json')
    destination.mkdir(parents=True,exist_ok=plan['completeLauncher']);(destination/'installation-incomplete.txt').write_text('Do not launch until installation completes.')
    data=destination/'data';lab=data/'native-lab';lab.mkdir(parents=True,exist_ok=plan['completeLauncher'])
    for index,source in enumerate(plan['sourceFiles']):
        target=lab/source.relative_to(arena);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if index%2000==0:print('Copied',index,'of',len(plan['sourceFiles']),'owned client files',flush=True)
    # No loader/game binaries are in our release: copy each from supplied local
    # prerequisites, with pinned hashes and no third-party plugin directories.
    for rel in plan['requirements']['loaderFiles']:
        target=lab/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(loader/rel,target)
    (lab/'sandbox-lab.json').write_text(json.dumps(dict(localOnly=True,requireAppContainer=True,source=str(arena),independentCopies=True),indent=2))
    (lab/'sandbox-source.txt').write_text(str(arena))
    version=plan['manifest']['version'];app=destination/'versions'/version
    if app.exists():
        if verify_tree(app)!=plan['manifest']:raise ValueError('Existing adapter version differs; preserved without overwrite')
    else:shutil.copytree(package,app,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    runtime=data/'forge-runtime';runtime.mkdir()
    jarrel=plan['forgeVariant']['jar'];shutil.copy2(forge/jarrel,runtime/'forge.jar')
    if (forge/'LICENSE.txt').is_file():shutil.copy2(forge/'LICENSE.txt',runtime/'LICENSE.txt')
    shutil.copy2(app/'third-party/gson/gson.jar',runtime/'gson.jar')
    for index,source in enumerate(plan['forgeResources']):
        target=runtime/source.relative_to(forge);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if index%2000==0:print('Copied',index,'of',len(plan['forgeResources']),'local Forge resource files',flush=True)
    (runtime/'forge.profile.properties').write_text('userDir='+str(runtime/'user').replace('\\','/')+'\ncacheDir='+str(runtime/'cache').replace('\\','/')+'\n')
    classes=data/'build/ForgeBackend/classes';shutil.copytree(app/'backend',classes)
    dotnet=plan['dotnet']
    if getattr(args,'copy_runtimes',False):
        java_copy=data/'runtimes/java';shutil.copytree(java,java_copy);java=java_copy
        net_copy=data/'runtimes/dotnet';shutil.copytree(Path(dotnet).parent,net_copy);dotnet=str(net_copy/'dotnet.exe')
    config=dict(schema=1,profileSchema=1,privateRoot=str(data),arenaInstall=str(arena),catalogueInstall=str(lab),forgeInstall=str(forge),forgeResourcesRoot=str(runtime),javaHome=str(java),python=sys.executable,dotnet=plan['dotnet'])
    config['dotnet']=dotnet;config['forgeVariant']=plan['forgeVariant']['id']
    if getattr(args,'copy_runtimes',False):config['forgeInstall']=str(runtime)
    if args.repository:
        config['updateRepository']=args.repository
        config['automaticUpdates']=True
        config['updateChannel']=getattr(args,'channel','test')
    configpath=destination/'sandbox-install.json';configpath.write_text(json.dumps(config,indent=2))
    env={**os.environ,'FORGE_ARENA_CONFIG':str(configpath),'PYTHONDONTWRITEBYTECODE':'1'}
    for script in ('ForgeBackend/build_card_coverage.py','DeckBackend/build_deck_catalog.py'):
        subprocess.run([sys.executable,str(app/script)],env=env,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    (lab/'board-fixture.json').write_text(json.dumps(board_template(),indent=2))
    (lab/'local-deck-seeds').mkdir()
    for path in (app/'decks').glob('*.txt'):shutil.copy2(path,lab/'local-deck-seeds'/path.name)
    for name,subdir in (('NativeHost.dll','plugins/ForgeArenaSandbox'),('LocalTransport.dll','plugins/ForgeArenaSandbox'),('PreferencePatcher.dll','patchers'),('LabPreferences.dll','core')):
        target=lab/'BepInEx'/subdir/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(app/'binaries'/name,target)
    # Recheck all pinned installed artifacts after copying, before marking ready.
    for rel,digest in plan['requirements']['arenaFiles'].items():
        if sha(lab/rel)!=digest:raise ValueError('Copied client changed during install: '+rel)
    (destination/'active-version.json').write_text(json.dumps(dict(version=version,previous=None,profileSchema=1),indent=2))
    install_launchers(destination,app)
    (destination/'installation-incomplete.txt').unlink()
    report.update(installed=True,finishedUtc=datetime.now(timezone.utc).isoformat(),config=str(configpath),packageManifestSha256=sha(app/'release-manifest.json'))
    (destination/'install-receipt.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    return report

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('arena','forge','java','loader','destination'):p.add_argument('--'+n,required=True)
    p.add_argument('--package',default=str(HERE));p.add_argument('--check-only',action='store_true');p.add_argument('--repository',help='Trusted GitHub owner/repository for automatic adapter updates');p.add_argument('--channel',default='test',choices=('test','stable'));p.add_argument('--dotnet');p.add_argument('--copy-runtimes',action='store_true');return p
if __name__=='__main__':
    try:install(parser().parse_args())
    except (OSError,ValueError,subprocess.SubprocessError) as e:raise SystemExit('Setup stopped; existing installs preserved: '+str(e))
