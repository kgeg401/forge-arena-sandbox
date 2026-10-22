"""First-install window. Launcher-only setup requires no games or accounts."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace
import argparse,json,os,shutil,subprocess,threading,queue,webbrowser
from tester_common import verify_tree,no_links,within,repository_name
from install_tester import install_launchers,inspect_install

HERE=Path(__file__).resolve().parent
REPOSITORY='kgeg401/forge-arena-sandbox'
LINKS={
    'Arena':'https://magic.wizards.com/en/mtgarena',
    'Forge':'https://github.com/Card-Forge/forge/releases',
    'Java 17':'https://adoptium.net/temurin/releases/?version=17',
    '.NET 8':'https://dotnet.microsoft.com/en-us/download/dotnet/8.0',
    'Loader':'https://github.com/BepInEx/BepInEx/releases/tag/v5.4.23.5',
}

def install_launcher(package,destination,repository=REPOSITORY):
    package=Path(package).resolve();destination=Path(destination).absolute();manifest=verify_tree(package)
    repository_name(repository);no_links(destination)
    if destination.exists():raise ValueError('Choose a new folder. Existing files are never overwritten.')
    if within(package,destination) or within(destination,package):raise ValueError('Install outside the extracted download folder so it can be removed afterward.')
    destination.mkdir(parents=True);(destination/'installation-incomplete.txt').write_text('Setup has not finished')
    app=destination/'versions'/manifest['version'];shutil.copytree(package,app,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (destination/'data/native-lab/local-profile').mkdir(parents=True)
    config=dict(schema=1,profileSchema=1,privateRoot=str(destination/'data'),python=sys.executable,installationMode='launcher-only',updateRepository=repository,updateChannel='test',automaticUpdates=True)
    (destination/'sandbox-install.json').write_text(json.dumps(config,indent=2))
    (destination/'active-version.json').write_text(json.dumps(dict(version=manifest['version'],previous=None,profileSchema=1),indent=2))
    install_launchers(destination,app)
    (destination/'installation-incomplete.txt').unlink()
    receipt=dict(version=manifest['version'],destination=str(destination),installationMode='launcher-only',finishedUtc=datetime.now(timezone.utc).isoformat(),gameFilesIncluded=False)
    (destination/'install-receipt.json').write_text(json.dumps(receipt,indent=2));return receipt

def show():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    window=tk.Tk();window.title('Install Forge Arena Sandbox');window.geometry('770x650')
    panel=ttk.Frame(window,padding=20);panel.pack(fill='both',expand=True)
    ttk.Label(panel,text='Install the sandbox test client',font=('Segoe UI',19,'bold')).pack(anchor='w')
    ttk.Label(panel,text='No games installed? Install the launcher first to test GitHub automatic updates.\nPlaying still requires your own compatible game files. Existing installations stay unchanged.',wraplength=720).pack(anchor='w',pady=12)
    values={}
    def field(key,label,default=''):
        row=ttk.Frame(panel);row.pack(fill='x',pady=4);ttk.Label(row,text=label,width=17).pack(side='left');var=tk.StringVar(value=default);values[key]=var
        ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True)
        def browse():
            selected=filedialog.askdirectory(title=label)
            if selected:var.set(selected)
        ttk.Button(row,text='Browse',command=browse).pack(side='left',padx=(6,0))
    field('destination','NEW install folder',str(Path.home()/'Games/ForgeArenaSandbox-Test'))
    ttk.Label(panel,text='Optional full game setup (use a NEW separate destination):',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(14,6))
    for key,label in (('arena','Arena folder'),('forge','Forge folder'),('java','Java 17 folder'),('loader','Extracted loader')):field(key,label)
    links=ttk.Frame(panel);links.pack(anchor='w',pady=10)
    for label,url in LINKS.items():ttk.Button(links,text=label,command=lambda u=url:webbrowser.open(u)).pack(side='left',padx=(0,4))
    ttk.Label(panel,text='The tested Forge snapshot is 2.0.15-SNAPSHOT-08.31, not the latest snapshot.\nOther builds are rejected. Full game setup may need developer compatibility work.',wraplength=720).pack(anchor='w')
    status=tk.StringVar(value='Choose launcher-only setup, or check your game files before full setup.')
    ttk.Label(panel,textvariable=status,wraplength=720).pack(anchor='w',pady=12)
    buttons=ttk.Frame(panel);buttons.pack(anchor='w');events=queue.Queue()
    def work(kind):
        paths={k:Path(v.get()).absolute() for k,v in values.items()};buttons_state('disabled');status.set('Checking files…' if kind=='check' else 'Installing… please keep this window open.')
        def task():
            try:
                if kind=='launcher':result=install_launcher(HERE,paths['destination'])
                elif kind=='check':
                    plan=inspect_install(paths['arena'],paths['forge'],paths['java'],paths['loader'],paths['destination'],HERE)
                    result={'checked':True,'requiredGiB':round(plan['estimatedTotalBytes']/1024**3,1)}
                else:
                    command=[sys.executable,'-B',str(HERE/'install_tester.py'),'--repository',REPOSITORY,'--channel','test']
                    for key in ('arena','forge','java','loader','destination'):command+=['--'+key,str(paths[key])]
                    log=Path(os.environ.get('TEMP',str(Path.home())))/('ForgeArena-setup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.log')
                    with log.open('w',encoding='utf8') as out:p=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                    if p.returncode:raise RuntimeError('Setup stopped. Existing installs were preserved. Details: '+str(log))
                    result={'destination':str(paths['destination'])}
                events.put((True,result))
            except Exception as e:events.put((False,str(e)))
        threading.Thread(target=task,daemon=True).start()
    def buttons_state(state):
        for b in buttons.winfo_children():b.configure(state=state)
    for text,kind in (('Install launcher only','launcher'),('Check game files','check'),('Install with game files','game')):ttk.Button(buttons,text=text,command=lambda k=kind:work(k)).pack(side='left',padx=(0,8))
    def poll():
        try:
            ok,result=events.get_nowait();buttons_state('normal')
            if not ok:status.set(result);messagebox.showerror('Setup stopped',result)
            elif result.get('checked'):status.set('Compatible files. Full setup needs '+str(result['requiredGiB'])+' GiB plus a 2 GiB reserve. Click Install with game files to copy.')
            else:status.set('Installed. Open Start Sandbox in '+result['destination']);messagebox.showinfo('Installed','Open Start Sandbox in:\n'+result['destination']+'\nThe launcher checks GitHub automatically when opened.')
        except queue.Empty:pass
        window.after(150,poll)
    poll();window.mainloop()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--launcher-destination');p.add_argument('--package',default=str(HERE));a=p.parse_args()
    if a.launcher_destination:print(json.dumps(install_launcher(a.package,a.launcher_destination),indent=2))
    else:show()
