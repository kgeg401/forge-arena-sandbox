"""Negative prerequisite/setup checks with disposable authored files."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib,io,json,tarfile,zipfile
from dependencies import approved_url,download,extract,match_forge
from install_tester import check_destination
from auto_install import install_automatic
from tester_common import sha
from types import SimpleNamespace
from install_tester import install
from update_tester import require_stopped

checks=[]
def check(label,ok):
    if not ok:raise AssertionError(label)
    checks.append(label)
def reject(label,action):
    try:action()
    except (ValueError,OSError):check(label,True)
    else:raise AssertionError('Unexpected acceptance: '+label)

with TemporaryDirectory(prefix='forge-prereq-check-') as temp:
    base=Path(temp)
    check('Official release downloads use HTTPS',approved_url('https://github.com/Card-Forge/forge/releases/download/forge-2.0.15/file.zip').startswith('https:'))
    for bad in ('http://github.com/file','https://example.com/file','https://github.com:81/file','https://user:secret@github.com/file'):
        reject('Unapproved download origin '+bad,lambda v=bad:approved_url(v))
    cache=base/'downloads';cache.mkdir();data=b'authored prerequisite archive fixture';digest=hashlib.sha256(data).hexdigest()
    item=dict(filename='prereq.zip',label='authored fixture',url='https://github.com/owner/repo/file.zip',digest=digest,maximumBytes=100)
    (cache/'prereq.zip').write_bytes(data)
    with patch('dependencies.urllib.request.build_opener') as network:
        check('Verified cached archive is reused',download(item,cache).read_bytes()==data)
        check('Verified cache avoids a download',not network.called)
    class Opener:
        def __init__(self,payload):self.payload=payload
        def open(self,*a,**kw):return io.BytesIO(self.payload)
    (cache/'prereq.zip').write_bytes(b'changed cache')
    with patch('dependencies.urllib.request.build_opener',return_value=Opener(data)):
        check('Corrupt cache is replaced only by verified bytes',download(item,cache).read_bytes()==data)
    check('Rejected cached bytes are retained',len(list(cache.glob('*.rejected-*')))==1)
    other={**item,'filename':'wrong.zip'}
    with patch('dependencies.urllib.request.build_opener',return_value=Opener(b'bad download')):
        reject('Bad download digest blocks preparation',lambda:download(other,cache))
    check('Bad download is never made active',not (cache/'wrong.zip').exists())
    with patch('dependencies.urllib.request.build_opener',return_value=Opener(b'x'*101)):
        reject('Oversized download stops before installation',lambda:download(other,cache))
    good=base/'good.zip'
    with zipfile.ZipFile(good,'w') as z:z.writestr('nested/tool.txt','authored')
    extract(good,base/'good','zip');check('Ordinary ZIP extraction succeeds',(base/'good/nested/tool.txt').read_text()=='authored')
    reject('Existing extraction is never overwritten',lambda:extract(good,base/'good','zip'))
    for index,name in enumerate(('../escape','C:/escape','/escape','folder/../escape')):
        archive=base/('bad-'+str(index)+'.zip')
        with zipfile.ZipFile(archive,'w') as z:z.writestr(name,'bad')
        reject('ZIP traversal rejected '+name,lambda a=archive,i=index:extract(a,base/('bad-stage-'+str(i)),'zip'))
    linked=base/'link.tar.bz2'
    with tarfile.open(linked,'w:bz2') as t:
        info=tarfile.TarInfo('link');info.type=tarfile.SYMTYPE;info.linkname='../escape';t.addfile(info)
    reject('TAR symbolic link is rejected',lambda:extract(linked,base/'tar-link','tar.bz2'))
    source=base/'forge';(source/'res').mkdir(parents=True);(source/'engine.jar').write_bytes(b'authored stable engine');(source/'res/cards.zip').write_bytes(b'authored scripts')
    stable=dict(id='stable',jar='engine.jar',files={'engine.jar':sha(source/'engine.jar'),'res/cards.zip':sha(source/'res/cards.zip')})
    req=dict(forgeVariants=[dict(id='old',jar='old.jar',files={'old.jar':'0'*64}),stable])
    check('Stable version matches its complete pinned fingerprint',match_forge(source,req)['id']=='stable')
    runtime=base/'runtime';(runtime/'res').mkdir(parents=True);(runtime/'forge.jar').write_bytes((source/'engine.jar').read_bytes());(runtime/'res/cards.zip').write_bytes((source/'res/cards.zip').read_bytes())
    check('Installed renamed jar matches the stable variant',match_forge(runtime,req,runtime=True)['id']=='stable')
    (runtime/'res/cards.zip').write_bytes(b'changed');reject('Changed Forge scripts are rejected',lambda:match_forge(runtime,req,runtime=True))
    unrelated=base/'unrelated';unrelated.mkdir();(unrelated/'keep.txt').write_text('keep')
    reject('Unrelated existing destination is preserved',lambda:check_destination(unrelated));check('Existing unrelated file stays unchanged',(unrelated/'keep.txt').read_text()=='keep')
    launcher=base/'launcher';profile=launcher/'data/native-lab/local-profile';profile.mkdir(parents=True);(profile/'decks.json').write_text('my deck')
    (launcher/'sandbox-install.json').write_text(json.dumps(dict(installationMode='launcher-only',profileSchema=1,privateRoot=str(launcher/'data'))))
    check('Owned launcher can be completed without a new folder',check_destination(launcher))
    check('Completion preflight retains deck bytes',(profile/'decks.json').read_text()=='my deck')
    (launcher/'data/unexpected.txt').write_text('preserve')
    reject('Unexpected launcher data prevents copying over it',lambda:check_destination(launcher))
    # Invalid Arena must fail before a network request or destination creation.
    package=base/'package';package.mkdir();(package/'requirements.json').write_text(json.dumps(dict(arenaFiles={'MTGA.exe':'0'*64})))
    (package/'release-manifest.json').write_text(json.dumps(dict(schema=1,profileSchema=1,version='0.1.0-test.4',files={'requirements.json':sha(package/'requirements.json')})))
    arena=base/'arena';arena.mkdir();(arena/'MTGA.exe').write_bytes(b'wrong authored build')
    destination=base/'new-client'
    with patch('auto_install.prepare') as network:
        reject('Wrong Arena build fails before dependency setup',lambda:install_automatic(arena,destination,package,base/'cache'))
        check('Wrong Arena never triggers a download',not network.called)
        check('Wrong Arena never creates the install destination',not destination.exists())
    # Exercise the real completion/copy path that previously tried to recreate
    # native-lab. Only prerequisite probes and external programs are stubbed;
    # all file copies, backups, config and completion markers are real.
    complete=base/'complete-launcher';saved=complete/'data/native-lab/local-profile';saved.mkdir(parents=True)
    (saved/'decks.json').write_bytes(b'preserve this existing local deck')
    (complete/'sandbox-install.json').write_text(json.dumps(dict(installationMode='launcher-only',profileSchema=1,privateRoot=str(complete/'data'))))
    own=base/'authored-package';own.mkdir();fake_forge=base/'fake-forge';fake_forge.mkdir();(fake_forge/'engine.jar').write_bytes(b'authored engine fixture')
    for name in ('backend/Engine.class','third-party/gson/gson.jar','binaries/NativeHost.dll','binaries/LocalTransport.dll','binaries/PreferencePatcher.dll','binaries/LabPreferences.dll'):
        path=own/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'authored nonexecutable fixture')
    (own/'decks').mkdir();manifest=dict(version='0.1.0-test.4',profileSchema=1)
    (own/'release-manifest.json').write_text(json.dumps(manifest))
    requirements=dict(loaderFiles={},arenaFiles={'MTGA.exe':sha(arena/'MTGA.exe')})
    plan=dict(manifest=manifest,requirements=requirements,forgeVariant=dict(id='authored',jar='engine.jar'),completeLauncher=True,sourceFiles=[arena/'MTGA.exe'],forgeResources=[],checks=[],estimatedArenaBytes=20,estimatedForgeBytes=20,estimatedTotalBytes=40,dotnet='authored-dotnet.exe')
    args=SimpleNamespace(arena=str(arena),forge=str(fake_forge),java=str(base/'fake-java'),loader=str(base/'fake-loader'),destination=str(complete),package=str(own),repository=None,check_only=False)
    with patch('install_tester.inspect_install',return_value=plan),patch('install_tester.subprocess.run'),patch('install_tester.install_launchers'):
        result=install(args)
    check('Full completion accepts the existing native profile directory',result['installed'])
    check('Completion preserves every existing deck byte',(saved/'decks.json').read_bytes()==b'preserve this existing local deck')
    check('Completion creates a saved-profile backup',len(list((complete/'profile-backups').glob('*/local-profile/decks.json')))==1)
    check('Completion clears its in-progress marker',not (complete/'installation-incomplete.txt').exists())
    check('Completion changes launcher-only configuration only after copying',json.loads((complete/'sandbox-install.json').read_text()).get('installationMode')!='launcher-only')
    # Private Java lives under data after automatic setup. It must be stopped
    # by the same identity-checked IPC route used for an external Java runtime.
    data=base/'private-java-data';ipc=data/'native-lab/forge-ipc';ipc.mkdir(parents=True)
    (ipc/'backend-process.json').write_text(json.dumps({'pid':7274}))
    engine=dict(ProcessId=7274,ExecutablePath=str(data/'runtimes/java/bin/java.exe'),CommandLine='java -cp '+str(data)+' ForgeLandEngine')
    with patch('launch_tester.win_processes',side_effect=[[engine],[],[]]):require_stopped({'privateRoot':str(data)})
    check('Closed-game update quiesces the recorded private Java backend',(ipc/'stop.request').is_file())
    (ipc/'stop.request').unlink();(ipc/'backend-process.json').write_text(json.dumps({'pid':9999}))
    with patch('launch_tester.win_processes',return_value=[engine]):reject('Private Java with a mismatched PID is never stopped',lambda:require_stopped({'privateRoot':str(data)}))
    check('Mismatched identity publishes no stop request',not (ipc/'stop.request').exists())
    game=dict(ProcessId=123,ExecutablePath=str(data/'native-lab/MTGA.exe'),CommandLine='owned game')
    with patch('launch_tester.win_processes',return_value=[game]):reject('Running game still blocks updates',lambda:require_stopped({'privateRoot':str(data)}))
print(json.dumps(dict(checks=len(checks),passed=checks,scope='Authored safety fixtures; real official downloads and native game are tested separately'),indent=2))
