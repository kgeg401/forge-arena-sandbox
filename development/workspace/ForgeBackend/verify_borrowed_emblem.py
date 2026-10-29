"""A borrowed planeswalker ability retains emblem identity and upkeep rules."""
from pathlib import Path
import argparse,os,json,time
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[]
try:
    e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,
        fixtureHand=['Island'],fixtureLands=[],fixtureBattlefield=['Nicol Bolas, Dragon-God','Chandra, Awakened Inferno'],
        fixtureCounters=[dict(seat=1,cardName=n,occurrence=0,type='LOYALTY',count=4) for n in ['Nicol Bolas, Dragon-God','Chandra, Awakened Inferno']],
        fixtureLibrary=['Plains']*30)
    for name in ['Chandra, Awakened Inferno','Nicol Bolas, Dragon-God']:
        card=next(c for c in e.state['battlefield'] if c['name']==name)
        offer=next(v for v in e.state['legalActivations'] if v['forgeId']==card['forgeId'] and v['abilityId']==133609)
        execute(e,trace,'activate_ability',card['forgeId'],abilityId=offer['abilityId'])
        for _ in range(12):
            if not e.state['stackAbilities']:break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Emblem ability did not resolve')
        assert not e.state['fidelityGap'],e.state['fidelityGap']
    emblems=[c for c in e.state['command'] if c.get('objectKind')=='emblem']
    assert len(emblems)==2 and all(c['presentationKey']=='emblem:Chandra, Awakened Inferno' and c['owner']==2 for c in emblems),emblems
    ids={c['forgeId'] for c in emblems};seen=set();deadline=time.monotonic()+90
    for _ in range(150):
        assert time.monotonic()<deadline,'Upkeep deadline'
        assert not e.state['fidelityGap'],e.state['fidelityGap']
        seen.update(v['sourceForgeId'] for v in e.state['stackAbilities'] if v['sourceForgeId'] in ids)
        if e.state['turn']==2 and e.state['phase']=='UPKEEP' and e.state['opponentLife']==18 and not e.state['stackAbilities']:break
        execute(e,trace,'pass_priority')
    else:raise AssertionError('Emblems did not deal upkeep damage')
    assert seen==ids,(seen,ids)
    assert next(c for c in e.state['battlefield'] if c['name']=='Nicol Bolas, Dragon-God')['loyalty']==6
    report=dict(passed=True,emblemCount=2,identity='emblem:Chandra, Awakened Inferno',opponentLife=18,upkeepSources=sorted(seen),evidence=str(e.ipc))
    (a.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
finally:
    if e:
        (a.output/'trace.json').write_text(json.dumps(trace,indent=2),encoding='utf8');e.close()
