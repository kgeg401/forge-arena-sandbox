"""Specific top-viewed Commander interactions through original native handlers.

Only initial zones and explicit player choices are fixtures. Resolution, costs,
stack copies, combat and wins execute in Forge. No blanket card certification.
"""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

CASES=('oracle-pact','storm-freeze','breach-freeze','winota-historian','bowmasters-draw','delney-tataru','oltec-copy','powerbalance-match','powerbalance-mismatch','krrik-life','krrik-mana','krrik-insufficient','krrik-mixed','krrik-cancel','krrik-normal-cancel','tax-rhystic','tax-remora','tax-sentinel','tax-combined','force-will-alternate','beseech-bargain','one-ring-cycle','ring-protection','mana-vault-upkeep')

def run(a,key):
    e=None;trace=[];mode_count=0;life_choices=0;cancel_stage=False
    settings=dict(fixtureHand=[],fixtureLands=['Island']*4+['Swamp']*4+['Mountain']*4+['Plains']*4+['Forest']*4,
                  fixtureBattlefield=[],fixtureOpponentBattlefield=[],fixtureBattlefieldReady=True,
                  fixtureLibrary=['Forest','Island','Mountain','Swamp','Plains']+['Forest']*15)
    if key=='oracle-pact':settings.update(fixtureHand=["Thassa's Oracle",'Tainted Pact'],fixtureLibrary=['Forest','Island','Mountain','Swamp','Plains'])
    elif key=='storm-freeze':settings.update(fixtureHand=['Dark Ritual','Brain Freeze'])
    elif key=='breach-freeze':settings.update(fixtureHand=['Underworld Breach'],fixtureGraveyard=['Brain Freeze','Forest','Island','Swamp','Mountain','Plains','Sol Ring'])
    elif key=='winota-historian':settings.update(fixtureBattlefield=['Winota, Joiner of Forces','Ornithopter'],fixtureLibrary=['Gingerbrute','Blade Historian','Field Creeper','Forest','Island','Mountain']+['Plains']*15)
    elif key=='bowmasters-draw':settings.update(fixtureBattlefield=['Orcish Bowmasters'],fixtureOpponentSpell='Divination',fixtureOpponentLands=['Island']*3)
    elif key.startswith('tax-'):
        sources={'tax-rhystic':['Rhystic Study'],'tax-remora':['Mystic Remora'],'tax-sentinel':['Esper Sentinel'],'tax-combined':['Rhystic Study','Mystic Remora','Esper Sentinel']}[key]
        settings.update(fixtureBattlefield=sources,fixtureOpponentSpell='Divination',fixtureOpponentLands=['Island']*3)
    elif key=='force-will-alternate':settings.update(fixtureHand=['Force of Will','Opt'],fixtureLands=[],fixtureOpponentSpell='Divination',fixtureOpponentLands=['Island']*3)
    elif key=='beseech-bargain':settings.update(fixtureHand=['Beseech the Mirror'],fixtureLands=['Swamp']*4,fixtureBattlefield=['Ornithopter'],fixtureLibrary=['Orcish Bowmasters','Forest','Island','Plains','Mountain']*4)
    elif key=='one-ring-cycle':settings.update(fixtureHand=['The One Ring'],fixtureLands=['Island']*4)
    elif key=='ring-protection':settings.update(fixtureHand=['Lightning Bolt'],fixtureLands=['Mountain'],fixtureOpponentSpell='The One Ring',fixtureOpponentLands=['Island']*4,fixtureOpponentBattlefield=['Grizzly Bears'])
    elif key=='mana-vault-upkeep':settings.update(fixtureHand=['Mana Vault'],fixtureLands=['Island']*4)
    elif key=='delney-tataru':settings.update(fixtureBattlefield=['Delney, Streetwise Lookout'],fixtureHand=['Tataru Taru'])
    elif key=='oltec-copy':settings.update(fixtureBattlefield=['Delney, Streetwise Lookout','Oltec Matterweaver'],fixtureHand=['Ornithopter','Ornithopter'])
    elif key.startswith('powerbalance-'):settings.update(fixtureLands=[],fixtureBattlefield=['Powerbalance'],fixtureLibrary=['Divination' if key.endswith('match') and not key.endswith('mismatch') else 'Dark Ritual','Forest','Island','Plains'],fixtureOpponentSpell='Divination',fixtureOpponentLands=['Island']*3)
    elif key.startswith('krrik-'):
        settings.update(fixtureHand=["K'rrik, Son of Yawgmoth",'Dark Ritual'],fixtureLands=['Forest']*4+(['Swamp']*4 if key=='krrik-mana' else []))
        if key=='krrik-insufficient':settings['fixtureLocalLife']=5
        if key in ('krrik-mixed','krrik-cancel'):settings['fixtureHand']=["K'rrik, Son of Yawgmoth",'Necropotence']
        if key=='krrik-mixed':settings.update(fixtureLocalLife=9,fixtureLands=['Forest']*4+['Swamp']*2)
    def choices(c,s):
        nonlocal mode_count,life_choices
        typ=c['type'];opts=c.get('options',[])
        if typ=='confirm':
            if key in ('krrik-cancel','krrik-normal-cancel') and cancel_stage and c.get('context')=='life-payment':
                life_choices+=1;return [dict(accept=life_choices==1)]
            return [dict(accept=key in ('winota-historian','krrik-life','krrik-mixed','krrik-cancel','krrik-normal-cancel','force-will-alternate','beseech-bargain') or key.startswith(('powerbalance-','tax-')))]
        if key=='beseech-bargain' and typ=='optional-costs':return [dict(choiceId=v['choiceId']) for v in opts if 'Bargain' in v.get('label','')]
        if key in ('force-will-alternate','beseech-bargain') and typ in ('cards-zone','cards-effect','entities'):
            wanted='Opt' if key=='force-will-alternate' else 'Ornithopter' if any(v.get('label')=='Ornithopter' for v in opts) else 'Orcish Bowmasters'
            return [dict(choiceId=next(v['choiceId'] for v in opts if v.get('label')==wanted))]
        if key=='oltec-copy' and typ=='modes':
            phrase='Create a 1/1' if mode_count==0 else "copy of target";mode_count+=1
            return [dict(choiceId=next(v['choiceId'] for v in opts if phrase in v.get('label','')))]
        if typ in ('cards-zone','cards-effect','entities'):
            if key=='oracle-pact':return []
            if key=='winota-historian':
                picked=[v for v in opts if v.get('label')=='Blade Historian']
                if picked:return [dict(choiceId=picked[0]['choiceId'])]
            if key=='breach-freeze' and c.get('min',0)==3:return [dict(choiceId=v['choiceId']) for v in opts[:3]]
        return None
    def targets(d,s):
        if key=='ring-protection':
            e.check('Actual Ring protection excludes the opposing player from legal targets',not any(v.get('targetSeat')==2 for v in d['options']))
            ids={c['forgeId'] for c in s['battlefield'] if c['name']=='Grizzly Bears' and c['controller']==2}
            return [v for v in d['options'] if v['forgeId'] in ids][:d['minTargets']]
        if key in ('force-will-alternate','beseech-bargain'):
            if key=='force-will-alternate':
                ids={c['forgeId'] for c in s['stack'] if c['name']=='Divination' and c['owner']==2}
                return [v for v in d['options'] if v['forgeId'] in ids][:d['minTargets']]
            return [v for v in d['options'] if v.get('targetSeat')==2][:d['minTargets']]
        if key=='oltec-copy':
            ids={c['forgeId'] for c in s['battlefield'] if c.get('token') and 'Gnome' in c['currentSubtypes']}
            return [v for v in d['options'] if v['forgeId'] in ids][:1]
        return [v for v in d['options'] if v.get('targetSeat')==2][:d['minTargets']]
    def attackers(d,s):
        bodies={c['forgeId']:c['name'] for c in s['battlefield']}
        return [dict(forgeId=v['forgeId'],targetSeat=2) for v in d['options'] if bodies.get(v['forgeId'])=='Ornithopter']
    def act(op,id=0,**kw):return execute(e,trace,op,id,_choice_policy=choices,_target_policy=targets,_attack_policy=attackers,**kw)
    def settle():
        for _ in range(45):
            if e.state['gameOver'] or not e.state['stackOrder']:return
            act('pass_priority')
        raise AssertionError('Stack exceeded45 controller boundaries')
    def spell(name,zone='hand'):
        id=next(c['forgeId'] for c in e.state[zone] if c['name']==name and c['owner']==1)
        e.check('The real native cast is legally available: '+name,id in e.state['legalCasts'])
        act('cast_spell',id);return id
    def library(seat):return [c['forgeId'] for c in e.state['hidden'] if c['owner']==seat and c['zone']=='Library']
    try:
        if key=='krrik-normal-cancel':
            # A normal shuffled Commander game exercises playChosenSpellAbility;
            # the other cases deliberately test only the card-family handler.
            deck=dict(name='Normal Krrik cancellation validation',format='commander-40',experimental=True,commander=dict(name="K'rrik, Son of Yawgmoth",count=1),cards=[dict(name='Swamp',count=98),dict(name='Necropotence',count=1)])
            opponent=dict(name='Passive validation mana deck',format='commander-40',experimental=True,commander=dict(name='Isamaru, Hound of Konda',count=1),cards=[dict(name='Plains',count=99)])
            e=NativeEngine('commander-duel',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=14,localDeck=deck,opponentDeck=opponent,startingPlayerPolicy='local-first')
        else:e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,**settings)
        before=library(2);local_before=library(1)
        if key=='krrik-normal-cancel':
            for _ in range(180):
                d=e.state.get('decision') or {}
                if d.get('kind')=='mulligan':act('submit_mulligan',decisionToken=d['token'],assignments=[dict(keep=True)]);continue
                commander=next((c for c in e.state['command'] if c['name']=="K'rrik, Son of Yawgmoth"),None)
                lands=[c for c in e.state['battlefield'] if c['name']=='Swamp']
                if e.state['activeSeat']==1 and e.state['phase']=='MAIN1':
                    if len(lands)>=4 and commander and commander['forgeId'] in e.state['legalCasts']:break
                    if e.state['landsPlayed']==0:
                        land=next((c for c in e.state['hand'] if c['name']=='Swamp'),None)
                        if land:act('play_land',land['forgeId']);continue
                act('pass_priority')
            else:raise AssertionError('Normal game did not reach the fourth real land drop')
            e.check('Known shuffled native opening provides the cancellation spell',any(c['name']=='Necropotence' for c in e.state['hand']))
            before_life=e.state['life'];spell("K'rrik, Son of Yawgmoth",'command');settle();cancel_stage=True
            e.check('Commander actually used four lands and six life in the normal turn loop',e.state['life']==before_life-6 and len([c for c in e.state['battlefield'] if c['name']=='Swamp' and c['tapped']])==4)
            before_life=e.state['life'];spell('Necropotence')
            e.check('Normal controller acknowledges cancellation and preserves the exact life total',e.state['life']==before_life and any(c['name']=='Necropotence' for c in e.state['hand']) and not e.state['stackOrder'])
            replies=[json.loads(p.read_text()) for p in (e.ipc/'responses').glob('*.json')]
            e.check('Normal controller produced no failed native response',all(v['accepted'] for v in replies))
        elif key=='oracle-pact':
            oracle=spell("Thassa's Oracle");act('pass_priority')
            e.check('Real Oracle enters with its triggered ability still on the stack',any(c['forgeId']==oracle for c in e.state['battlefield']) and any(v['sourceForgeId']==oracle for v in e.state['stackAbilities']))
            spell('Tainted Pact');act('pass_priority')
            e.check('Pact actually exiles the complete five-card library before the Oracle trigger',not library(1) and set(local_before)<={c['forgeId'] for c in e.state['exile']} and not e.state['gameOver'])
            settle();e.check('The original Oracle trigger wins the native game',e.state['gameOver'] and e.state['winnerSeat']==1)
        elif key=='storm-freeze':
            spell('Dark Ritual');settle();e.check('The real Ritual produces three black mana',e.state['manaTotal']==3)
            spell('Brain Freeze');settle()
            e.check('One prior cast creates one storm copy, milling exactly six original cards',library(2)==before[6:] and set(before[:6])<={c['forgeId'] for c in e.state['graveyard'] if c['owner']==2})
            e.check('Storm copies do not pay or cast the original Ritual again',len([c for c in e.state['graveyard'] if c['name']=='Dark Ritual'])==1)
        elif key=='breach-freeze':
            frozen=next(c['forgeId'] for c in e.state['graveyard'] if c['name']=='Brain Freeze')
            fuel={c['forgeId'] for c in e.state['graveyard'] if c['forgeId']!=frozen}
            e.check('Brain Freeze has no escape before Breach actually resolves',frozen not in e.state['legalCasts'])
            spell('Underworld Breach');settle()
            # Breach itself was cast first: two Freeze resolutions, then three.
            for count,expected_mill in ((1,6),(2,15)):
                e.check('Escape is a real currently offered graveyard cast '+str(count),frozen in e.state['legalCasts'])
                spell('Brain Freeze','graveyard');settle()
                exiled={c['forgeId'] for c in e.state['exile']}
                e.check('Each actual escape exiles exactly three other original cards '+str(count),len(fuel&exiled)==count*3)
                e.check('Escaped spell and its storm copies mill the exact expected library prefix '+str(count),library(2)==before[expected_mill:])
            e.check('With no other graveyard fuel a third escape is unavailable',frozen not in e.state['legalCasts'])
        elif key=='winota-historian':
            expected=local_before[1]
            for _ in range(75):
                if e.state['phase']=='MAIN2':break
                act('pass_priority')
            else:raise AssertionError('Winota combat did not reach MAIN2')
            historian=next(c for c in e.state['battlefield'] if c['forgeId']==expected)
            e.check('Winota places the original chosen Human directly from the top six',historian['name']=='Blade Historian' and historian['tapped'])
            hits=[v for v in e.state['events'] if v['kind']=='damage' and v.get('sourceForgeId')==expected and v.get('combat')]
            e.check('The newly attacking Human deals two real double-strike hits',len(hits)==2 and sum(v['amount'] for v in hits)==4 and e.state['opponentLife']==16)
            e.check('Winota grants the arriving Human real indestructible until end of turn','Indestructible' in historian['rulesKeywords'])
        elif key=='mana-vault-upkeep':
            vault=spell('Mana Vault');settle();offer=next(v for v in e.state['legalManaOffers'] if v['forgeId']==vault)
            act('activate_mana',vault,abilityId=offer['abilityId'])
            e.check('Original Vault taps for exactly three colorless mana',e.state['manaTotal']==3 and next(c for c in e.state['battlefield'] if c['forgeId']==vault)['tapped'])
            turn=e.state['turn']
            for _ in range(120):
                if e.state['turn']>turn and e.state['life']==19 and not e.state['stackOrder']:break
                act('pass_priority')
            else:raise AssertionError('Unpaid Vault did not reach its next draw-step damage')
            e.check('Declining real upkeep leaves Vault tapped through the untap step',next(c for c in e.state['battlefield'] if c['forgeId']==vault)['tapped'])
            e.check('The original delayed Vault trigger deals one real damage',any(v['kind']=='damage' and v.get('sourceForgeId')==vault and v.get('amount')==1 for v in e.state['events']))
        elif key=='ring-protection':
            settle();e.check('Opposing Ring was really cast and resolved before testing protection',any(c['name']=='The One Ring' and c['owner']==2 for c in e.state['battlefield']))
            spell('Lightning Bolt');settle()
            e.check('Protection of the player does not protect their unrelated creature',e.state['opponentLife']==20 and any(c['name']=='Grizzly Bears' and c['owner']==2 for c in e.state['graveyard']))
        elif key=='one-ring-cycle':
            ring=spell('The One Ring');settle()
            for count in (1,2):
                before_library=library(1);ability=next(v for v in e.state['legalActivations'] if v['forgeId']==ring)
                act('activate_ability',ring,abilityId=ability['abilityId']);settle()
                current=next(c for c in e.state['battlefield'] if c['forgeId']==ring)
                e.check('Ring accumulates real burden and draws its exact prefix '+str(count),sum(v['count'] for v in current['counters'] if v['type']=='BURDEN')==count and library(1)==before_library[count:])
                expected=e.state['life']-count;turn=e.state['turn']
                for _ in range(120):
                    if e.state['turn']>turn and e.state['life']==expected and any(v['forgeId']==ring for v in e.state['legalActivations']):break
                    act('pass_priority')
                else:raise AssertionError('Ring did not reach next real untap/upkeep life loss')
                e.check('Original next upkeep loses life equal to burden '+str(count),e.state['life']==expected)
        elif key=='force-will-alternate':
            original=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Opt');spell('Force of Will');settle()
            e.check('Original alternate cost pays exactly one life and exiles the chosen original blue card',e.state['life']==19 and any(c['forgeId']==original for c in e.state['exile']) and not any(c['controller']==1 for c in e.state['battlefield']) and e.state['manaTotal']==0)
            e.check('Real opposing spell is countered before any of its draw occurs',library(2)==before and any(c['name']=='Divination' and c['owner']==2 for c in e.state['graveyard']) and any(v['kind']=='countered' for v in e.state['events']))
        elif key=='beseech-bargain':
            fodder=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Ornithopter');spell('Beseech the Mirror');settle()
            e.check('Bargain sacrifices the real original artifact',any(c['forgeId']==fodder for c in e.state['graveyard']) and not any(c['forgeId']==fodder for c in e.state['battlefield']))
            e.check('Actual bargained tutor free-casts Bowmasters and resolves its own ETB',any(c['name']=='Orcish Bowmasters' for c in e.state['battlefield']) and any(c.get('token') and 'Army' in c['currentSubtypes'] for c in e.state['battlefield']) and e.state['opponentLife']==19 and all(c['tapped'] for c in e.state['battlefield'] if c['name']=='Swamp'))
        elif key.startswith('tax-'):
            hand_before={c['forgeId'] for c in e.state['hand']};settle();count=3 if key=='tax-combined' else 1
            e.check('Each original unpaid tax trigger draws its exact library prefix',library(1)==local_before[count:] and {c['forgeId'] for c in e.state['hand']}-hand_before==set(local_before[:count]))
            e.check('The opposing spell still resolves its own exact two-card draw',library(2)==before[2:])
            e.check('Tax enchantments and creature retain their original identities',all(any(c['name']==name and c['controller']==1 for c in e.state['battlefield']) for name in sources))
        elif key=='bowmasters-draw':
            settle()
            army=[c for c in e.state['battlefield'] if c.get('token') and 'Army' in c['currentSubtypes']]
            e.check('Divination really draws the original top two opposing cards',library(2)==before[2:])
            e.check('Two original Bowmasters triggers each deal one selected damage',e.state['opponentLife']==18)
            e.check('The same real Orc Army accumulates both amass counters',len(army)==1 and army[0]['power']==army[0]['toughness']==2)
        elif key=='delney-tataru':
            spell('Tataru Taru');settle()
            e.check('Delney doubles the original Tataru entry draw into the exact next two cards',{c['forgeId'] for c in e.state['hand']}==set(local_before[:2]))
            e.check('The opponent receives both chosen entry draws',library(2)==before[2:])
            treasure=[c for c in e.state['battlefield'] if c.get('token') and 'Treasure' in c['currentSubtypes']]
            # Delney adds triggers, not copies; "only once" still prohibits a second.
            e.check('Scions retains its once-per-turn limit despite Delney and two draws',len(treasure)==1 and treasure[0]['tapped'])
        elif key=='oltec-copy':
            spell('Ornithopter');settle()
            initial=[c for c in e.state['battlefield'] if c.get('token') and 'Gnome' in c['currentSubtypes']]
            e.check('With no artifact target the first cast correctly forces two Gnome modes',len(initial)==2 and mode_count==0)
            spell('Ornithopter');settle()
            gnomes=[c for c in e.state['battlefield'] if c.get('token') and 'Gnome' in c['currentSubtypes']]
            e.check('Doubled Oltec triggers retain two distinct real mode choices',mode_count==2)
            e.check('The second cast creates one Gnome and copies a legally pre-existing artifact token',len(gnomes)==4 and all(c['power']==c['toughness']==1 and 'Artifact' in c['currentTypes'] for c in gnomes))
            e.check('Both original creatures resolve after their respective cast triggers',sum(c['name']=='Ornithopter' and not c.get('token') for c in e.state['battlefield'])==2)
        elif key.startswith('powerbalance-'):
            settle();matched=key=='powerbalance-match'
            own_casts=[v for v in e.state['researchTrace'] if v['kind']=='zone-change' and v.get('from')=='Library' and v.get('to')=='Stack' and v.get('forgeId')==local_before[0]]
            e.check('Only matching mana value casts the original revealed library card',len(own_casts)==(1 if matched else 0))
            e.check('The original opposing Divination resolves and draws its own two cards',library(2)==before[2:])
            e.check('Free cast needs no substituted mana or payment',e.state['manaTotal']==0 and not any('Land' in c['currentTypes'] and c['controller']==1 for c in e.state['battlefield']))
            if matched:e.check('The real free Divination draws the next two library identities',{c['forgeId'] for c in e.state['hand']}==set(local_before[1:3]))
            else:e.check('A mismatching revealed card stays at the same library position',library(1)==local_before and not e.state['hand'])
        elif key=='krrik-insufficient':
            id=next(c['forgeId'] for c in e.state['hand'] if c['name']=="K'rrik, Son of Yawgmoth")
            e.check('Five life cannot pay the three real two-life phyrexian symbols',id not in e.state['legalCasts'])
            e.check('Availability probing spends no life or lands',e.state['life']==5 and all(not c['tapped'] for c in e.state['battlefield']))
        elif key in ('krrik-mixed','krrik-cancel'):
            if key=='krrik-mixed':
                for forest in [c for c in e.state['battlefield'] if c['name']=='Forest']:
                    offer=next(v for v in e.state['legalManaOffers'] if v['forgeId']==forest['forgeId']);act('activate_mana',forest['forgeId'],abilityId=offer['abilityId'])
            id=spell("K'rrik, Son of Yawgmoth");settle();cancel_stage=True
            e.check('Initial Krrik paid exactly six life',e.state['life']==(3 if key=='krrik-mixed' else 14))
            necro=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Necropotence')
            if key=='krrik-mixed':
                spell('Necropotence');settle()
                e.check('Mixed black payment uses two real Swamps and exactly two life',e.state['life']==1 and sum(c['name']=='Swamp' and c['tapped'] for c in e.state['battlefield'])==2 and any(c['forgeId']==necro for c in e.state['battlefield']))
            else:
                try:spell('Necropotence')
                except RuntimeError as error:
                    if 'canceled' not in str(error).lower():raise
                e.check('Declining the remaining black payments cancels the spell',any(c['forgeId']==necro for c in e.state['hand']) and not e.state['stackOrder'])
                e.check('Incomplete mana payment cannot consume the tentative first two life',e.state['life']==14)
                replies=[json.loads(p.read_text()) for p in (e.ipc/'responses').glob('*.json')]
                e.check('Explicit mana cancellation is acknowledged without a rejected native action',any(v['accepted'] and v.get('reason')=='Controller canceled pending cast during mana payment' for v in replies) and all(v['accepted'] for v in replies))
        elif key.startswith('krrik-'):
            id=spell("K'rrik, Son of Yawgmoth");settle();life=14 if key=='krrik-life' else 20
            e.check('Three printed phyrexian symbols use the chosen real life or mana payment',e.state['life']==life)
            spell('Dark Ritual');settle();krrik=next(c for c in e.state['battlefield'] if c['forgeId']==id)
            e.check('Krrik permits ordinary black costs to use life only when chosen',e.state['life']==(12 if key=='krrik-life' else 20))
            e.check('The actual black-spell trigger adds one counter and Ritual produces three mana',krrik['power']==krrik['toughness']==3 and sum(v['count'] for v in krrik['counters'] if v['type']=='P1P1')==1 and e.state['manaTotal']==3)
        e.check('No unsupported callback, orphaned chooser or dead rules owner',not e.state['fidelityGap'] and not e.state.get('decision') and e.process.poll() is None)
        result=dict(case=key,passed=True,checks=e.checks,evidence=str(e.ipc))
    except Exception as error:result=dict(case=key,passed=False,error=repr(error)[:1800],traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
    (a.output/(key+'.json')).write_text(json.dumps(result,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps({k:result.get(k) for k in ('case','passed','error','evidence')}),flush=True)
    return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--case',choices=CASES,action='append');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    passed=[run(a,key) for key in (a.case or CASES)];raise SystemExit(0 if all(passed) else 1)
