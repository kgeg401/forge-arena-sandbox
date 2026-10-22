import json,pathlib,subprocess,time
from runtime_paths import ROOT, JAVA_HOME
ipc=ROOT/'native-lab'/'forge-ipc';ipc.mkdir(exist_ok=True)
metadata=ipc/'backend-process.json'
if metadata.exists():
    old=json.loads(metadata.read_text())
    check=subprocess.run(['powershell.exe','-NoProfile','-Command',f"Get-CimInstance Win32_Process -Filter 'ProcessId={int(old['pid'])}' | Select-Object -ExpandProperty CommandLine"],capture_output=True,text=True)
    if 'ForgeLandEngine' in check.stdout:raise SystemExit('A ForgeLandEngine backend is already running; reuse it.')
    metadata.rename(ipc/f'backend-process-prior-{int(time.time())}.json')
java=str(JAVA_HOME/'bin/java.exe')
cp=';'.join(str(p) for p in [ROOT/'build'/'ForgeBackend'/'classes',ROOT/'forge-runtime'/'forge.jar',ROOT/'forge-runtime'/'gson.jar'])
with (ipc/'engine.log').open('w') as log:
    # Forge's GuiDesktop class queries display scaling during static initialization.
    # No Forge window is created; only that desktop-library requirement is enabled.
    p=subprocess.Popen([java,'-Xmx2g','-Djava.awt.headless=false','-cp',cp,'ForgeLandEngine',str(ROOT/'forge-runtime'),str(ipc)],cwd=ROOT/'forge-runtime',stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
(ipc/'backend-process.json').write_text(json.dumps({'pid':p.pid,'class':'ForgeLandEngine','ipc':str(ipc),'started':time.time()},indent=2))
for _ in range(90):
    if (ipc/'state.json').exists():
        state=json.loads((ipc/'state.json').read_text());print(json.dumps({k:state[k] for k in ['session','scenario','phase','turn','life','opponentLife']},indent=2));break
    if p.poll() is not None:raise SystemExit((ipc/'engine.log').read_text()[-5000:])
    time.sleep(1)
else:raise SystemExit('Forge initialization timed out; process metadata and log retained.')
