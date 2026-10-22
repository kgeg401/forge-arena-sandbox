"""Launch a bounded research scenario in the existing independent offline lab.

No retail process is attached, no game binaries are changed, and profiles are
not deleted. Old engine IPC and deployed adapter/manifest evidence are retained.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

BASE=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox')
LAB=BASE/'native-lab'
NO_WINDOW=subprocess.CREATE_NO_WINDOW


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def processes():
    script="@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'MTGA.exe' -or $_.Name -eq 'java.exe'} | Select-Object ProcessId,ExecutablePath,CommandLine) | ConvertTo-Json -Compress"
    value=subprocess.run(['powershell.exe','-NoProfile','-Command',script],check=True,capture_output=True,text=True,creationflags=NO_WINDOW).stdout.strip()
    rows=json.loads(value) if value else []
    return rows if isinstance(rows,list) else [rows]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-config',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--scenario-json',type=Path,required=True)
    a=p.parse_args()
    config=read(a.runtime_config);runtime_root=Path(config['privateRoot']).resolve();runtime=runtime_root/'forge-runtime'
    manifest=read(a.manifest);scenario=read(a.scenario_json)
    derived=[]
    if not manifest.get('researchOnly'):
        for name in ('deck-catalog.json','card-support-index.json'):
            path=runtime_root/'native-lab'/name
            data=read(path)
            policy_hash=data.get('policySha256') or data.get('provenance',{}).get('policySha256')
            if policy_hash!=manifest['policySha256']:raise ValueError('Generated '+name+' differs from the selected verified policy')
            derived.append(path)
    if scenario.get('scenario') in ('card-family','attack-double-blocked','defend'):
        if not manifest.get('researchOnly'):raise ValueError('Card-family fixtures require a research-only manifest')
    elif scenario.get('scenario')!='custom-duel':raise ValueError('Use a bounded research fixture or normally shuffled custom duel')
    if LAB.resolve()!=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab') or not (LAB/'sandbox-lab.json').is_file():raise ValueError('Independent lab boundary mismatch')
    retail=Path(config['arenaInstall']).resolve()
    for rel in ('MTGA.exe','UnityPlayer.dll'):
        if hashlib.sha256((retail/rel).read_bytes()).digest()!=hashlib.sha256((LAB/rel).read_bytes()).digest():raise ValueError('Owned retail/lab build mismatch: '+rel)
    current=processes()
    for proc in current:
        if proc['ExecutablePath'] and Path(proc['ExecutablePath']).name.lower()=='mtga.exe':
            if Path(proc['ExecutablePath']).resolve()!=LAB/'MTGA.exe':raise ValueError('Retail Arena is open; research will not attach to it')
            subprocess.run(['powershell.exe','-NoProfile','-Command','Stop-Process -Id '+str(int(proc['ProcessId']))+' -ErrorAction Stop'],check=True,creationflags=NO_WINDOW)
    ipc=LAB/'forge-ipc';metadata=ipc/'backend-process.json'
    if metadata.exists():
        old=read(metadata);proc=next((v for v in current if v['ProcessId']==int(old['pid'])),None)
        if proc:
            if 'ForgeLandEngine' not in (proc['CommandLine'] or '') or str(ipc) not in proc['CommandLine']:raise ValueError('Recorded backend PID no longer matches the exact lab IPC')
            (ipc/'stop.request').write_text('Research launch: retain prior evidence')
            end=time.monotonic()+15
            while time.monotonic()<end and any(v['ProcessId']==old['pid'] for v in processes()):time.sleep(.2)
            if any(v['ProcessId']==old['pid'] for v in processes()):raise RuntimeError('Recorded backend did not stop')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:6]
    evidence=BASE/'research/broad-card-support'/('native-'+stamp);evidence.mkdir(parents=True)
    if ipc.exists():
        archived=LAB/('forge-ipc-evidence-'+stamp)
        if archived.parent.resolve()!=LAB.resolve():raise ValueError('IPC archive escaped lab')
        ipc.rename(archived)
    ipc.mkdir()
    for name in ('bridge-card-manifest.json','deck-catalog.json','card-support-index.json','native-host-status.json','launch-receipt.json','native-action.request.json','native-action-result.json','capture-frame.request'):
        path=LAB/name
        if path.exists():shutil.copy2(path,evidence/name)
        if name in ('native-action.request.json','capture-frame.request') and path.exists():path.rename(evidence/('retired-'+name))
    target=LAB/'BepInEx/plugins/ForgeArenaSandbox/NativeHost.dll'
    shutil.copy2(target,evidence/'previous-NativeHost.dll')
    shutil.copy2(BASE/'build/NativeHost/bin/Debug/netstandard2.1/NativeHost.dll',target)
    shutil.copy2(a.manifest,LAB/'bridge-card-manifest.json')
    for path in derived:shutil.copy2(path,LAB/path.name)
    (LAB/'full-control-test.flag').write_text('Research validation: retain manual priority')
    shutil.copy2(a.scenario_json,ipc/'scenario.json')
    cp=';'.join(str(runtime_root/path) for path in ('build/ForgeBackend/classes','forge-runtime/forge.jar','forge-runtime/gson.jar'))
    with (ipc/'engine.log').open('w',encoding='utf8') as log:
        engine=subprocess.Popen([str(Path(config['javaHome'])/'bin/java.exe'),'-Xmx1024m','-XX:ActiveProcessorCount=2','-Djava.awt.headless=false','-cp',cp,'ForgeLandEngine',str(runtime),str(ipc)],cwd=runtime,stdout=log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
    (ipc/'backend-process.json').write_text(json.dumps(dict(pid=engine.pid,**{'class':'ForgeLandEngine'},ipc=str(ipc),started=time.time())))
    end=time.monotonic()+45
    while time.monotonic()<end:
        if (ipc/'state.json').exists():break
        if engine.poll() is not None:raise RuntimeError((ipc/'engine.log').read_text()[-5000:])
        time.sleep(.2)
    else:raise TimeoutError('Research engine initialization timed out; recorded PID and logs retained')
    result=subprocess.run([r'C:\Program Files\dotnet\dotnet.exe',str(BASE/'build/LabLauncher/bin/Debug/net8.0-windows/LabLauncher.dll'),str(LAB)],capture_output=True,text=True,creationflags=NO_WINDOW,timeout=30)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    launch=read(LAB/'launch-receipt.json')
    if not launch['appContainer'] or launch['capabilityCount']!=0:raise RuntimeError('Native process did not retain zero network capabilities')
    receipt=dict(utc=datetime.now(timezone.utc).isoformat(),enginePid=engine.pid,nativeLaunch=launch,scenario=scenario,manifestSha256=hashlib.sha256(a.manifest.read_bytes()).hexdigest(),evidence=str(evidence),scope='Isolated native validation; no public update or recipient-PC claim')
    (evidence/'research-launch.json').write_text(json.dumps(receipt,indent=2))
    # The independent lab deliberately starts without official services. Load
    # cached owned assets, then request the original board through existing hooks.
    opened=subprocess.run(['powershell.exe','-NoProfile','-File',str(Path(__file__).resolve().parents[1]/'Open-NativeBoard.ps1')],capture_output=True,text=True,creationflags=NO_WINDOW,timeout=150)
    (evidence/'board-start.log').write_text(opened.stdout+opened.stderr,encoding='utf8')
    if opened.returncode:raise RuntimeError('Native board did not initialize; see '+str(evidence/'board-start.log'))
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
