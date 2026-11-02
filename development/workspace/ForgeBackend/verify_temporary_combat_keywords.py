"""Original native temporary grants survive combat and expire at actual cleanup."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute
from runtime_paths import ROOT

def run(a):
    e=None;trace=[]
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,
            fixtureHand=['Heroic Intervention'],fixtureLands=['Forest']*2,fixtureBattlefield=['Vampire Nighthawk'],
            fixtureOpponentBattlefield=['Giant Spider','Mammoth Spider'],fixtureOpponentPolicy='block-all',fixtureBattlefieldReady=True,fixtureLibrary=['Forest']*20)
        actor=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Vampire Nighthawk');victims={c['forgeId'] for c in e.state['battlefield'] if c['owner']==2}
        metadata=json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text(encoding='utf-8-sig'))
        expected={metadata['keywordAbilityIds'][name] for name in ('hexproof','indestructible')}
        def native():return [json.loads(v)['value'] for v in (e.native_folder/'native-model.jsonl').read_text().splitlines() if json.loads(v)['kind']=='native-update'][-1]
        def grants():return {v['abilityId'] for c in native()['cards'] if c['id']==1000+actor for v in c['keywordGrants']}
        spell=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Heroic Intervention');execute(e,trace,'cast_spell',spell)
        for _ in range(20):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Real protection spell did not resolve')
        e.check('Real spell grants both actual temporary keywords',{'Hexproof','Indestructible'}<=set(next(c for c in e.state['battlefield'] if c['forgeId']==actor)['rulesKeywords']))
        e.check('Original native model has both exact added abilities',expected<=grants())
        protected=e.state;attack={actor:2}
        for _ in range(50):
            if e.state['phase']=='MAIN2' and not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',_attack_seat=attack)
        else:raise AssertionError('Actual protected combat did not reach second main')
        survivor=next(c for c in e.state['battlefield'] if c['forgeId']==actor)
        e.check('Indestructible creature survives five marked damage while both blockers die',survivor['damage']==5 and victims<={c['forgeId'] for c in e.state['graveyard']})
        e.check('Actual lifelink and opponent life follow real combat',e.state['life']==22 and e.state['opponentLife']==20)
        e.check('Original native grants remain throughout the marked-damage step',expected<=grants() and next(c['damage'] for c in native()['cards'] if c['id']==1000+actor)==5)
        combat=e.state
        for _ in range(80):
            if e.state['turn']>=3 and e.state['activeSeat']==1 and e.state['phase']=='MAIN1':break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Actual turn cleanup did not complete')
        returned=next(c for c in e.state['battlefield'] if c['forgeId']==actor)
        e.check('Real cleanup expires temporary keywords and clears marked damage',not {'Hexproof','Indestructible'}&set(returned['rulesKeywords']) and returned['damage']==0)
        e.check('Native ability adders expire without losing printed keywords',not expected&grants() and {'Flying','Lifelink','Deathtouch'}<=set(returned['rulesKeywords']))
        e.check('No unresolved callback, generic choice, or fidelity gap remains',not e.state.get('decision') and not e.state['fidelityGap'] and not any(v.get('kind') in ('choice','order_cards') for v in trace))
        result=dict(passed=True,checks=e.checks,protectedState=protected,combatState=combat,finalState=e.state,evidence=str(e.ipc))
    except Exception as error:result=dict(passed=False,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
    (a.output/'report.json').write_text(json.dumps(result,indent=2));(a.output/'trace.json').write_text(json.dumps(trace,indent=2));print(json.dumps({k:result.get(k) for k in ('passed','error','checks','evidence')}));return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('worker','managed','fixture','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);raise SystemExit(0 if run(a) else 1)
