"""Cast, protect, attack and defeat an actual Arena Siege through Forge.

Only initial mana, library and ready attacker counters are fixtures. Search,
protector designation, combat damage, defeat and transformed casting are real
rules-engine operations. This is one bounded battle sequence, not all battles.
"""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

def run(factory=Engine):
    trace=[];e=factory('card-family',fixtureHand=['Invasion of Ikoria'],fixtureLands=['Forest']*4,
        fixtureBattlefield=['Grizzly Bears'],fixtureBattlefieldReady=True,fixtureOpponentBattlefield=[],
        fixtureCounters=[dict(seat=1,cardName='Grizzly Bears',occurrence=0,type='P1P1',count=4)],
        fixtureLibrary=['Grizzly Bears','Forest','Forest','Forest','Forest','Forest','Forest','Forest'])
    try:
        battle=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Invasion of Ikoria')
        attacker=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears')
        searched=next(c['forgeId'] for c in e.state['hidden'] if c['zone']=='Library' and c['owner']==1)
        def choices(c,state):
            if c['type']=='number':return [dict(number=2)]
            if c['type']=='confirm':return [dict(accept=not c.get('prompt','').startswith('Cancel Search?'))]
            if c['type']=='cards-zone':return [dict(choiceId=next(o['choiceId'] for o in c['options'] if o.get('forgeId')==searched or o.get('label')=='Grizzly Bears'))]
            return None
        args=dict(_choice_policy=choices)
        e.check('Battle is available to cast',battle in e.state['legalCasts'])
        execute(e,trace,'cast_spell',battle,**args)
        for _ in range(12):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',**args)
        source=next(c for c in e.state['battlefield'] if c['forgeId']==battle)
        e.check('Battle enters with six defense under its caster control',source['controller']==1 and source['defense']==6)
        e.check('Opposing player protects the locally controlled Siege',source['protectorSeat']==2)
        e.check('X two searches the actual seeded non-Human creature onto battlefield',any(c['forgeId']==searched and c['name']=='Grizzly Bears' and c['controller']==1 for c in e.state['battlefield']))
        saw_attack=False
        def attacks(spec,state):
            nonlocal saw_attack
            option=next(o for o in spec['options'] if o['forgeId']==attacker)
            e.check('Protector seat and own Battle are a legal combat destination',dict(targetSeat=2,targetForgeId=battle) in option['attackTargets'])
            e.check('Freshly searched creature cannot attack',not any(o['forgeId']==searched for o in spec['options']))
            saw_attack=True
            return [dict(forgeId=attacker,targetSeat=2,targetForgeId=battle)]
        for _ in range(30):
            execute(e,trace,'pass_priority',_attack_policy=attacks,**args)
            if any(c['name']=='Zilortha, Apex of Ikoria' for c in e.state['battlefield']):break
            if e.state['turn']>2:raise AssertionError('Battle did not transform within the attacking turn')
        creature=next(c for c in e.state['battlefield'] if c['name']=='Zilortha, Apex of Ikoria')
        e.check('Actual combat attacked the Siege',saw_attack)
        e.check('Defeat trigger casts the original back face as an 8/8 with reach',creature['power']==8 and creature['toughness']==8 and 'Reach' in creature['rulesKeywords'])
        e.check('Transformation removes Battle protector designation',not creature.get('protectorSeat') and 'Battle' not in creature['currentTypes'])
        e.check('Damage went to the Siege, not the protecting player',e.state['opponentLife']==20)
        e.check('Defeat completed without pending decision, stack or gap',not e.state.get('decision') and not e.state['stackOrder'] and not e.state['fidelityGap'])
        return dict(passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:
        message=error.args[0] if isinstance(error,AssertionError) and error.args else error
        if isinstance(message,tuple):message=message[0]
        return dict(passed=False,error=str(message)[:1800],evidence=str(e.ipc),trace=trace)
    finally:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    for key in ('native-worker','managed','fixture'):p.add_argument('--'+key,type=Path)
    a=p.parse_args();factory=Engine
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native paths')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    result=run(factory);result['nativeHandlers']=bool(a.native_worker);a.output.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='trace'}));raise SystemExit(0 if result['passed'] else 1)
