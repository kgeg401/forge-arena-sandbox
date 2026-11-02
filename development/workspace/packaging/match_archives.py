"""Bound future closed-match diagnostics; preserve legacy evidence and profiles."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,os,re,shutil,uuid,zipfile
from tester_common import no_links,within

MARKER='.consumer-match-archive.json'
NAME=re.compile(r'forge-ipc-evidence-[0-9]{8}-[0-9]{6}-[0-9]{6}-[0-9a-f]{8}')
MAX_ARCHIVES=3
MAX_BYTES=512*1024*1024

def files(folder):
    """Do not descend through junctions or symbolic links, including on Windows."""
    pending=[Path(folder)]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.is_symlink() or getattr(entry.stat(follow_symlinks=False),'st_file_attributes',0)&0x400:
                    raise ValueError('Linked match diagnostic path preserved: '+entry.path)
                if entry.is_dir(follow_symlinks=False):pending.append(Path(entry.path))
                else:yield Path(entry.path)

def prune(lab,max_archives=MAX_ARCHIVES,max_bytes=MAX_BYTES):
    lab=Path(lab).resolve();no_links(lab);managed=[]
    for path in lab.glob('forge-ipc-evidence-*'):
        if not NAME.fullmatch(path.name):continue
        no_links(path)
        marker=path/MARKER
        if not marker.is_file():continue
        no_links(marker)
        try:identity=json.loads(marker.read_text(encoding='utf8'))
        except (OSError,ValueError):continue
        if identity!=dict(schema=1,archive=path.name):continue
        size=sum(p.stat().st_size for p in files(path));managed.append((path,size))
    removed=[];kept=0;total=0
    for path,size in sorted(managed,key=lambda row:row[0].name,reverse=True):
        if kept<max_archives and total+size<=max_bytes:kept+=1;total+=size;continue
        # Delete only our marked closed archives directly under this exact lab.
        if path.resolve().parent!=lab or not NAME.fullmatch(path.name):raise ValueError('Archive escaped private lab')
        no_links(path);list(files(path));shutil.rmtree(path);removed.append(path.name)
    return dict(retained=kept,bytes=total,removed=removed)

def archive_match(lab,keep_all=False):
    lab=Path(lab).absolute();no_links(lab);source=lab/'forge-ipc'
    if not source.exists():return None
    no_links(source)
    if not source.is_dir():raise ValueError('Match IPC must be a private directory')
    target=lab/('forge-ipc-evidence-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
    source.rename(target)
    # Legacy directories have no marker and are never retroactively deleted.
    # Failed bookkeeping/cleanup must not prevent the next match from starting.
    try:
        (target/MARKER).write_text(json.dumps(dict(schema=1,archive=target.name)),encoding='utf8')
        if not keep_all:prune(lab)
    except (OSError,ValueError) as error:print('Match diagnostic cleanup skipped: '+str(error),flush=True)
    return target

def export_latest(lab,destination):
    lab=Path(lab).absolute();destination=Path(destination).absolute();no_links(lab);no_links(destination)
    if destination.exists() or within(destination,lab):raise ValueError('Export to a new ZIP outside the game data folder')
    archives=sorted((p for p in lab.glob('forge-ipc-evidence-*') if p.is_dir()),key=lambda p:p.name,reverse=True)
    if not archives:raise ValueError('No closed match diagnostics are available')
    source=archives[0];no_links(source);paths=list(files(source))
    temporary=destination.with_name(destination.name+'.pending');no_links(temporary)
    with zipfile.ZipFile(temporary,'x',zipfile.ZIP_DEFLATED) as output:
        for path in paths:output.write(path,path.relative_to(source).as_posix())
    temporary.rename(destination);return dict(archive=source.name,export=str(destination),bytes=destination.stat().st_size)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--lab',type=Path,required=True);parser.add_argument('--export',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(export_latest(args.lab,args.export)))
