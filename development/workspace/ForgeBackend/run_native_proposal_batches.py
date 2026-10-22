"""Bounded visible casting batches in the existing isolated native research lab.

Requires prior user authorization to launch/restart that lab. Never changes
admission, publishes, attaches to retail Arena, or erases a player profile.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
LAB=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab')
LANDS=dict(W='Plains',U='Island',B='Swamp',R='Mountain',G='Forest')


def run(a):
    proposals=json.loads(a.proposals.read_text(encoding='utf8'))['proposals']
    baseline=json.loads(a.baseline_policy.read_text(encoding='utf-8-sig'))
    if baseline.get('researchOnly'):raise ValueError('Verified baseline required')
    specs=[p for p in proposals if p['name'] not in baseline['verifiedNames'] or p['template']=='fixed-untargeted-draw-life-v1']
    a.output.mkdir(parents=True,exist_ok=False);reports=[]
    config=json.loads(a.runtime_config.read_text(encoding='utf8'));root=Path(config['privateRoot'])
    if (root/'native-lab/MTGA.exe').exists():raise ValueError('Separate backend runtime required')
    env={**os.environ,'FORGE_ARENA_CONFIG':str(a.ui_config.resolve()),'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1'}
    groups=[];group=[]
    def budget(values):
        colors={s for p in values for s in p['printedCost']['symbols']} or {'W'}
        total=sum(p['printedCost']['total'] for p in values)
        return colors,total
    for spec in specs:
        colors,total=budget(group+[spec])
        if group and (len(group)>=6 or len(colors)*total>100):groups.append(group);group=[]
        group.append(spec)
    if group:groups.append(group)
    for index,group in enumerate(groups):
        folder=a.output/('batch-'+str(index+1));folder.mkdir()
        colors,total=budget(group)
        # Every required color has the entire group's mana budget. Generic
        # auto-payment for an earlier card therefore cannot consume a later
        # card's last colored source. This is a casting fixture, not a deck.
        lands=[LANDS[s] for s in sorted(colors) for _ in range(total)]
        scenario=folder/'scenario.json';scenario.write_text(json.dumps(dict(scenario='card-family',randomSeed=7274+index,fixtureHand=[p['name'] for p in group],fixtureLands=lands),indent=2),encoding='utf8')
        with (folder/'launch.log').open('w',encoding='utf8') as log:
            subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'launch_research_native.py'),'--runtime-config',str(a.runtime_config),'--manifest',str(root/'native-lab/bridge-card-manifest.json'),'--scenario-json',str(scenario)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
        launch=json.loads((LAB/'launch-receipt.json').read_text())
        with (folder/'verification.log').open('w',encoding='utf8') as log:
            subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'verify_native_proposal_batch.py'),'--proposals',str(a.proposals),'--scenario-json',str(scenario),'--expected-native-pid',str(launch['pid']),'--output',str(folder/'checks')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
        result=json.loads((folder/'checks/report.json').read_text());reports.append(dict(report=str(folder/'checks/report.json'),cards=result['cards'],checks=result['checks'],passed=result['passed']))
        (a.output/'progress.json').write_text(json.dumps(reports,indent=2),encoding='utf8')
        print(json.dumps(dict(batch=len(reports),cards=sum(len(r['cards']) for r in reports),checks=sum(r['checks'] for r in reports))),flush=True)
    result=dict(cards=[n for r in reports for n in r['cards']],checks=sum(r['checks'] for r in reports),passed=all(r['passed'] for r in reports),batches=reports,newAdmissions=0,
        scope='Native casting outcomes only. Remaining keyword, interaction, whole-game and admission gates stay separate. Restore original native lab/session after research.')
    (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(report=str(a.output/'report.json'),cards=len(result['cards']),checks=result['checks'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('proposals','baseline-policy','runtime-config','ui-config','output'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
