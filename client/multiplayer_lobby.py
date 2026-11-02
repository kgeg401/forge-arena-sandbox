"""Small connection window; the match itself uses the original Arena board."""
import threading,time
from client_service import read,atomic

def lobby(ipc,deck,run):
    import tkinter as tk
    from tkinter import ttk
    window=tk.Tk();window.title('Forge Arena — Private Commander');window.geometry('690x340');window.minsize(620,320)
    body=ttk.Frame(window,padding=22);body.pack(fill='both',expand=True)
    ttk.Label(body,text='Private Commander · 2 players · 40 life',font=('Segoe UI',16)).pack(anchor='w')
    ttk.Label(body,text='Your saved deck: '+deck).pack(anchor='w',pady=(8,18))
    text=tk.StringVar();field=ttk.Entry(body,textvariable=text);field.pack(fill='x')
    message=tk.StringVar(value='Host a room, or paste the invitation your brother sends you.');ttk.Label(body,textvariable=message,wraplength=620).pack(anchor='w',pady=15)
    buttons=ttk.Frame(body);buttons.pack(fill='x');worker=None;hidden=False;invitation=None;started=False
    def start(choice):
        nonlocal worker,started
        if started:return
        started=True
        for button in (host,join):button.configure(state='disabled')
        field.configure(state='readonly');message.set('Connecting…')
        worker=threading.Thread(target=run,args=(choice,),daemon=True);worker.start()
    def close():
        (ipc/'stop.request').write_text('Player closed the private room')
        window.withdraw()
    host=ttk.Button(buttons,text='Host room',command=lambda:start(dict(mode='host')));host.pack(side='left')
    join=ttk.Button(buttons,text='Join room',command=lambda:start(dict(mode='join',invitation=text.get().strip())));join.pack(side='left',padx=8)
    def copy():
        if invitation:window.clipboard_clear();window.clipboard_append(invitation);window.update()
    ttk.Button(buttons,text='Copy invitation',command=copy).pack(side='left');ttk.Button(buttons,text='Cancel / close room',command=close).pack(side='right')
    window.protocol('WM_DELETE_WINDOW',close)
    def poll():
        nonlocal hidden,invitation
        try:
            status=read(ipc/'network-status.json');message.set(status['message'])
            if status.get('invitation') and invitation is None:invitation=status['invitation'];text.set(invitation)
            if status.get('boardReady') and not hidden:hidden=True;window.withdraw()
            if status.get('error'):window.deiconify()
        except (OSError,ValueError,KeyError):pass
        # The same bounded file route also lets private native QA select the
        # actual host/join flow without sending keyboard input to another app.
        if not started and (ipc/'network-choice.json').exists():start(read(ipc/'network-choice.json'))
        if worker is not None and not worker.is_alive():window.destroy();return
        if (ipc/'stop.request').exists() and worker is None:window.destroy();return
        window.after(150,poll)
    window.after(150,poll);window.mainloop()
    if worker is not None:worker.join(timeout=35)
