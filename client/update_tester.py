"""Versioned adapter updates/rollback; local profiles and game assets stay put."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, os, re, shutil, sys, time, uuid
import urllib.request, urllib.parse
from tester_common import extract_verified, verify_tree, sha, version, no_links, within, repository_name, install_lock

ASSET_NAME='ForgeArenaSandbox-Windows.zip'
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def atomic(path,value):
    temp=path.with_suffix('.pending');temp.write_text(json.dumps(value,indent=2));os.replace(temp,path)

class GithubRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        parsed=urllib.parse.urlparse(newurl)
        if parsed.scheme!='https' or parsed.hostname not in ('github.com','release-assets.githubusercontent.com','objects.githubusercontent.com') or parsed.port not in (None,443):raise ValueError('Unexpected release download redirect')
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def latest(repository,channel='stable'):
    if not repository:raise ValueError('No GitHub update repository is configured. Publishing/setup has not happened yet.')
    repository_name(repository)
    if channel not in ('stable','test'):raise ValueError('Unknown release channel')
    url='https://api.github.com/repos/'+repository+('/releases?per_page=30' if channel=='test' else '/releases/latest')
    request=urllib.request.Request(url,headers={'User-Agent':'ForgeArenaSandbox-Tester-Updater','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(request,timeout=20) as response:
        raw=response.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:raise ValueError('Unexpected release response size')
    payload=json.loads(raw)
    if channel=='test':
        candidates=[]
        for row in payload:
            if row.get('draft') or not row.get('prerelease'):continue
            try:order=version(row['tag_name'].removeprefix('v'))
            except ValueError:continue
            if any(a['name']==ASSET_NAME for a in row.get('assets',[])):candidates.append((order,row))
        if not candidates:raise ValueError('No published Windows test release is available')
        release=max(candidates,key=lambda r:r[0])[1]
    else:
        release=payload
        if release.get('draft') or release.get('prerelease'):raise ValueError('The stable updater does not install drafts or prereleases')
    assets=[a for a in release['assets'] if a['name']==ASSET_NAME]
    if len(assets)!=1:raise ValueError('Latest release has no unique Windows adapter package')
    asset=assets[0];expected=asset.get('digest','')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',expected):raise ValueError('Release asset has no SHA-256 digest; download and review manually')
    parsed=urllib.parse.urlparse(asset['browser_download_url'])
    if parsed.scheme!='https' or parsed.netloc.casefold()!='github.com' or not parsed.path.casefold().startswith(('/'+repository+'/releases/download/').casefold()):raise ValueError('Asset is outside the configured GitHub repository')
    return dict(version=release['tag_name'].removeprefix('v'),url=asset['browser_download_url'],sha256=expected[7:],size=asset['size'],releaseUrl=release['html_url'])

def compatible(manifest,folder,config):
    if manifest['profileSchema']!=config['profileSchema']:raise ValueError('A profile migration is required; no update applied')
    req=read(folder/'requirements.json');data=Path(config['privateRoot']);lab=data/'native-lab'
    if config.get('installationMode')=='launcher-only':
        # Game admission is deferred only when no game has been configured.
        if (lab/'MTGA.exe').exists() or (data/'forge-runtime/forge.jar').exists():raise ValueError('Unexpected game files in launcher-only install; inspect setup before updating')
        return
    for rel,digest in req['arenaFiles'].items():
        if sha(lab/rel)!=digest:raise ValueError('Update needs a different Arena build; preserve this sandbox until a tested asset migration exists')
    from dependencies import match_forge
    match_forge(data/'forge-runtime',req,runtime=True)
    for rel,digest in req['loaderFiles'].items():
        if sha(lab/rel)!=digest:raise ValueError('Update needs a different loader build')

def require_stopped(config):
    from launch_tester import win_processes
    root=str(Path(config['privateRoot'])).casefold()
    procs=win_processes()
    for p in procs:
        if root in (p.get('ExecutablePath') or '').casefold():
            # Automatic setup keeps Java inside data too. Its recorded Forge
            # backend is quiesced below after the game window closes.
            known_backend='ForgeLandEngine' in (p.get('CommandLine') or '') and root in (p.get('CommandLine') or '').casefold() and Path(p.get('ExecutablePath') or '').name.casefold()=='java.exe'
            if not known_backend:raise ValueError('Close this sandbox window before applying an update or rollback')
    # Closing the game window can leave its headless rules process waiting.
    # Stop only that exact owned backend through its existing IPC shutdown.
    for p in procs:
        if 'ForgeLandEngine' in (p.get('CommandLine') or '') and root in (p.get('CommandLine') or '').casefold():
            ipc=Path(config['privateRoot'])/'native-lab/forge-ipc'
            metadata=read(ipc/'backend-process.json')
            if metadata['pid']!=p['ProcessId']:raise ValueError('Backend identity differs from local receipt; no update applied')
            (ipc/'stop.request').write_text('Window closed; quiesce rules for adapter update')
            end=time.monotonic()+12
            while time.monotonic()<end and any(c['ProcessId']==p['ProcessId'] for c in win_processes()):time.sleep(.2)
            if any(c['ProcessId']==p['ProcessId'] for c in win_processes()):raise ValueError('Headless rules process did not stop; current version preserved')

def apply_archive(install,archive,expected_sha256=None,expected_version=None):
    install=Path(install).resolve();no_links(install);config=read(install/'sandbox-install.json');active=read(install/'active-version.json')
    if Path(config['privateRoot']).resolve()!=install/'data':raise ValueError('Configured data root differs from independent data tree')
    require_stopped(config)
    if expected_sha256 and sha(archive)!=expected_sha256:raise ValueError('Downloaded release checksum mismatch; current version preserved')
    staging=install/'versions'/('.staging-'+uuid.uuid4().hex)
    manifest=extract_verified(archive,staging);new=manifest['version']
    if expected_version and new!=expected_version:raise ValueError('Archive version differs from GitHub release')
    if version(new)<=version(active['version']):raise ValueError('Use rollback for older releases; current version preserved')
    compatible(manifest,staging,config)
    target=install/'versions'/new
    retained=target.exists()
    if retained and verify_tree(target)!=manifest:raise ValueError('Retained version differs from this release; no files overwritten')
    profile=Path(config['privateRoot'])/'native-lab/local-profile'
    backup=None
    if profile.exists():
        no_links(profile);backup=install/'profile-backups'/(active['version']+'-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copytree(profile,backup)
    if not retained:staging.rename(target)
    # This is the only live mutation. Old binaries and the entire data tree stay.
    next_active=dict(version=new,previous=active['version'],profileSchema=active['profileSchema'])
    atomic(install/'active-version.json',next_active)
    receipt=dict(utc=datetime.now(timezone.utc).isoformat(),previous=active['version'],version=new,archiveSha256=sha(archive),profileBackup=str(backup) if backup else None,profileUntouched=True)
    atomic(install/'last-update.json',receipt);return receipt

def rollback(install):
    install=Path(install).resolve();no_links(install);active=read(install/'active-version.json');config=read(install/'sandbox-install.json');previous=active.get('previous')
    if not previous:raise ValueError('No previous version is available')
    if Path(config['privateRoot']).resolve()!=install/'data':raise ValueError('Configured data root differs from independent data tree')
    version(previous);require_stopped(config);folder=install/'versions'/previous;manifest=verify_tree(folder)
    if config.get('installationMode')!='launcher-only':
        from rules_runtime import restore_compatible
        restore_compatible(Path(config['privateRoot']),read(folder/'requirements.json'))
    compatible(manifest,folder,config)
    atomic(install/'active-version.json',dict(version=previous,previous=active['version'],profileSchema=active['profileSchema']))
    config['automaticUpdates']=False
    atomic(install/'sandbox-install.json',config)
    return dict(version=previous,previous=active['version'],profileUntouched=True)

def main(args):
    install=Path(args.install_root).resolve()
    if args.rollback:return rollback(install)
    if args.archive:
        if not args.apply:raise ValueError('Use --apply to install a manually reviewed local package')
        return apply_archive(install,Path(args.archive).resolve())
    config=read(install/'sandbox-install.json');release=latest(config.get('updateRepository'),config.get('updateChannel','stable'))
    current=read(install/'active-version.json')['version'];release['currentVersion']=current;release['updateAvailable']=version(release['version'])>version(current)
    if not args.apply:return release
    if not release['updateAvailable']:
        config['automaticUpdates']=True;atomic(install/'sandbox-install.json',config)
        return release
    if release['size']>128*1024*1024:raise ValueError('Unexpected adapter download size')
    downloads=install/'downloads';downloads.mkdir(exist_ok=True);archive=downloads/(release['version']+'-'+uuid.uuid4().hex+'.zip.pending')
    opener=urllib.request.build_opener(GithubRedirect)
    with opener.open(release['url'],timeout=30) as response,archive.open('xb') as out:
        total=0
        while block:=response.read(1024*1024):
            total+=len(block)
            if total>128*1024*1024:raise ValueError('Release download exceeded size bound')
            out.write(block)
    if total!=release['size']:raise ValueError('Incomplete release download; current version preserved')
    receipt=apply_archive(install,archive,release['sha256'],release['version'])
    config['automaticUpdates']=True;atomic(install/'sandbox-install.json',config)
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--install-root',required=True);p.add_argument('--apply',action='store_true');p.add_argument('--archive');p.add_argument('--rollback',action='store_true')
    try:
        args=p.parse_args()
        with install_lock(args.install_root):print(json.dumps(main(args),indent=2))
    except (OSError,ValueError,RuntimeError) as e:raise SystemExit('Update stopped; current version/profile preserved: '+str(e))
