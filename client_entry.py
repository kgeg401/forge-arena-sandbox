"""Versioned launcher UI and automatic startup updates, outside the game."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import argparse,json,os,subprocess,traceback
from datetime import datetime,timezone
from types import SimpleNamespace
from tester_common import install_lock,verify_tree
from update_tester import main as update,read,atomic

GAME_MODES=('practice','hares','decks')

def startup(install,mode='hub'):
    """Check/apply at startup; failed updates preserve the verified install."""
    root=Path(install);config=read(root/'sandbox-install.json');status={'checked':False,'applied':False}
    if (root/'installation-incomplete.txt').exists():raise ValueError('Finish installation before opening the client')
    with install_lock(root):
        active=read(root/'active-version.json');verify_tree(root/'versions'/active['version'])
        if config.get('automaticUpdates') and config.get('updateRepository'):
            print('Checking GitHub for sandbox updates…',flush=True)
            try:
                result=update(SimpleNamespace(install_root=str(root),rollback=False,archive=None,apply=True))
                status.update(checked=True,applied='previous' in result,result=result)
            except (OSError,ValueError,RuntimeError) as e:status['warning']=str(e)
        active=read(root/'active-version.json');app=root/'versions'/active['version'];verify_tree(app)
        status.update(version=active['version'],mode=mode,utc=datetime.now(timezone.utc).isoformat())
        atomic(root/'last-startup-update.json',status)
        if mode in GAME_MODES:
            if config.get('installationMode')=='launcher-only':raise ValueError('The launcher is installed; game files still need setup. Open Start Sandbox and choose Set up game files.')
            code=subprocess.call([config['python'],'-B',str(app/'launch_tester.py'),'--install-root',str(root),'--mode',mode],env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
            if code:raise RuntimeError('Game launch failed; see data/native-lab diagnostics')
        return status

def show_hub(root,status):
    import tkinter as tk
    from tkinter import ttk
    config=read(root/'sandbox-install.json');active=read(root/'active-version.json');app=root/'versions'/active['version'];info=read(app/'release-info.json')
    window=tk.Tk();window.title('Forge Arena Sandbox — test client');window.geometry('680x470');window.minsize(620,440)
    pane=ttk.Frame(window,padding=24);pane.pack(fill='both',expand=True)
    ttk.Label(pane,text='Forge Arena Sandbox',font=('Segoe UI',22,'bold')).pack(anchor='w')
    ttk.Label(pane,text='Installed: '+active['version']+'  |  Public test channel',font=('Segoe UI',11)).pack(anchor='w',pady=(8,14))
    ttk.Label(pane,text=info['headline'],wraplength=600,font=('Segoe UI',12,'bold')).pack(anchor='w')
    text=('Updated automatically from GitHub. Your saved files were preserved.' if status['applied'] else 'Automatic updates are checked each time you start this launcher.')
    if not config.get('automaticUpdates'):text='Automatic updates are paused after rollback. Use Check / install update to resume.'
    if status.get('warning'):text='Update check did not complete. Using the verified installed version.\n'+status['warning']
    ttk.Label(pane,text=text,wraplength=600).pack(anchor='w',pady=(12,14))
    launcher_only=config.get('installationMode')=='launcher-only'
    ttk.Label(pane,text=('Launcher/update test is ready. Playing requires compatible local Arena, Forge and runtimes. No games are included.' if launcher_only else 'Game files are configured. Close the game before applying updates.'),wraplength=600).pack(anchor='w',pady=(0,12))
    def run(mode):
        window.destroy();subprocess.Popen([config['python'],'-B',str(root/'client_bootstrap.py'),mode])
    row=ttk.Frame(pane);row.pack(anchor='w',pady=8)
    for title,mode in (('Start practice','practice'),('Open decks','decks')):
        ttk.Button(row,text=title,command=lambda m=mode:run(m),state='disabled' if launcher_only else 'normal').pack(side='left',padx=(0,8))
    ttk.Button(pane,text='Set up game files…',command=lambda:subprocess.Popen([config['python'],'-B',str(app/'setup_client.py')])).pack(anchor='w',pady=4)
    ttk.Button(pane,text='Check / install update',command=lambda:run('update')).pack(anchor='w',pady=4)
    ttk.Button(pane,text='Rollback previous version',command=lambda:run('rollback')).pack(anchor='w',pady=4)
    ttk.Label(pane,text='Developer preview | limited verified cards | no multiplayer',foreground='#666666').pack(anchor='w',pady=(14,0))
    window.mainloop()

def main(args):
    root=Path(args.install_root).resolve();(root/'logs').mkdir(exist_ok=True)
    if args.mode in ('hub',*GAME_MODES):
        result=startup(root,args.mode);print(json.dumps(result,indent=2),flush=True)
        if args.mode=='hub' and not args.no_window:show_hub(root,result)
        return result
    with install_lock(root):
        result=update(SimpleNamespace(install_root=str(root),rollback=args.mode=='rollback',archive=args.archive,apply=args.mode=='update'))
        atomic(root/('last-'+args.mode+'-action.json'),result)
    print(json.dumps(result,indent=2),flush=True)
    if not args.no_window:
        import tkinter as tk
        from tkinter import messagebox
        w=tk.Tk();w.withdraw();messagebox.showinfo('Sandbox update','Installed version: '+read(root/'active-version.json')['version']+'\nSaved files were preserved.\nRestart Start Sandbox to continue.');w.destroy()
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--install-root',required=True);p.add_argument('mode',nargs='?',default='hub',choices=('hub',*GAME_MODES,'check','update','rollback'));p.add_argument('--no-window',action='store_true');p.add_argument('--archive');a=p.parse_args()
    try:main(a)
    except Exception as e:
        log=Path(a.install_root)/'logs'/('error-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.log');log.parent.mkdir(exist_ok=True);log.write_text(traceback.format_exc(),encoding='utf8')
        print('Sandbox stopped: '+str(e)+'\nDetails: '+str(log))
        if not a.no_window:
            import tkinter as tk
            from tkinter import messagebox
            w=tk.Tk();w.withdraw();messagebox.showerror('Sandbox stopped',str(e)+'\nDetails: '+str(log));w.destroy()
        raise SystemExit(1)
