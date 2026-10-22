"""Qualify fixed creature damage independently from exact native English text."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from types import SimpleNamespace
import zipfile
from build_card_test_catalogue import parse,parameters,cost,sha
from prepare_generated_removal_batches import clean,LANDS
from clone_research_runtime import clone
from validate_card_scenario import validate


def prepare(a):
    if a.output.exists():raise ValueError('Fresh burn batch required')
    catalogue=json.loads(a.catalogue.read_text(encoding='utf8'));provenance=catalogue['provenance']
    for key,path in [('auditSha256',a.audit),('mappingsSha256',a.mappings),('databaseSha256',a.database),('scriptsSha256',a.scripts)]:
        if provenance[key]!=sha(path):raise ValueError('Source input drift: '+key)
    audit=json.loads(a.audit.read_text(encoding='utf8'));mapping=json.loads(a.mappings.read_text(encoding='utf8'))
    policy=json.loads(a.baseline_policy.read_text(encoding='utf8'));policy['researchOnly']=True
    by=defaultdict(list)
    for p in mapping['printings']:by[p['name']].append(p)
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True);texts=defaultdict(list)
    for identity,text in db.execute('SELECT a.Id,l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId WHERE l.Formatted=1'):texts[identity].append(clean(text))
    hidden=dict(db.execute('SELECT GrpId,HiddenAbilityIds FROM Cards'));db.close();proposals=[]
    with zipfile.ZipFile(a.scripts) as archive:
        for card in audit['cards']:
            if card['name'] in policy['verifiedNames'] or card['construction']!='constructed-not-playtested' or len(card['forgeScripts'])!=1:continue
            raw=archive.read(card['forgeScripts'][0]);p=parse(raw.decode('utf-8-sig'));f=p['fields']
            if hashlib.sha256(raw).hexdigest()!=card['sourceForgeScriptSha256']:raise ValueError('Script changed')
            if p['extraFaces'] or p['unknown'] or p['svars'] or any(f.get(k) for k in ('K','T','S','R')) or len(f.get('A',[]))!=1:continue
            params=parameters(f['A'][0]);predicate=params.get('ValidTgts')
            if params.get('SP')!='DealDamage' or predicate not in ('Creature','Creature.withFlying') or set(params)-{'SP','ValidTgts','NumDmg','TgtPrompt','IsCurse'}:continue
            if not params.get('NumDmg','').isdecimal() or not 1<=int(params['NumDmg'])<=9:continue
            damage=int(params['NumDmg']);phrase='creature' if predicate=='Creature' else 'creature with flying'
            expected='CARDNAME deals '+str(damage)+' damage to target '+phrase+'.'
            for printing in sorted(by[card['name']],key=lambda p:p['grpId']):
                if printing['digitalOnly'] or printing['rebalanced'] or printing['linkedFaces'] or hidden.get(printing['grpId']) or printing['supertypes'] or set(printing['types']) not in ({'Instant'},{'Sorcery'}):continue
                values=[texts[i] for i in printing['abilityIds']]
                if any(len(v)!=1 for v in values) or '\n'.join(v[0] for v in values)!=expected:continue
                mana=cost(printing);tokens=' '.join(f.get('ManaCost',[])).split()
                if not mana or not all(t.isdecimal() or t in LANDS for t in tokens) or sum(int(t) for t in tokens if t.isdecimal())!=mana['generic'] or Counter(t for t in tokens if not t.isdecimal())!=Counter(mana['symbols']) or f.get('Types')!=printing['types']:continue
                proposals.append(dict(name=card['name'],template='fixed-creature-damage-v1',printing=printing['grpId'],nativeTypes=printing['types'],nativeTexts=[expected],nativeAbilityIds=printing['abilityIds'],printedCost=mana,predicate=predicate,damage=damage,promptId=1010 if predicate=='Creature' else 1051,promptText='Target a '+phrase+'.',sourceScriptSha256=hashlib.sha256(raw).hexdigest()))
                break
    a.output.mkdir(parents=True);cards={};cases=[]
    def sel(name,owner=1,zone='Battlefield'):return dict(name=name,owner=owner,zone=zone)
    for p in proposals:
        name=p['name'];mana=p['printedCost'];symbols=mana['symbols'];lands=[LANDS[s] for s in symbols]+[LANDS[symbols[0]] if symbols else 'Plains']*mana['generic'];flying=p['predicate']=='Creature.withFlying'
        # Battlefield Raptor is a source-verified1/2 flyer; all qualified flying
        # burn deals7. Field Creeper2/1 supplies an ordinary lethal boundary.
        small='Battlefield Raptor' if flying else 'Field Creeper';large='Air Elemental' if flying else 'Gigantosaurus';branches=[];key=hashlib.sha256(name.encode()).hexdigest()[:16]
        p['happyTarget']=small
        def cast(target,expected,**extra):return dict(op='cast',card=name,mana=mana['total'],draw=0,life=0,targetPlan=dict(kind='targets',expectedOptions=expected,choose=[target],probeEmpty=True,probeStale=True),**extra)
        def damage_assert(target,zone):return dict(op='assert',damageEvents=[dict(source=sel(name,1,'Graveyard'),target=sel(target['name'],target['owner'],zone),amount=p['damage'],combat=False)])
        def case(branch,fixture,steps):
            branches.append(branch);cases.append(dict(id='burn-'+key+'-'+branch,card=name,covers=[branch],fixture=fixture,steps=steps,oracleSource=dict(printing=p['printing'],nativeDamage=p['damage'],scriptSha256=p['sourceScriptSha256']),scope='Fixed creature damage: legal targets, actual damage, lethal/nonlethal, cleanup and fizzle. Not damage prevention/replacement or all interactions.'))
        world=dict(fixtureHand=[name],fixtureLands=lands,fixtureBattlefield=[small],fixtureOpponentBattlefield=[small])
        for owner,label in [(1,'friendly-lethal'),(2,'enemy-lethal')]:
            target=sel(small,owner);case(label,world,[cast(target,[sel(small),sel(small,2)],zoneChanges=[dict(selector=target,to='Graveyard')]),damage_assert(target,'Graveyard')])
        for owner,label in [(1,'friendly-nonlethal-cleanup'),(2,'enemy-nonlethal-cleanup')]:
            target=sel(large,owner);world_large=dict(fixtureHand=([name,'Titanic Growth'] if flying else [name]),fixtureLands=(['Forest','Forest']+lands if flying else lands),**({'fixtureBattlefield':[large]} if owner==1 else {'fixtureOpponentBattlefield':[large]}))
            steps=[]
            if flying:steps.append(dict(op='cast',card='Titanic Growth',mana=2,draw=0,life=0,targetPlan=dict(kind='targets',expectedOptions=[target],choose=[target])))
            steps.extend([cast(target,[target]),dict(op='assert',objects=[dict(selector=target,values=dict(damage=p['damage']))]),damage_assert(target,'Battlefield'),dict(op='advance',phase='MAIN1',activeSeat=2,decisions=[]),dict(op='assert',objects=[dict(selector=target,values=dict(damage=0))])]);case(label,world_large,steps)
        canceled=cast(sel(small),[sel(small),sel(small,2)]);canceled['targetPlan'].pop('choose');canceled['targetPlan']['cancel']=True;case('cancel',world,[canceled])
        case('underfunded',dict(world,fixtureLands=lands[:-1]),[dict(op='deny',card=name)])
        wrong=next(c for c in LANDS if c not in symbols);case('wrong-color',dict(world,fixtureLands=[LANDS[wrong]]*mana['total']),[dict(op='deny',card=name)])
        case('combat-timing',world,[dict(op='advance',phase='COMBAT_BEGIN',activeSeat=1,decisions=[])]+([cast(sel(small,2),[sel(small),sel(small,2)],zoneChanges=[dict(selector=sel(small,2),to='Graveyard')])] if 'Instant' in p['nativeTypes'] else [dict(op='deny',card=name)]))
        target=sel(small);first=cast(target,[target],resolve=False,fizzled=True)
        case('invalidated-target',dict(fixtureHand=[name,'Unsummon'],fixtureLands=lands+['Island'],fixtureBattlefield=[small]),[first,dict(op='cast',card='Unsummon',mana=1,draw=0,life=0,targetPlan=dict(kind='targets',expectedOptions=[target],choose=[target]),zoneChanges=[dict(selector=target,to='Hand')]),dict(op='resolve',selector=sel(name,1,'Stack'))])
        if not flying:
            own=sel('Gladecover Scout');enemy=sel('Gladecover Scout',2);step=cast(own,[own],zoneChanges=[dict(selector=own,to='Graveyard')]);step['targetPlan']['invalid']=[enemy]
            case('hexproof-owner',dict(fixtureHand=[name],fixtureLands=lands,fixtureBattlefield=['Gladecover Scout'],fixtureOpponentBattlefield=['Gladecover Scout']),[step])
        cards[name]=branches;policy['verifiedNames'].append(name);policy['preferredPrintings'][name]=p['printing'];policy.setdefault('colorIdentities',{})[name]=sorted(set(symbols));policy.setdefault('targetPromptBindings',{})[name]=dict(promptId=p['promptId'],expectedText=p['promptText'])
    suite=dict(schema=2,name='Native-text fixed creature burn',cards=cards,cases=cases);validate(suite)
    for filename,data in [('qualified-research-policy.json',policy),('generated-suite.json',suite),('additional-proposals.json',dict(schema=1,provenance=provenance,qualifierSource=str(Path(__file__).resolve()),qualifierSha256=sha(Path(__file__)),proposals=proposals,newAdmissions=0))]:
        (a.output/filename).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8')
    clone(SimpleNamespace(source_config=a.source_config,source_policy=a.source_policy,qualified_policy=a.output/'qualified-research-policy.json',output=a.output/'prepared',javac=a.javac))
    result=dict(cards=len(cards),cases=len(cases),names=list(cards));(a.output/'generation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('audit','mappings','catalogue','database','scripts','source-config','source-policy','baseline-policy','output','javac'):p.add_argument('--'+key,type=Path,required=True)
    prepare(p.parse_args())
