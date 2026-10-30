"""Assert real mixed permanent/stack targeting, resolution and cancel behavior."""
import argparse
import json
from pathlib import Path
from engine_test_client import Engine


def run(case, factory=Engine):
    e=factory('card-family', fixtureHand=['Sink into Stupor'],fixtureLands=['Island']*3,
              fixtureBattlefield=['Grizzly Bears'],fixtureOpponentBattlefield=['Field Creeper','Forest'],
              fixtureOpponentSpell='Divination',fixtureOpponentLands=['Island']*3)
    try:
        spell=e.state['hand'][0]['forgeId']
        stack=next(c['forgeId'] for c in e.state['stack'] if c['name']=='Divination')
        permanent=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Field Creeper')
        initial_order=e.state['stackOrder'][:]
        request=e.begin('cast_spell',spell)
        progress=e.wait_json(e.ipc/'decision.json');e.state=progress['state'];decision=e.state['decision']
        ids={o['forgeId'] for o in decision['options']};fields=dict(decisionToken=decision['token'])
        e.check('Only opposing spell and nonland permanent are offered together',ids=={stack,permanent})
        e.check('Target identities retain distinct kinds',{o['targetKind'] for o in decision['options']}=={'card','spell'})
        e.check('Casting announcement has not paid mana or changed resolvable stack',e.state['stackOrder']==initial_order and all(not c['tapped'] for c in e.state['battlefield'] if c['owner']==1 and c['name']=='Island'))
        if case=='cancel':
            e.check('Cast cancellation accepted',e.send('cancel_targets',**fields)['accepted'])
            e.finish(request)
            e.check('Cancel restores spell, mana and existing stack',spell in e.state['legalCasts'] and e.state['stackOrder']==initial_order and all(not c['tapped'] for c in e.state['battlefield'] if c['owner']==1 and c['name']=='Island'))
        else:
            own=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears')
            e.check('Own permanent rejected',not e.send('select_targets',assignments=[dict(forgeId=own)],**fields)['accepted'])
            e.check('Foreign target rejected',not e.send('select_targets',assignments=[dict(forgeId=-99999)],**fields)['accepted'])
            e.check('Empty submission rejected',not e.send('submit_targets',**fields)['accepted'])
            target=stack if case=='spell' else permanent
            e.check('Explicit target accepted',e.send('select_targets',assignments=[dict(forgeId=target)],**fields)['accepted'])
            e.check('Selection submitted',e.send('submit_targets',**fields)['accepted']);e.finish(request)
            e.check('Real spell target retained on stack',next(c for c in e.state['stack'] if c['forgeId']==spell)['targetForgeIds']==[target])
            e.check('Exactly three mana paid',sum(c['tapped'] for c in e.state['battlefield'] if c['owner']==1 and c['name']=='Island')==3)
            _,pending=e.pass_or_decision();e.check('Bounce resolves without optional confirmation',pending is None)
            e.check('Target moved to opponent hand',any(c['forgeId']==target and c['owner']==2 and c['zone']=='Hand' for c in e.state['hidden']))
            e.check('Other candidate remains in its zone',any(c['forgeId']==permanent for c in e.state['battlefield']) if case=='spell' else any(c['forgeId']==stack for c in e.state['stack']))
            e.check('Bounce spell reaches graveyard',any(c['forgeId']==spell for c in e.state['graveyard']))
        e.check('No rules gap',not e.state['fidelityGap'])
        return dict(case=case,passed=True,checks=len(e.checks),evidence=str(e.ipc))
    finally:e.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    for name in ('native-worker','managed','fixture'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();factory=Engine
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native worker arguments')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    result=dict(passed=True,nativeHandlers=bool(a.native_worker),cases=[run(case,factory) for case in ('spell','permanent','cancel')])
    a.output.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
