"""Generate narrow combat oracles from independently qualified native creatures.

No observed Forge state supplies expected damage, life, survival or stats. The
fixed opponent is an owned source-checked plain 4/4. Blocked attacking trample,
multi-block allocation and arbitrary interactions remain separate requirements.
"""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from build_card_test_catalogue import build
from clone_research_runtime import clone
from validate_card_scenario import validate

LANDS=dict(W='Plains',U='Island',B='Swamp',R='Mountain',G='Forest')


def blocking_oracle(power,toughness,keywords):
    """One blocking creature against an unmodified attacking vanilla 4/4."""
    first=bool({'First Strike','Double Strike'}&set(keywords))
    first_damage=power if first else 0
    dies_first=first_damage>0 and ('Deathtouch' in keywords or first_damage>=4)
    regular_damage=0 if dies_first else (power if not first or 'Double Strike' in keywords else 0)
    total=first_damage+regular_damage
    received=0 if dies_first else 4
    return dict(localDead=received>=toughness,opponentDead=total>0 and ('Deathtouch' in keywords or total>=4),
                localDamage=received,opponentDamage=total,lifeGain=total if 'Lifelink' in keywords else 0)


def prepare(a):
    if a.output.exists():raise ValueError('Fresh combat evidence folder required')
    a.output.mkdir(parents=True)
    build(SimpleNamespace(audit=a.audit,mappings=a.mappings,policy=a.baseline_policy,database=a.database,scripts=a.scripts,output=a.output/'qualification'))
    props=json.loads((a.output/'qualification/test-proposals.json').read_text(encoding='utf8'))['proposals']
    opponent=next(p for p in props if p['name']=='Rumbling Baloth')
    if opponent.get('oracleCharacteristics')!=dict(power=4,toughness=4) or opponent['keywords']:raise ValueError('Independent fixed opponent changed')
    props=[p for p in props if p['template']=='simple-creature-cast-v1']
    cards={};cases=[]
    def select(name,zone='Battlefield',owner=1):return dict(name=name,zone=zone,owner=owner)
    for p in props:
        name=p['name'];kw=set(p['keywords']);power=p['oracleCharacteristics']['power'];toughness=p['oracleCharacteristics']['toughness']
        if toughness<=0:raise ValueError('Zero-toughness initial combat fixture needs a separate state-based-action oracle')
        key=hashlib.sha256(name.encode()).hexdigest()[:16];branches=[]
        def add(suffix,branch,fixture,steps):
            branches.append(branch);cases.append(dict(id='combat-'+key+'-'+suffix,card=name,covers=[branch],fixture=fixture,steps=steps,
                oracleSource=dict(printing=p['printing'],nativePower=power,nativeToughness=toughness,nativeKeywords=p['keywords'],scriptSha256=p['sourceScriptSha256']),
                scope='Single creature combat and arrival timing only; blocked attacking trample, multiple recipients and arbitrary interactions remain unverified.'))
        own=select(name);enemy=select('Rumbling Baloth',owner=2)
        assignment=dict(blocker=own,attackers=[enemy]);outcome=blocking_oracle(power,toughness,kw)
        ours=select(name,'Graveyard' if outcome['localDead'] else 'Battlefield')
        theirs=select('Rumbling Baloth','Graveyard' if outcome['opponentDead'] else 'Battlefield',2)
        own_values=dict(power=power,toughness=toughness)
        if not outcome['localDead']:own_values['damage']=outcome['localDamage']
        enemy_values=dict(power=4,toughness=4)
        if not outcome['opponentDead']:enemy_values['damage']=outcome['opponentDamage']
        add('block','block-vanilla-four-four',dict(fixtureHand=[],fixtureLands=[],fixtureBattlefield=[name],fixtureOpponentBattlefield=['Rumbling Baloth'],fixtureActiveSeat=2,fixtureOpponentPolicy='attack-all'),[
            dict(op='advance',phase='MAIN2',activeSeat=2,decisions=[dict(kind='blockers',assignments=[assignment],expectedOptions=[assignment])]),
            dict(op='assert',state=dict(life=20+outcome['lifeGain'],opponentLife=20),objects=[dict(selector=ours,values=own_values),dict(selector=theirs,values=enemy_values)])])
        multiplier=2 if 'Double Strike' in kw else 1
        ready_damage=power*multiplier
        if 'Defender' not in kw:
            add('ready','ready-unblocked-attack',dict(fixtureHand=[],fixtureLands=[],fixtureBattlefield=[name],fixtureBattlefieldReady=True),[
                dict(op='advance',phase='MAIN2',activeSeat=1,decisions=[dict(kind='attackers',choose=[own],expectedOptions=[own])]),
                dict(op='assert',state=dict(life=20+(ready_damage if 'Lifelink' in kw else 0),opponentLife=20-ready_damage),objects=[dict(selector=own,values=dict(power=power,toughness=toughness,tapped='Vigilance' not in kw))])])
        mana=p['printedCost'];lands=[LANDS[s] for s in mana['symbols']]+[LANDS[mana['symbols'][0]] if mana['symbols'] else 'Plains']*mana['generic']
        hasty='Haste' in kw and 'Defender' not in kw;damage=ready_damage if hasty else 0
        add('arrival','cast-arrival-attack-timing',dict(fixtureHand=[name],fixtureLands=lands),[
            dict(op='cast',card=name,mana=mana['total'],draw=0,life=0,zone='battlefield'),
            dict(op='advance',phase='MAIN2',activeSeat=1,decisions=[dict(kind='attackers',choose=[own],expectedOptions=[own])] if hasty else []),
            dict(op='assert',state=dict(life=20+(damage if 'Lifelink' in kw else 0),opponentLife=20-damage),objects=[dict(selector=own,values=dict(power=power,toughness=toughness,tapped=hasty and 'Vigilance' not in kw))])])
        cards[name]=branches
    suite=dict(schema=2,name='Independent native-stat single-creature combat',cards=cards,cases=cases,
        scope='Native-source stat/keyword oracles for block outcomes, readied unblocked attacks and actual cast-arrival timing. Not exhaustive keyword behavior or admission.')
    validate(suite);(a.output/'generated-combat-suite.json').write_text(json.dumps(suite,indent=2,ensure_ascii=False),encoding='utf8')
    clone(SimpleNamespace(source_config=a.source_config,source_policy=a.source_policy,output=a.output/'prepared',javac=a.javac))
    receipt=dict(cards=len(cards),cases=len(cases),newAdmissions=0,provenance=opponent['sourceScriptSha256'],
        independentOracle='Native stats/keywords plus literal arithmetic for fixed 4/4 combat and unblocked attacks. No runtime outcome feeds expected values.',
        limits=['No blocked attacking trample allocation','No multi-block interactions','No native combat controls or complete games proven by generation'])
    (a.output/'generated-combat.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps(receipt))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('audit','mappings','baseline-policy','database','scripts','source-config','source-policy','output','javac'):p.add_argument('--'+key,type=Path,required=True)
    prepare(p.parse_args())
