"""Bounded fresh native fixtures grouped by independently planned legal targets."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from prepare_generated_removal_batches import WORLD,eligible,clean
from build_card_test_catalogue import sha
import sqlite3

HERE=Path(__file__).resolve().parent
LAB=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab')
LANDS={'W':'Plains','U':'Island','B':'Swamp','R':'Mountain','G':'Forest'}


def run(a):
    proposals=json.loads(a.proposals.read_text(encoding='utf8'))['proposals'];policy=json.loads(a.policy.read_text(encoding='utf8'))
    mappings=json.loads(a.mappings.read_text(encoding='utf8'));byid={p['grpId']:p for p in mappings['printings']}
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True);texts={}
    for identity,text in db.execute('SELECT a.Id,l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId WHERE l.Formatted=1'):texts[identity]=clean(text)
    db.close();world={}
    for name in WORLD:
        card=dict(byid[policy['preferredPrintings'][name]]);card['_nativeTexts']=[texts[i] for i in card['abilityIds']];world[name]=card
    groups=[];remaining=list(proposals)
    while remaining:
        alive=[(n,o) for o in (2,1) for n in WORLD];group=[]
        while remaining and len(group)<4:
            p=remaining[0];options=[(n,o) for n,o in alive if eligible(p['predicate'],world[n])]
            if not options:break
            target=options[0];group.append(dict(name=p['name'],targetName=target[0],targetOwner=target[1],expectedTargets=[dict(name=n,owner=o) for n,o in options]));alive.remove(target);remaining.pop(0)
        if not group:raise ValueError('No authored native target for next card')
        groups.append(group)
    a.output.mkdir(parents=True,exist_ok=False);reports=[]
    inputs=[a.config,a.manifest,a.proposals,a.policy,a.mappings,a.database,Path(__file__),HERE/'verify_native_removal_batch.py',HERE/'native_ui_client.py',HERE/'native_ui_qa.py',HERE/'launch_research_native.py',HERE/'prepare_generated_removal_batches.py',HERE.parent/'NativeHost/ForgeLandBridge.cs',Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\build\NativeHost\bin\Debug\netstandard2.1\NativeHost.dll')]
    identities={str(p.resolve()):sha(p) for p in inputs};specs={p['name']:p for p in proposals}
    def save(status):
        (a.output/'report.json').write_text(json.dumps(dict(status=status,utc=datetime.now(timezone.utc).isoformat(),identities=identities,batches=reports,cards=[n for r in reports for n in r.get('cards',[])],plannedCards=len(proposals)),indent=2))
    save('running')
    try:
        for index,plan in enumerate(groups):
            if any(sha(Path(p))!=h for p,h in identities.items()):raise ValueError('Native input/source changed during family')
            folder=a.output/('batch-'+str(index+1));folder.mkdir();lands=[]
            for row in plan:
                mana=specs[row['name']]['printedCost'];lands.extend([LANDS[s] for s in mana['symbols']]+[LANDS[mana['symbols'][0]] if mana['symbols'] else 'Plains']*mana['generic'])
            fixture=folder/'scenario.json';fixture.write_text(json.dumps(dict(scenario='card-family',randomSeed=7274,fixtureHand=[r['name'] for r in plan],fixtureLands=lands,fixtureBattlefield=WORLD,fixtureOpponentBattlefield=WORLD),indent=2))
            plan_path=folder/'plan.json';plan_path.write_text(json.dumps(plan,indent=2))
            with (folder/'launch.log').open('w',encoding='utf8') as log:subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'launch_research_native.py'),'--runtime-config',str(a.config),'--manifest',str(a.manifest),'--scenario-json',str(fixture)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=210)
            receipt=json.loads((LAB/'launch-receipt.json').read_text());(folder/'launch-receipt.json').write_text(json.dumps(receipt,indent=2))
            with (folder/'driver.log').open('w',encoding='utf8') as log:subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'verify_native_removal_batch.py'),'--expected-native-pid',str(receipt['pid']),'--proposals',str(a.proposals),'--plan',str(plan_path),'--output',str(folder/'proof')],env={**os.environ,'FORGE_ARENA_CONFIG':str(a.ui_config.resolve())},stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
            result=json.loads((folder/'proof/report.json').read_text());assert result['passed'];reports.append(dict(cards=result['cards'],checks=result['checks'],report=str(folder/'proof/report.json'),reportSha256=sha(folder/'proof/report.json')));save('running');print(json.dumps(reports[-1]),flush=True)
    except BaseException:
        save('failed');raise
    save('passed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','manifest','policy','proposals','mappings','database','ui-config','output'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
