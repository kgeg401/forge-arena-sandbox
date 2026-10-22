"""Drive only original Arena card/button callbacks for the five-color family."""
from datetime import datetime
import json
from pathlib import Path
import shutil
import time
import native_ui_client as native
from runtime_paths import ROOT

lab=ROOT/'native-lab';out=ROOT/'research/broad-card-support'/('native-actions-'+datetime.now().strftime('%Y%m%d-%H%M%S'));out.mkdir()
checks=[]
def state():return json.loads((lab/'forge-ipc/state.json').read_text())
def check(label,ok):
    assert ok,label
    checks.append(dict(check=label,passed=True))
def capture(name):
    image=lab/'native-board.png';before=image.stat().st_mtime_ns if image.exists() else 0
    (lab/'capture-frame.request').write_text(name)
    end=time.monotonic()+8
    while (not image.exists() or image.stat().st_mtime_ns==before) and time.monotonic()<end:time.sleep(.1)
    check('New rendered frame '+name,image.exists() and image.stat().st_mtime_ns!=before)
    shutil.copy2(image,out/(name+'.png'))
def press_primary():
    p=native.inspect();buttons=[b for b in p['buttons'] if b['enabled'] and b['text'] in ('Resolve','Pass')]
    if len(buttons)!=1:raise RuntimeError('Expected one original primary button: '+str(p))
    return native.action('button',buttons[0]['text'],observed=p)

capture('initial-five-color-hand')
for name in ('Gigantosaurus','Fusion Elemental','Fire Elemental','Dune Beetle','Aegis Turtle'):
    s=state();card=next(c for c in s['hand']+s['stack'] if c['name']==name)
    if card['zone']=='Hand':
        check('Original card is legally offered '+name,card['forgeId'] in s['legalCasts'])
        native.card(card['forgeId'])
    s=state();check('Original card callback casts '+name,any(c['forgeId']==card['forgeId'] for c in s['stack']))
    press_primary()
    s=state();check('Original Resolve callback puts '+name+' on battlefield',any(c['forgeId']==card['forgeId'] for c in s['battlefield']) and not s['stack'])
    check('No fidelity gap after '+name,not s['fidelityGap'])
    if name in ('Fusion Elemental','Aegis Turtle'):capture('resolved-'+name.replace(' ','-'))
s=state();check('All five colors were paid through actual native casts',{c['name'] for c in s['battlefield'] if c['tapped']}>={'Plains','Island','Swamp','Mountain','Forest'})
shutil.copy2(lab/'forge-ipc/native-wire.jsonl',out/'native-wire.jsonl')
shutil.copy2(lab/'forge-ipc/state.json',out/'final-state.json')
(out/'report.json').write_text(json.dumps(dict(checks=len(checks),passed=checks,scope='Original native callbacks and rendered five-color slice; physical mouse focus was blocked by foreground ownership and is not claimed.'),indent=2))
print(json.dumps(dict(checks=len(checks),evidence=str(out)),indent=2))
