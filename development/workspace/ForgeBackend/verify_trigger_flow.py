"""Check automatic trigger ordering and the preserved manual override in Forge.

Only initial state and player inputs are seeded. Life gains and stack identities
must come from the engine. These checks do not establish rendered UI parity.
"""
import argparse
import json
from pathlib import Path
from engine_test_client import Engine


def run(mode,factory=Engine):
    e=factory('card-family',fixtureHand=['Savannah Lions'],fixtureLands=['Plains'],
             fixtureBattlefield=['Impassioned Orator','Impassioned Orator'],
             autoOrderTriggers=mode!='manual')
    try:
        if mode=='toggle':
            # The same field is forwarded from the native gameplay preference.
            r=e.send('snapshot',autoOrderTriggers=False)
            e.check('Ordering preference can change within a game',r['accepted'])
            r=e.send('snapshot',autoOrderTriggers='false')
            e.check('String preference is rejected without coercion',not r['accepted'])
        lion=e.state['hand'][0]
        e.check('Creature cast accepted',e.send('cast_spell',lion['forgeId'])['accepted'])
        r,pending=e.pass_or_decision()
        if mode=='auto':
            e.check('Mandatory triggers reach the stack without a choice',pending is None)
        else:
            e.check('Disabled automatic ordering retains a player decision',pending is not None)
            choice=e.state['decision'];spec=choice['choice']
            e.check('Both distinct effect sources are available',len(spec['options'])==2 and len({o['effectSourceForgeId'] for o in spec['options']})==2)
            chosen=spec['options'][1]
            e.check('Manual reverse order accepted',e.send('submit_choice',decisionToken=choice['token'],assignments=[dict(choiceId=chosen['choiceId'])])['accepted'])
            e.finish(pending['parentRequestId'])
            top=e.state['stackOrder'][0]
            e.check('Chosen source really resolves first',next(a for a in e.state['stackAbilities'] if a['forgeId']==top)['sourceForgeId']==chosen['effectSourceForgeId'])
        order=e.state['stackOrder'][:]
        e.check('Two separate triggers wait for priority',len(order)==2 and len(set(order))==2 and e.state['life']==20)
        for i,identity in enumerate(order):
            _,d=e.pass_or_decision()
            e.check('Resolve exactly one trigger without confirmation '+str(i),d is None and e.state['life']==21+i and e.state['stackOrder']==order[i+1:])
            e.check('Life event belongs to the actual resolving trigger '+str(i),e.state['events'][-1]['sourceStackForgeId']==identity)
        e.check('No rules gap or engine exit',not e.state['fidelityGap'] and e.process.poll() is None)
        return dict(mode=mode,passed=True,checks=len(e.checks),evidence=str(e.ipc))
    finally:e.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    for name in ('native-worker','managed','fixture'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();factory=Engine
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all three native worker arguments')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    rows=[run(mode,factory) for mode in (('auto','manual') if a.native_worker else ('auto','manual','toggle'))]
    result=dict(passed=True,nativeHandlers=bool(a.native_worker),cases=rows,scope=__doc__)
    a.output.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
