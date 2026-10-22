"""Original native controls for seven exact reviewed conditional draw/life spells."""
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
    if launch['pid']!=a.expected_native_pid or not launch.get('appContainer') or launch.get('capabilityCount')!=0 or not manifest.get('researchOnly'):raise ValueError('Expected independent zero-network research process')
    # Expected numbers follow the authored initial fixture and this exact order:
    # own graveyard2 Inventory+Forest; enemy graveyard20 Forest; own10/10 actor.
    specs=[('Feed the Clan',2,0,10),('Frantic Inventory',2,3,0),('Life Goes On',1,0,4),("Sphinx's Insight",4,2,2),('Sudden Insight',6,3,0),('Union of the Third Path',3,1,10),('Visions of Beyond',1,3,0)]
    source={p['name']:p for p in json.loads(a.proposals.read_text(encoding='utf8'))['proposals']}
    a.output.mkdir(parents=True,exist_ok=False);checks=[];completed=[]
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
        raise TimeoutError('Original conditional spell presentation did not settle')
    try:
        initial=state();ids={c['name']:c['forgeId'] for c in initial['hand']}
        check('Authored seven original cards and initial conditions',len(initial['hand'])==7 and initial['life']==20 and initial['opponentLife']==20 and len([c for c in initial['graveyard'] if c['owner']==2])==20)
        with (a.output/'actions.log').open('w',encoding='utf8') as log,redirect_stdout(log):
            capture(a.output/'initial.png')
            for name,cost,draw,life in specs:
                before=state();identity=ids[name];hand={c['forgeId'] for c in before['hand']};library={c['forgeId'] for c in before['hidden'] if c['owner']==1 and c['zone']=='Library'}
                check(name+' source printing and printed cost match',manifest['cards'][name]['grpId']==source[name]['printing'] and cost==source[name]['printedCost']['total'])
                check(name+' original card is legally offered',identity in before['legalCasts']);native.card(identity);s=state()
                check(name+' original callback enters real stack before effects',any(c['forgeId']==identity for c in s['stack']) and s['life']==before['life'])
                observed=native.inspect();buttons=[b for b in observed['buttons'] if b['enabled'] and b['text'] in ('Pass','Resolve')]
                check(name+' one original resolution button',len(buttons)==1);native.action('button',buttons[0]['text'],observed=observed);settle();after=state()
                remaining={c['forgeId'] for c in after['hidden'] if c['owner']==1 and c['zone']=='Library'};drawn=library-remaining
                check(name+' authored draw count and exact library object identities',len(drawn)==draw and remaining<=library and {c['forgeId'] for c in after['hand']}==(hand-{identity})|drawn)
                check(name+' independently authored conditional life change',after['life']-before['life']==life)
                check(name+' actual printed mana payment',sum(c['tapped'] for c in after['battlefield'] if c['owner']==1)-sum(c['tapped'] for c in before['battlefield'] if c['owner']==1)==cost)
                check(name+' actual spell destination and strict human controls',not after['stack'] and any(c['forgeId']==identity for c in after['graveyard']) and after['researchControls']['strictHumanCallbacks'] and not after['fidelityGap'])
                check(name+' hidden opponent names remain private',all('name' not in c for c in after['hidden']))
                completed.append(name);capture(a.output/(str(len(completed))+'-resolved.png'))
            check('Whole authored native sequence ends at life46 with12 cards',state()['life']==46 and len(state()['hand'])==12)
    finally:
        for name in ('state.json','native-wire.jsonl','engine-journal.jsonl','scenario.json'):
            if (lab/'forge-ipc'/name).exists():shutil.copy2(lab/'forge-ipc'/name,a.output/name)
        (a.output/'report.json').write_text(json.dumps(dict(passed=completed==[r[0] for r in specs] and all(c['passed'] for c in checks),cards=completed,checks=len(checks),results=checks),indent=2))
    print(json.dumps(dict(cards=completed,checks=len(checks))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expected-native-pid',type=int,required=True)
    for key in ('proposals','output'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
