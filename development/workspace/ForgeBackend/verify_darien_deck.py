"""Bounded Darien paper-card casts and named interaction regressions.

Only initial environments are supplied; original native handlers pay costs and
Forge resolves effects. Cast checks and interaction checks are reported separately.
"""
import argparse,json,time,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

def choices(c,s):
    if c['type']=='confirm':return [dict(accept=True)]
    if c['type']=='number' and c.get('prompt','').startswith('Choose X '):return [dict(number=min(5,c['max']))]
    return None

def settle(e,trace):
    for _ in range(40):
        if not e.state['stackOrder']:return
        execute(e,trace,'pass_priority',_choice_policy=choices)
    raise AssertionError('Stack did not settle within bound')

def run(name,a):
    e=None;trace=[]
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,
            fixtureHand=[name],fixtureLands=['Plains']*16,fixtureBattlefield=['Savannah Lions','Sol Ring'],
            fixtureOpponentBattlefield=['Field Creeper','Forest'],fixtureGraveyard=['Savannah Lions','Plains'],
            fixtureLibrary=['Plains']*14,fixtureBattlefieldReady=True)
        s=e.state;card=next(c for c in s['hand'] if c['name']==name);id=card['forgeId']
        if id in s['legalLands']:execute(e,trace,'play_land',id,_choice_policy=choices)
        else:
            e.check('Source card is legally castable in the declared environment',id in s['legalCasts'])
            execute(e,trace,'cast_spell',id,_choice_policy=choices)
        settle(e,trace)
        e.check('Original spell/land reaches a real resolved zone',any(c['forgeId']==id for z in ('battlefield','graveyard','exile') for c in e.state[z]))
        e.check('No unresolved decision or reported fidelity gap',not e.state.get('decision') and not e.state['fidelityGap'])
        return dict(card=name,passed=True,kind='cast-or-land',checks=e.checks,trace=trace,evidence=str(e.ipc))
    except Exception as error:return dict(card=name,passed=False,error=repr(error),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None,trace=trace)
    finally:
        if e:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('worker','managed','fixture','cards','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--offset',type=int,default=0);p.add_argument('--stride',type=int,default=1)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);names=json.loads(a.cards.read_text());rows=[]
    for i,n in enumerate(names[a.offset::a.stride]):
        r=run(n,a);(a.out/(str(i)+'.json')).write_text(json.dumps(r,indent=2));rows.append(r);print(json.dumps({k:r.get(k) for k in ('card','passed','error')}),flush=True)
    (a.out/'report.json').write_text(json.dumps(rows,indent=2));raise SystemExit(0 if all(r['passed'] for r in rows) else 1)
