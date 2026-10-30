"""Real combat windows, ninjutsu payments, arrivals and named damage effects.

Cases test one combat sequence, not every ability or interaction of these cards.
Yuriko's commander case uses a seeded initial command zone, not a full pod.
"""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

CASES=[('Ingenious Infiltrator',2,'draw'),('Mist-Syndicate Naga',3,'copy'),('Moon-Circuit Hacker',2,'draw'),('Ninja of the Deep Hours',2,'draw'),('Prosperous Thief',3,'treasure'),('Silver-Fur Master',2,'plain'),('Skullsnatcher',2,'exile'),('Thousand-Faced Shadow',1,'shadow'),("Yuriko, the Tiger's Shadow",1,'reveal'),('Ninja of the Deep Hours',3,'reduced'),("Yuriko, the Tiger's Shadow",1,'commander')]
def run(name,power,effect,factory=Engine):
    settings=dict(fixtureHand=[] if effect=='commander' else [name],fixtureLands=['Island']*6+['Swamp']*3,fixtureBattlefield=['Grizzly Bears']+(['Field Creeper'] if effect=='shadow' else [])+(['Silver-Fur Master'] if effect=='reduced' else []),fixtureBattlefieldReady=True,fixtureOpponentBattlefield=[],fixtureOpponentGraveyard=['Forest','Grizzly Bears'],fixtureLibrary=['Grizzly Bears']+['Forest']*9)
    if effect=='commander':settings['fixtureCommander']=name
    e=factory('card-family',**settings);trace=[]
    try:
        source=next(c['forgeId'] for c in e.state['command' if effect=='commander' else 'hand'] if c['name']==name)
        bear=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears')
        returned=next(c['forgeId'] for c in e.state['battlefield'] if c['name']==('Field Creeper' if effect=='shadow' else 'Grizzly Bears'))
        first=next(c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library')
        grave={c['forgeId'] for c in e.state['graveyard'] if c['owner']==2}
        def offered():return [v for v in e.state['legalActivations'] if v['forgeId']==source]
        e.check('Ninjutsu is unavailable before combat has unblocked attackers',not offered())
        def attacks(spec,state):return [dict(forgeId=i,targetSeat=2) for i in dict.fromkeys((bear,returned))]
        def choices(spec,state):
            if spec['type']=='confirm':return [dict(accept=True)]
            match=[v for v in spec['options'] if v.get('forgeId')==returned]
            if match:return [dict(choiceId=match[0]['choiceId'])]
            return None
        def targets(spec,state):
            wanted=grave if effect=='exile' else {bear}
            e.check('Original effect offers every intended legal target',wanted.issubset({v['forgeId'] for v in spec['options']}))
            return [v for v in spec['options'] if v['forgeId'] in wanted]
        args=dict(_attack_policy=attacks,_choice_policy=choices,_target_policy=targets)
        for _ in range(20):
            if offered():break
            execute(e,trace,'pass_priority',**args)
        e.check('Ninjutsu becomes available in the actual blocker-step response window',bool(offered()) and e.state['phase']=='COMBAT_DECLARE_BLOCKERS' and e.state['opponentLife']==20)
        e.check('The native activation identity is offered exactly once',len(offered())==1)
        execute(e,trace,'activate_ability',source,abilityId=offered()[0]['abilityId'],**args)
        for _ in range(12):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',**args)
        ninja=next(c for c in e.state['battlefield'] if c['forgeId']==source)
        e.check('Cost returns the actual unblocked attacker to hand',any(c['forgeId']==returned for c in e.state['hand']))
        e.check('Ninja arrives tapped and attacking the original player',ninja['tapped'] and ninja['attackTarget']==2 and ninja['power']==power)
        if effect=='reduced':e.check('Master reduces generic ninjutsu payment to exactly one blue mana',len([c for c in e.state['battlefield'] if c['name']=='Island' and c['tapped']])==1 and not any(c['name']=='Swamp' and c['tapped'] for c in e.state['battlefield']))
        if effect=='commander':e.check('Commander ninjutsu moves without casting or commander tax',not e.state['command'] and ninja['commandCasts']==0 and ninja['commanderTax']==0)
        for _ in range(20):
            if e.state['phase']=='MAIN2' and not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',**args)
        expected=20-power-(4 if effect=='shadow' else 2 if effect in ('reveal','commander') else 0)
        e.check('Combat and additional life loss match independent expected totals',e.state['opponentLife']==expected)
        if effect in ('draw','reduced','reveal','commander'):
            e.check('The actual next library card reaches hand',any(c['forgeId']==first for c in e.state['hand']))
            e.check('Entering Hacker needs no discard; returned attacker remains',any(c['forgeId']==returned for c in e.state['hand']))
        if effect=='copy':e.check('Naga creates one actual 3/1 copy',len([c for c in e.state['battlefield'] if c.get('token') and c['name']==name and c['power']==3 and c['toughness']==1])==1)
        if effect=='shadow':e.check('Shadow creates one attacking-copy Bears token',len([c for c in e.state['battlefield'] if c.get('token') and c['name']=='Grizzly Bears' and c['power']==2 and c['toughness']==2])==1)
        if effect=='treasure':e.check('Prosperous Thief creates one Treasure',len([c for c in e.state['battlefield'] if c.get('token') and 'Treasure' in c['currentSubtypes']])==1)
        if effect=='exile':e.check('Skullsnatcher exiles the two selected opponent graveyard cards',grave.issubset({c['forgeId'] for c in e.state['exile']}))
        e.check('Main phase resumes without a gap or pending stack',e.state['phase']=='MAIN2' and not e.state['stackOrder'] and not e.state.get('decision') and not e.state['fidelityGap'])
        return dict(card=name,effect=effect,passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:
        msg=error.args[0] if isinstance(error,AssertionError) and error.args else error
        if isinstance(msg,tuple):msg=msg[0]
        return dict(card=name,effect=effect,passed=False,error=type(error).__name__+': '+str(msg)[:1600],evidence=str(e.ipc),trace=trace)
    finally:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--shard-index',type=int,default=0);p.add_argument('--shard-count',type=int,default=1)
    for key in ('native-worker','managed','fixture'):p.add_argument('--'+key,type=Path)
    a=p.parse_args();factory=Engine
    if not 0<=a.shard_index<a.shard_count<=4:p.error('Invalid shard')
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native paths')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    rows=[]
    for case in CASES[a.shard_index::a.shard_count]:
        r=run(*case,factory);rows.append(r);print(json.dumps({k:v for k,v in r.items() if k!='trace'}),flush=True)
        a.output.write_text(json.dumps(dict(passed=all(v['passed'] for v in rows),nativeHandlers=bool(a.native_worker),cases=rows),indent=2))
    raise SystemExit(0 if rows and all(v['passed'] for v in rows) else 1)
