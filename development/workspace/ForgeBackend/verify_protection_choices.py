"""Protection selections, actual blocking restrictions, and cleanup lifetime."""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

CASES=[('Giver of Runes','colorless'),('Giver of Runes','red'),('Pippin, Guard of the Citadel','Artifact'),('Pippin, Guard of the Citadel','Creature'),('Pippin, Guard of the Citadel','Instant'),('Pippin, Guard of the Citadel','Kindred')]
def run(name,quality,factory=Engine):
    trace=[];e=factory('card-family',fixtureHand=[],fixtureLands=['Plains','Island'],fixtureBattlefield=[name,'Grizzly Bears'],fixtureBattlefieldReady=True,fixtureOpponentBattlefield=['Field Creeper'],fixtureOpponentPolicy='block-all',fixtureLibrary=['Forest']*8)
    try:
        source=next(c['forgeId'] for c in e.state['battlefield'] if c['name']==name)
        target=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears')
        is_color=name=='Giver of Runes';expected='Protection from '+quality if is_color else 'Protection:'+quality
        def targets(spec,state):
            e.check('Protection cannot target its own source',source not in {v['forgeId'] for v in spec['options']})
            return [next(v for v in spec['options'] if v['forgeId']==target)]
        def choices(spec,state):
            e.check('Original chooser uses the correct protection family',spec['type']==('colors' if is_color else 'type'))
            return [dict(choiceId=next(v['choiceId'] for v in spec['options'] if (v.get('color') if is_color else v['label']).lower()==quality.lower()))]
        offer=next(v for v in e.state['legalActivations'] if v['forgeId']==source)
        execute(e,trace,'activate_ability',source,abilityId=offer['abilityId'],_target_policy=targets,_choice_policy=choices)
        for _ in range(6):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',_choice_policy=choices)
        bear=next(c for c in e.state['battlefield'] if c['forgeId']==target)
        e.check('Forge grants the exact chosen quality',expected in bear['rulesKeywords'])
        e.check('Protection presentation retains its original source',any(g['keyword']==expected and g['sourceForgeId']==source for g in bear['keywordGrants']))
        e.check('Ability really taps the source',next(c for c in e.state['battlefield'] if c['forgeId']==source)['tapped'])
        combat=quality in ('colorless','Artifact','Creature')
        def attack(spec,state):return [dict(forgeId=target,targetSeat=2)] if combat else []
        for _ in range(25):
            execute(e,trace,'pass_priority',_attack_policy=attack)
            if e.state['activeSeat']==2 and e.state['phase']=='MAIN1':break
        e.check('Protected creature survives the sequence',any(c['forgeId']==target for c in e.state['battlefield']))
        e.check('Colorless artifact creature cannot block relevant protection',e.state['opponentLife']==(18 if combat else 20))
        bear=next(c for c in e.state['battlefield'] if c['forgeId']==target)
        e.check('Until-end-of-turn protection expires through real cleanup',e.state['activeSeat']==2 and expected not in bear['rulesKeywords'] and not bear['keywordGrants'])
        e.check('No pending choice or native gap remains',not e.state.get('decision') and not e.state['fidelityGap'])
        return dict(card=name,quality=quality,passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:
        msg=error.args[0] if isinstance(error,AssertionError) and error.args else error
        if isinstance(msg,tuple):msg=msg[0]
        return dict(card=name,quality=quality,passed=False,error=str(msg)[:1500],evidence=str(e.ipc),trace=trace)
    finally:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    for key in ('native-worker','managed','fixture'):p.add_argument('--'+key,type=Path)
    a=p.parse_args();factory=Engine
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native paths')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    rows=[]
    for name,quality in CASES:
        r=run(name,quality,factory);rows.append(r);print(json.dumps({k:v for k,v in r.items() if k!='trace'}),flush=True)
        a.output.write_text(json.dumps(dict(passed=all(v['passed'] for v in rows),nativeHandlers=bool(a.native_worker),cases=rows),indent=2))
    raise SystemExit(0 if all(v['passed'] for v in rows) else 1)
