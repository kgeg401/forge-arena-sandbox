"""Upgrade the private Forge dependency with retained, verified rollback copies."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,os,shutil,uuid
from dependencies import match_forge,prepare
from tester_common import no_links,sha,within

def atomic(path,value):
    temp=path.with_suffix('.pending');temp.write_text(json.dumps(value,indent=2));os.replace(temp,path)

def switch_runtime(data,candidate):
    data=Path(data);candidate=Path(candidate);current=data/'forge-runtime'
    for p in (data,candidate,current):no_links(p)
    if not within(candidate,data):raise ValueError('Rules candidate escaped private data')
    journal=data/'rules-runtime-switch.json'
    backup=data/'forge-runtime-backups'/uuid.uuid4().hex;backup.parent.mkdir(exist_ok=True)
    atomic(journal,dict(candidate=str(candidate),backup=str(backup)))
    try:
        if current.exists():current.rename(backup)
        candidate.rename(current)
    except BaseException:
        if not current.exists() and backup.exists():backup.rename(current)
        raise
    journal.unlink();return backup

def recover(data):
    data=Path(data);journal=data/'rules-runtime-switch.json';current=data/'forge-runtime'
    if not journal.exists():return
    entry=json.loads(journal.read_text());backup=Path(entry['backup'])
    no_links(backup)
    if not within(backup,data/'forge-runtime-backups'):raise ValueError('Invalid rules recovery path')
    if not current.exists():
        if not backup.is_dir():raise ValueError('Rules migration needs inspection; old files retained')
        backup.rename(current)
    journal.unlink()

def restore_compatible(data,requirements):
    data=Path(data);recover(data)
    try:return match_forge(data/'forge-runtime',requirements,runtime=True)
    except ValueError:pass
    for candidate in sorted((data/'forge-runtime-backups').glob('*')):
        try:variant=match_forge(candidate,requirements,runtime=True)
        except ValueError:continue
        switch_runtime(data,candidate);return variant
    raise ValueError('No retained Forge runtime matches this release; current files preserved')

def ensure_rules_runtime(app,config,progress=print):
    app=Path(app);data=Path(config['privateRoot']);recover(data)
    req=json.loads((app/'requirements.json').read_text());preferred=req.get('preferredForgeVariant')
    if not preferred:return match_forge(data/'forge-runtime',req,runtime=True)
    variants=[v for v in req['forgeVariants'] if v['id']==preferred]
    if len(variants)!=1:raise ValueError('Missing pinned preferred Forge build')
    exact=dict(forgeVariants=variants)
    try:return match_forge(data/'forge-runtime',exact,runtime=True)
    except ValueError:pass
    from update_tester import require_stopped
    require_stopped(config)
    lock=json.loads((app/'dependencies-lock.json').read_text())['dependencies']['forge']
    if lock['files']!=variants[0]['files']:raise ValueError('Rules download and required files differ')
    source=prepare(lock,data/'prerequisite-cache',progress)
    staged=data/('.forge-runtime-'+uuid.uuid4().hex);staged.mkdir();variant=variants[0]
    shutil.copytree(source/'res',staged/'res')
    shutil.copy2(source/variant['jar'],staged/'forge.jar')
    shutil.copy2(data/'forge-runtime/gson.jar',staged/'gson.jar')
    for name in ('LICENSE.txt','README.txt'):
        if (source/name).is_file():shutil.copy2(source/name,staged/name)
    for name in ('user','cache'):
        if (data/'forge-runtime'/name).is_dir():shutil.copytree(data/'forge-runtime'/name,staged/name)
    runtime=data/'forge-runtime'
    (staged/'forge.profile.properties').write_text('userDir='+str(runtime/'user').replace('\\','/')+'\ncacheDir='+str(runtime/'cache').replace('\\','/')+'\n')
    match_forge(staged,exact,runtime=True)
    backup=switch_runtime(data,staged)
    config.update(forgeInstall=str(runtime),forgeResourcesRoot=str(runtime),forgeVariant=preferred)
    atomic(data.parent/'sandbox-install.json',config)
    atomic(data/'rules-runtime-upgrade.json',dict(variant=preferred,archiveSha256=lock['digest'],previousRuntime=str(backup),profileUntouched=True))
    return variant
