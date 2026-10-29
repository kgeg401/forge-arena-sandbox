"""Jace Cunning Castaway +1: created effect, combat trigger, loot and expiry."""
from pathlib import Path
import argparse,os,json,time
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[];seen=[]
try:
    e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,
        fixtureHand=['Island'],fixtureLands=[],
        fixtureBattlefield=['Jace, Cunning Castaway','Savannah Lions','Grizzly Bears'],
        fixtureBattlefieldReady=True,
        fixtureCounters=[dict(seat=1,cardName='Jace, Cunning Castaway',occurrence=0,type='LOYALTY',count=3)],
        fixtureLibrary=['Plains']*30)
    jace=next(c for c in e.state['battlefield'] if c['name']=='Jace, Cunning Castaway')
    ability=next(v for v in e.state['legalActivations'] if v['forgeId']==jace['forgeId'] and v['api']=='Effect')
    execute(e,trace,'activate_ability',jace['forgeId'],abilityId=ability['abilityId'])
    deadline=time.monotonic()+120;start_turn=e.state['turn'];trigger_ids=set();loot_hand=None
    for _ in range(350):
        assert time.monotonic()<deadline,'Sequence deadline'
        assert not e.state['fidelityGap'],e.state['fidelityGap']
        for v in e.state['stackAbilities']:
            if v['abilityId']==116810:
                assert v['sourceForgeId']==jace['forgeId'] and v['name']==jace['name'],v
                trigger_ids.add(v['forgeId']);seen.append(dict(turn=e.state['turn'],phase=e.state['phase'],ability=v))
        if trigger_ids and not e.state['stackAbilities'] and loot_hand is None:
            loot_hand=dict(hand=len(e.state['hand']),grave=[c['name'] for c in e.state['graveyard'] if c['owner']==1])
            assert loot_hand['hand']==1 and loot_hand['grave'],'Loot must draw one and discard one'
        if e.state['turn']>=start_turn+2 and e.state['phase']=='MAIN2':break
        execute(e,trace,'pass_priority')
    else:raise AssertionError('No second combat reached')
    assert len(trigger_ids)==1 and loot_hand is not None,(trigger_ids,loot_hand)
    assert e.state['opponentLife']==12,e.state['opponentLife']
    report=dict(passed=True,triggerId=116810,sourceForgeId=jace['forgeId'],triggerCount=len(trigger_ids),
        loot=loot_hand,opponentLife=e.state['opponentLife'],expiredNextTurn=True,evidence=str(e.ipc),seen=seen)
    (a.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
finally:
    if e:
        (a.output/'trace.json').write_text(json.dumps(trace,indent=2),encoding='utf8');e.close()
