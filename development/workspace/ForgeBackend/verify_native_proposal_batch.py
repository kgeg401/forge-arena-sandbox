"""Check declared source-qualified casting outcomes through original native UI.

Runs only in the isolated zero-network research lab. Uses initial fixtures,
original card/Resolve callbacks, and read-only engine snapshots thereafter.
"""
import argparse
from contextlib import redirect_stdout
import hashlib
import json
from pathlib import Path
import shutil
import time
import native_ui_client as native
from native_client_ui import capture
from runtime_paths import ROOT


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run(a):
    lab=ROOT/'native-lab'
    manifest=json.loads((lab/'bridge-card-manifest.json').read_text())
    launch=json.loads((lab/'launch-receipt.json').read_text())
    if not manifest.get('researchOnly') or not launch.get('appContainer') or launch.get('capabilityCount')!=0 or launch['pid']!=a.expected_native_pid:
        raise ValueError('Expected zero-network research process required')
    proposals=json.loads(a.proposals.read_text(encoding='utf8'))
    if proposals['provenance']['databaseSha256']!=manifest['sourceDatabaseSha256'] or proposals['provenance']['scriptsSha256']!=manifest['sourceForgeScriptsSha256']:
        raise ValueError('Proposal source identities do not match the live manifest')
    specs={p['name']:p for p in proposals['proposals']}
    fixture=json.loads(a.scenario_json.read_text(encoding='utf8'));names=fixture['fixtureHand']
    if fixture.get('scenario')!='card-family' or len(names)!=len(set(names)) or not set(names)<=specs.keys():raise ValueError('Distinct qualified fixture cards required')
    for name in names:
        p=specs[name];m=manifest['cards'][name]
        if m['grpId']!=p['printing']:raise ValueError('Native printing differs: '+name)
    a.output.mkdir(parents=True,exist_ok=False);checks=[];completed=[]
    def state():return json.loads((lab/'forge-ipc/state.json').read_text())
    def check(label,value):
        checks.append(dict(check=label,passed=bool(value)))
        if not value:raise AssertionError(label)
    def settle():
        end=time.monotonic()+15
        while time.monotonic()<end:
            p=native.inspect();host=json.loads((lab/'native-host-status.json').read_text())
            if not host.get('presentationBusy') and p['workflow']=='ActionsAvailableWorkflow':return
            time.sleep(.1)
        raise TimeoutError('Original native presentation failed to settle')
    try:
        capture(a.output/'initial.png')
        with (a.output/'actions.log').open('w',encoding='utf8') as log,redirect_stdout(log):
            for name in names:
                p=specs[name];before=state();identity=next(c['forgeId'] for c in before['hand'] if c['name']==name)
                hand={c['forgeId'] for c in before['hand']};library={c['forgeId'] for c in before['hidden'] if c['owner']==1 and c['zone']=='Library'}
                tapped=sum(c['tapped'] for c in before['battlefield'] if c['owner']==1)
                check(name+' original card is offered',identity in before['legalCasts'])
                native.card(identity)
                stack=state()
                check(name+' original callback enters real stack',any(c['forgeId']==identity for c in stack['stack']))
                check(name+' effects wait for resolution',stack['life']==before['life'] and {c['forgeId'] for c in stack['hand']}==hand-{identity})
                observed=native.inspect();buttons=[b for b in observed['buttons'] if b['enabled'] and b['text'] in ('Resolve','Pass')]
                check(name+' has exactly one original resolution control',len(buttons)==1)
                native.action('button',buttons[0]['text'],observed=observed);settle();after=state()
                draw=sum(e['amount'] for e in p.get('oracleEffects',[]) if e['kind']=='Draw')
                life=sum(e['amount'] for e in p.get('oracleEffects',[]) if e['kind']=='GainLife')
                remaining={c['forgeId'] for c in after['hidden'] if c['owner']==1 and c['zone']=='Library'}
                drawn=library-remaining
                check(name+' exact library identities become the authored draw',len(drawn)==draw and remaining<=library and {c['forgeId'] for c in after['hand']}==(hand-{identity})|drawn)
                check(name+' life equals independent native-text oracle',after['life']-before['life']==life)
                check(name+' actual payment equals printed cost',sum(c['tapped'] for c in after['battlefield'] if c['owner']==1)-tapped==p['printedCost']['total'])
                zone='battlefield' if p.get('oracleCharacteristics',{}).get('toughness',0)>0 else 'graveyard'
                objects=[c for c in after[zone] if c['forgeId']==identity]
                check(name+' original spell reaches authored destination',not after['stack'] and len(objects)==1)
                if 'oracleCharacteristics' in p:
                    check(name+' printed stats match native metadata',all(objects[0].get(k)==v for k,v in p['oracleCharacteristics'].items()))
                check(name+' strict human controls retain no gap',after.get('researchControls',{}).get('strictHumanCallbacks') is True and not after['fidelityGap'])
                check(name+' opponent hidden identity stays private',all('name' not in c for c in after['hidden']))
                completed.append(name)
                (a.output/'progress.json').write_text(json.dumps(dict(completed=completed,checks=len(checks))),encoding='utf8')
            capture(a.output/'resolved.png')
    finally:
        for name in ('state.json','native-wire.jsonl','engine-journal.jsonl'):
            if (lab/'forge-ipc'/name).exists():shutil.copy2(lab/'forge-ipc'/name,a.output/name)
        result=dict(cards=names,completed=completed,checks=len(checks),passed=completed==names and all(c['passed'] for c in checks),results=checks,
            proposalSha256=sha(a.proposals),scenarioSha256=sha(a.scenario_json),manifestSha256=sha(lab/'bridge-card-manifest.json'),nativePid=a.expected_native_pid,
            scope='Source-qualified casting/payment/stats or fixed-amount outcomes via original UI callbacks. No keyword combat, all-interaction, physical-mouse, animation-parity, complete-match or admission claim.')
        (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(cards=len(completed),checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('proposals','scenario-json','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--expected-native-pid',type=int,required=True)
    run(p.parse_args())
