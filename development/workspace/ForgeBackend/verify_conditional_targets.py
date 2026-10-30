"""Validate target relationships as each click changes the native selection."""
import argparse,json
from pathlib import Path
from engine_test_client import Engine

def run(factory):
    e=factory('card-family',fixtureHand=['Run Away Together'],fixtureLands=['Island']*2,fixtureBattlefield=['Grizzly Bears'],fixtureOpponentBattlefield=['Field Creeper','Grizzly Bears'])
    try:
        spell=e.state['hand'][0]['forgeId'];own=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears' and c['controller']==1)
        opponents=[c['forgeId'] for c in e.state['battlefield'] if c['controller']==2];parent=e.begin('cast_spell',spell)
        e.state=e.wait_json(e.ipc/'decision.json')['state'];token=e.state['decision']['token'];fields=dict(decisionToken=token)
        def ids():return {o['forgeId'] for o in e.state['decision']['options']}
        e.check('All three initial creatures are offered',ids()=={own,*opponents})
        e.check('First opponent selected',e.send('select_targets',assignments=[dict(forgeId=opponents[0])],**fields)['accepted'])
        e.check('Only a different controller is highlighted next',ids()=={own,opponents[0]})
        before=e.state['decision']['assignments'][:]
        e.check('Second creature with same controller rejected',not e.send('select_targets',assignments=[dict(forgeId=opponents[1])],**fields)['accepted'])
        e.check('Rejected combination retains the existing selection',e.state['decision']['assignments']==before)
        e.check('Incomplete target set cannot be submitted',not e.send('submit_targets',**fields)['accepted'])
        e.check('Unselect accepted',e.send('select_targets',assignments=[dict(forgeId=opponents[0],selected=False)],**fields)['accepted'])
        e.check('Unselect restores previously ineligible creatures',ids()=={own,*opponents})
        e.check('Own creature can be selected first',e.send('select_targets',assignments=[dict(forgeId=own)],**fields)['accepted'])
        e.check('Opponent remains a valid second target',e.send('select_targets',assignments=[dict(forgeId=opponents[1])],**fields)['accepted'])
        e.check('No mana spent before submission',all(not c['tapped'] for c in e.state['battlefield'] if c['name']=='Island'))
        e.check('Exact pair submits',e.send('submit_targets',**fields)['accepted']);e.finish(parent)
        _,pending=e.pass_or_decision();e.check('Pair resolves',pending is None)
        e.check('Local target returned to hand',any(c['forgeId']==own for c in e.state['hand']))
        e.check('Opponent target returned to hand',any(c['forgeId']==opponents[1] and c['zone']=='Hand' for c in e.state['hidden']))
        e.check('Untargeted creature remained',any(c['forgeId']==opponents[0] for c in e.state['battlefield']))
        e.check('No rules gap',not e.state['fidelityGap'])
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
