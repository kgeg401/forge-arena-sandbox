"""Independent effect assertions for shared failures found in the Moxfield pool.

Seeds only initial objects and explicit player inputs. Successful cases establish
these scenarios, not every mode/interaction of a card or rendered UI parity.
"""
import argparse
import json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute


def run(case,factory=Engine):
    kind,value=case.split(':');trace=[]
    if kind=='gift':
        config=dict(fixtureHand=['Into the Flood Maw'],fixtureLands=['Island'],fixtureOpponentBattlefield=['Field Creeper'])
    elif kind=='reveal':
        config=dict(fixtureHand=['Fortified Village','Forest','Plains'],fixtureLands=[],fixtureOpponentBattlefield=[])
    elif kind=='keyword':
        config=dict(fixtureHand=['Orcish Medicine'],fixtureLands=['Swamp']*2,fixtureBattlefield=['Grizzly Bears'],fixtureOpponentBattlefield=[])
    else:
        card={'inferno':'Inferno Titan','fury':'Fury','fire':'Fire Covenant','smashing':'Shatterskull Smashing','pyro':'Pyrokinesis'}[kind]
        config=dict(fixtureHand=[card],fixtureLands=['Mountain']*6+['Swamp']*3,fixtureOpponentBattlefield=['Grizzly Bears','Field Creeper'])
    e=factory('card-family',fixtureLibrary=['Forest','Island','Plains','Mountain']*3,**config)
    try:
        spell=e.state['hand'][0]['forgeId'];op='play_land' if kind=='reveal' else 'cast_spell'
        battlefield={c['name']:c['forgeId'] for c in e.state['battlefield']}
        def choices(c,state):
            prompt=c.get('prompt','')
            if c['type']=='number':return [dict(number=int(value))]
            if c['type']=='confirm':return [dict(accept=value=='yes' or kind=='fire' and c.get('context')=='life-payment')]
            if c['type']=='options':
                if 'additional costs' in prompt:return [dict(choiceId=o['choiceId']) for o in c['options']] if kind=='gift' and value=='yes' else []
                if kind=='keyword':return [dict(choiceId=next(o['choiceId'] for o in c['options'] if o['label'].lower()==value))]
            return None
        def targets(spec,state):
            if kind=='keyword':return [next(o for o in spec['options'] if o['forgeId']==battlefield['Grizzly Bears'])]
            if kind in ('gift',):return [next(o for o in spec['options'] if o['forgeId']==battlefield['Field Creeper'])]
            return [next(o for o in spec['options'] if o['forgeId']==battlefield[n]) for n in ['Grizzly Bears','Field Creeper']]
        def damage(spec,state):
            total=spec['totalDamage']
            # Send malformed distributions before the real choice. No payment or
            # damage may happen when a total, recipient or minimum is invalid.
            if not hasattr(e,'native_call'):
                previous=json.loads(json.dumps(state));opts=spec['options'];first=opts[0]['forgeId'];second=opts[1]['forgeId']
                invalid=[[dict(forgeId=first,amount=total),dict(forgeId=second,amount=0)],
                         [dict(forgeId=first,amount=1),dict(forgeId=second,amount=1)],
                         [dict(forgeId=first,amount=1),dict(forgeId=first,amount=total-1)],
                         [dict(forgeId=-99999,amount=1),dict(forgeId=second,amount=total-1)],
                         [dict(forgeId=first,amount=1.5),dict(forgeId=second,amount=total-1)]]
                for assignments in invalid:
                    r=e.send('submit_assign_damage',decisionToken=spec['token'],assignments=assignments)
                    e.check('Invalid distribution remains pending',not r['accepted'] and e.state['decision']['token']==spec['token'])
                    e.check('Invalid distribution cannot pay or damage',all(e.state[k]==previous[k] for k in ('life','battlefield','stackOrder','manaTotal','graveyard')))
            return [dict(forgeId=o['forgeId'],amount=2 if o['forgeId']==battlefield['Grizzly Bears'] else total-2) for o in spec['options']]
        kwargs=dict(_choice_policy=choices,_target_policy=targets,_damage_policy=damage)
        execute(e,trace,op,spell,**kwargs)
        if kind=='reveal':
            land=next(c for c in e.state['battlefield'] if c['forgeId']==spell)
            e.check('Revealing is optional and controls entry tapped',land['tapped']==(value=='no'))
            e.check('Revealed card stays in hand',{c['name'] for c in e.state['hand']}=={'Forest','Plains'})
        else:
            for _ in range(8):
                if not e.state['stackOrder']:break
                execute(e,trace,'pass_priority',**kwargs)
            e.check('Entire tested stack resolved',not e.state['stackOrder'])
            if kind=='gift':
                e.check('Target bounced to opponent hand',any(c['forgeId']==battlefield['Field Creeper'] and c['zone']=='Hand' and c['owner']==2 for c in e.state['hidden']))
                fish=[c for c in e.state['battlefield'] if c.get('token') and c['controller']==2]
                e.check('Gift changes only when explicitly selected',len(fish)==(1 if value=='yes' else 0))
                if fish:e.check('Gift is a tapped blue 1/1 Fish',fish[0]['tapped'] and fish[0]['power']==1 and fish[0]['toughness']==1 and fish[0]['colorMask']==2 and 'Fish' in fish[0]['currentSubtypes'])
            elif kind=='keyword':
                creature=next(c for c in e.state['battlefield'] if c['forgeId']==battlefield['Grizzly Bears'])
                e.check('Chosen protection keyword applies',value in [k.lower() for k in creature['rulesKeywords']])
                other='lifelink' if value=='indestructible' else 'indestructible'
                e.check('Unchosen keyword does not apply',other not in [k.lower() for k in creature['rulesKeywords']])
                e.check('Amass created one 1/1 army',len([c for c in e.state['battlefield'] if c.get('token') and c['controller']==1 and c['power']==1 and c['toughness']==1])==1)
            else:
                zero=kind in ('fire','smashing') and value=='0'
                damage_events=[x for x in e.state['events'] if x['kind']=='damage' and not x.get('combat')]
                if zero:
                    e.check('Zero X has no targeting or allocation prompt',not any(x.get('kind') in ('targets','assign_damage') for x in trace))
                    e.check('Zero X does not damage either creature',all(any(c['forgeId']==battlefield[n] and c['damage']==0 for c in e.state['battlefield']) for n in ('Grizzly Bears','Field Creeper')))
                else:
                    total=3 if kind=='inferno' else 4 if kind in ('fury','pyro') else int(value)
                    actual={x['targetForgeId']:x['amount'] for x in damage_events}
                    e.check('Forge deals exactly the authored split',{battlefield['Grizzly Bears']:2,battlefield['Field Creeper']:total-2}.items()<=actual.items())
                    e.check('State based actions kill both recipients',{battlefield['Grizzly Bears'],battlefield['Field Creeper']}.issubset({c['forgeId'] for c in e.state['graveyard']}))
                if kind=='fire':e.check('Fire Covenant pays exactly announced life',e.state['life']==20-int(value))
        e.check('Engine remains healthy with no unsupported callback',not e.state['fidelityGap'] and e.process.poll() is None)
        return dict(case=case,passed=True,checks=len(e.checks),evidence=str(e.ipc),decisions=trace)
    except Exception as error:
        return dict(case=case,passed=False,error=str(error)[:1000],evidence=str(e.ipc),decisions=trace)
    finally:e.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append')
    for name in ('native-worker','managed','fixture'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();factory=Engine
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native worker arguments')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    cases=a.case or ['gift:yes','gift:no','reveal:yes','reveal:no','keyword:indestructible','keyword:lifelink','inferno:3','fury:4','fire:3','fire:0','smashing:3','smashing:0','pyro:4']
    rows=[]
    for case in cases:
        r=run(case,factory);rows.append(r);print(json.dumps({k:v for k,v in r.items() if k!='decisions'}),flush=True)
        a.output.write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),nativeHandlers=bool(a.native_worker),cases=rows),indent=2),encoding='utf8')
    raise SystemExit(0 if all(r['passed'] for r in rows) else 1)
