"""A real instant can resolve after first-strike damage and before regular damage."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

def run(a):
    e=None;trace=[]
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,
            randomSeed=7274,fixtureHand=['Giant Growth','Forest'],fixtureLands=['Forest'],
            fixtureBattlefield=['Fencing Ace'],fixtureOpponentBattlefield=['Yoked Ox'],
            fixtureBattlefieldReady=True,fixtureOpponentPolicy='block-all',fixtureLibrary=['Forest']*20)
        actor=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Fencing Ace')
        ox=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Yoked Ox')
        growth=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Giant Growth')
        execute(e,trace,'play_land',e.state['legalLands'][0])
        for _ in range(30):
            hits=[v for v in e.state['events'] if v['kind']=='damage' and v.get('sourceForgeId')==actor]
            if hits:break
            execute(e,trace,'pass_priority',_attack_seat=2)
        else:raise AssertionError('First strike did not occur')
        e.check('First strike deals only the original unpumped one damage',len(hits)==1 and hits[0]['phase']=='COMBAT_FIRST_STRIKE_DAMAGE' and hits[0]['amount']==1 and hits[0]['targetForgeId']==ox)
        e.check('The actual post-first-strike priority offers the real instant',e.state['phase']=='COMBAT_FIRST_STRIKE_DAMAGE' and growth in e.state['legalCasts'] and not e.state['stackOrder'])
        before=e.state
        def target(d,s):return [v for v in d['options'] if v['forgeId']==actor]
        execute(e,trace,'cast_spell',growth,_target_policy=target)
        for _ in range(20):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',_target_policy=target)
        e.check('Giant Growth resolves during the same first-strike response window',e.state['phase']=='COMBAT_FIRST_STRIKE_DAMAGE' and any(c['forgeId']==actor and c['power']==4 for c in e.state['battlefield']))
        for _ in range(20):
            if e.state['phase']=='MAIN2':break
            execute(e,trace,'pass_priority')
        hits=[v for v in e.state['events'] if v['kind']=='damage' and v.get('sourceForgeId')==actor]
        e.check('Regular damage uses the actual post-response power',[(v['phase'],v['amount'],v['targetForgeId']) for v in hits]==[('COMBAT_FIRST_STRIKE_DAMAGE',1,ox),('COMBAT_DAMAGE',4,ox)])
        e.check('The original blocker dies and the attacker survives without spill damage',any(c['forgeId']==ox for c in e.state['graveyard']) and any(c['forgeId']==actor for c in e.state['battlefield']) and e.state['opponentLife']==20)
        e.check('No unresolved decision or unsupported effect remains',not e.state.get('decision') and not e.state['fidelityGap'])
        result=dict(passed=True,checks=e.checks,evidence=str(e.ipc),firstResponseState=before,finalState=e.state)
    except Exception as error:
        result=dict(passed=False,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
    a.output.write_text(json.dumps(result,indent=2));a.output.with_name(a.output.stem+'-trace.json').write_text(json.dumps(trace,indent=2))
    print(json.dumps({k:result.get(k) for k in ('passed','error','evidence')}));return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('worker','managed','fixture','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();assert not a.output.exists();raise SystemExit(0 if run(a) else 1)
