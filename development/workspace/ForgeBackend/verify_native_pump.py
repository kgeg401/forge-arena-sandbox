"""Original qualified pump target/Cancel/Submit/Resolve and visible expiration."""
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
    if launch['pid']!=a.expected_native_pid or not launch.get('appContainer') or launch.get('capabilityCount')!=0 or not manifest.get('researchOnly'):raise ValueError('Expected independent native research process')
    p=next(v for v in json.loads(a.proposals.read_text(encoding='utf8'))['proposals'] if v['name']==a.card)
    if p['template']!='fixed-target-pump-v1' or manifest['cards'][a.card]['grpId']!=p['printing']:raise ValueError('Independent source oracle or selected printing differs')
    buffed=(2+p['oracleDelta']['power'],2+p['oracleDelta']['toughness'])
    a.output.mkdir(parents=True,exist_ok=False);checks=[];completed=False
    def state():return json.loads((lab/'forge-ipc/state.json').read_text())
    def check(label,value):
        checks.append(dict(check=label,passed=bool(value)))
        if not value:raise AssertionError(label)
    def actor_stats(s,actor):
        c=next(c for c in s['battlefield'] if c['forgeId']==actor);return c['power'],c['toughness']
    def wire_stats(actor):
        objects,mapping=native.mapping();cards=[c for i,c in objects.items() if mapping.get(i)==actor]
        if len(cards)!=1:raise AssertionError('One original native actor object required')
        return cards[0]['power']['value'],cards[0]['toughness']['value']
    def priority():
        observed=settle();buttons=[b for b in observed['buttons'] if b['enabled'] and b['text'] in ('Pass','Resolve')]
        if not buttons:buttons=[b for b in observed['buttons'] if b['enabled'] and b['tag']=='Primary']
        check('One observed original priority control',len(buttons)==1)
        native.action('button',buttons[0]['text'],observed=observed)
    def settle():
        end=time.monotonic()+20
        while time.monotonic()<end:
            observed=native.inspect();host=json.loads((lab/'native-host-status.json').read_text())
            if observed['workflow']=='ActionsAvailableWorkflow' and not host.get('presentationBusy'):return observed
            time.sleep(.1)
        raise TimeoutError('Original pump presentation did not settle')
    try:
        s=state();spell=next(c['forgeId'] for c in s['hand'] if c['name']==a.card);actor=next(c['forgeId'] for c in s['battlefield'] if c['name']=='Grizzly Bears' and c['owner']==1)
        enemy=next(c['forgeId'] for c in s['battlefield'] if c['name']=='Grizzly Bears' and c['owner']==2)
        check('Source fixture begins at printed2/2 and full life',actor_stats(s,actor)==(2,2) and s['life']==s['opponentLife']==20)
        with (a.output/'actions.log').open('w',encoding='utf8') as log,redirect_stdout(log):
            capture(a.output/'before.png');native.card(spell);observed=native.inspect();before=state()
            check('Original target workflow offers exactly both creature objects',observed['workflow']=='SelectTargetsWorkflow' and {v['forgeId'] for v in before['decision']['options']}=={actor,enemy})
            native.action('ui','DuelScene/ClientPrompt/ClientPrompt_Button_Cancel',observed=observed)
            s=state();check('Original Cancel preserves spell and unspent sources',not s['stack'] and all(s[k]==before[k] for k in ('hand','battlefield','life','hidden')))
            native.card(spell);native.card(actor);s=state()
            if s.get('decision'):
                check('Original selection is the authored friendly creature',{v['forgeId'] for v in s['decision']['assignments']}=={actor})
                observed=native.inspect();buttons=[b for b in observed['buttons'] if b['enabled'] and b['text'].startswith('Submit')]
                check('One original target Submit control',len(buttons)==1);native.action('button',buttons[0]['text'],observed=observed)
            s=state();check('Original selection puts exact source and target on stack',len(s['stack'])==1 and s['stack'][0]['forgeId']==spell and s['stack'][0]['targetForgeIds']==[actor])
            check('No stat change before real resolution',actor_stats(s,actor)==(2,2));priority();settle();s=state()
            check('Actual Forge actor receives independently sourced bonus',actor_stats(s,actor)==buffed)
            check('Original native object receives exact independently expected stats',wire_stats(actor)==buffed)
            check('Untargeted opponent remains printed2/2',actor_stats(s,enemy)==(2,2))
            check('Spell enters graveyard and exact source cost is paid',any(c['forgeId']==spell for c in s['graveyard']) and sum(c['owner']==1 and c['tapped'] for c in s['battlefield'])==p['printedCost']['total'])
            capture(a.output/'buffed.png');end=time.monotonic()+100;actions=0
            while time.monotonic()<end and actions<32:
                s=state()
                if s['turn']>1 and actor_stats(s,actor)==(2,2):break
                if s.get('decision'):raise AssertionError('Unexpected decision while observing pump expiration: '+s['decision']['kind'])
                priority();actions+=1
            else:raise TimeoutError('Actual cleanup expiration was not reached')
            settle();s=state()
            check('Actual turn progression removes temporary modifier',s['turn']>1 and actor_stats(s,actor)==(2,2))
            check('Original native object also returns to printed2/2',wire_stats(actor)==(2,2))
            check('No collateral life change, hidden name leak or callback gap',s['life']==s['opponentLife']==20 and not s['fidelityGap'] and s['researchControls']['strictHumanCallbacks'] and all('name' not in c for c in s['hidden']))
            capture(a.output/'expired.png');completed=True
    finally:
        for filename in ('state.json','native-wire.jsonl','engine-journal.jsonl'):
            if (lab/'forge-ipc'/filename).exists():shutil.copy2(lab/'forge-ipc'/filename,a.output/filename)
        (a.output/'report.json').write_text(json.dumps(dict(cards=[a.card],passed=completed and all(v['passed'] for v in checks),checks=len(checks),results=checks,scope='Original target, Cancel, Submit and priority/Resolve callbacks; exact source-defined native buff and cleanup2/2 objects and rendered scenes. Separate from full matches or arbitrary modifier layers.'),indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expected-native-pid',type=int,required=True)
    p.add_argument('--proposals',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--card',default='Giant Growth')
    run(p.parse_args())
