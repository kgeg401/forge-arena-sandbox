"""Exact native/source qualification and independent creature-removal cases.

Only one unconditional Destroy or battlefield-to-Exile/Hand effect, ordinary
mana, and explicit independently interpreted creature predicates qualify.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
from types import SimpleNamespace
import zipfile
from build_card_test_catalogue import parse, parameters, cost, sha
from clone_research_runtime import clone
from validate_card_scenario import validate

LANDS={'W':'Plains','U':'Island','B':'Swamp','R':'Mountain','G':'Forest'}
PREDICATES={
    'Creature':'creature', 'Creature.toughnessGE4':'creature with toughness 4 or greater',
    'Creature.powerLE2':'creature with power 2 or less',
    'Creature.totalPT_LE5':'creature with total power and toughness 5 or less',
    'Creature.Black':'black creature', 'Creature.withoutFlying':'creature without flying',
    'Creature.nonBlack':'nonblack creature', 'Creature.nonArtifact':'nonartifact creature',
    'Creature.powerGE4':'creature with power 4 or greater', 'Creature.withFlying':'creature with flying',
    'Creature.powerLE3':'creature with power 3 or less', 'Creature.MonoColor':'monocolored creature',
    'Creature.nonMerfolk':'non-Merfolk creature', 'Creature.cmcGE3':'creature with mana value 3 or greater',
    'Creature.nonAngel+nonDemon+nonDevil+nonDragon':'non-Angel, non-Demon, non-Devil, non-Dragon creature',
}
WORLD=['Grizzly Bears','Air Elemental','Colossal Dreadmaw','Walking Corpse','Field Creeper','Mantis Rider','Coral Merfolk','Serra Angel']


def clean(text):
    return html.unescape(re.sub('<[^>]+>','',text)).replace('\\n','\n').strip()


def eligible(predicate, card):
    """Independent predicate oracle over native printing metadata, not Forge offers."""
    colors=card['colors'].split(',');subtypes=card['subtypes']
    if predicate=='Creature':return True
    if predicate=='Creature.toughnessGE4':return int(card['toughness'])>=4
    if predicate=='Creature.powerLE2':return int(card['power'])<=2
    if predicate=='Creature.totalPT_LE5':return int(card['power'])+int(card['toughness'])<=5
    if predicate=='Creature.Black':return '3' in colors
    if predicate=='Creature.nonBlack':return '3' not in colors
    if predicate=='Creature.nonArtifact':return 'Artifact' not in card['types']
    if predicate=='Creature.powerGE4':return int(card['power'])>=4
    if predicate=='Creature.powerLE3':return int(card['power'])<=3
    if predicate=='Creature.MonoColor':return len([c for c in colors if c in ('1','2','3','4','5')])==1
    if predicate=='Creature.nonMerfolk':return 'Merfolk' not in subtypes
    if predicate=='Creature.cmcGE3':return cost(card)['total']>=3
    if predicate=='Creature.nonAngel+nonDemon+nonDevil+nonDragon':return not set(subtypes)&{'Angel','Demon','Devil','Dragon'}
    if predicate in ('Creature.withFlying','Creature.withoutFlying'):
        flying='Flying' in card['_nativeTexts']
        return flying if predicate=='Creature.withFlying' else not flying
    raise ValueError('Unauthored target predicate: '+predicate)


def prepare(a):
    if a.output.exists():raise ValueError('Fresh removal batch directory required')
    base= json.loads(a.catalogue.read_text(encoding='utf8'));provenance=base['provenance']
    for key,path in [('auditSha256',a.audit),('mappingsSha256',a.mappings),('databaseSha256',a.database),('scriptsSha256',a.scripts)]:
        if provenance[key]!=sha(path):raise ValueError('Source input drift: '+key)
    audit=json.loads(a.audit.read_text(encoding='utf8'));mapping=json.loads(a.mappings.read_text(encoding='utf8'))
    source=json.loads(a.source_policy.read_text(encoding='utf8'));baseline=json.loads(a.baseline_policy.read_text(encoding='utf8'))
    if not source.get('researchOnly') or baseline.get('researchOnly'):raise ValueError('Expected research runtime and production baseline')
    # Start from the exact delivered baseline, not unrelated research candidates.
    policy=dict(baseline);policy['researchOnly']=True
    by=defaultdict(list)
    for row in mapping['printings']:by[row['name']].append(row)
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True);texts=defaultdict(list)
    for ability,text in db.execute('SELECT a.Id,l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId WHERE l.Formatted=1'):texts[ability].append(clean(text))
    hidden=dict(db.execute('SELECT GrpId,HiddenAbilityIds FROM Cards'))
    prompts=defaultdict(list)
    for identity,text in db.execute('SELECT p.Id,l.Loc FROM Prompts p JOIN Localizations_enUS l ON p.LocId=l.LocId WHERE l.Formatted=1'):prompts[clean(text)].append(identity)
    db.close();proposals=[]
    with zipfile.ZipFile(a.scripts) as archive:
        for card in audit['cards']:
            if card['name'] in baseline['verifiedNames'] or card['construction']!='constructed-not-playtested' or len(card['forgeScripts'])!=1:continue
            raw=archive.read(card['forgeScripts'][0])
            if hashlib.sha256(raw).hexdigest()!=card['sourceForgeScriptSha256']:raise ValueError('Script changed')
            parsed=parse(raw.decode('utf-8-sig'));f=parsed['fields']
            if parsed['extraFaces'] or parsed['unknown'] or parsed['svars'] or any(f.get(k) for k in ('K','T','S','R')) or len(f.get('A',[]))!=1:continue
            params=parameters(f['A'][0]);api=params.get('SP');predicate=params.get('ValidTgts')
            if api not in ('Destroy','ChangeZone') or predicate not in PREDICATES:continue
            if set(params)-{'SP','ValidTgts','TgtPrompt','Origin','Destination','IsCurse','StackDescription'}:continue
            destination='Graveyard' if api=='Destroy' else params.get('Destination')
            if api=='Destroy' and any(k in params for k in ('Origin','Destination')):continue
            if api=='ChangeZone' and (params.get('Origin')!='Battlefield' or destination not in ('Exile','Hand')):continue
            phrase=PREDICATES[predicate]
            expected=('Destroy target '+phrase+'.' if api=='Destroy' else 'Exile target '+phrase+'.' if destination=='Exile' else "Return target "+phrase+" to its owner's hand.")
            prompt='Target '+('an ' if phrase[0].lower() in 'aeiou' else 'a ')+phrase+'.'
            if len(prompts[prompt])!=1:continue
            for printing in sorted(by[card['name']],key=lambda p:p['grpId']):
                if printing['digitalOnly'] or printing['rebalanced'] or printing['linkedFaces'] or hidden.get(printing['grpId']) or printing['supertypes'] or set(printing['types']) not in ({'Instant'},{'Sorcery'}):continue
                values=[texts[i] for i in printing['abilityIds']]
                if any(len(v)!=1 for v in values) or '\n'.join(v[0] for v in values)!=expected:continue
                mana=cost(printing);tokens=' '.join(f.get('ManaCost',[])).split()
                if not mana or not all(t.isdecimal() or t in LANDS for t in tokens):continue
                if sum(int(t) for t in tokens if t.isdecimal())!=mana['generic'] or Counter(t for t in tokens if not t.isdecimal())!=Counter(mana['symbols']):continue
                if f.get('Types')!=printing['types']:continue
                proposals.append(dict(name=card['name'],template='fixed-creature-removal-v1',printing=printing['grpId'],nativeTypes=printing['types'],nativeTexts=[expected],nativeAbilityIds=printing['abilityIds'],printedCost=mana,
                    predicate=predicate,destination=destination,api=api,promptId=prompts[prompt][0],promptText=prompt,sourceScriptSha256=card['sourceForgeScriptSha256']))
                break
    native_world={}
    for name in WORLD+['Gladecover Scout']:
        card=next(p for p in by[name] if p['grpId']==baseline['preferredPrintings'][name]);card=dict(card)
        card['_nativeTexts']=[texts[i][0] for i in card['abilityIds'] if len(texts[i])==1];native_world[name]=card
    a.output.mkdir(parents=True);cases=[];cards={}
    def sel(name,owner=1,zone='Battlefield'):return dict(name=name,owner=owner,zone=zone)
    for p in proposals:
        name=p['name'];mana=p['printedCost'];symbols=mana['symbols'];lands=[LANDS[s] for s in symbols]+[LANDS[symbols[0]] if symbols else 'Plains']*mana['generic']
        good=[n for n in WORLD if eligible(p['predicate'],native_world[n])];bad=[n for n in WORLD if n not in good]
        if not good or (p['predicate']!='Creature' and not bad):raise ValueError('No positive/negative independent target boundary: '+name)
        p['happyTarget']=good[0];branches=[];key=hashlib.sha256(name.encode()).hexdigest()[:16]
        def case(branch,fixture,steps):
            branches.append(branch);cases.append(dict(id='remove-'+key+'-'+branch,card=name,covers=[branch],fixture=fixture,steps=steps,oracleSource=dict(printing=p['printing'],nativeTexts=p['nativeTexts'],predicate=p['predicate'],destination=p['destination'],scriptSha256=p['sourceScriptSha256']),scope='Exact single unconditional creature removal and explicit target predicate; no extra costs, triggers, replacements or other effects.'))
        def cast(target,expected,**extra):return dict(op='cast',card=name,mana=mana['total'],draw=0,life=0,targetPlan=dict(kind='targets',expectedOptions=expected,choose=[target],probeEmpty=True,probeStale=True),zoneChanges=[dict(selector=target,to=p['destination'])],**extra)
        world=dict(fixtureHand=[name],fixtureLands=lands,fixtureBattlefield=WORLD,fixtureOpponentBattlefield=WORLD)
        expected=[sel(n,o) for o in (1,2) for n in good]
        for owner,label in [(1,'friendly-resolution'),(2,'enemy-resolution')]:
            step=cast(sel(good[0],owner),expected)
            if bad:step['targetPlan']['invalid']=[sel(bad[0],1),sel(bad[0],2)]
            case(label,world,[step])
        canceled=cast(sel(good[0]),expected);canceled['targetPlan'].pop('choose');canceled['targetPlan']['cancel']=True
        case('cancel',world,[canceled])
        case('underfunded',dict(world,fixtureLands=lands[:-1]),[dict(op='deny',card=name)])
        wrong=next(c for c in LANDS if c not in symbols)
        case('wrong-color',dict(world,fixtureLands=[LANDS[wrong]]*mana['total']),[dict(op='deny',card=name)])
        case('combat-timing',world,[dict(op='advance',phase='COMBAT_BEGIN',activeSeat=1,decisions=[])]+([cast(sel(good[0],2),expected)] if 'Instant' in p['nativeTypes'] else [dict(op='deny',card=name)]))
        # Invalidate an already selected target with an independently cast bounce.
        target=sel(good[0]);first=cast(target,[target],resolve=False,fizzled=True);first.pop('zoneChanges')
        case('invalidated-target',dict(fixtureHand=[name,'Unsummon'],fixtureLands=lands+['Island'],fixtureBattlefield=[good[0]]),[
            first,dict(op='cast',card='Unsummon',mana=1,draw=0,life=0,targetPlan=dict(kind='targets',expectedOptions=[target],choose=[target]),zoneChanges=[dict(selector=target,to='Hand')]),dict(op='resolve',selector=sel(name,1,'Stack'))])
        if eligible(p['predicate'],native_world['Gladecover Scout']):
            own=sel('Gladecover Scout');enemy=sel('Gladecover Scout',2);step=cast(own,[own]);step['targetPlan']['invalid']=[enemy]
            case('hexproof-owner',dict(fixtureHand=[name],fixtureLands=lands,fixtureBattlefield=['Gladecover Scout'],fixtureOpponentBattlefield=['Gladecover Scout']),[step])
        cards[name]=branches;policy['verifiedNames'].append(name);policy['preferredPrintings'][name]=p['printing'];policy.setdefault('colorIdentities',{})[name]=sorted(set(symbols))
        policy.setdefault('targetPromptBindings',{})[name]=dict(promptId=p['promptId'],expectedText=p['promptText'])
    policy['candidateNames']=[n for n in policy['candidateNames'] if n not in policy['verifiedNames']]
    suite=dict(schema=2,name='Exact native creature-removal families',cards=cards,cases=cases)
    validate(suite)
    for filename,data in [('qualified-research-policy.json',policy),('generated-suite.json',suite),('additional-proposals.json',dict(schema=1,provenance=provenance,qualifierSource=str(Path(__file__).resolve()),qualifierSha256=sha(Path(__file__)),proposals=proposals,newAdmissions=0))]:
        (a.output/filename).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8')
    clone(SimpleNamespace(source_config=a.source_config,source_policy=a.source_policy,qualified_policy=a.output/'qualified-research-policy.json',output=a.output/'prepared',javac=a.javac))
    result=dict(cards=len(cards),cases=len(cases),names=list(cards));(a.output/'generation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('audit','mappings','catalogue','database','scripts','source-config','source-policy','baseline-policy','output','javac'):p.add_argument('--'+key,type=Path,required=True)
    prepare(p.parse_args())
