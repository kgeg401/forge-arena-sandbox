"""First-install window for Arena checks and full sandbox setup."""
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
    from auto_install import install_automatic,check_arena
    window=tk.Tk();window.title('Install Forge Arena Sandbox');window.geometry('790x440')
    panel=ttk.Frame(window,padding=22);panel.pack(fill='both',expand=True)
    ttk.Label(panel,text='Install the sandbox',font=('Segoe UI',21,'bold')).pack(anchor='w')
    ttk.Label(panel,text='Install Arena separately and finish its content download first.\nSetup downloads and configures Forge, Java, .NET and the loader automatically.\nAllow at least 20 GiB free for an independent copy; your Arena installation stays unchanged.',wraplength=740).pack(anchor='w',pady=12)
    values={}
    def field(key,label,default=''):
        row=ttk.Frame(panel);row.pack(fill='x',pady=5);ttk.Label(row,text=label,width=16).pack(side='left');var=tk.StringVar(value=default);values[key]=var
        ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True)
        def browse():
            selected=filedialog.askdirectory(title=label)
            if selected:var.set(selected)
        ttk.Button(row,text='Browse',command=browse).pack(side='left',padx=(6,0))
    installed=HERE.parent.parent if HERE.parent.name=='versions' else None
    arena_default=''
    if installed and (installed/'sandbox-install.json').exists():arena_default=json.loads((installed/'sandbox-install.json').read_text()).get('arenaInstall','')
    if not arena_default:
        for p in (Path('D:/GAMES/MTGA'),Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Wizards of the Coast/MTGA'):
            if (p/'MTGA.exe').exists():arena_default=str(p);break
    field('arena','Installed Arena',arena_default)
    field('destination','Sandbox folder',str(installed or Path.home()/'Games/ForgeArenaSandbox-Test'))
    ttk.Label(panel,text='Forge 2.0.15 is pinned to an official release. Existing launcher installations\ncan be completed here; saved decks are backed up and retained.',wraplength=740).pack(anchor='w',pady=12)
    status=tk.StringVar(value='Ready to check Arena and install the sandbox.');ttk.Label(panel,textvariable=status,wraplength=740).pack(anchor='w',pady=8)
    buttons=ttk.Frame(panel);buttons.pack(anchor='w',pady=8);events=queue.Queue();busy=False
    def work(kind):
        nonlocal busy
        paths={k:Path(v.get()).absolute() for k,v in values.items()};busy=True
        for b in buttons.winfo_children():b.configure(state='disabled')
        status.set('Checking files…')
        def task():
            try:
                if kind=='check':check_arena(paths['arena'],paths['destination'],HERE);result={'checked':True}
                else:result=install_automatic(paths['arena'],paths['destination'],HERE,progress=lambda text:events.put(('progress',text)))
                events.put((True,result))
            except Exception as e:events.put((False,str(e)))
        threading.Thread(target=task,daemon=True).start()
    for title,kind in (('Check Arena','check'),('Install sandbox','game')):ttk.Button(buttons,text=title,command=lambda k=kind:work(k)).pack(side='left',padx=(0,8))
    def poll():
        nonlocal busy
        try:
            # Drain progress messages so large downloads do not stall the UI.
            while True:
                ok,result=events.get_nowait()
                if ok=='progress':status.set(result);continue
                busy=False
                for b in buttons.winfo_children():b.configure(state='normal')
                if not ok:status.set(result);messagebox.showerror('Setup stopped',result)
                elif result.get('checked'):status.set('Arena is compatible. Click Install sandbox to download and configure the remaining dependencies.')
                else:status.set('Installed: '+result['destination']);messagebox.showinfo('Installed','Open Start Sandbox in:\n'+result['destination'])
        except queue.Empty:pass
        window.after(150,poll)
    def close():
        if busy:messagebox.showinfo('Setup is running','Please wait for setup to finish. Progress is shown in this window.')
        else:window.destroy()
    window.protocol('WM_DELETE_WINDOW',close);poll();window.mainloop()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--launcher-destination');p.add_argument('--package',default=str(HERE));a=p.parse_args()
    if a.launcher_destination:print(json.dumps(install_launcher(a.package,a.launcher_destination),indent=2))
    else:show()
