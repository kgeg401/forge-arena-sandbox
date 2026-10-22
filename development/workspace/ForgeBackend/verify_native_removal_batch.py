"""Original native Cancel/target/Submit/Resolve and removal zone observations."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import shutil
import time
import native_ui_client as native
from native_client_ui import capture
from runtime_paths import ROOT


def run(a):
    lab=ROOT/'native-lab';launch=json.loads((lab/'launch-receipt.json').read_text());manifest=json.loads((lab/'bridge-card-manifest.json').read_text())
    if launch['pid']!=a.expected_native_pid or not launch.get('appContainer') or launch.get('capabilityCount')!=0 or not manifest.get('researchOnly'):raise ValueError('Expected isolated research native client')
    specs={p['name']:p for p in json.loads(a.proposals.read_text(encoding='utf8'))['proposals']}
    plan=json.loads(a.plan.read_text(encoding='utf8'));a.output.mkdir(parents=True,exist_ok=False);checks=[];completed=[]
    def state():return json.loads((lab/'forge-ipc/state.json').read_text())
    def check(label,value):
        checks.append(dict(check=label,passed=bool(value)))
        if not value:raise AssertionError(label)
    def settle():
        end=time.monotonic()+25
        while time.monotonic()<end:
            observed=native.inspect();host=json.loads((lab/'native-host-status.json').read_text())
            if observed['workflow']=='ActionsAvailableWorkflow' and not host.get('presentationBusy'):return observed
            time.sleep(.1)
        raise TimeoutError('Original removal presentation failed to settle')
    try:
        with (a.output/'actions.log').open('w',encoding='utf8') as log,redirect_stdout(log):
            capture(a.output/'initial.png')
            for row in plan:
                name=row['name'];p=specs[name];s=state();spell=next(c['forgeId'] for c in s['hand'] if c['name']==name)
                target=next(c['forgeId'] for c in s['battlefield'] if c['name']==row['targetName'] and c['owner']==row['targetOwner'])
                expected={c['forgeId'] for c in s['battlefield'] if (c['name'],c['owner']) in {(t['name'],t['owner']) for t in row['expectedTargets']}}
                check(name+' exact source-bound prompt and printing',manifest['cards'][name]['grpId']==p['printing'] and manifest['cards'][name]['targetPromptId']==p['promptId'])
                native.card(spell);before=state();observed=native.inspect()
                check(name+' original target workflow has independently authored options',observed['workflow']=='SelectTargetsWorkflow' and {v['forgeId'] for v in before['decision']['options']}==expected)
                requests=[json.loads(line)['message']['selectTargetsReq'] for line in (lab/'forge-ipc/native-wire.jsonl').read_text().splitlines() if 'selectTargetsReq' in json.loads(line)['message']]
                check(name+' actual original wire uses the exact owned target prompt',requests[-1]['targets'][0]['prompt']['promptId']==p['promptId'])
                native.action('ui','DuelScene/ClientPrompt/ClientPrompt_Button_Cancel',observed=observed);s=state()
                check(name+' original Cancel preserves original hand, resources and life',not s['stack'] and all(s[k]==before[k] for k in ('hand','battlefield','life','hidden')))
                native.card(spell);native.card(target);s=state()
                if s.get('decision'):
                    observed=native.inspect();buttons=[b for b in observed['buttons'] if b['enabled'] and b['text'].startswith('Submit')]
                    check(name+' one original Submit confirms selected target',len(buttons)==1);native.action('button',buttons[0]['text'],observed=observed)
                s=state();check(name+' exact spell and target enter real stack',len(s['stack'])==1 and s['stack'][0]['forgeId']==spell and s['stack'][0]['targetForgeIds']==[target])
                check(name+' target survives until resolution',any(c['forgeId']==target for c in s['battlefield']))
                observed=native.inspect();buttons=[b for b in observed['buttons'] if b['enabled'] and b['text'] in ('Pass','Resolve')]
                check(name+' one original resolution control',len(buttons)==1);native.action('button',buttons[0]['text'],observed=observed);settle();s=state()
                check(name+' exact target reaches independently sourced destination',any(c['forgeId']==target and c['zone']==p['destination'] for zone in ('graveyard','exile','hand','hidden') for c in s[zone]))
                check(name+' exact target leaves battlefield and spell resolves to graveyard',not any(c['forgeId']==target for c in s['battlefield']) and not s['stack'] and any(c['forgeId']==spell for c in s['graveyard']))
                objects,mapping=native.mapping();zones={}
                for line in (lab/'forge-ipc/native-wire.jsonl').read_text().splitlines():
                    message=json.loads(line)['message'].get('gameStateMessage',{})
                    for zone in message.get('zones',[]):zones[zone['zoneId']]=set(zone.get('objectInstanceIds',[]))
                # Original presentation can retain the prior object while its
                # zone-transfer animation finishes. Membership is authoritative.
                views=[c for i,c in objects.items() if mapping.get(i)==target and i in zones.get(c['zoneId'],set())]
                destination=29 if p['destination']=='Exile' else 33 if row['targetOwner']==1 else 37
                check(name+' original native object receives correct public destination',len(views)==1 and views[0]['zoneId']==destination)
                check(name+' actual payment and unchanged life',sum(c['tapped'] for c in s['battlefield'] if c['owner']==1)-sum(c['tapped'] for c in before['battlefield'] if c['owner']==1)==p['printedCost']['total'] and s['life']==before['life'])
                check(name+' no unsupported callback or hidden identity leak',not s['fidelityGap'] and s['researchControls']['strictHumanCallbacks'] and all('name' not in c for c in s['hidden']))
                capture(a.output/(str(len(completed))+'-resolved.png'));completed.append(name)
                (a.output/'progress.json').write_text(json.dumps(dict(completed=completed,checks=len(checks))))
    finally:
        for name in ('state.json','native-wire.jsonl','engine-journal.jsonl'):
            if (lab/'forge-ipc'/name).exists():shutil.copy2(lab/'forge-ipc'/name,a.output/name)
        (a.output/'report.json').write_text(json.dumps(dict(passed=completed==[r['name'] for r in plan] and all(c['passed'] for c in checks),cards=completed,checks=len(checks),results=checks),indent=2))
    print(json.dumps(dict(cards=completed,checks=len(checks))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected-native-pid',type=int,required=True)
    for key in ('proposals','plan','output'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
