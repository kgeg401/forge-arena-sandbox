"""Native context-gated activations with independent effect/resource assertions.

Only the initial board, library and graveyard are seeded. Threshold, attack
history, payments, regeneration and cleanup execute in the original rules.
These named scenarios do not establish all abilities or interactions.
"""
import argparse,json
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

NAMES={'ring':'Barbarian Ring','coliseum':'Cephalid Coliseum','seer':'Atzocan Seer','mite':'Haywire Mite','kogla':'Kogla, the Titan Ape','plaza':'Plaza of Heroes','fault':'Volatile Fault','mistveil':'Mistveil Plains','minas':'Minas Tirith','swarmyard':'Swarmyard'}
CASES=['ring','ring-six','coliseum','coliseum-six','seer','mite','kogla','plaza','fault','mistveil','mistveil-one','minas','minas-one','swarmyard']

def run(case,a):
    kind=case.split('-')[0];name=NAMES[kind];trace=[];e=None
    settings=dict(fixtureHand=[],fixtureLands=['Forest']*4+['Island']*4+['Swamp']*2+['Mountain']*2+['Plains']*3,fixtureBattlefield=[name],fixtureBattlefieldReady=True,fixtureOpponentBattlefield=[],fixtureOpponentLands=[],fixtureLibrary=['Forest','Island','Mountain','Swamp','Plains']*3)
    if kind in ('ring','coliseum'):settings['fixtureGraveyard']=['Plains']*(6 if case.endswith('-six') else 7)
    if kind=='coliseum':settings['fixtureHand']=['Arcane Signet']
    if kind=='seer':settings['fixtureGraveyard']=['Etali, Primal Conqueror']
    if kind=='mite':settings['fixtureOpponentBattlefield']=['Arcane Signet','Ornithopter']
    if kind=='kogla':settings['fixtureBattlefield'].append('Esper Sentinel')
    if kind=='plaza':settings['fixtureBattlefield'].append('Kogla, the Titan Ape')
    if kind=='fault':settings['fixtureOpponentBattlefield']=['Command Tower']
    if kind=='mistveil':settings.update(fixtureBattlefield=[name,'Savannah Lions']+([] if case.endswith('-one') else ['Yoked Ox']),fixtureGraveyard=['Grizzly Bears'],fixtureHand=['Divination','Divination'],fixtureLibrary=['Forest','Island','Mountain'])
    if kind=='minas':settings['fixtureBattlefield']+=['Grizzly Bears','Savannah Lions']
    if kind=='swarmyard':settings.update(fixtureBattlefield=[name,'Haywire Mite'],fixtureHand=['Doom Blade'])
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,**settings)
        def card(zone,n,owner=1):return next(c for c in e.state[zone] if c['name']==n and c.get('owner')==owner)
        source=card('battlefield',name)['forgeId'];wanted=None;target_seat=None
        def targets(spec,state):
            if target_seat:return [next(o for o in spec['options'] if o.get('targetSeat')==target_seat)]
            if kind=='mite':e.check('Creature artifact is not a legal exile target',card('battlefield','Ornithopter',2)['forgeId'] not in {o['forgeId'] for o in spec['options']})
            return [next(o for o in spec['options'] if o.get('forgeId')==wanted)]
        def choices(spec,state):
            if spec['type']=='confirm':return [dict(accept=True)]
            return None
        attackers=[]
        def action(op,forge_id=0,**fields):return execute(e,trace,op,forge_id,_target_policy=targets,_choice_policy=choices,_attack_policy=lambda spec,state:[dict(forgeId=i,targetSeat=2) for i in attackers],**fields)
        def settle():
            for _ in range(20):
                if not e.state['stackOrder']:return
                action('pass_priority')
            raise AssertionError('Stack did not resolve within its bound')
        def offers():return [v for v in e.state['legalActivations'] if v['forgeId']==source]
        def library_count():return sum(c['zone']=='Library' and c['owner']==1 for c in e.state['hidden'])
        if kind=='minas':
            e.check('Draw is unavailable before declaring attackers',not offers())
            attackers=[card('battlefield','Savannah Lions')['forgeId']]
            if not case.endswith('-one'):attackers.append(card('battlefield','Grizzly Bears')['forgeId'])
            for _ in range(80):
                if e.state['activeSeat']==1 and e.state['phase']=='MAIN2':break
                action('pass_priority')
            else:raise AssertionError('Actual combat did not reach second main phase')
            e.check('Actual declared creatures dealt their combat damage',e.state['opponentLife']==(18 if case.endswith('-one') else 16))
        if case.endswith(('-six','-one')):
            e.check('Actual threshold or permanent/attacker condition rejects activation',not offers())
        else:
            if kind in ('ring','coliseum'):target_seat=2 if kind=='ring' else 1
            elif kind=='seer':wanted=card('graveyard','Etali, Primal Conqueror')['forgeId']
            elif kind=='mite':wanted=card('battlefield','Arcane Signet',2)['forgeId']
            elif kind=='kogla':wanted=card('battlefield','Esper Sentinel')['forgeId']
            elif kind=='plaza':wanted=card('battlefield','Kogla, the Titan Ape')['forgeId']
            elif kind=='fault':wanted=card('battlefield','Command Tower',2)['forgeId']
            elif kind=='mistveil':wanted=card('graveyard','Grizzly Bears')['forgeId']
            elif kind=='swarmyard':wanted=card('battlefield','Haywire Mite')['forgeId']
            available=offers();e.check('Original context offers exactly one nonmana activation',len(available)==1)
            before_hand=len(e.state['hand']);before_library=library_count()
            action('activate_ability',source,abilityId=available[0]['abilityId']);settle()
            if kind=='ring':
                e.check('Ring was sacrificed and dealt exactly two damage',card('graveyard',name) and e.state['opponentLife']==18 and e.state['life']==20)
            elif kind=='coliseum':
                e.check('Coliseum sacrificed with three actual draws and three discards',card('graveyard',name) and library_count()==before_library-3 and len(e.state['hand'])==before_hand and len(e.state['graveyard'])==11)
            elif kind=='seer':
                e.check('Seer sacrificed and selected Dinosaur returned to hand',card('graveyard',name) and any(c['forgeId']==wanted for c in e.state['hand']))
            elif kind=='mite':
                e.check('Mite sacrificed, its real death trigger gained two life, target exiled',card('graveyard',name) and e.state['life']==22 and any(c['forgeId']==wanted for c in e.state['exile']))
            elif kind in ('kogla','plaza'):
                recipient=card('battlefield','Kogla, the Titan Ape');expected={'Indestructible'}|({'Hexproof'} if kind=='plaza' else set())
                e.check('Original ability grants the exact keywords',expected<=set(recipient['rulesKeywords']))
                if kind=='kogla':e.check('Chosen Human returned to hand',any(c['forgeId']==wanted for c in e.state['hand']))
                else:e.check('Plaza paid its actual exile cost',any(c['forgeId']==source for c in e.state['exile']))
                for _ in range(80):
                    if e.state['turn']>1:break
                    action('pass_priority')
                e.check('Temporary keywords expire at original cleanup',e.state['turn']>1 and not expected&set(card('battlefield','Kogla, the Titan Ape')['rulesKeywords']))
            elif kind=='fault':
                e.check('Source sacrificed and opposing nonbasic destroyed',card('graveyard',name) and any(c['forgeId']==wanted for c in e.state['graveyard']))
                e.check('Opponent searched a real basic and local player made Treasure',any(c['owner']==2 and c['name'] in ('Plains','Island','Swamp','Mountain','Forest') for c in e.state['battlefield']) and sum(c['name']=='Treasure Token' and c['owner']==1 for c in e.state['battlefield'])==1)
            elif kind=='mistveil':
                e.check('Target left graveyard and library grew by one',not any(c['forgeId']==wanted for c in e.state['graveyard']) and library_count()==before_library+1)
                for _ in range(2):action('cast_spell',card('hand','Divination')['forgeId']);settle()
                e.check('Two actual draw-two spells reach exactly the bottom card',sorted(c['name'] for c in e.state['hand'])==sorted(['Forest','Island','Mountain','Grizzly Bears']) and library_count()==0)
            elif kind=='minas':e.check('Actual two-attacker history enabled one real draw',len(e.state['hand'])==before_hand+1 and library_count()==before_library-1 and card('battlefield',name)['tapped'])
            else:
                action('cast_spell',card('hand','Doom Blade')['forgeId']);settle()
                mite=card('battlefield','Haywire Mite')
                e.check('Regeneration replaced actual destroy without a death trigger',mite['forgeId']==wanted and mite['tapped'] and e.state['life']==20 and not any(c['forgeId']==wanted for c in e.state['graveyard']))
                e.check('Regeneration source tapped and removal spell resolved',card('battlefield',name)['tapped'] and card('graveyard','Doom Blade'))
        e.check('No fidelity gap or pending choice',not e.state['fidelityGap'] and not e.state.get('decision'))
        return dict(case=case,card=name,passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:
        message=error.args[0] if isinstance(error,AssertionError) and error.args else str(error)
        if isinstance(message,tuple):message=message[0]
        return dict(case=case,card=name,passed=False,error=str(message)[:1200],evidence=str(e.ipc) if e else None,trace=trace)
    finally:
        if e:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--case',action='append',choices=CASES);a=p.parse_args();rows=[]
    for case in a.case or CASES:
        row=run(case,a);rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='trace'}),flush=True)
        a.output.write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),cases=rows,scope=__doc__),indent=2),encoding='utf8')
    raise SystemExit(0 if all(r['passed'] for r in rows) else 1)
