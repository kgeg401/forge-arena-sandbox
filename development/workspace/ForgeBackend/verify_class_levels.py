"""Wizard Class's real levels, triggered draws/counters and zone-change reset."""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

def run(factory=Engine):
    e=factory('card-family',fixtureHand=['Wizard Class','Divination','Otawara, Soaring City','Opt'],fixtureLands=['Island']*18,fixtureBattlefield=['Grizzly Bears'],fixtureLibrary=['Forest']*12);trace=[]
    try:
        ids={c['name']:c['forgeId'] for c in e.state['hand']};source=ids['Wizard Class'];bear=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears')
        library=[c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library']
        def resolve(op,card,**fields):
            def targets(spec,state):
                wanted=source if card==ids['Otawara, Soaring City'] else bear
                return [next(v for v in spec['options'] if v['forgeId']==wanted)]
            execute(e,trace,op,card,_target_policy=targets,**fields)
            for _ in range(12):
                if not e.state['stackOrder']:break
                execute(e,trace,'pass_priority',_target_policy=targets)
            else:raise AssertionError('Class sequence failed to resolve within bound')
            e.check('Class action leaves no hidden choice or gap',not e.state.get('decision') and not e.state['fidelityGap'])
        def current():return next(c for c in e.state['battlefield'] if c['forgeId']==source)
        resolve('cast_spell',source)
        e.check('Class enters at level one',current()['classLevel']==1)
        for level in (2,3):
            offers=[v for v in e.state['legalActivations'] if v['forgeId']==source]
            e.check('Only the next legal Class upgrade is offered',len(offers)==1 and offers[0]['api']=='ClassLevelUp')
            resolve('activate_ability',source,abilityId=offers[0]['abilityId'])
            e.check('Paid Class upgrade reaches level '+str(level),current()['classLevel']==level)
            e.check('Level two draws exactly two cards, level three adds no immediate draw',set(library[:2])=={c['forgeId'] for c in e.state['hand'] if c['name']=='Forest'})
        resolve('cast_spell',ids['Divination'])
        e.check('Divination draws the next two real library cards',set(library[:4])=={c['forgeId'] for c in e.state['hand'] if c['name']=='Forest'})
        target=next(c for c in e.state['battlefield'] if c['forgeId']==bear)
        e.check('Two separate draw triggers actually grow the selected creature to four four',target['power']==4 and target['toughness']==4)
        e.check('Real target choices remain, automatic ordering adds no confirmation',len([r for r in trace if r.get('op')=='pass_priority' and r['kind']=='targets'])==2 and not any(r.get('type') in ('confirm','abilities-order') for r in trace))
        channel=next(v for v in e.state['legalActivations'] if v['forgeId']==ids['Otawara, Soaring City'])
        resolve('activate_ability',ids['Otawara, Soaring City'],abilityId=channel['abilityId'])
        e.check('Channel pays by discarding its actual source',any(c['forgeId']==ids['Otawara, Soaring City'] for c in e.state['graveyard']))
        e.check('Returning Class to hand resets the source level',next(c for c in e.state['hand'] if c['forgeId']==source)['classLevel']==1)
        resolve('cast_spell',source)
        e.check('Recast Class starts at one again',current()['classLevel']==1)
        resolve('cast_spell',ids['Opt'])
        e.check('Recast level one no longer creates level three draw triggers',next(c for c in e.state['battlefield'] if c['forgeId']==bear)['power']==4)
        return dict(passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:
        msg=error.args[0] if isinstance(error,AssertionError) and error.args else error
        if isinstance(msg,tuple):msg=msg[0]
        return dict(passed=False,error=type(error).__name__+': '+str(msg)[:1600],evidence=str(e.ipc),trace=trace)
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
