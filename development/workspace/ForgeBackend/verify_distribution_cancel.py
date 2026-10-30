"""Cancel a real divided spell after target selection but before payment."""
import argparse,json,time
from pathlib import Path
from engine_test_client import Engine

def run(factory):
    e=factory('card-family',fixtureHand=['Pyrokinesis'],fixtureLands=['Mountain']*6,fixtureOpponentBattlefield=['Grizzly Bears','Field Creeper'])
    try:
        spell=e.state['hand'][0]['forgeId'];original={k:e.state[k] for k in ('life','battlefield','graveyard','exile','manaTotal')}
        parent=e.begin('cast_spell',spell);d=e.wait_json(e.ipc/'decision.json')['state']['decision'];e.state=e.wait_json(e.ipc/'decision.json')['state']
        e.check('Original targeting request appears first',d['kind']=='targets')
        for o in d['options']:
            if o.get('targetKind')=='card' and o['forgeId']!=spell:e.check('Target selected',e.send('select_targets',decisionToken=d['token'],assignments=[dict(forgeId=o['forgeId'])])['accepted'])
        submit=e.begin('submit_targets',decisionToken=d['token']);end=time.monotonic()+8
        while time.monotonic()<end:
            s=e.wait_json(e.ipc/'state.json')
            if (s.get('decision') or {}).get('kind')=='assign_damage':e.state=s;break
            time.sleep(.02)
        else:raise AssertionError('Distribution never appeared')
        d=e.state['decision'];e.check('Allocation is an optional-to-complete cast step',d['policy']=='divided-spell' and d['canCancel'])
        e.check('No resources paid before the distribution is submitted',all(e.state[k]==v for k,v in original.items()))
        r=e.send('cancel_assign_damage',decisionToken=d['token']);e.check('Cancel acknowledged',r['accepted']);e.finish(submit);e.finish(parent)
        e.check('Cast returns to hand and remains playable',spell in e.state['legalCasts'] and any(c['forgeId']==spell for c in e.state['hand']))
        e.check('Cancel preserves mana, life, targets and zones',all(e.state[k]==v for k,v in original.items()))
        e.check('No pending stack or decision',not e.state['stackOrder'] and not e.state.get('decision') and not e.state['fidelityGap'])
        return dict(passed=True,checks=len(e.checks),evidence=str(e.ipc))
    finally:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    for name in ('native-worker','managed','fixture'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();factory=Engine
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native arguments')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    r=run(factory);r['nativeHandlers']=bool(a.native_worker);a.output.write_text(json.dumps(r,indent=2));print(json.dumps(r))
