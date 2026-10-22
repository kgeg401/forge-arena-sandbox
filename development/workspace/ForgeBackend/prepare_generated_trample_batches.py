"""Independent native-stat trample outcomes for source-qualified plain creatures.

Only initial objects are seeded. Expected phase hits, damage, life and survival
come from native stats/keywords and explicit damage choices, never observed Forge
outputs. Replacement effects, protection and nonplayer attack targets are outside
this template. Generation and passing cases never admit a card.
"""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from build_card_test_catalogue import build
from clone_research_runtime import clone
from validate_card_scenario import validate


def prepare(a):
    if a.output.exists():raise ValueError('Fresh trample evidence folder required')
    a.output.mkdir(parents=True)
    build(SimpleNamespace(audit=a.audit,mappings=a.mappings,policy=a.baseline_policy,database=a.database,scripts=a.scripts,output=a.output/'qualification'))
    proposals=json.loads((a.output/'qualification/test-proposals.json').read_text(encoding='utf8'))['proposals'];by={p['name']:p for p in proposals}
    refs=[by['Canopy Spider'],by['Giant Spider']]
    if [r['oracleCharacteristics'] for r in refs]!=[dict(power=1,toughness=3),dict(power=2,toughness=4)] or any(r['keywords']!=['Reach'] for r in refs):raise ValueError('Independent fixed reach-blocker definitions changed')
    props=[p for p in proposals if p['template']=='simple-creature-cast-v1' and 'Trample' in p['keywords']]
    cards={};cases=[]
    def select(name,zone='Battlefield',owner=1):return dict(name=name,zone=zone,owner=owner)
    player=dict(targetSeat=2)
    for p in props:
        name=p['name'];power=p['oracleCharacteristics']['power'];toughness=p['oracleCharacteristics']['toughness'];keywords=set(p['keywords'])
        key=hashlib.sha256(name.encode()).hexdigest()[:16];branches=[]
        for suffix,count,all_on_blocker in [('single-max',1,False),('single-overkill',1,True),('multiple-max',2,False)]:
            enemy=refs[:count];health=[r['oracleCharacteristics']['toughness'] for r in enemy];dead=[False]*count;events=[];decisions=[];life_gain=0;player_damage=0;incoming=0
            first=bool({'First Strike','Double Strike'}&keywords);phases=['first','normal'] if first else ['normal']
            for phase in phases:
                living=[i for i in range(count) if not dead[i]]
                retaliation=sum(enemy[i]['oracleCharacteristics']['power'] for i in living) if phase=='normal' else 0
                deals=(phase=='first' or not first or 'Double Strike' in keywords) and power>0
                if deals:
                    if living:
                        options=[select(enemy[i]['name'],owner=2) for i in living]+[player]
                        initial=[];remaining=power
                        for i in living:
                            value=min(remaining,health[i]);initial.append(value);remaining-=value
                        initial.append(remaining)
                        chosen=([power]+[0]*len(living)) if all_on_blocker else initial
                        decisions.append(dict(kind='assign_damage',total=power,expectedOptions=options,
                            expectedLethal=[dict(target=t,amount=health[i]) for t,i in zip(options,living)]+[dict(target=player,amount=0)],
                            expectedSuggestions=[dict(target=t,amount=n) for t,n in zip(options,initial)],
                            allocations=[dict(target=t,amount=n) for t,n in zip(options,chosen)]))
                        for i,amount in zip(living,chosen):
                            if amount:events.append(dict(index=i,amount=amount))
                            health[i]-=amount
                        excess=chosen[-1]
                    else:excess=power
                    if excess:events.append(dict(index='player',amount=excess))
                    player_damage+=excess
                    if 'Lifelink' in keywords:life_gain+=power
                for i in range(count):dead[i]=health[i]<=0
                if phase=='normal':incoming=retaliation
            own_dead=incoming>=toughness;own=select(name,'Graveyard' if own_dead else 'Battlefield')
            own_values=dict(p['oracleCharacteristics'])
            if not own_dead:own_values['damage']=incoming
            objects=[dict(selector=own,values=own_values)];final_targets={}
            for i,r in enumerate(enemy):
                target=select(r['name'],'Graveyard' if dead[i] else 'Battlefield',2);final_targets[i]=target
                values=dict(r['oracleCharacteristics'])
                if not dead[i]:values['damage']=r['oracleCharacteristics']['toughness']-health[i]
                objects.append(dict(selector=target,values=values))
            damage=[dict(source=own,target=player if row['index']=='player' else final_targets[row['index']],amount=row['amount']) for row in events]
            branch='trample-'+suffix;branches.append(branch)
            steps=[dict(op='advance',phase='MAIN2',activeSeat=1,decisions=[dict(kind='attackers',choose=[select(name)],expectedOptions=[select(name)]),*decisions]),
                dict(op='assert',state=dict(life=20+life_gain,opponentLife=20-player_damage),objects=objects,damageEvents=damage)]
            cases.append(dict(id='trample-'+key+'-'+suffix,card=name,covers=[branch],fixture=dict(fixtureHand=[],fixtureLands=[],fixtureBattlefield=[name],fixtureBattlefieldReady=True,fixtureOpponentBattlefield=[r['name'] for r in enemy],fixtureOpponentPolicy='block-all'),steps=steps,
                oracleSource=dict(printing=p['printing'],sourceScriptSha256=p['sourceScriptSha256'],nativeStats=p['oracleCharacteristics'],nativeKeywords=p['keywords']),
                scope='Literal source-qualified creature against fixed reach blockers; explicit max-player or zero-player allocations. Not arbitrary combat or admission.'))
        cards[name]=branches
    suite=dict(schema=2,name='Independent native-stat trample allocations',cards=cards,cases=cases,scope='Single/multiple fixed reach blockers, explicit allocations, phase damage, life and survival. No replacement/protection/planeswalker/battle/banding claim.')
    validate(suite);(a.output/'generated-suite.json').write_text(json.dumps(suite,indent=2,ensure_ascii=False),encoding='utf8')
    clone(SimpleNamespace(source_config=a.source_config,source_policy=a.source_policy,output=a.output/'prepared',javac=a.javac))
    receipt=dict(cards=len(cards),cases=len(cases),newAdmissions=0,independentOracle='Requalified native stats/keywords, explicit allocations, first/regular combat-step arithmetic; no observed outcomes feed expectations.')
    (a.output/'generation.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps(receipt))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('audit','mappings','baseline-policy','database','scripts','source-config','source-policy','output','javac'):p.add_argument('--'+key,type=Path,required=True)
    prepare(p.parse_args())
