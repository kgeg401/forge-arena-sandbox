"""Resolve-my acceleration must stop at an opponent-controlled stack object."""
import argparse,json,time
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

p=argparse.ArgumentParser(description=__doc__)
for name in ('worker','managed','fixture','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,fixtureHand=[],fixtureLands=[],fixtureBattlefield=['Soul Warden']*4,fixtureOpponentBattlefield=['Impassioned Orator']*4+['Parallel Lives','Doubling Season'],fixtureOpponentSpell='Army of the Damned',fixtureOpponentLands=['Swamp']*8,autoOrderTriggers=True,autoChooseReplacementEffects=True,randomSeed=7117)
try:
    execute(e,[],'pass_priority');assert len(e.state['stackOrder'])==416,len(e.state['stackOrder'])
    reply=e.native_call('fast_stack_start',policy='own');assert reply['accepted']
    end=time.monotonic()+90;seen=False;boundary=None
    while time.monotonic()<end:
        status=e.native_wait(e.native_folder/'status.json');e.native_status=status;e.state=status['state']
        seen|=status['loop']['fastResolving']
        top=next((x for x in e.state['stackAbilities'] if e.state['stackOrder'] and x['forgeId']==e.state['stackOrder'][0]),None)
        if seen and not status['loop']['fastResolving'] and top and top['controller']==2:
            boundary=status;break
        assert not e.state['fidelityGap'] and not e.state.get('decision')
        time.sleep(.025)
    assert boundary is not None and not e.state.get('actionOffersDeferred')
    assert e.state['life']==228 and len(e.state['stackOrder'])>0
    result=dict(passed=True,localTriggersResolved=208,opponentTriggersRemaining=len(e.state['stackOrder']),localLife=e.state['life'],evidence=str(e.ipc),scope=__doc__+' Seeded, original native handlers and Forge; no multiplayer/network proof.')
finally:e.close()
(a.output/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
