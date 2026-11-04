"""A printed-zero human cost must still pay Forge's actual tax."""
import argparse,json
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

p=argparse.ArgumentParser(description=__doc__)
for name in ('worker','managed','fixture','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);results=[]
for taxed,lands in [(False,[]),(True,[]),(True,['Plains'])]:
    e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,fixtureHand=['Lotus Petal'],fixtureLands=lands,fixtureOpponentBattlefield=['Thalia, Guardian of Thraben'] if taxed else [],fixtureOpponentPolicy='passive')
    try:
        petal=e.state['hand'][0]['forgeId'];offered=petal in e.state['legalCasts'];expected=not taxed or bool(lands)
        assert offered==expected,(taxed,lands,offered)
        if expected:
            execute(e,[],'cast_spell',petal);execute(e,[],'pass_priority')
            assert any(c['forgeId']==petal for c in e.state['battlefield'])
            assert sum(c['name']=='Plains' and c['tapped'] for c in e.state['battlefield'])==int(taxed)
        else:
            assert not e.send('cast_spell',petal)['accepted']
        assert not e.state['fidelityGap']
        results.append(dict(taxed=taxed,lands=lands,passed=True,evidence=str(e.ipc)))
    finally:e.close()
(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=results,scope=__doc__),indent=2));print(json.dumps(dict(passed=True,cases=len(results))))
