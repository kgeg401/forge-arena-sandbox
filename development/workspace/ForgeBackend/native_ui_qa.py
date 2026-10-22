"""One observed action through the original native UI; never writes engine requests."""
from pathlib import Path
import json,time,sys,uuid
from runtime_paths import ROOT
LAB=ROOT/'native-lab'
OUT=ROOT/'research/native-ui'
OUT.mkdir(parents=True,exist_ok=True)

def read(name):return json.loads((LAB/name).read_text(encoding='utf-8-sig'))
def publish(value):
    path=LAB/'native-action.request.json'
    if path.exists():raise RuntimeError('Unconsumed native action; no overwrite sent')
    value['requestId']=uuid.uuid4().hex
    pending=path.with_suffix('.pending')
    pending.write_text(json.dumps(value));pending.replace(path)
def inspect():
    pending=LAB/'native-action.request.json';limit=time.monotonic()+8
    while pending.exists() and time.monotonic()<limit:time.sleep(.05)
    if pending.exists():raise RuntimeError('Previous native action was not consumed; no overwrite sent')
    p=LAB/'native-action-probe.json';before=p.stat().st_mtime_ns if p.exists() else 0
    publish(dict(op='inspect',primary='--primary' in sys.argv))
    end=time.monotonic()+4
    while (not p.exists() or p.stat().st_mtime_ns==before) and time.monotonic()<end:time.sleep(.05)
    x=read('native-action-probe.json');host=read('native-host-status.json')
    if host.get('gap'):raise RuntimeError(host['gap'])
    if x['nativeState']!=host['nativeState'] or x['applied']!='Applied':raise RuntimeError('Native state not stable; observe again')
    return x

def objects():
    cards={}
    for line in (LAB/'forge-ipc/native-wire.jsonl').read_text().splitlines():
        row=json.loads(line)
        if row['direction']!='incoming':continue
        state=row['message'].get('gameStateMessage',{})
        for card in state.get('gameObjects',[]):cards[card['instanceId']]=card
        for key in state.get('diffDeletedInstanceIds',[]):cards.pop(key,None)
    return cards

x=inspect();op=sys.argv[1] if len(sys.argv)>1 else 'inspect'
summary=dict(workflow=x['workflow'],state=x['nativeState'],orderCardIds=x.get('orderCardIds'),damageAssignments=x.get('damageAssignments'),damageControls=x.get('damageControls'),buttons=x.get('buttons'),uiButtons=x.get('uiButtons'),clickable=[v for v in x['views'] if v['click'] and v['active']])
if op=='inspect':print(json.dumps(summary,indent=2));raise SystemExit(0)
if '--expected-state' in sys.argv and x['nativeState']!=int(sys.argv[sys.argv.index('--expected-state')+1]):
    raise RuntimeError('Native QA observation changed before publication; inspect again')
action=dict(expectedWorkflow=x['workflow'],nativeState=x['nativeState'],primary='--primary' in sys.argv)
if op=='button':
    matches=[b for b in x['buttons'] if b['enabled'] and b['text']==sys.argv[2]]
    if len(matches)!=1:raise RuntimeError('Button is not uniquely observed/enabled: '+sys.argv[2])
    action.update(op='button',text=matches[0]['text'],tag=matches[0]['tag'])
elif op=='ui':
    matches=[b for b in x['uiButtons'] if b['enabled'] and b['key']==sys.argv[2]]
    if len(matches)!=1:raise RuntimeError('UI key is not uniquely observed/enabled')
    action.update(op='ui_button',path=matches[0]['path'])
elif op=='damage-toggle':
    toggle=(x.get('damageControls') or {}).get('autoAssign')
    if x['workflow']!='AssignDamageWorkflow' or not toggle or not toggle['enabled']:raise RuntimeError('Original damage toggle unavailable')
    action.update(op='damage_toggle',expectedValue=toggle['value'])
elif op=='damage-spinner':
    direction=sys.argv[3]
    if direction not in ('increase','decrease'):raise ValueError('Select increase or decrease')
    matches=[v for v in (x.get('damageControls') or {}).get('spinners',[]) if v['instanceId']==int(sys.argv[2]) and v[direction]]
    if x['workflow']!='AssignDamageWorkflow' or len(matches)!=1:raise RuntimeError('Original damage spinner is not uniquely enabled')
    action.update(op='damage_spinner',instanceId=matches[0]['instanceId'],expectedValue=matches[0]['value'],direction=direction)
elif op in ('keep','mulligan','play'):
    keys=('DuelScene/Browsers/StartingPlayer_PlayFirst',) if op=='play' else ('DuelScene/StartingPlayer/KeepPlural','DuelScene/StartingPlayer/KeepSingular') if op=='keep' else ('DuelScene/StartingPlayer/FreeMulligan_ButtonText','DuelScene/StartingPlayer/Mulligan_ButtonText')
    matches=[b for b in x['uiButtons'] if b['enabled'] and b['key'] in keys]
    if len(matches)!=1:raise RuntimeError('Keep button is not uniquely available')
    action.update(op='ui_button',path=matches[0]['path'])
elif op in ('land','commander','click'):
    cards=objects();matches=[]
    for view in x['views']:
        card=cards.get(view['id'],{})
        if not view['click'] or not view['active'] or not view['visible'] or (op!='click' and card.get('ownerSeatId')!=1):continue
        if op=='land' and card.get('grpId')==75556 and card.get('zoneId')==31:matches.append(view)
        if op=='commander' and card.get('grpId')==72175 and card.get('zoneId')==26:matches.append(view)
        if op=='click' and view['id']==int(sys.argv[2]):matches.append(view)
    if not matches or (op!='land' and len(matches)!=1):raise RuntimeError('No unique original legal card interaction: '+op)
    action.update(op='click',instanceId=matches[0]['id'])
else:raise ValueError('Unknown native QA action')
before=read('forge-ipc/state.json')
stamp=str(time.time_ns());(OUT/(stamp+'-before.json')).write_text(json.dumps(dict(observation=summary,forge=before,action=action),indent=2))
publish(action)
deadline=time.monotonic()+8
while (LAB/'native-action.request.json').exists() and time.monotonic()<deadline:time.sleep(.05)
if (LAB/'native-action.request.json').exists():raise RuntimeError('Action was not consumed; no retry sent')

deadline=time.monotonic()+4
while time.monotonic()<deadline:
    result_path=LAB/'native-action-result.json'
    if result_path.exists():
        try:result=json.loads(result_path.read_text(encoding='utf-8-sig'))
        except (json.JSONDecodeError,PermissionError):time.sleep(.05);continue
        if result.get('requestId')==action['requestId']:break
    time.sleep(.05)
else:raise RuntimeError('No matching native action receipt; no retry sent')
if not result['accepted']:
    (OUT/(stamp+'-rejected.json')).write_text(json.dumps(result,indent=2))
    raise RuntimeError('Native QA rejected without invoking UI: '+result['reason'])
time.sleep(.25)
after=read('forge-ipc/state.json');host=read('native-host-status.json')
if host.get('gap'):raise RuntimeError(host['gap'])
(OUT/(stamp+'-after.json')).write_text(json.dumps(dict(receipt=result,forge=after,host=host),indent=2))
print(json.dumps(dict(action=action,evidence=stamp,turn=after['turn'],phase=after['phase'],decision=(after.get('decision') or {}).get('kind'),lands=after['landsPlayed'],life=[after['life'],after['opponentLife']]),indent=2))
