"""Exercise the real startup path with authored packages and controlled network."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace
import json,shutil,zipfile,urllib.error
from tester_common import sha,install_lock
from client_entry import startup
from update_tester import apply_archive,rollback,latest,main as update

checks=[]
def check(label,condition):
    if not condition:raise AssertionError(label)
    checks.append(label)

def rejected(label,action):
    try:action()
    except (OSError,ValueError,RuntimeError):check(label,True)
    else:raise AssertionError('Unexpected acceptance: '+label)

with TemporaryDirectory(prefix='forge-startup-') as temp:
    base=Path(temp);root=base/'Installed Client';profile=root/'data/native-lab/local-profile';profile.mkdir(parents=True)
    (profile/'my-decks.json').write_text('{"deck":"brother-keeps-this"}')
    original=(profile/'my-decks.json').read_bytes();versions=root/'versions';versions.mkdir()
    config=dict(schema=1,profileSchema=1,privateRoot=str(root/'data'),installationMode='launcher-only',automaticUpdates=True,updateRepository='kgeg401/forge-arena-sandbox',updateChannel='test')
    (root/'sandbox-install.json').write_text(json.dumps(config))
    (root/'active-version.json').write_text(json.dumps(dict(version='0.1.0-test.1',previous=None,profileSchema=1)))
    def make(tag):
        folder=base/tag;folder.mkdir();(folder/'application.txt').write_text('Authored test '+tag)
        (folder/'requirements.json').write_text(json.dumps(dict(arenaFiles={},forgeFiles={},loaderFiles={})))
        (folder/'release-manifest.json').write_text(json.dumps(dict(schema=1,profileSchema=1,version=tag,files={p.name:sha(p) for p in folder.iterdir()})))
        archive=base/(tag+'.zip')
        with zipfile.ZipFile(archive,'w') as z:
            for p in folder.iterdir():z.write(p,p.name)
        return folder,archive
    first,_=make('0.1.0-test.1');shutil.copytree(first,versions/first.name)
    second,archive=make('0.1.0-test.2')
    def available(args):return apply_archive(root,archive,sha(archive),'0.1.0-test.2')
    with patch('client_entry.update',side_effect=available) as call:
        result=startup(root)
        check('Startup automatically applies a newer package',result['applied'] and result['version']=='0.1.0-test.2')
        check('Startup requests test channel download and apply',call.call_args.args[0].apply)
    check('Startup saved a visible update receipt',json.loads((root/'last-startup-update.json').read_text())['applied'])
    check('Startup preserves every deck byte',(profile/'my-decks.json').read_bytes()==original)
    check('Previous adapter remains for rollback',(versions/'0.1.0-test.1/application.txt').exists())
    backups=list((root/'profile-backups').glob('*/my-decks.json'))
    check('Startup backs up the saved deck',len(backups)==1 and backups[0].read_bytes()==original)
    with patch('client_entry.update',side_effect=urllib.error.URLError('offline')):
        result=startup(root)
        check('Offline startup uses the verified installed release',result['version']=='0.1.0-test.2' and not result['applied'] and 'offline' in result['warning'])
    with patch('client_entry.update',side_effect=ValueError('Downloaded release checksum mismatch')):
        result=startup(root)
        check('Rejected checksum is visible without replacing the good release','checksum' in result['warning'] and result['version']=='0.1.0-test.2')
    with install_lock(root):rejected('Concurrent launch/update is refused',lambda:startup(root))
    with patch('client_entry.update',return_value={'updateAvailable':False}):
        rejected('Launcher-only install cannot silently launch the game',lambda:startup(root,'practice'))
    rollback(root)
    check('Rollback pauses automatic updates',not json.loads((root/'sandbox-install.json').read_text())['automaticUpdates'])
    with patch('client_entry.update') as call:
        check('Rolled-back version remains selected on startup',startup(root)['version']=='0.1.0-test.1')
        check('Paused startup does not query/download',not call.called)
    apply_archive(root,archive,sha(archive),'0.1.0-test.2')
    check('An identical retained release can be reactivated without overwrite',json.loads((root/'active-version.json').read_text())['version']=='0.1.0-test.2')
    rollback(root)
    # Existing versions are deliberately never overwritten; a separate later
    # release exercises explicit resume without reinstalling a retained folder.
    third,third_zip=make('0.1.0-test.3')
    release=dict(version='0.1.0-test.3',url='https://github.com/kgeg401/forge-arena-sandbox/releases/download/v0.1.0-test.3/ForgeArenaSandbox-Windows.zip',size=third_zip.stat().st_size,sha256=sha(third_zip))
    class Download:
        def open(self,*a,**kw):return third_zip.open('rb')
    with patch('update_tester.latest',return_value=release),patch('update_tester.urllib.request.build_opener',return_value=Download()):
        result=update(SimpleNamespace(install_root=str(root),rollback=False,archive=None,apply=True))
    check('Explicit update resumes automatic updates',json.loads((root/'sandbox-install.json').read_text())['automaticUpdates'] and result['version']=='0.1.0-test.3')
    check('Resume still preserves saved deck',(profile/'my-decks.json').read_bytes()==original)
    active=root/'active-version.json';before=active.read_bytes()
    (versions/'0.1.0-test.3/application.txt').write_text('corrupt installed code')
    with patch('client_entry.update') as call:
        rejected('Corrupt installed files block startup',lambda:startup(root))
        check('Corruption is rejected before any updater executes',not call.called)
    check('Failed startup does not switch versions',active.read_bytes()==before)

    # Validate actual feed selection, not only a mocked latest() result.
    asset=dict(name='ForgeArenaSandbox-Windows.zip',digest='sha256:'+'a'*64,size=42,browser_download_url='https://github.com/kgeg401/forge-arena-sandbox/releases/download/v0.1.0-test.10/ForgeArenaSandbox-Windows.zip')
    def row(tag,pre=True,draft=False,assets=None):return dict(tag_name=tag,prerelease=pre,draft=draft,assets=[asset] if assets is None else assets,html_url='https://github.com/kgeg401/forge-arena-sandbox/releases/tag/'+tag)
    feed=[row('v0.1.0-test.2'),row('v0.1.0-test.10'),row('v99.0.0-test.1',draft=True),row('v8.0.0',pre=False),row('not-a-version'),row('v10.0.0-test.1',assets=[])]
    class Response:
        def __init__(self,payload):self.payload=payload
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,*a):return json.dumps(self.payload).encode()
    with patch('update_tester.urllib.request.urlopen',return_value=Response(feed)):
        check('Test feed chooses numeric newest matching non-draft prerelease',latest(config['updateRepository'],'test')['version']=='0.1.0-test.10')
    with patch('update_tester.urllib.request.urlopen',return_value=Response(row('v0.2.0'))):
        rejected('Stable channel rejects prereleases',lambda:latest(config['updateRepository'],'stable'))
    rejected('Unknown channel is rejected',lambda:latest(config['updateRepository'],'wrong'))

print(json.dumps(dict(checks=len(checks),passed=checks,scope='Authored startup/feed fixtures; real GitHub and rendered checks are separate'),indent=2))
