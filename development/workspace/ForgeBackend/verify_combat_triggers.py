"""Actual tap and combat-damage triggers with no optional confirmation."""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

SETTINGS=dict(fixtureHand=['Forest'],fixtureLands=['Forest','Mountain'],fixtureBattlefield=['Magda, Brazen Outlaw','Toski, Bearer of Secrets','Grizzly Bears'],fixtureBattlefieldReady=True,fixtureOpponentBattlefield=[],fixtureLibrary=['Forest']*12)

def run(factory=Engine):
    e=factory('card-family',**SETTINGS);trace=[]
    try:
        drawn=[c['forgeId'] for c in e.state['hidden'] if c['zone']=='Library' and c['owner']==1][:3]
        land=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Forest')
        execute(e,trace,'play_land',land)
        for _ in range(30):
            execute(e,trace,'pass_priority')
            if set(drawn).issubset({c['forgeId'] for c in e.state['hand']}) and not e.state['stackOrder']:break
            if e.state['activeSeat']!=1:raise AssertionError('Combat did not finish the three draw triggers during its own turn')
        e.check('Three unblocked attackers deal exactly five damage',e.state['opponentLife']==15)
        treasures=[c for c in e.state['battlefield'] if c.get('token') and 'Treasure' in c['currentSubtypes']]
        e.check('Tapping Magda creates exactly one Treasure',len(treasures)==1 and treasures[0]['controller']==1)
        e.check('Three creature hits draw the actual next three library cards',set(drawn)=={c['forgeId'] for c in e.state['hand']})
        e.check('Only attacker selection requires a controller decision',{r['kind'] for r in trace if 'op' in r}=={'attackers'})
        e.check('No order, confirm or choose prompt for mandatory triggers',not any(r['kind'] in ('choice','order_cards') for r in trace))
        e.check('Mandatory trigger sequence fully resolves without a gap',not e.state['stackOrder'] and not e.state.get('decision') and not e.state['fidelityGap'])
        return dict(passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:
        message=error.args[0] if isinstance(error,AssertionError) and error.args else error
        if isinstance(message,tuple):message=message[0]
        return dict(passed=False,error=str(message)[:1500],evidence=str(e.ipc),trace=trace)
    finally:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    for key in ('native-worker','managed','fixture'):p.add_argument('--'+key,type=Path)
    a=p.parse_args();factory=Engine
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native paths')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    r=run(factory);r['nativeHandlers']=bool(a.native_worker);a.output.write_text(json.dumps(r,indent=2));print(json.dumps({k:v for k,v in r.items() if k!='trace'}));raise SystemExit(0 if r['passed'] else 1)
