"""Bounded original-client cast/target/expiration checks for a qualified family."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
LAB=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab')
LANDS={'W':'Plains','U':'Island','B':'Swamp','R':'Mountain','G':'Forest'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(a):
    proposals=json.loads(a.proposals.read_text(encoding='utf8'))['proposals']
    if not 1<=len(proposals)<=12 or len({p['name'] for p in proposals})!=len(proposals) or any(p['template']!='fixed-target-pump-v1' for p in proposals):raise ValueError('One small qualified pump family required')
    a.output.mkdir(parents=True,exist_ok=False);archive=a.output/'source';archive.mkdir()
    inputs=[a.config,a.manifest,a.proposals,a.ui_config,Path(__file__),HERE/'verify_native_pump.py',HERE/'native_ui_client.py',HERE/'native_ui_qa.py',HERE/'launch_research_native.py',HERE.parent/'NativeHost/ForgeLandBridge.cs',HERE.parent/'NativeHost/Plugin.cs',Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\build\NativeHost\bin\Debug\netstandard2.1\NativeHost.dll')]
    identities={str(p.resolve()):sha(p) for p in inputs}
    for index,path in enumerate(inputs):shutil.copy2(path,archive/(str(index)+'-'+path.name))
    result=dict(status='running',startedUtc=datetime.now(timezone.utc).isoformat(),identities=identities,cases=[],newAdmissions=0,scope='Fresh independent native fixture per qualified card; original target/Cancel/Submit/Resolve controls and actual stat bonus/expiration. Not complete-match or arbitrary interaction coverage.')
    report=a.output/'report.json'
    def save():report.write_text(json.dumps(result,indent=2),encoding='utf8')
    save()
    try:
        for index,p in enumerate(proposals):
            if any(sha(Path(path))!=digest for path,digest in identities.items()):raise ValueError('Native family source/input changed')
            folder=a.output/('case-'+str(index+1));folder.mkdir();mana=p['printedCost'];filler=LANDS[mana['symbols'][0]] if mana['symbols'] else 'Plains'
            scenario=dict(scenario='card-family',randomSeed=7274,fixtureHand=[p['name']],fixtureLands=[LANDS[s] for s in mana['symbols']]+[filler]*mana['generic'],fixtureBattlefield=['Grizzly Bears'],fixtureOpponentBattlefield=['Grizzly Bears'])
            fixture=folder/'scenario.json';fixture.write_text(json.dumps(scenario,indent=2),encoding='utf8')
            with (folder/'launch.log').open('w',encoding='utf8') as log:
                subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'launch_research_native.py'),'--runtime-config',str(a.config),'--manifest',str(a.manifest),'--scenario-json',str(fixture)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=210)
            receipt=json.loads((LAB/'launch-receipt.json').read_text());(folder/'launch-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
            env={**os.environ,'FORGE_ARENA_CONFIG':str(a.ui_config.resolve())}
            with (folder/'driver.log').open('w',encoding='utf8') as log:
                subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'verify_native_pump.py'),'--card',p['name'],'--expected-native-pid',str(receipt['pid']),'--proposals',str(a.proposals),'--output',str(folder/'proof')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=210)
            path=folder/'proof/report.json';data=json.loads(path.read_text())
            if data['passed'] is not True or data['cards']!=[p['name']] or data['checks']!=len(data['results']) or not all(v['passed'] for v in data['results']):raise ValueError('Native proof incomplete')
            result['cases'].append(dict(card=p['name'],printing=p['printing'],checks=data['checks'],report=str(path),reportSha256=sha(path)));save()
            print(json.dumps(result['cases'][-1]),flush=True)
        if any(sha(Path(path))!=digest for path,digest in identities.items()):raise ValueError('Native family source/input changed before seal')
        result.update(status='passed',cards=len(proposals),checks=sum(v['checks'] for v in result['cases']))
    except BaseException as error:
        result.update(status='needs-attention',error=repr(error));raise
    finally:
        result['finishedUtc']=datetime.now(timezone.utc).isoformat();save()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','manifest','proposals','ui-config','output'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
