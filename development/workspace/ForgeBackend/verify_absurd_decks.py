"""Seeded mass-arrival, opponent-copy and poison interactions through native handlers.

Only starting zones/resources are fixtures. Forge pays costs and resolves effects.
These bounded scenarios do not certify full decks or competitive power levels.
"""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

CASES=['wave-arrival','sarkhan-arrival','miirym-copies','roaming-copies','doppelgang','clone-legion','infect-combat','poison-aura','exoskeleton','zaxara-mana','esix-hydra','drake-blink','kindred-arrival','copied-poison-army','replication-upkeep']

def run(a,key):
    e=None;trace=[];x=5
    settings=dict(fixtureHand=[],fixtureLands=['Forest']*15+['Island']*15+['Mountain']*10+['Swamp']*10,
        fixtureBattlefield=[],fixtureOpponentBattlefield=['Field Creeper','Yoked Ox'],fixtureLibrary=['Forest']*30,
        fixtureBattlefieldReady=True,fixtureLocalLife=200)
    if key=='wave-arrival':settings.update(fixtureHand=['Genesis Wave'],fixtureBattlefield=['Maskwood Nexus'],fixtureLibrary=['Wrathful Red Dragon','Peregrine Drake','Ganax, Astral Hunter'])
    elif key=='sarkhan-arrival':settings.update(fixtureHand=['Sarkhan Unbroken'],fixtureBattlefield=['Maskwood Nexus','Doubling Season'],fixtureLibrary=['Wrathful Red Dragon','Peregrine Drake','Ganax, Astral Hunter','Forest'])
    elif key=='miirym-copies':settings.update(fixtureHand=['Ganax, Astral Hunter'],fixtureBattlefield=['Doubling Season'],fixtureCommander='Miirym, Sentinel Wyrm',fixtureCommanderInPlay=True)
    elif key=='roaming-copies':settings.update(fixtureHand=['Roaming Throne'],fixtureBattlefield=['Maskwood Nexus'],fixtureCommander='Miirym, Sentinel Wyrm',fixtureCommanderInPlay=True)
    elif key=='doppelgang':x=2;settings.update(fixtureHand=['Doppelgang'],fixtureCommander='Zaxara, the Exemplary',fixtureCommanderInPlay=True)
    elif key=='copied-poison-army':x=2;settings.update(fixtureHand=['Doppelgang','Second Harvest','Finale of Devastation','Triumph of the Hordes'],fixtureCommander='Zaxara, the Exemplary',fixtureCommanderInPlay=True)
    elif key=='clone-legion':settings.update(fixtureHand=['Clone Legion'])
    elif key=='replication-upkeep':settings.update(fixtureHand=['Extravagant Replication'],fixtureBattlefield=['Field Creeper'])
    elif key=='infect-combat':settings.update(fixtureHand=['Triumph of the Hordes'],fixtureBattlefield=['Utvara Hellkite','Utvara Hellkite'],fixtureOpponentBattlefield=[])
    elif key=='poison-aura':settings.update(fixtureHand=['Phyresis'],fixtureBattlefield=['Utvara Hellkite'],fixtureOpponentBattlefield=[])
    elif key=='exoskeleton':settings.update(fixtureHand=['Grafted Exoskeleton'],fixtureBattlefield=['Utvara Hellkite'],fixtureOpponentBattlefield=[])
    elif key=='zaxara-mana':settings.update(fixtureHand=['Freed from the Real'],fixtureCommander='Zaxara, the Exemplary',fixtureCommanderInPlay=True,fixtureLands=['Island']*3)
    elif key=='esix-hydra':x=2;settings.update(fixtureHand=['Doppelgang'],fixtureBattlefield=['Esix, Fractal Bloom'],fixtureCommander='Zaxara, the Exemplary',fixtureCommanderInPlay=True)
    elif key=='drake-blink':settings.update(fixtureHand=['Peregrine Drake'],fixtureBattlefield=['Deadeye Navigator'],fixtureLands=['Island']*5)
    elif key=='kindred-arrival':settings.update(fixtureHand=['Kindred Summons'],fixtureBattlefield=['Maskwood Nexus','Llanowar Elves','Elvish Mystic','Birds of Paradise'],fixtureLibrary=['Wrathful Red Dragon','Peregrine Drake','Ganax, Astral Hunter','Forest'])

    def choices(c,s):
        if c['type']=='confirm':return [dict(accept=not ('draw' in c.get('prompt','').lower() and not s.get('libraryCount',1)))]
        if c['type']=='number' and 'Choose X' in c.get('prompt',''):return [dict(number=min(x,c['max']))]
        opts=c.get('options',[])
        dragon=next((v for v in opts if v.get('label')=='Dragon'),None)
        if dragon:return [dict(choiceId=dragon['choiceId'])]
        if c['type']=='colors':
            blue=next(v for v in opts if v.get('color','').lower()=='blue');return [dict(choiceId=blue['choiceId'])]
        if c['type']=='entities':
            if 'put into battlefield' in c.get('prompt',''):return [dict(choiceId=v['choiceId']) for v in opts[:c.get('max',len(opts))]]
            pick=next((v for v in opts if ('Field Creeper' if key=='esix-hydra' else 'Deadeye Navigator') in v.get('label','')),None)
            if pick:return [dict(choiceId=pick['choiceId'])]
        if c['type'] in ('cards-zone','cards-effect'):return [dict(choiceId=v['choiceId']) for v in opts[:c.get('max',len(opts))]]
        return None
    def targets(spec,s):
        cards={c['forgeId']:c for c in s['battlefield']}
        if key in ('poison-aura','exoskeleton'):
            return [v for v in spec['options'] if cards.get(v['forgeId'],{}).get('name')=='Utvara Hellkite'][:1]
        if key=='zaxara-mana':return [v for v in spec['options'] if cards.get(v['forgeId'],{}).get('name')=='Zaxara, the Exemplary'][:1]
        if key=='replication-upkeep':return [v for v in spec['options'] if cards.get(v['forgeId'],{}).get('controller')==1 and cards.get(v['forgeId'],{}).get('name')=='Field Creeper'][:1]
        if key in ('doppelgang','esix-hydra','copied-poison-army'):
            return [v for v in spec['options'] if cards.get(v['forgeId'],{}).get('controller')==2][:2]
        players=[v for v in spec['options'] if v.get('targetSeat')==2]
        return (players or spec['options'])[:max(1,spec['minTargets'])]
    def act(op,id=0,**kw):execute(e,trace,op,id,_choice_policy=choices,_target_policy=targets,**kw)
    def settle():
        for _ in range(70):
            if not e.state['stackOrder'] or e.state['gameOver']:return
            act('pass_priority')
        raise AssertionError('Stack did not settle within bound')
    def card(name):return next(c for c in e.state['battlefield'] if c['name']==name)
    def cast(name):act('cast_spell',next(c['forgeId'] for c in e.state['hand'] if c['name']==name));settle()
    def activate(name,contains):
        id=card(name)['forgeId'];offer=next(v for v in e.state['legalActivations'] if v['forgeId']==id and contains.lower() in json.dumps(v).lower())
        act('activate_ability',id,abilityId=offer['abilityId']);settle()
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,**settings)
        before_opponent_library=[c['forgeId'] for c in e.state['hidden'] if c['owner']==2 and c['zone']=='Library']
        cast(settings['fixtureHand'][0])
        if key=='copied-poison-army':
            e.check('Copy spell preserves both opposing originals and their exact library IDs',len([c for c in e.state['battlefield'] if c['controller']==2])==2 and [c['forgeId'] for c in e.state['hidden'] if c['owner']==2 and c['zone']=='Library']==before_opponent_library,'opposing originals/library')
            cast('Second Harvest')
            e.check('Second Harvest doubles the four opposing-creature token copies',len([c for c in e.state['battlefield'] if c.get('token') and c['name'] in ('Field Creeper','Yoked Ox')])==8,'actual token copies')
            x=10;cast('Finale of Devastation');cast('Triumph of the Hordes')
            army=[c for c in e.state['battlefield'] if c['controller']==1 and 'Creature' in c['currentTypes']]
            e.check('The real copied army receives haste and infect before combat',len(army)>=6 and all({'Haste','Infect'}<=set(c['rulesKeywords']) for c in army),'actual army keywords')
            for _ in range(35):
                if e.state['gameOver']:break
                act('pass_priority',_attack_seat=2)
            e.check('Copied opponents plus Finale and Triumph win through real poison combat',e.state['gameOver'] and next(p for p in e.state['players'] if p['seat']==1)['won'],'poison outcome')
        if key=='sarkhan-arrival':
            e.check('Doubling Season gives Sarkhan eight actual loyalty',sum(v['count'] for v in card('Sarkhan Unbroken')['counters'] if v['type']=='LOYALTY')==8)
            activate('Sarkhan Unbroken','ChangeZone')
        elif key=='exoskeleton':activate('Grafted Exoskeleton','Attach')
        elif key=='zaxara-mana':
            id=card('Zaxara, the Exemplary')['forgeId']
            def tap():
                offer=next(v for v in e.state['legalManaOffers'] if v['forgeId']==id)
                act('activate_mana',id,abilityId=offer['abilityId'])
            tap();initial=e.state['manaTotal'];activate('Freed from the Real','untap');tap()
            e.check('A real paid untap and second tap net one mana',e.state['manaTotal']==initial+1 and card('Zaxara, the Exemplary')['tapped'])
        elif key=='drake-blink':
            e.check('Drake really untaps five lands after casting',sum(not c['tapped'] for c in e.state['battlefield'] if c['name']=='Island')==5)
            activate('Peregrine Drake','ChangeZone')
            e.check('Paid blink returns Drake and untaps the spent lands again',card('Peregrine Drake') and sum(not c['tapped'] for c in e.state['battlefield'] if c['name']=='Island')==5)
        elif key=='replication-upkeep':
            for _ in range(100):
                if any(c.get('token') and c['name']=='Field Creeper' for c in e.state['battlefield']):break
                act('pass_priority',_attack_policy=lambda d,s:[])
            e.check('The retained real upkeep trigger creates a creature-copy token',any(c.get('token') and c['name']=='Field Creeper' for c in e.state['battlefield']),'actual upkeep copy')
        if key in ('wave-arrival','sarkhan-arrival','kindred-arrival'):
            names={'Ganax, Astral Hunter','Wrathful Red Dragon','Peregrine Drake'}
            e.check('Every starting-library creature arrives as its original card',names<={c['name'] for c in e.state['battlefield'] if not c.get('token')})
            treasures=[c for c in e.state['battlefield'] if c.get('token') and 'Treasure' in c.get('currentSubtypes',[])]
            expected=6 if key=='sarkhan-arrival' else 3
            e.check('Ganax sees itself AND the two simultaneous Dragon arrivals',len(treasures)==expected,dict(expected=expected,actual=len(treasures)))
        elif key=='miirym-copies':
            copies=[c for c in e.state['battlefield'] if c['name']=='Ganax, Astral Hunter' and c.get('token')]
            e.check('Miirym plus Doubling Season makes two nonlegendary copies',len(copies)==2 and all('Legendary' not in c.get('currentSupertypes',c.get('supertypes',[])) for c in copies))
        elif key=='roaming-copies':
            thrones=[c for c in e.state['battlefield'] if c['name']=='Roaming Throne']
            e.check('Original Throne and both Miirym copies survive their real as-enters choices',len(thrones)==3 and sum(bool(c.get('token')) for c in thrones)==2)
            e.check('Native type chooser handled the original and both initially zoneless copies',sum(v.get('type')=='type' for v in trace)>=3)
        elif key in ('clone-legion','doppelgang'):
            copies=[c for c in e.state['battlefield'] if c.get('token') and c['name'] in ('Field Creeper','Yoked Ox')]
            e.check('Actual opposing bodies become separately controlled tokens',len(copies)==(2 if key=='clone-legion' else 4) and all(c['controller']==1 for c in copies))
            e.check('Both opposing originals remain on their battlefield',len([c for c in e.state['battlefield'] if c['name'] in ('Field Creeper','Yoked Ox') and c['controller']==2])==2)
            after=[c['forgeId'] for c in e.state['hidden'] if c['owner']==2 and c['zone']=='Library']
            e.check('Copy spell does not mill, exile or consume opposing library cards',after==before_opponent_library)
            if key=='doppelgang':e.check('X=2 also creates a genuine 2/2 Hydra',any(c.get('token') and 'Hydra' in c.get('currentSubtypes',[]) and c['power']==c['toughness']==2 for c in e.state['battlefield']))
        elif key in ('infect-combat','poison-aura','exoskeleton'):
            infected='Utvara Hellkite'
            e.check('Original creature actually gains infect','Infect' in card(infected)['rulesKeywords'],infected)
            for _ in range(90):
                if e.state['gameOver']:break
                act('pass_priority',_attack_seat=2)
            e.check('Real infect combat eliminates the opponent at ten poison',e.state['gameOver'] and next(p for p in e.state['players'] if p['seat']==1)['won'])
        elif key=='esix-hydra':
            copies=[c for c in e.state['battlefield'] if c.get('token')]
            e.check('Esix replaces the Hydra with a real creature copy retaining X counters',any(sum(v['count'] for v in c['counters'] if v['type']=='P1P1')==2 and c['name']!='Hydra' for c in copies))
        e.check('Scenario ends without an unresolved choice or fidelity gap',not e.state.get('decision') and not e.state['fidelityGap'])
        result=dict(case=key,passed=True,checks=e.checks,evidence=str(e.ipc))
    except Exception as error:result=dict(case=key,passed=False,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
    (a.output/(key+'.json')).write_text(json.dumps(result,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps(dict(case=key,passed=result['passed'],error=result.get('error','')[:400],evidence=result.get('evidence'))),flush=True)
    return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--case',choices=CASES);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    results=[run(a,k) for k in ([a.case] if a.case else CASES)];raise SystemExit(0 if all(results) else 1)
