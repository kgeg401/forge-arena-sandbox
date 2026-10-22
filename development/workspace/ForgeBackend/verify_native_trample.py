"""Original attack, damage-browser/player spinner and Done callbacks for trample."""
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
    try:
        s=state();actor=next(c['forgeId'] for c in s['battlefield'] if c['name']=='Colossal Dreadmaw' and c['owner']==1)
        blocker=next(c['forgeId'] for c in s['battlefield'] if c['name']=='Grizzly Bears' and c['owner']==2)
        check('Exact authored starting stats and life',s['life']==20 and s['opponentLife']==20 and next(c for c in s['battlefield'] if c['forgeId']==actor)['power']==6)
        with (a.output/'actions.log').open('w',encoding='utf8') as log,redirect_stdout(log):
            capture(a.output/'initial.png');deadline=time.monotonic()+120;actions=0
            while time.monotonic()<deadline and actions<40:
                p=native.inspect();s=state();kind=(s.get('decision') or {}).get('kind')
                if kind=='assign_damage' and p['workflow']=='AssignDamageWorkflow':break
                if kind=='attackers' and p['workflow']=='DeclareAttackersWorkflow':
                    check('Original attack choice offers exactly the authored creature',{v['forgeId'] for v in s['decision']['options']}=={actor})
                    selected=any(v['forgeId']==actor and v['targetSeat']==2 for v in s['decision']['assignments'])
                    all_attack=[b for b in p['buttons'] if b['enabled'] and b['text']=='All Attack']
                    if not selected and len(all_attack)==1:native.action('button','All Attack',observed=p)
                    elif not selected:native.card(actor)
                    else:
                        primary=[b for b in p['buttons'] if b['enabled'] and b['tag']=='Primary']
                        check('One original attacker submission',len(primary)==1)
                        native.action('button',primary[0]['text'],observed=p)
                    actions+=1
                elif not kind and p['workflow']=='ActionsAvailableWorkflow' and s.get('canPass'):
                    buttons=[b for b in p['buttons'] if b['enabled'] and b['text'] in ('Pass','Resolve')]
                    if not buttons:buttons=[b for b in p['buttons'] if b['enabled'] and b['tag']=='Primary']
                    check('One original priority control before damage',len(buttons)==1)
                    native.action('button',buttons[0]['text'],observed=p);actions+=1
                else:time.sleep(.1)
            else:raise TimeoutError('Original trample damage browser was not reached')
            d=s['decision'];check('Exact real trample total and blocker/player options',d['totalDamage']==6 and {v['forgeId'] for v in d['options']}=={blocker,-1000002})
            check('No damage applied before the human confirms',s['life']==20 and s['opponentLife']==20 and not [v for v in s['events'] if v['kind']=='damage'])
            _,mapping=native.mapping();native_blocker=next(i for i in p['damageAssignments'] if mapping.get(i['instanceId'])==blocker)
            native_player=next(i for i in p['damageAssignments'] if i['instanceId']==2)
            check('Original blocker spinner displays source-authored lethal2 and assignment2',native_blocker['lethalDamage']==2 and native_blocker['assignedDamage']==2 and not native_blocker['isPlayer'])
            check('Original player avatar spinner receives the excess4',native_player['isPlayer'] and native_player['isAttackQuarry'] and native_player['assignedDamage']==4)
            if a.blocker_damage!=2:
                check('Original auto-allocation starts enabled',p['damageControls']['autoAssign']['value'] is True)
                p=native.action('damage-toggle',observed=p)
                check('Original toggle exposes manual spinner buttons',p['damageControls']['autoAssign']['value'] is False and next(v for v in p['damageControls']['spinners'] if v['instanceId']==native_blocker['instanceId'])['increase'])
                p=native.action('damage-spinner',native_blocker['instanceId'],'increase',observed=p)
                check('Original increase transfers exactly one damage from player to blocker',{v['instanceId']:v['assignedDamage'] for v in p['damageAssignments']}=={native_blocker['instanceId']:3,2:3})
                p=native.action('damage-toggle',observed=p)
                check('Original auto-allocation restores lethal2 and excess4',{v['instanceId']:v['assignedDamage'] for v in p['damageAssignments']}=={native_blocker['instanceId']:2,2:4})
                p=native.action('damage-toggle',observed=p)
                for amount in range(3,a.blocker_damage+1):
                    p=native.action('damage-spinner',native_blocker['instanceId'],'increase',observed=p)
                    check('Original manual assignment '+str(amount)+' has exact complementary player damage',{v['instanceId']:v['assignedDamage'] for v in p['damageAssignments']}=={native_blocker['instanceId']:amount,2:6-amount})
                unchanged=state()
                check('Local spinner editing does not apply Forge damage',unchanged['decision']['token']==d['token'] and unchanged['opponentLife']==20 and not [v for v in unchanged['events'] if v['kind']=='damage'])
            (a.output/'damage-browser-probe.json').write_text(json.dumps(p,indent=2),encoding='utf8');capture(a.output/'trample-damage-browser.png')
            done=[b for b in p['uiButtons'] if b['enabled'] and b['key']=='DuelScene/KeywordSelection/KeywordSelection_Done']
            check('One original damage-browser Done control',len(done)==1)
            native.action('ui',done[0]['key'],observed=p)
            end=time.monotonic()+20
            while time.monotonic()<end:
                p=native.inspect();s=state();host=json.loads((lab/'native-host-status.json').read_text())
                if not s.get('decision') and p['workflow']=='ActionsAvailableWorkflow' and not host.get('presentationBusy'):break
                time.sleep(.1)
            else:raise TimeoutError('Original trample presentation failed to settle')
            check('Actual player life reflects chosen excess damage',s['opponentLife']==20-(6-a.blocker_damage) and s['life']==20)
            check('Actual source survives its two incoming damage',any(c['forgeId']==actor and c['damage']==2 and c['power']==6 and c['toughness']==6 for c in s['battlefield']))
            check('Actual blocker dies',any(c['forgeId']==blocker for c in s['graveyard']))
            actual=[(v.get('targetForgeId',-1000000-v.get('targetSeat',0)),v['amount']) for v in s['events'] if v['kind']=='damage' and v['sourceForgeId']==actor and v['amount']>0]
            expected=[(blocker,a.blocker_damage)]+([(-1000002,6-a.blocker_damage)] if a.blocker_damage<6 else [])
            check('Exact real card then player combat damage chosen in original controls',actual==expected)
            check('Strict player controls and privacy remain intact',s['researchControls']['strictHumanCallbacks'] and not s['fidelityGap'] and all('name' not in c for c in s['hidden']))
            capture(a.output/'trample-resolved.png');completed=True
    finally:
        for name in ('state.json','native-wire.jsonl','engine-journal.jsonl'):
            if (lab/'forge-ipc'/name).exists():shutil.copy2(lab/'forge-ipc'/name,a.output/name)
        (a.output/'report.json').write_text(json.dumps(dict(cards=['Colossal Dreadmaw'],passed=completed and all(c['passed'] for c in checks),checks=len(checks),results=checks,
            scope='Original attack and trample player/card damage spinners, Done and rendered outcomes. No physical-input, all-card or full animation parity claim.'),indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-native-pid',type=int,required=True);p.add_argument('--blocker-damage',type=int,choices=range(2,7),default=2)
    run(p.parse_args())
