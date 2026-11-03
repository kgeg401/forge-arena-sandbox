"""Build an unpublished adapter-only ZIP from explicit, own-file allowlists."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path, PureWindowsPath, PurePosixPath
from datetime import datetime, timezone
import argparse, json, os, shutil, subprocess, zipfile
from tester_common import sha, version, verify_tree

REPO=Path(__file__).resolve().parents[1]
PRIVATE=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox')
ARENA=Path(r'D:\GAMES\MTGA')
FORGE=Path.home()/'Games/Forge'
LOADER=PRIVATE/'tools/BepInEx-5.4.23.5'
OWN_SCRIPTS=('multiplayer_room.py','multiplayer_rules.py','multiplayer_view.py','multiplayer_session.py','multiplayer_lobby.py','install_tester.py','launch_tester.py','update_tester.py','rules_runtime.py','tester_common.py','match_archives.py','board_template.py','client_bootstrap.py','client_entry.py','client_service.py','setup_client.py','auto_install.py','dependencies.py','dependencies-lock.json','starter-decks.json','starter_content.py','starter-content.json','paper_art.py','paper-art.json','Setup.cmd','Start-Client.ps1','Manage-Updates.ps1','TESTER-README.md','LICENSE.txt')
PYTHON_FILES=('ForgeBackend/runtime_paths.py','ForgeBackend/arena_catalog.py','ForgeBackend/card_support.py','ForgeBackend/start_backend.py','ForgeBackend/deck_import.py','ForgeBackend/experimental_cards.py','ForgeBackend/build_card_coverage.py','ForgeBackend/bridge_support.json','DeckBackend/build_deck_catalog.py','PackBackend/build_pack_catalog.py')

def build(tag,output,gameplay_ref=None,headline='Public launcher and automatic update test',support_index=None,display_version=None,native_build_root=None,experimental_admission=None,forge_build_jar=None,arena_install=None):
    arena=Path(arena_install) if arena_install else ARENA
    version(tag)
    if not gameplay_ref:raise ValueError('Select an independently verified committed gameplay checkpoint with --gameplay-ref; working admission drafts cannot be packaged')
    if output.exists():raise ValueError('Use a new package staging directory; prior packages are preserved')
    output.mkdir(parents=True)
    # A Windows-native first step can install Python before any Python script
    # is needed on the recipient's machine. Compile only our authored source.
    compiler=Path(__import__('os').environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler),'/nologo','/target:winexe','/platform:x64','/optimize+',
        '/r:System.Windows.Forms.dll','/r:System.Drawing.dll','/r:System.Web.Extensions.dll',
        '/out:'+str(output/'Setup.exe'),str(REPO/'packaging/SetupBootstrap.cs')],check=True)
    subprocess.run([str(compiler),'/nologo','/target:winexe','/platform:x64','/optimize+',
        '/r:System.Windows.Forms.dll','/r:System.Drawing.dll','/r:System.Web.Extensions.dll',
        '/out:'+str(output/'ForgeArenaSandbox.exe'),str(REPO/'packaging/ClientLauncher.cs')],check=True)
    (output/'client-launcher-info.json').write_text(json.dumps(dict(schema=1,sourceSha256=sha(REPO/'packaging/ClientLauncher.cs'),sha256=sha(output/'ForgeArenaSandbox.exe')),indent=2))
    for filename in (*OWN_SCRIPTS,'arena_compat.py'):shutil.copy2(REPO/'packaging'/filename,output/filename)
    shutil.copy2(REPO/'packaging/TESTER-README.md',output/'README.md')
    for filename in (*PYTHON_FILES,'ForgeBackend/arena-builds.json','ForgeBackend/experimental-admission-14589.json'):
        target=output/filename;target.parent.mkdir(exist_ok=True);shutil.copy2(REPO/filename,target)
    shutil.copytree(REPO/'decks',output/'decks',ignore=shutil.ignore_patterns('__pycache__'))
    if gameplay_ref:
        # Publish a verified gameplay checkpoint without including unfinished
        # card-policy work in the developer checkout.
        policy=subprocess.run(['git','show',gameplay_ref+':./ForgeBackend/bridge_support.json'],cwd=REPO,capture_output=True,check=True).stdout
        (output/'ForgeBackend/bridge_support.json').write_bytes(policy)
        names=subprocess.run(['git','ls-tree','-r','--name-only',gameplay_ref,'decks'],cwd=REPO,capture_output=True,text=True,check=True).stdout.splitlines()
        for p in (output/'decks').iterdir():
            if p.is_file() and 'decks/'+p.name not in names:p.unlink()
    policy=json.loads((output/'ForgeBackend/bridge_support.json').read_text())
    if policy.get('researchOnly'):raise ValueError('Research admission policies cannot be packaged as supported gameplay')
    experimental=None
    if experimental_admission:
        sys.path.insert(0,str(REPO/'ForgeBackend'))
        from experimental_cards import load_experimental
        experimental=load_experimental(experimental_admission)
        if experimental['policySha256']!=sha(output/'ForgeBackend/bridge_support.json'):raise ValueError('Experimental inventory differs from packaged verified baseline')
        # Evidence hashes are useful in the release; this developer's absolute
        # machine paths are not. Keep identities and bindings byte-for-byte in
        # JSON value terms, changing only the projection input labels.
        source=experimental.get('humanChoices',{}).get('provenance',{}).get('source',{})
        if 'inputs' in source:
            portable={}
            for name,digest in source['inputs'].items():
                label=PureWindowsPath(name).name if '\\' in name else PurePosixPath(name).name
                if label in portable:raise ValueError('Ambiguous packaged evidence input name: '+label)
                portable[label]=digest
            source['inputs']=portable
        (output/'ForgeBackend/experimental-admission.json').write_text(json.dumps(experimental,indent=2),encoding='utf8')
        current_path=output/'ForgeBackend/experimental-admission-14589.json'
        current=json.loads(current_path.read_text(encoding='utf8'))
        profile=next(b for b in json.loads((output/'ForgeBackend/arena-builds.json').read_text(encoding='utf8'))['builds'] if b['id']=='arena-14589')
        if current['sourceDatabaseSha256']!=profile['databaseSha256'] or current['humanChoices']['sourceDatabaseSha256']!=profile['databaseSha256'] or current['policySha256']!=experimental['policySha256'] or current['cards']!=experimental['cards']:
            raise ValueError('Current Arena overlay does not preserve the reviewed catalogue')
        for key in ('cardOverrides','presentationObjects','keywordAbilityIds','typeEnumIds','cardNameIds'):
            if current['humanChoices'][key]!=experimental['humanChoices'][key]:raise ValueError('Current Arena presentation identities drifted: '+key)
        inputs=current['humanChoices'].get('provenance',{}).get('source',{}).get('inputs')
        if inputs:
            labels={PureWindowsPath(name).name if '\\' in name else PurePosixPath(name).name:digest for name,digest in inputs.items()}
            if len(labels)!=len(inputs):raise ValueError('Ambiguous current Arena evidence input name')
            current['humanChoices']['provenance']['source']['inputs']=labels
        current_path.write_text(json.dumps(current,indent=2),encoding='utf8')
    if support_index:
        index=json.loads(Path(support_index).read_text(encoding='utf8'))
        if index.get('schema')!=1 or index.get('provenance',{}).get('policySha256')!=sha(output/'ForgeBackend/bridge_support.json'):
            raise ValueError('Support diagnostics must match the packaged admission policy exactly')
        shutil.copy2(support_index,output/'ForgeBackend/card-support-index.json')
    release_info=dict(version=tag,displayVersion=display_version or tag,headline=headline,testRelease=True,gameplaySource=gameplay_ref,admittedNames=policy['verifiedNames'])
    if experimental:release_info.update(experimentalAdmission=True,experimentalNames=sorted(experimental['cards']),experimentalStatus='Experimental access; runtime gaps remain explicit')
    (output/'release-info.json').write_text(json.dumps(release_info,indent=2))
    docs=output/'docs';docs.mkdir()
    for file in [*(REPO/'packaging/public-docs').glob('*.md'),*(REPO/'packaging/public-docs').glob('MOXFIELD-CARD-COVERAGE.csv')]:shutil.copy2(file,docs/file.name)
    if experimental:
        notice='# Experimental card catalogue\n\nThis build enables '+str(len(experimental['cards']))+' additional experimental card names. The verified catalogue remains '+str(len(policy['verifiedNames']))+' names. See docs/VERIFICATION.md and docs/MOXFIELD-COVERAGE.md for tested scenarios and per-card coverage. Permission to start a match is not exhaustive proof of its effects or combos. Actual unmapped mechanics still report a gap.\n\nUse Manage-Updates.ps1 rollback to return to the previous build. Saved decks and profiles are retained.\n'
        (docs/'EXPERIMENTAL.md').write_text(notice+'\n## Remaining hard blockers\n\n'+''.join('- '+name+': '+reason+'\n' for name,reason in experimental['blockedCards'].items()),encoding='utf8')
        for readme in ('README.md','TESTER-README.md'):
            file=output/readme;file.write_text(notice+'\n---\n\n'+file.read_text(encoding='utf8'),encoding='utf8')
    supported='# Verified card names\n\nThis release admits '+str(len(policy['verifiedNames']))+' main-deck names. Brawl commanders are separately verified.\nSearching, opening or storing another Arena card does not establish match support.\n\n## Brawl commanders\n\n'
    supported+=''.join('- '+name+'\n' for name in sorted(policy.get('brawlCommanders',{})))
    supported+='\n## Main-deck names\n\n'+''.join('- '+name+'\n' for name in sorted(policy['verifiedNames'],key=str.casefold))
    (docs/'SUPPORTED-CARDS.md').write_text(supported,encoding='utf8')
    starters=json.loads((output/'starter-decks.json').read_text())
    if starters.get('schema')!=1 or not starters.get('decks'):raise ValueError('Missing recommended starter decks')
    for entry in starters['decks']:
        if Path(entry['file']).name!=entry['file'] or not (output/'decks'/entry['file']).is_file():raise ValueError('Starter deck is outside the packaged checkpoint')

    native_build_root=Path(native_build_root) if native_build_root else PRIVATE/'build'
    binaries=output/'binaries';binaries.mkdir()
    for name,project in (('NativeHost','NativeHost'),('LocalTransport','LocalTransport'),('PreferencePatcher','PreferencePatcher'),('LabPreferences','LabPreferences')):
        shutil.copy2(native_build_root/f'{project}/bin/Debug/netstandard2.1/{name}.dll',binaries/(name+'.dll'))
    launcher=binaries/'launcher';launcher.mkdir()
    for ext in ('dll','exe','deps.json','runtimeconfig.json'):shutil.copy2(native_build_root/f'LabLauncher/bin/Debug/net8.0-windows/LabLauncher.{ext}',launcher/f'LabLauncher.{ext}')
    # Build the packaged rules from this source, never an unrelated/stale cache.
    backend=output/'backend';backend.mkdir()
    javac=Path(os.environ.get('FORGE_ARENA_JAVAC',str(Path.home()/'Games/ForgeRuntime-Java17/jdk-17.0.20.1+1/bin/javac.exe')))
    compiler_version=subprocess.run([str(javac),'-version'],capture_output=True,text=True,check=True)
    compiler_text=(compiler_version.stdout+compiler_version.stderr).strip()
    if not compiler_text.startswith('javac 17.'):raise ValueError('Package rules require the pinned Java 17 compiler')
    forge_jar=Path(forge_build_jar) if forge_build_jar else FORGE/'forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar'
    lock=json.loads((REPO/'packaging/dependencies-lock.json').read_text())
    known_jar_hashes={sha(FORGE/'forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar')}|{digest for name,digest in lock['dependencies']['forge']['files'].items() if name.endswith('.jar')}
    if sha(forge_jar) not in known_jar_hashes:raise ValueError('Compile against a supported pinned Forge engine')
    gson_jar=PRIVATE/'tools/gson-2.13.2/gson.jar'
    source_java=REPO/'ForgeBackend/ForgeLandEngine.java'
    subprocess.run([str(javac),'-J-Xmx512m','-J-XX:ActiveProcessorCount=2','-encoding','UTF-8','-cp',str(forge_jar)+';'+str(gson_jar),'-d',str(backend),str(source_java)],check=True,timeout=90)
    if not (backend/'ForgeLandEngine.class').is_file():raise ValueError('Fresh rules compilation produced no engine class')
    (output/'backend-build.json').write_text(json.dumps(dict(schema=1,compiler=compiler_text,sourceSha256=sha(source_java),
        forgeJarSha256=sha(forge_jar),gsonSha256=sha(gson_jar),classes={p.name:sha(p) for p in sorted(backend.glob('ForgeLandEngine*.class'))}),indent=2))
    # Include corresponding adapter source, never decompiled engine source.
    source=output/'adapter-source';source.mkdir()
    shutil.copy2(REPO/'packaging/SetupBootstrap.cs',source/'SetupBootstrap.cs')
    shutil.copy2(REPO/'packaging/ClientLauncher.cs',source/'ClientLauncher.cs')
    for directory in ('NativeHost','LocalTransport','LabLauncher','LabPreferences','PreferencePatcher','Shared'):
        for file in [*(REPO/directory).glob('*.cs'),*(REPO/directory).glob('*.csproj')]:
            target=source/directory/file.name;target.parent.mkdir(exist_ok=True);shutil.copy2(file,target)
    shutil.copy2(REPO/'packaging/Adapter.Build.props',source/'Directory.Build.props')
    shutil.copy2(REPO/'ForgeBackend/ForgeLandEngine.java',source/'ForgeLandEngine.java')
    gson=PRIVATE/'tools/gson-2.13.2'
    if sha(gson/'gson.jar')!='dd0ce1b55a3ed2080cb70f9c655850cda86c206862310009dcb5e5c95265a5e0':raise ValueError('Unrecognized Gson dependency; retrieve the pinned official Maven artifact')
    shutil.copytree(gson,output/'third-party/gson')
    profiles=json.loads((REPO/'ForgeBackend/arena-builds.json').read_text(encoding='utf8'))
    from arena_compat import select_arena
    selected=select_arena({'arenaVariants':profiles['builds']},arena)
    arena_files=selected['arenaFiles']
    for rel,digest in arena_files.items():
        if sha(arena/rel)!=digest:raise ValueError('Arena input differs from pinned build identity: '+rel)
    jar='forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar'
    forge_files={rel:sha(FORGE/rel) for rel in (jar,'res/cardsfolder/cardsfolder.zip','res/tokenscripts/w_1_1_rabbit.txt')}
    lock=json.loads((REPO/'packaging/dependencies-lock.json').read_text())
    stable=lock['dependencies']['forge'];stable_jar=next(name for name in stable['files'] if name.endswith('.jar'))
    if support_index and index['provenance'].get('sourceForgeScriptsSha256') not in {forge_files['res/cardsfolder/cardsfolder.zip'],stable['files']['res/cardsfolder/cardsfolder.zip']}:
        raise ValueError('Support diagnostics do not match a supported Forge script distribution')
    if support_index and index['provenance'].get('forgeJarSha256') not in {forge_files[jar],stable['files'][stable_jar]}:
        raise ValueError('Support diagnostics do not match a supported Forge engine')
    loader_files={file.relative_to(LOADER).as_posix():sha(file) for file in LOADER.rglob('*') if file.is_file()}
    requirements=dict(schema=1,platform='Windows x64',arenaBuild='Client0.1.14517.1329972',unity='6000.3.14f1',javaMajor=17,dotnetMajor=8,pythonMinimum='3.10',loader='BepInEx 5.4.23.5',thirdParty=dict(gson=dict(version='2.13.2',license='Apache-2.0',sha256=sha(gson/'gson.jar'))),
        arenaFiles=arena_files,forgeJar=jar,forgeFiles=forge_files,
        forgeVariants=[dict(id='legacy-snapshot-08.31',jar=jar,files=forge_files),*stable.get('compatibilityVariants',[]),dict(id=stable.get('variant','official-2.0.15'),jar=stable_jar,files=stable['files'])],preferredForgeVariant=stable.get('variant','official-2.0.15'),loaderFiles=loader_files,
        admission=str(len(policy['verifiedNames']))+' explicitly admitted Arena names plus separately admitted commanders/tokens; no general-card support claim',features=['dedicated Windows client launcher','automatic startup updates','automatic Forge and runtime setup','persistent native Home/Decks/Packs/Play','normal practice bot matches','100-card Brawl bot matches','40-life Commander bot matches','four-player local Commander with one human and three bots','experimental shared table and public zones','native commander slot and local format choice','local sandbox pack opening','native local deck browser'],
        excluded=['human multiplayer pods','online matchmaking','retail account services','complete card support','retail banlist/format legality','retail pack collation','automatic client-asset migration'])
    requirements['features']+=['private two-player internet Commander with saved decks and 40 life']
    requirements['arenaVariants']=profiles['builds']
    requirements['arenaFamily']=profiles['family']
    # Pre-15.4 updaters read only the primary fingerprint. Retain their exact
    # original assets here; current setup/launch selects a full store variant.
    bootstrap=next(b for b in profiles['builds'] if b['id']=='arena-14517')
    for key in ('arenaBuild','arenaFiles','unity'):requirements[key]=bootstrap[key]
    requirements['arenaVariant']=bootstrap['id']
    requirements['features']+=['solo 40-life 200-card Zombie/Horror reanimation Horde','Horde with saved 99-card-plus-commander decks','optional human Exert choices']
    requirements['features']+=['Horde preparation based on commander mana value','original FREAK-OFF Darien paper Commander deck','private cached paper-card illustrations through the original renderer']
    requirements['features']+=['survivor-aware Commander table and camera','experimental ten-player attack-left Commander pod','Gamba Gamba Yusri coin-flip Commander deck']
    (output/'requirements.json').write_text(json.dumps(requirements,indent=2))
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=REPO,capture_output=True,text=True,check=True).stdout.strip()
    state=subprocess.run(['git','status','--porcelain'],cwd=REPO,capture_output=True,text=True,check=True).stdout.strip()
    manifest=dict(schema=1,version=tag,profileSchema=1,createdUtc=datetime.now(timezone.utc).isoformat(),sourceCommit=commit,sourceDirty=bool(state),published=False,
        files={p.relative_to(output).as_posix():sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    (output/'release-manifest.json').write_text(json.dumps(manifest,indent=2));verify_tree(output)
    archive=output.parent/(output.name+'.zip')
    if archive.exists():raise ValueError('Archive already exists')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for file in sorted(output.rglob('*')):
            if file.is_file():z.write(file,file.relative_to(output).as_posix())
    # Match game-file hashes for all payload files: dependencies are local-only.
    prohibited=set(arena_files.values())|set(forge_files.values())|set(loader_files.values())
    copied_game_files=[name for name,digest in manifest['files'].items() if digest in prohibited]
    if copied_game_files:raise ValueError('Package contains prerequisite/game files: '+str(copied_game_files))
    receipt=dict(version=tag,archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),files=len(manifest['files']),gameFilesIncluded=copied_game_files,published=False)
    print(json.dumps(receipt,indent=2));return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--version',default='0.1.0-test.1');p.add_argument('--output',required=True);p.add_argument('--gameplay-ref');p.add_argument('--support-index',type=Path);p.add_argument('--headline',default='Public launcher and automatic update test');p.add_argument('--display-version');p.add_argument('--native-build-root',type=Path,help='Explicit native outputs from the tested source checkpoint');p.add_argument('--experimental-admission',type=Path);p.add_argument('--forge-build-jar',type=Path);p.add_argument('--arena-install',type=Path);a=p.parse_args();build(a.version,Path(a.output).resolve(),a.gameplay_ref,a.headline,a.support_index,a.display_version,a.native_build_root,a.experimental_admission,a.forge_build_jar,a.arena_install)
