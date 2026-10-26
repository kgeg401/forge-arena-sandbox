"""Arena is supplied by the user; all other prerequisites are managed here."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,os,shutil,subprocess,uuid
from tester_common import verify_tree,no_links,within,sha,install_lock
from dependencies import prepare
from install_tester import check_destination

def check_arena(arena,destination,package):
    arena=Path(arena).absolute();destination=Path(destination).absolute();package=Path(package).resolve()
    verify_tree(package);req=json.loads((package/'requirements.json').read_text())
    for path in (arena,destination,package):no_links(path)
    if not arena.is_dir():raise ValueError('Select your installed Arena folder first. Arena is installed separately.')
    check_destination(destination)
    if within(destination,arena) or within(arena,destination) or within(destination,package) or within(package,destination):raise ValueError('Choose a sandbox folder separate from Arena and the extracted download.')
    for rel,digest in req['arenaFiles'].items():
        path=arena/rel;no_links(path)
        if not path.is_file():raise ValueError('Arena files are incomplete: '+rel+'. Finish Arena installation and content downloads, then retry.')
        if sha(path)!=digest:raise ValueError('This Arena build differs from the tested client: '+rel+'. Setup stopped before downloading prerequisites.')
    parent=destination.parent
    while not parent.exists():parent=parent.parent
    if shutil.disk_usage(parent).free<20*1024**3:raise ValueError('Allow at least 20 GiB free for the independent sandbox, Forge and runtimes.')
    return req

def install_automatic(arena,destination,package,workspace=None,progress=lambda text:None):
    arena=Path(arena).absolute();destination=Path(destination).absolute();package=Path(package).resolve()
    progress('Checking Arena and the new sandbox destination…');check_arena(arena,destination,package)
    lock=json.loads((package/'dependencies-lock.json').read_text())
    if lock.get('schema')!=1:raise ValueError('Unsupported prerequisite manifest')
    workspace=Path(workspace or Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'ForgeArenaSandbox/prerequisites').absolute()
    no_links(workspace)
    if any(within(workspace,p) or within(p,workspace) for p in (arena,destination,package)):raise ValueError('Prerequisite cache must be separate from Arena, the sandbox and download.')
    workspace.mkdir(parents=True,exist_ok=True)
    with install_lock(workspace):
        prepared={}
        for key in ('forge','java','dotnet','loader'):prepared[key]=prepare(lock['dependencies'][key],workspace,progress)
        # The downloaded cache never becomes a required path after installation;
        # Forge and both private runtimes are copied into the sandbox's data tree.
        command=[sys.executable,'-B','-u',str(package/'install_tester.py'),'--package',str(package),'--arena',str(arena),'--destination',str(destination),'--forge',str(prepared['forge']),'--java',str(prepared['java']),'--loader',str(prepared['loader']),'--dotnet',str(prepared['dotnet']/'dotnet.exe'),'--copy-runtimes','--repository','kgeg401/forge-arena-sandbox','--channel','test']
        logs=workspace/'setup-logs';logs.mkdir(exist_ok=True);log=logs/(datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:8]+'.log')
        progress('Copying owned Arena files, Forge and private runtimes. This may take several minutes…')
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'}
        with log.open('w',encoding='utf8') as out:
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',env=env,creationflags=subprocess.CREATE_NO_WINDOW)
            for line in process.stdout:
                out.write(line);out.flush()
                if line.startswith(('Copied','Wrote')):progress(line.strip())
            code=process.wait()
        if code:raise RuntimeError('Sandbox setup stopped. Existing programs and saved files were preserved. Details: '+str(log))
        receipt=json.loads((destination/'install-receipt.json').read_text())
        receipt.update(automaticPrerequisites=True,forgeVersion=lock['dependencies']['forge']['label'],arenaInstalledBySetup=False,privateRuntimes=True,prerequisiteCache=str(workspace),setupLog=str(log))
        (destination/'automatic-setup-receipt.json').write_text(json.dumps(receipt,indent=2))
        progress('Ready. Open Forge Arena Sandbox in '+str(destination));return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--arena',required=True);p.add_argument('--destination',required=True);p.add_argument('--package',default=str(Path(__file__).resolve().parent));p.add_argument('--workspace');a=p.parse_args()
    print(json.dumps(install_automatic(a.arena,a.destination,a.package,a.workspace,lambda s:print(s,flush=True)),indent=2))
