"""Named, independently asserted paper-Darien effects through native handlers."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute
from verify_darien_deck import settle

CASES=['damage-lifegain','soldier-lords','lifegain-chain','court-tap','mentor-draw','prava-token','yes-man','nomad-mana','nomad-threshold','myriad-search','wayfarer-search','embalm','jade-redirect','martyr-redirect','worship','bastion-commander','martial-coup','coppercoats','torture-chamber','barbed-wire','angel-trumpet','paladin-levels','suture-opponent']
CASES+=['catapult-exile','keeper-catchup','knight-ramp','defiler-life','conjurer-blink','lunarch-disturb','jinxed-control','diamond-mana','idol-abilities','well-draw','attack-lifegain']

def run(key,a):
    e=None;trace=[]
    try:
        settings=dict(fixtureHand=[],fixtureLands=['Plains']*16,fixtureBattlefield=[],fixtureOpponentBattlefield=['Field Creeper'],fixtureLibrary=['Plains']*30,fixtureBattlefieldReady=True)
        bf=[];hand=[]
        if key=='damage-lifegain':bf=['Darien, King of Kjeldor','Soul Warden'];hand=['Lightning Bolt'];settings['fixtureLands']+=['Mountain']
        elif key=='soldier-lords':bf=['Field Marshal','Valiant Veteran','Honor of the Pure'];hand=['Heraldic Banner','Rally the Ranks','Captain of the Watch']
        elif key=='lifegain-chain':bf=['Soul Warden',"Soul's Attendant",'Healer of the Pride',"Ajani's Welcome",'Anointer Priest','Daxos, Blessed by the Sun','Suture Priest'];hand=["Captain's Call"]
        elif key=='court-tap':bf=['Court Street Denizen'];hand=['Savannah Lions']
        elif key=='mentor-draw':bf=['Mentor of the Meek'];hand=['Savannah Lions']
        elif key=='prava-token':bf=['Prava of the Steel Legion']
        elif key=='yes-man':bf=['Yes Man, Personal Securitron'];hand=['Disenchant']
        elif key.startswith('nomad-'):bf=['Nomad Stadium'];settings['fixtureLands']=['Plains'];settings['fixtureGraveyard']=['Plains']*7 if key.endswith('threshold') else []
        elif key=='myriad-search':bf=['Myriad Landscape'];settings['fixtureLands']=['Plains']*2
        elif key=='wayfarer-search':bf=['Weathered Wayfarer'];settings.update(fixtureLands=['Plains'],fixtureOpponentBattlefield=['Forest']*3)
        elif key=='embalm':settings.update(fixtureGraveyard=['Anointer Priest']);hand=["Captain's Call"]
        elif key in ('jade-redirect','martyr-redirect'):
            bf=['Darien, King of Kjeldor','Savannah Lions'];hand=['Blood of the Martyr'] if key=='martyr-redirect' else []
            if key=='jade-redirect':bf+=['Jade Monolith']
            settings.update(fixtureOpponentSpell='Lightning Bolt',fixtureOpponentLands=['Mountain'],fixtureOpponentTargets=[dict(seat=1,cardName='Savannah Lions',occurrence=0)])
        elif key=='worship':bf=['Darien, King of Kjeldor','Worship'];hand=['Lightning Bolt'];settings.update(fixtureLocalLife=2,fixtureLands=['Mountain'])
        elif key=='bastion-commander':bf=['Bastion Protector'];hand=['Savannah Lions','Wrath of God'];settings.update(fixtureCommander='Darien, King of Kjeldor',fixtureCommanderInPlay=True)
        elif key=='martial-coup':bf=['Savannah Lions'];hand=['Martial Coup']
        elif key=='coppercoats':hand=['Call the Coppercoats'];settings['fixtureOpponentBattlefield']=['Field Creeper','Savannah Lions','Yoked Ox']
        elif key=='torture-chamber':bf=['Torture Chamber']
        elif key=='barbed-wire':bf=['Barbed Wire','Darien, King of Kjeldor']
        elif key=='angel-trumpet':bf=["Angel's Trumpet",'Darien, King of Kjeldor','Savannah Lions']
        elif key=='paladin-levels':bf=['Savannah Lions'];hand=['Paladin Class']
        elif key=='suture-opponent':bf=['Suture Priest'];settings.update(fixtureOpponentSpell='Grizzly Bears',fixtureOpponentLands=['Forest']*2)
        elif key=='catapult-exile':bf=['Catapult Master','Valiant Veteran'];hand=['Captain of the Watch']
        elif key=='keeper-catchup':bf=['Keeper of the Accord'];settings.update(fixtureLands=['Plains'],fixtureOpponentBattlefield=['Forest']*3+['Field Creeper','Yoked Ox'])
        elif key=='knight-ramp':hand=['Knight of the White Orchid'];settings.update(fixtureLands=['Plains']*2,fixtureOpponentBattlefield=['Forest']*3)
        elif key=='defiler-life':bf=['Defiler of Faith'];hand=['Ornithopter','Savannah Lions'];settings['fixtureLands']=[]
        elif key=='conjurer-blink':bf=['Distinguished Conjurer','Savannah Lions'];hand=['Savannah Lions']
        elif key=='lunarch-disturb':hand=['Savannah Lions','Swords to Plowshares'];settings['fixtureGraveyard']=['Lunarch Veteran']
        elif key=='jinxed-control':bf=['Jinxed Idol','Savannah Lions']
        elif key=='diamond-mana':hand=['Marble Diamond']
        elif key=='idol-abilities':bf=['Idol of Oblivion'];hand=["Captain's Call"]
        elif key=='well-draw':bf=['Well of Lost Dreams','Soul Warden'];hand=['Savannah Lions']
        elif key=='attack-lifegain':bf=['Path of Bravery','Righteous Cause','Linden, the Steadfast Queen','Savannah Lions'];hand=['Revitalize'];settings['fixtureLocalLife']=19
        else:raise ValueError(key)
        settings.update(fixtureHand=hand,fixtureBattlefield=bf)
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,**settings)
        def policy(c,s):
            if c['type']=='confirm':return [dict(accept=True)]
            if c['type']=='number' and c.get('prompt','').startswith('Choose X '):return [dict(number=min(5,c['max']))]
            if key=='well-draw' and c['type']=='number':return [dict(number=min(1,c['max']))]
            for label in ('Soldier','White','Lightning Bolt'):
                if key not in ('soldier-lords','jade-redirect'):break
                match=[v for v in c['options'] if v.get('label')==label or label=='Lightning Bolt' and 'Lightning Bolt' in v.get('label','')]
                if match:return [dict(choiceId=match[0]['choiceId'])]
            if key=='myriad-search' and c['type']=='cards-zone' and c.get('max')==2:return [dict(choiceId=v['choiceId']) for v in c['options'][:2]]
            return None
        def act(op,id=0,**kw):execute(e,trace,op,id,_choice_policy=policy,_attack_policy=(lambda spec,s:[]) if key=='angel-trumpet' else None,**kw)
        def resolve():
            for _ in range(60):
                if not e.state['stackOrder']:return
                act('pass_priority')
            raise AssertionError('Interaction stack did not settle')
        def card(name,zone='battlefield'):return next(c for c in e.state[zone] if c['name']==name)
        def cast(name,zone='hand',**kw):c=card(name,zone);e.check('Legal cast: '+name,c['forgeId'] in e.state['legalCasts']);act('cast_spell',c['forgeId'],**kw);resolve()
        def activate(name,**kw):
            c=next((v for v in e.state['battlefield']+e.state['graveyard'] if v['name']==name));offer=next(v for v in e.state['legalActivations'] if v['forgeId']==c['forgeId']);act('activate_ability',c['forgeId'],abilityId=offer['abilityId'],**kw);resolve()
        def tokens():return [c for c in e.state['battlefield'] if c.get('token') and c['controller']==1 and 'Soldier' in c['currentSubtypes']]
        def until(test):
            for _ in range(80):
                if test():return
                assert not e.state['gameOver'],'Game ended before the witness'
                act('pass_priority')
            raise AssertionError('Named interaction time/phase bound exceeded')
        if key=='damage-lifegain':
            cast('Lightning Bolt',_target_policy=lambda spec,s:[next(o for o in spec['options'] if o.get('targetSeat')==1)])
            e.check('Three real damage yields three Soldiers; Warden restores three life',len(tokens())==3 and e.state['life']==20)
        elif key=='soldier-lords':
            for n in hand:cast(n)
            e.check('All three Soldier tokens receive each distinct static bonus',len(tokens())==3 and all(c['power']==7 and c['toughness']==6 and {'Vigilance','First Strike'}<=set(c['rulesKeywords']) for c in tokens()))
        elif key=='lifegain-chain':cast(hand[0]);e.check('Three token entries resolve all eight life points each',len(tokens())==3 and e.state['life']==44)
        elif key=='court-tap':cast(hand[0]);e.check('White creature trigger taps the actual chosen opposing creature',card('Field Creeper')['tapped'])
        elif key=='mentor-draw':cast(hand[0]);e.check('Optional real one-mana payment draws one card',len(e.state['hand'])==1 and len([c for c in e.state['battlefield'] if c['tapped']])==2)
        elif key=='prava-token':activate(bf[0]);e.check('Prava creates a 1/1 token receiving +1/+4 on its controller turn',len(tokens())==1 and tokens()[0]['power']==2 and tokens()[0]['toughness']==5)
        elif key=='yes-man':
            id=card(bf[0])['forgeId'];activate(bf[0]);c=card(bf[0]);e.check('Yes Man changes control, draws two and receives one real quest counter',c['controller']==2 and len(e.state['hand'])==3 and sum(v['count'] for v in c['counters'])==1)
            cast('Disenchant',_target_policy=lambda spec,s:[next(v for v in spec['options'] if v.get('forgeId')==id)])
            e.check('Original owner receives one tapped Soldier on departure',len(tokens())==1 and tokens()[0]['tapped'])
        elif key=='nomad-mana':
            id=card('Nomad Stadium')['forgeId'];offer=next(o for o in e.state['legalManaOffers'] if o['forgeId']==id);act('activate_mana',id,abilityId=offer['abilityId']);e.check('Nomad produces white mana and deals one actual damage',e.state['manaTotal']==1 and e.state['life']==19)
        elif key=='nomad-threshold':activate('Nomad Stadium');e.check('Threshold sacrifices Stadium and gains four life',e.state['life']==24 and any(c['name']=='Nomad Stadium' for c in e.state['graveyard']))
        elif key=='myriad-search':activate('Myriad Landscape');e.check('Actual land search creates two tapped basic lands and sacrifices Myriad',len([c for c in e.state['battlefield'] if c['name']=='Plains'])==4 and any(c['name']=='Myriad Landscape' for c in e.state['graveyard']))
        elif key=='wayfarer-search':activate('Weathered Wayfarer');e.check('Wayfarer legally finds one land while behind on lands',len(e.state['hand'])==1 and e.state['hand'][0]['name']=='Plains')
        elif key=='embalm':activate('Anointer Priest');cast(hand[0]);e.check('Embalmed Priest is exiled, its actual copy gains life on each token entry',any(c['name']=='Anointer Priest' for c in e.state['exile']) and any(c.get('token') and c['name']=='Anointer Priest' for c in e.state['battlefield']) and e.state['life']==24)
        elif key in ('jade-redirect','martyr-redirect'):
            if key=='jade-redirect':activate('Jade Monolith',_target_policy=lambda spec,s:[next(v for v in spec['options'] if v.get('forgeId')==card('Savannah Lions')['forgeId'])])
            else:cast('Blood of the Martyr')
            resolve();e.check('Damage redirects to survivor, preserves creature and produces three real Soldiers',e.state['life']==17 and card('Savannah Lions')['damage']==0 and len(tokens())==3)
        elif key=='worship':cast('Lightning Bolt',_target_policy=lambda spec,s:[next(v for v in spec['options'] if v.get('targetSeat')==1)]);e.check('Worship changes resulting life loss, not the three damage counted by Darien',e.state['life']==1 and len(tokens())==3)
        elif key=='bastion-commander':
            cast('Savannah Lions');c=card('Darien, King of Kjeldor');e.check('Real commander receives +2/+2 and indestructible',c['commander'] and c['power']==5 and c['toughness']==5 and 'Indestructible' in c['rulesKeywords']);cast('Wrath of God');e.check('Wrath kills Protector but indestructible commander survives',any(c['name']=='Bastion Protector' for c in e.state['graveyard']) and card('Darien, King of Kjeldor')['commander'])
        elif key=='martial-coup':cast(hand[0]);e.check('X=5 creates five Soldiers and destroys the preexisting creatures',len(tokens())==5 and any(c['name']=='Savannah Lions' for c in e.state['graveyard']) and any(c['name']=='Field Creeper' for c in e.state['graveyard']))
        elif key=='coppercoats':cast(hand[0]);e.check('Three opposing creatures create three Human Soldiers',len(tokens())==3 and all('Human' in c['currentSubtypes'] for c in tokens()))
        elif key=='torture-chamber':
            until(lambda:any(v['count']>0 for v in card('Torture Chamber')['counters']) and e.state['phase']=='MAIN1' and e.state['activeSeat']==1);activate('Torture Chamber');e.check('Pain counter is removed as payment and deals one actual damage',not card('Torture Chamber')['counters'] and any(c['name']=='Field Creeper' for c in e.state['graveyard']))
        elif key=='barbed-wire':until(lambda:e.state['life']==19 and len(tokens())==1);e.check('Own upkeep damage creates one Soldier',len(tokens())==1)
        elif key=='angel-trumpet':until(lambda:e.state['life']==18 and len(tokens())==2);e.check('Two nonattacking creatures tap and cause two real damage',card('Darien, King of Kjeldor')['tapped'] and card('Savannah Lions')['tapped'])
        elif key=='paladin-levels':cast('Paladin Class');activate('Paladin Class');e.check('Class level two grants the original +1/+1 bonus',card('Paladin Class')['classLevel']==2 and card('Savannah Lions')['power']==3);activate('Paladin Class');e.check('Class reaches its actual third level',card('Paladin Class')['classLevel']==3)
        elif key=='suture-opponent':resolve();e.check('Opposing creature entry causes its controller to lose one life',e.state['opponentLife']==19)
        elif key=='catapult-exile':
            cast(hand[0]);activate('Catapult Master');e.check('Five Soldiers tap as the actual cost and the chosen creature is exiled',sum(c['tapped'] for c in e.state['battlefield'] if 'Soldier' in c['currentSubtypes'])==5 and any(c['name']=='Field Creeper' for c in e.state['exile']))
        elif key=='keeper-catchup':
            until(lambda:len(tokens())==1 and len([c for c in e.state['battlefield'] if c['name']=='Plains'])==2);e.check('Keeper catches up with one Soldier and one tapped Plains',len(tokens())==1 and any(c['name']=='Plains' and c['tapped'] for c in e.state['battlefield']))
        elif key=='knight-ramp':cast(hand[0]);e.check('Knight finds an untapped Plains while behind on lands',len([c for c in e.state['battlefield'] if c['name']=='Plains'])==3 and sum(not c['tapped'] for c in e.state['battlefield'] if c['name']=='Plains')==1)
        elif key=='defiler-life':cast('Ornithopter');cast('Savannah Lions');e.check('Defiler pays two life instead of white mana and creates a Soldier',e.state['life']==18 and len(tokens())==1)
        elif key=='conjurer-blink':
            cast('Savannah Lions');e.check('Creature entry causes Conjurer life gain',e.state['life']==21);id=card('Savannah Lions')['forgeId'];activate('Distinguished Conjurer');events=e.state['researchTrace'];e.check('Creature really passes through exile and returns immediately',any(v.get('kind')=='zone-change' and v.get('from')=='Battlefield' and v.get('to')=='Exile' for v in events) and any(v.get('kind')=='zone-change' and v.get('from')=='Exile' and v.get('to')=='Battlefield' for v in events));e.check('Immediate return causes a second life gain',e.state['life']==22)
        elif key=='lunarch-disturb':
            cast('Lunarch Veteran','graveyard');e.check('Disturb casts the actual flying back face',any(c['name']=='Luminous Phantom' and 'Flying' in c['rulesKeywords'] for c in e.state['battlefield']));cast('Savannah Lions');id=card('Savannah Lions')['forgeId'];cast('Swords to Plowshares',_target_policy=lambda spec,s:[next(o for o in spec['options'] if o.get('forgeId')==id)]);e.check('Phantom departure trigger and real Swords life gain resolve',e.state['life']==23)
        elif key=='jinxed-control':activate('Jinxed Idol');e.check('Sacrificing a creature transfers the actual Idol',card('Jinxed Idol')['controller']==2 and any(c['name']=='Savannah Lions' for c in e.state['graveyard']));until(lambda:e.state['opponentLife']==18);e.check('New controller receives the actual upkeep damage',e.state['opponentLife']==18)
        elif key=='diamond-mana':
            cast('Marble Diamond');e.check('Diamond enters tapped',card('Marble Diamond')['tapped']);until(lambda:not card('Marble Diamond')['tapped'] and e.state['activeSeat']==1);id=card('Marble Diamond')['forgeId'];offer=next(o for o in e.state['legalManaOffers'] if o['forgeId']==id);act('activate_mana',id,abilityId=offer['abilityId']);e.check('Diamond produces real white mana',e.state['manaTotal']==1 and e.state['mana'][0]['color']==1)
        elif key=='idol-abilities':
            cast(hand[0]);activate('Idol of Oblivion');e.check('Token-created condition enables a real card draw',len(e.state['hand'])==1);until(lambda:e.state['activeSeat']==1 and not card('Idol of Oblivion')['tapped']);activate('Idol of Oblivion');e.check('Eight mana and a real sacrifice create the 10/10 Eldrazi',any(c['name']=='Idol of Oblivion' for c in e.state['graveyard']) and any(c.get('token') and 'Eldrazi' in c['currentSubtypes'] and c['power']==10 and c['toughness']==10 for c in e.state['battlefield']))
        elif key=='well-draw':cast(hand[0]);e.check('Well spends one real mana after life gain to draw one card',e.state['life']==21 and len(e.state['hand'])==1)
        elif key=='attack-lifegain':
            cast('Revitalize');e.check('Reaching starting life activates Bravery bonus',card('Savannah Lions')['power']==3);until(lambda:e.state['life']>=28);e.check('Two white attackers cause distinct Linden, Bravery and Cause triggers',e.state['life']==28)
        e.check('No pending interaction or fidelity gap',not e.state.get('decision') and not e.state['fidelityGap'])
        return dict(case=key,passed=True,checks=e.checks,trace=trace,evidence=str(e.ipc))
    except Exception as error:return dict(case=key,passed=False,error=repr(error),traceback=traceback.format_exc(),trace=trace,evidence=str(e.ipc) if e else None,final=e.state if e else None)
    finally:
        if e:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('worker','managed','fixture','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--cases',nargs='+',default=CASES);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[]
    for k in a.cases:
        r=run(k,a);(a.out/(k+'.json')).write_text(json.dumps(r,indent=2));rows.append({k:r.get(k) for k in ('case','passed','error','evidence')});print(json.dumps({k:(v[:250] if k=='error' and v else v) for k,v in rows[-1].items()}),flush=True)
    (a.out/'report.json').write_text(json.dumps(rows,indent=2));raise SystemExit(0 if all(r['passed'] for r in rows) else 1)
