"""Original native card/button callbacks for casting and fixed draw/life spells.

No engine requests or intermediate state are injected. Research lab only.
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
    lab=ROOT/'native-lab'
    manifest=json.loads((lab/'bridge-card-manifest.json').read_text())
    launch=json.loads((lab/'launch-receipt.json').read_text())
    if not manifest.get('researchOnly') or not launch.get('appContainer') or launch.get('capabilityCount')!=0 or launch['pid']!=a.expected_native_pid:
        raise ValueError('Only the expected zero-network native research process is allowed')
    a.output.mkdir(parents=True,exist_ok=False);checks=[]
    def state():return json.loads((lab/'forge-ipc/state.json').read_text())
    def check(label,value):
        checks.append(dict(check=label,passed=bool(value)))
        if not value:raise AssertionError(label)
    def settle():
        end=time.monotonic()+15
        while time.monotonic()<end:
            p=n.inspect();h=json.loads((lab/'native-host-status.json').read_text())
            if not h.get('presentationBusy') and p['workflow']=='ActionsAvailableWorkflow':return p
            time.sleep(.1)
        raise TimeoutError('Original native presentation did not settle')
    specs=[('Colossal Dreadmaw',6,0,0,'battlefield'),('Revitalize',2,1,3,'graveyard'),('Ritual of Rejuvenation',3,1,4,'graveyard')]
    capture(a.output/'before.png')
    with (a.output/'actions.log').open('w',encoding='utf8') as log,redirect_stdout(log):
        for index,(name,cost,draw,life,zone) in enumerate(specs):
            s=state();identity=next(c['forgeId'] for c in s['hand'] if c['name']==name)
            library={c['forgeId'] for c in s['hidden'] if c['owner']==1 and c['zone']=='Library'}
            tapped=sum(c['tapped'] for c in s['battlefield'] if c['owner']==1)
            check(name+' original native cast offered',identity in s['legalCasts'])
            n.card(identity)
            check(name+' original callback enters real stack',any(c['forgeId']==identity for c in state()['stack']))
            observed=n.inspect();buttons=[b for b in observed['buttons'] if b['enabled'] and b['text'] in ('Resolve','Pass')]
            check(name+' unique original resolution button',len(buttons)==1)
            n.action('button',buttons[0]['text'],observed=observed)
            settle();after=state()
            remaining={c['forgeId'] for c in after['hidden'] if c['owner']==1 and c['zone']=='Library'}
            check(name+' exact actual life gain',after['life']-s['life']==life)
            check(name+' original library cards actually drawn',len(library-remaining)==draw and (library-remaining)<={c['forgeId'] for c in after['hand']})
            check(name+' printed mana paid by actual sources',sum(c['tapped'] for c in after['battlefield'] if c['owner']==1)-tapped==cost)
            check(name+' correct original card destination',not after['stack'] and any(c['forgeId']==identity for c in after[zone]))
            check(name+' strict human controls and no gap',not after['fidelityGap'] and after.get('researchControls',{}).get('strictHumanCallbacks') is True)
            capture(a.output/(str(index)+'-'+name.replace(' ','-')+'.png'))
    for name in ('state.json','native-wire.jsonl','engine-journal.jsonl'):
        shutil.copy2(lab/'forge-ipc'/name,a.output/name)
    result=dict(cards=[s[0] for s in specs],checks=len(checks),results=checks,
        scope='Original native callbacks and rendered board with actual rules outcomes; no physical mouse, full animation parity, complete-match or admission claim.')
    (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-native-pid',type=int,required=True)
    main(p.parse_args())
