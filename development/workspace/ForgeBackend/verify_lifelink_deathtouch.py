"""Native multi-block combat, simultaneous lifelink/deaths and a subsequent drain trigger."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

def run(a,drain):
    e=None;trace=[];allocations=[];key='death-trigger' if drain else 'lifelink-only'
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,
            randomSeed=7274,fixtureHand=['Forest'],fixtureLands=[],
            fixtureBattlefield=['Vampire Nighthawk']+(['Cruel Celebrant'] if drain else []),
            fixtureOpponentBattlefield=['Giant Spider','Mammoth Spider'],fixtureBattlefieldReady=True,
            fixtureOpponentPolicy='block-all',fixtureLibrary=['Forest']*20)
        source=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Vampire Nighthawk')
        victims={c['forgeId'] for c in e.state['battlefield'] if c['owner']==2}
        attack={c['forgeId']:2 if c['forgeId']==source else 0 for c in e.state['battlefield'] if c['owner']==1}
        def damage(d,s):
            allocations.append(d)
            return [dict(forgeId=v['forgeId'],amount=v['assignedDamage']) for v in d['options']]
        for _ in range(50):
            if e.state['phase']=='MAIN2' and not e.state['stackOrder']:break
            if e.state['legalLands']:execute(e,trace,'play_land',e.state['legalLands'][0],_attack_seat=attack,_damage_policy=damage)
            else:execute(e,trace,'pass_priority',_attack_seat=attack,_damage_policy=damage)
        else:raise AssertionError('Actual combat/death-trigger stack did not settle')
        e.check('Real deathtouch allocation assigns one lethal damage to each reach blocker',len(allocations)==1 and {v['forgeId'] for v in allocations[0]['options']}==victims and all(v['lethalDamage']==v['assignedDamage']==1 for v in allocations[0]['options']))
        e.check('All three actual combatants die from simultaneous combat damage',{source,*victims}<={c['forgeId'] for c in e.state['graveyard']})
        e.check('Lifelink gains damage dealt despite its source dying',e.state['life']==(23 if drain else 22))
        e.check('The later death trigger drains only the opposing player',e.state['opponentLife']==(19 if drain else 20))
        hits=[v for v in e.state['events'] if v['kind']=='damage' and v.get('sourceForgeId')==source]
        e.check('Actual damage is exactly one to each blocker, not its remaining toughness',len(hits)==2 and {v['targetForgeId'] for v in hits}==victims and all(v['amount']==1 and v['combat'] for v in hits))
        updates=[json.loads(v)['value'] for v in (e.native_folder/'native-model.jsonl').read_text().splitlines() if json.loads(v)['kind']=='native-update']
        native=[v for u in updates for v in u['damageEvents'] if v['source']==1000+source]
        e.check('Original parser receives both exact combat impact events',len(native)==2 and {v['target'] for v in native}=={1000+i for i in victims} and all(v['amount']==1 and v['type']=='Combat' for v in native))
        e.check('Combat and mandatory death trigger add no generic confirm/order choices',not any(v.get('kind') in ('choice','order_cards') for v in trace))
        e.check('No unsupported callback or unresolved decision remains',not e.state['fidelityGap'] and not e.state.get('decision'))
        result=dict(passed=True,case=key,checks=e.checks,evidence=str(e.ipc),finalState=e.state,allocations=allocations)
    except Exception as error:
        result=dict(passed=False,case=key,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
    (a.output/(key+'.json')).write_text(json.dumps(result,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2))
    print(json.dumps({k:result.get(k) for k in ('case','passed','error','evidence')}),flush=True);return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('worker','managed','fixture','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    results=[run(a,drain) for drain in (False,True)];raise SystemExit(0 if all(results) else 1)
