"""Resume observed Unsummon targeting: original Cancel, target, Submit, Resolve.

Only native control callbacks are invoked; the Forge IPC is read-only here.
"""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import shutil
import time
import native_ui_client as n
from native_client_ui import capture
from runtime_paths import ROOT


def main(a):
    lab=ROOT/'native-lab';launch=json.loads((lab/'launch-receipt.json').read_text())
    if launch['pid']!=a.expected_native_pid or not launch.get('appContainer') or launch.get('capabilityCount')!=0:raise ValueError('Wrong native research process')
    a.output.mkdir(parents=True,exist_ok=False);checks=[]
    def state():return json.loads((lab/'forge-ipc/state.json').read_text())
    def check(label,value):
        checks.append(dict(check=label,passed=bool(value)))
        if not value:raise AssertionError(label)
    s=state();spell=next(c['forgeId'] for c in s['hand'] if c['name']=='Unsummon')
    expected={c['forgeId'] for c in s['battlefield'] if c['name'] in ('Yoked Ox','Colossal Dreadmaw','Grizzly Bears')}
    enemy=next(c['forgeId'] for c in s['battlefield'] if c['name']=='Grizzly Bears' and c['owner']==2)
    check('Resume only the observed pending target decision',s.get('decision',{}).get('kind')=='targets' and n.inspect()['workflow']=='SelectTargetsWorkflow')
    check('Exactly the authored three creatures are legal targets',{v['forgeId'] for v in s['decision']['options']}==expected and len(expected)==3)
    with (a.output/'actions.log').open('w',encoding='utf8') as log,redirect_stdout(log):
        before=state();capture(a.output/'target-selection.png')
        observed=n.inspect()
        n.action('ui','DuelScene/ClientPrompt/ClientPrompt_Button_Cancel',observed=observed)
        after=state()
        check('Original Cancel preserves hand, resources, life and stack',not after.get('decision') and not after['stack'] and all(after[k]==before[k] for k in ('hand','battlefield','life','hidden')))
        capture(a.output/'canceled.png')
        n.card(spell);p=n.inspect(True)
        check('Original card starts the target workflow again',p['workflow']=='SelectTargetsWorkflow' and state().get('decision',{}).get('kind')=='targets')
        n.card(enemy)
        after=state()
        if after.get('decision'):
            check('Native target selection matches the chosen enemy',{v['forgeId'] for v in after['decision']['assignments']}=={enemy})
            p=n.inspect();buttons=[b for b in p['buttons'] if b['enabled'] and b['text'].startswith('Submit')]
            check('One original target confirmation is enabled',len(buttons)==1)
            n.action('button',buttons[0]['text'],observed=p)
        stacked=state()
        check('Original target confirmation puts exact target on stack',any(c['forgeId']==spell and c['targetForgeIds']==[enemy] for c in stacked['stack']))
        p=n.inspect();buttons=[b for b in p['buttons'] if b['enabled'] and b['text'] in ('Resolve','Pass')]
        check('Original resolution control is available',len(buttons)==1)
        n.action('button',buttons[0]['text'],observed=p)
        end=time.monotonic()+15
        while time.monotonic()<end:
            p=n.inspect();h=json.loads((lab/'native-host-status.json').read_text())
            if not h.get('presentationBusy') and p['workflow']=='ActionsAvailableWorkflow':break
            time.sleep(.1)
        else:raise TimeoutError('Original target-resolution presentation did not settle')
        after=state()
        check('Enemy creature actually reaches its hidden owner hand',not after['stack'] and any(c['forgeId']==enemy and c['owner']==2 and c['zone']=='Hand' for c in after['hidden']))
        check('Other authored creatures remain on the battlefield',{c['forgeId'] for c in after['battlefield'] if c['name'] in ('Yoked Ox','Colossal Dreadmaw')}==expected-{enemy})
        check('No hidden identity leaks or unsupported decision',all('name' not in c for c in after['hidden']) and not after['fidelityGap'])
        capture(a.output/'resolved.png')
    for name in ('native-wire.jsonl','engine-journal.jsonl','state.json'):shutil.copy2(lab/'forge-ipc'/name,a.output/name)
    (a.output/'report.json').write_text(json.dumps(dict(checks=len(checks),results=checks,scope='Actual original target/cancel/submit/resolve callbacks and rendered outcome. Separate from all-target-card or animation parity claims.'),indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expected-native-pid',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
