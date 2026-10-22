"""Original native targeting and resolution of a response that invalidates a target.

Two Unsummons target the same enemy creature. The response returns it; the
original must fizzle. Engine IPC is read-only; all actions use original controls.
"""
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
    if launch['pid']!=a.expected_native_pid or not launch.get('appContainer') or launch.get('capabilityCount')!=0 or not manifest.get('researchOnly'):raise ValueError('Expected isolated research native process required')
    a.output.mkdir(parents=True,exist_ok=False);checks=[];completed=False
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
        raise TimeoutError('Native presentation did not reach its original action workflow')
    def resolve_button():
        p=native.inspect();buttons=[b for b in p['buttons'] if b['enabled'] and b['text'] in ('Resolve','Pass')]
        check('Exactly one original resolution button is enabled',len(buttons)==1)
        native.action('button',buttons[0]['text'],observed=p);settle()
    try:
        s=state();spells=[c['forgeId'] for c in s['hand'] if c['name']=='Unsummon'];enemy=next(c['forgeId'] for c in s['battlefield'] if c['name']=='Grizzly Bears' and c['owner']==2)
        own=next(c['forgeId'] for c in s['battlefield'] if c['name']=='Yoked Ox' and c['owner']==1)
        check('Authored initial two spells and unchanged empty stack',len(spells)==2 and not s['stack'] and s['life']==20 and s['opponentLife']==20)
        with (a.output/'actions.log').open('w',encoding='utf8') as log,redirect_stdout(log):
            capture(a.output/'initial.png')
            for index,spell in enumerate(spells):
                before=state();check('Original response card is legally offered '+str(index),spell in before['legalCasts'])
                native.card(spell)
                d=state().get('decision');check('Original target workflow offers exactly both authored creatures '+str(index),native.inspect(True)['workflow']=='SelectTargetsWorkflow' and d and d['kind']=='targets' and {v['forgeId'] for v in d['options']}=={enemy,own})
                native.card(enemy)
                if state().get('decision'):
                    p=native.inspect();buttons=[b for b in p['buttons'] if b['enabled'] and b['text'].startswith('Submit')]
                    check('One original target confirmation '+str(index),len(buttons)==1)
                    native.action('button',buttons[0]['text'],observed=p)
                settle();after=state()
                check('Actual target confirmed on original stack object '+str(index),any(c['forgeId']==spell and c['targetForgeIds']==[enemy] for c in after['stack']))
                check('Response preserves earlier unresolved spell '+str(index),{c['forgeId'] for c in after['stack']}==set(spells[:index+1]))
                check('Target remains before actual resolution '+str(index),any(c['forgeId']==enemy for c in after['battlefield']))
            capture(a.output/'two-spells-on-stack.png')
            resolve_button();middle=state()
            check('Only the latest spell resolves first',{c['forgeId'] for c in middle['stack']}=={spells[0]} and any(c['forgeId']==spells[1] for c in middle['graveyard']))
            check('Response actually returns target to hidden owner hand',any(c['forgeId']==enemy and c['owner']==2 and c['zone']=='Hand' for c in middle['hidden']))
            capture(a.output/'response-resolved.png')
            resolve_button();after=state()
            check('Original spell leaves stack for graveyard',not after['stack'] and {c['forgeId'] for c in after['graveyard']}>=set(spells))
            resolutions=[r for r in after['researchTrace'] if r['kind']=='spell-resolved' and r['sourceForgeId'] in spells]
            check('Forge events report response success then original fizzle',[(r['sourceForgeId'],r['hasFizzled']) for r in resolutions]==[(spells[1],False),(spells[0],True)])
            check('Both actual colored sources were paid',sum(c['tapped'] for c in after['battlefield'] if c['owner']==1 and c['name']=='Island')==2)
            check('No unintended life change or other creature change',after['life']==20 and after['opponentLife']==20 and any(c['forgeId']==own for c in after['battlefield']))
            check('Strict choice control and hidden identity remain intact',after['researchControls']['strictHumanCallbacks'] and not after['fidelityGap'] and all('name' not in c for c in after['hidden']))
            capture(a.output/'original-fizzled.png')
            completed=True
    finally:
        for name in ('state.json','native-wire.jsonl','engine-journal.jsonl'):
            if (lab/'forge-ipc'/name).exists():shutil.copy2(lab/'forge-ipc'/name,a.output/name)
        result=dict(cards=['Unsummon'],checks=len(checks),passed=completed and bool(checks) and all(c['passed'] for c in checks),results=checks,
            scope='Original native response targeting/stack/resolution controls with actual Forge fizzle event and rendered outcome. No all-target-card or full animation parity claim.')
        (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-native-pid',type=int,required=True)
    run(p.parse_args())
