"""Original native combat controls and graveyard ordering browser round trip.

Two local blockers die to an attacking 9/9. Their original Order Cards browser
submits a real OrderResp. Its displayed order, reversed wire IDs, and Forge's
resulting graveyard insertion order must agree. Engine IPC is read-only.
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
    if launch['pid']!=a.expected_native_pid or not launch.get('appContainer') or launch.get('capabilityCount')!=0 or not manifest.get('researchOnly'):raise ValueError('Expected isolated native research process required')
    a.output.mkdir(parents=True,exist_ok=False);checks=[];completed=False
    def state():return json.loads((lab/'forge-ipc/state.json').read_text())
    def check(label,value):
        checks.append(dict(check=label,passed=bool(value)))
        if not value:raise AssertionError(label)
    try:
        initial=state();own=[next(c['forgeId'] for c in initial['battlefield'] if c['name']==name and c['owner']==1) for name in ('Grizzly Bears','Coral Merfolk')]
        enemy=next(c['forgeId'] for c in initial['battlefield'] if c['name']=='Ancient Brontodon' and c['owner']==2)
        if a.resume_after_blocks:
            previous=json.loads((a.resume_after_blocks/'state.json').read_text())
            check('Resume only the exact unchanged post-blocking Forge snapshot',initial==previous and initial['phase']=='COMBAT_DECLARE_BLOCKERS' and not initial.get('decision'))
        with (a.output/'actions.log').open('w',encoding='utf8') as log,redirect_stdout(log):
            if not a.resume_after_blocks:
                capture(a.output/'initial.png')
                for _ in range(12):
                    p=native.inspect();s=state()
                    if s.get('decision',{}).get('kind')=='blockers':break
                    buttons=[b for b in p['buttons'] if b['enabled'] and b['text'] in ('Pass','Resolve')]
                    if not buttons and p['workflow']=='ActionsAvailableWorkflow' and s.get('canPass'):
                        buttons=[b for b in p['buttons'] if b['enabled'] and b['tag']=='Primary']
                    check('One original priority control before blockers',len(buttons)==1)
                    native.action('button',buttons[0]['text'],observed=p)
                check('Original blocker workflow agrees with actual Forge choice',state().get('decision',{}).get('kind')=='blockers' and native.inspect()['workflow']=='DeclareBlockersWorkflow')
                for blocker in own:
                    native.card(blocker,wait_for_change=False)
                    s=state()
                    paired=any(v['forgeId']==blocker and v['attackerIds']==[enemy] for v in s['decision']['assignments'])
                    if not paired:native.card(enemy)
                    check('Original clicks assign authored blocker '+str(blocker),any(v['forgeId']==blocker and v['attackerIds']==[enemy] for v in state()['decision']['assignments']))
                p=native.inspect();primary=[b for b in p['buttons'] if b['enabled'] and b['tag']=='Primary']
                check('Exactly one original blocker submission',len(primary)==1)
                native.action('button',primary[0]['text'],observed=p)
            end=time.monotonic()+30;advances=0
            while time.monotonic()<end:
                p=native.inspect();s=state()
                if p['workflow']=='OrderWorkflow' and s.get('decision',{}).get('kind')=='order_cards':break
                if not s.get('decision') and p['workflow']=='ActionsAvailableWorkflow' and s.get('canPass') and advances<6:
                    buttons=[b for b in p['buttons'] if b['enabled'] and b['text'] in ('Pass','Resolve')]
                    if not buttons:buttons=[b for b in p['buttons'] if b['enabled'] and b['tag']=='Primary']
                    check('One original priority control between blocking and damage',len(buttons)==1)
                    native.action('button',buttons[0]['text'],observed=p);advances+=1
                else:time.sleep(.1)
            else:raise TimeoutError('Original graveyard ordering browser did not appear')
            check('Real simultaneous deaths expose exactly the authored two objects',{v['forgeId'] for v in s['decision']['options']}==set(own) and s['decision']['destination']=='Graveyard')
            native_order=p.get('orderCardIds');_,mapping=native.mapping()
            expected=[mapping.get(i) for i in native_order] if native_order else []
            check('Displayed original browser list matches the actual offered objects',len(expected)==2 and set(expected)==set(own))
            (a.output/'original-browser-probe.json').write_text(json.dumps(p,indent=2),encoding='utf8')
            capture(a.output/'order-cards.png')
            done=[b for b in p['buttons'] if b['enabled'] and b['text'].casefold() in ('done','submit')]
            if len(done)==1:native.action('button',done[0]['text'],observed=p)
            else:
                ui=[b for b in p['uiButtons'] if b['enabled'] and (b.get('key') or '').casefold().endswith(('_done','/done'))]
                check('One original Done control in the browser',len(ui)==1)
                native.action('ui',ui[0]['key'],observed=p)
            end=time.monotonic()+20
            while time.monotonic()<end:
                p=native.inspect();s=state();host=json.loads((lab/'native-host-status.json').read_text())
                if not s.get('decision') and p['workflow']=='ActionsAvailableWorkflow' and not host.get('presentationBusy'):break
                time.sleep(.1)
            else:raise TimeoutError('Ordering did not reach the next stable original workflow')
            check('Original browser order becomes exact graveyard insertion order',[c['forgeId'] for c in s['graveyard'] if c['owner']==1]==expected)
            wire=[json.loads(l) for l in (lab/'forge-ipc/native-wire.jsonl').read_text().splitlines()]
            replies=[r['message']['orderResp'] for r in wire if r['direction']=='outgoing' and 'orderResp' in r['message']]
            check('Shipped browser emits its recovered reversed-ID OrderResp',len(replies)==1 and replies[0]['ids']==list(reversed(native_order)) and replies[0]['ordering']=='OrderingType_OrderAsIndicated')
            check('Only authored combat consequences occur',s['life']==20 and s['opponentLife']==20 and any(c['forgeId']==enemy and c['damage']==4 for c in s['battlefield']))
            check('No unsupported choice or private opponent identity leak',not s['fidelityGap'] and s['researchControls']['strictHumanCallbacks'] and all('name' not in c for c in s['hidden']))
            capture(a.output/'ordered-graveyard.png');completed=True
    finally:
        for name in ('state.json','native-wire.jsonl','engine-journal.jsonl'):
            if (lab/'forge-ipc'/name).exists():shutil.copy2(lab/'forge-ipc'/name,a.output/name)
        (a.output/'report.json').write_text(json.dumps(dict(cards=['Grizzly Bears','Coral Merfolk'],resumedFrom=str(a.resume_after_blocks) if a.resume_after_blocks else None,passed=completed and all(c['passed'] for c in checks),checks=len(checks),results=checks,
            scope='Original blocker clicks, submit and Order Cards/Done callbacks, actual wire permutation and resulting graveyard order. No physical-mouse, arbitrary zone-ordering or full animation parity claim.'),indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-native-pid',type=int,required=True)
    p.add_argument('--resume-after-blocks',type=Path)
    run(p.parse_args())
