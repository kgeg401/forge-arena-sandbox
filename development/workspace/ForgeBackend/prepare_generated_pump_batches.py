"""Source-qualified, single-target temporary pumps; never playable admission.

Reads independent native English deltas, costs and exact Forge definitions.
Rejects added keywords, conditions, subabilities, faces and hidden/digital cards.
Expected target stats and cleanup expiration are authored before any game runs.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
from types import SimpleNamespace
import zipfile
from build_card_test_catalogue import parse,parameters,cost,sha
from clone_research_runtime import clone
from run_card_batches import validate

LANDS={'W':'Plains','U':'Island','B':'Swamp','R':'Mountain','G':'Forest'}


def native_pump(texts):
    text=html.unescape(re.sub('<[^>]+>','','\n'.join(texts))).replace('\\n','\n').strip()
    match=re.fullmatch(r'Target creature gets \+([1-9][0-9]?)/\+([1-9][0-9]?) until end of turn\.',text)
    return dict(power=int(match[1]),toughness=int(match[2])) if match else None


def forge_pump(parsed):
    fields=parsed['fields']
    if parsed['extraFaces'] or parsed['unknown'] or parsed['svars'] or any(fields.get(k) for k in ('K','T','S','R')) or len(fields.get('A',[]))!=1:return None
    p=parameters(fields['A'][0])
    if set(p)!={'SP','ValidTgts','NumAtt','NumDef'} or p['SP']!='Pump' or p['ValidTgts']!='Creature':return None
    if not re.fullmatch(r'\+[1-9][0-9]?',p['NumAtt']) or not re.fullmatch(r'\+[1-9][0-9]?',p['NumDef']):return None
    return dict(power=int(p['NumAtt']),toughness=int(p['NumDef']))


def prepare(a):
    if a.output.exists():raise ValueError('Fresh pump evidence folder required')
    audit=json.loads(a.audit.read_text(encoding='utf8'));mappings=json.loads(a.mappings.read_text(encoding='utf8'))
    base=json.loads(a.catalogue.read_text(encoding='utf8'));provenance=base['provenance']
    if provenance['auditSha256']!=sha(a.audit) or provenance['mappingsSha256']!=sha(a.mappings) or provenance['databaseSha256']!=sha(a.database) or provenance['scriptsSha256']!=sha(a.scripts):raise ValueError('Pinned source inputs differ')
    source_policy=json.loads(a.source_policy.read_text(encoding='utf8'))
    if not source_policy.get('researchOnly'):raise ValueError('Independent research policy required')
    by=defaultdict(list)
    for row in mappings['printings']:by[row['name']].append(row)
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True);texts={}
    for ability,text in db.execute('SELECT a.Id,l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId WHERE l.Formatted=1'):texts.setdefault(ability,[]).append(text)
    hidden=dict(db.execute('SELECT GrpId,HiddenAbilityIds FROM Cards'));db.close();proposals=[]
    with zipfile.ZipFile(a.scripts) as archive:
        for card in audit['cards']:
            if card['construction']!='constructed-not-playtested' or len(card['forgeScripts'])!=1:continue
            raw=archive.read(card['forgeScripts'][0])
            if hashlib.sha256(raw).hexdigest()!=card['sourceForgeScriptSha256']:raise ValueError('Source definition changed')
            parsed=parse(raw.decode('utf-8-sig'));source=forge_pump(parsed)
            if not source:continue
            eligible=[p for p in by[card['name']] if not p['digitalOnly'] and not p['rebalanced'] and not p['linkedFaces'] and not hidden.get(p['grpId']) and set(p['types']) in ({'Instant'},{'Sorcery'}) and not p['supertypes']]
            for printing in sorted(eligible,key=lambda p:(p['grpId']!=source_policy.get('preferredPrintings',{}).get(card['name']),p['grpId'])):
                values=[texts.get(i,[]) for i in printing['abilityIds']]
                if any(len(v)!=1 for v in values):continue
                native=[v[0] for v in values];oracle=native_pump(native);mana=cost(printing);tokens=' '.join(parsed['fields'].get('ManaCost',[])).split()
                if not oracle or oracle!=source or not mana or not all(t.isdecimal() or t in LANDS for t in tokens):continue
                if sum(int(t) for t in tokens if t.isdecimal())!=mana['generic'] or Counter(t for t in tokens if not t.isdecimal())!=Counter(mana['symbols']):continue
                if parsed['fields'].get('Types')!=printing['types']:continue
                proposals.append(dict(name=card['name'],template='fixed-target-pump-v1',printing=printing['grpId'],nativeTypes=printing['types'],nativeTexts=native,nativeAbilityIds=printing['abilityIds'],printedCost=mana,
                    oracleDelta=oracle,sourceScriptSha256=card['sourceForgeScriptSha256'],status='source-qualified-proposal-not-executed',remainingGates=['target ownership/hexproof and cancellation','actual cost/timing','resolution and target invalidation','cleanup expiration','original native controls/assets','complete shuffled matches','interaction review']))
                break
    if not proposals:raise ValueError('No exact independent native/source pump pairs')
    a.output.mkdir(parents=True);cards={};cases=[]
    def sel(name='Grizzly Bears',owner=1,zone='Battlefield'):return dict(name=name,owner=owner,zone=zone)
    for p in proposals:
        name=p['name'];key=hashlib.sha256(name.encode()).hexdigest()[:16];mana=p['printedCost'];symbols=mana['symbols'];filler=LANDS[symbols[0]] if symbols else 'Plains'
        lands=[LANDS[s] for s in symbols]+[filler]*mana['generic'];delta=p['oracleDelta'];branches=[]
        def cast(target,expected,**extra):return dict(op='cast',card=name,mana=mana['total'],draw=0,life=0,targetPlan=dict(kind='targets',expectedOptions=expected,choose=[target],probeEmpty=True,probeStale=True),**extra)
        def stats(target,buffed):return dict(op='assert',objects=[dict(selector=target,values=dict(power=2+(delta['power'] if buffed else 0),toughness=2+(delta['toughness'] if buffed else 0)))])
        def case(branch,fixture,steps):
            branches.append(branch);cases.append(dict(id='pump-'+key+'-'+branch,card=name,covers=[branch],fixture=fixture,steps=steps,oracleSource=dict(printing=p['printing'],nativeDelta=delta,scriptSha256=p['sourceScriptSha256']),scope='Exact fixed single-target temporary pump only. No keyword additions, layers with other modifiers, digital variants or automatic admission.'))
        for owner,label in ((1,'friendly-expiration'),(2,'enemy-expiration')):
            f=dict(fixtureHand=[name],fixtureLands=lands,fixtureBattlefield=['Grizzly Bears'],fixtureOpponentBattlefield=['Grizzly Bears'])
            target=sel(owner=owner)
            case(label,f,[cast(target,[sel(),sel(owner=2)]),stats(target,True),dict(op='advance',phase='MAIN1',activeSeat=2,decisions=[]),stats(target,False)])
        f=dict(fixtureHand=[name],fixtureLands=lands,fixtureBattlefield=['Grizzly Bears'])
        canceled=cast(sel(),[sel()]);canceled['targetPlan'].pop('choose');canceled['targetPlan']['cancel']=True
        case('cancel',f,[canceled,stats(sel(),False)])
        hexed=sel('Gladecover Scout');enemy_hex=sel('Gladecover Scout',2)
        f=dict(fixtureHand=[name],fixtureLands=lands,fixtureBattlefield=['Gladecover Scout'],fixtureOpponentBattlefield=['Gladecover Scout'])
        action=cast(hexed,[hexed]);action['targetPlan']['invalid']=[enemy_hex]
        case('hexproof-owner',f,[action,dict(op='assert',objects=[dict(selector=hexed,values=dict(power=1+delta['power'],toughness=1+delta['toughness'])),dict(selector=enemy_hex,values=dict(power=1,toughness=1))])])
        case('underfunded',dict(fixtureHand=[name],fixtureLands=lands[:-1],fixtureBattlefield=['Grizzly Bears']),[dict(op='deny',card=name)])
        wrong=next(color for color in LANDS if color not in symbols)
        case('wrong-color',dict(fixtureHand=[name],fixtureLands=[LANDS[wrong]]*mana['total'],fixtureBattlefield=['Grizzly Bears']),[dict(op='deny',card=name)])
        f=dict(fixtureHand=[name],fixtureLands=lands,fixtureBattlefield=['Grizzly Bears'])
        case('combat-timing',f,[dict(op='advance',phase='COMBAT_BEGIN',activeSeat=1,decisions=[])]+([cast(sel(),[sel()]),stats(sel(),True)] if 'Instant' in p['nativeTypes'] else [dict(op='deny',card=name)]))
        f=dict(fixtureHand=[name,'Unsummon'],fixtureLands=lands+['Island'],fixtureBattlefield=['Grizzly Bears'])
        case('invalidated-target',f,[cast(sel(),[sel()],resolve=False,fizzled=True),dict(op='cast',card='Unsummon',mana=1,draw=0,life=0,targetPlan=dict(kind='targets',expectedOptions=[sel()],choose=[sel()]),zoneChanges=[dict(selector=sel(),to='Hand')]),dict(op='resolve',selector=sel(name,zone='Stack')),stats(sel(zone='Hand'),False)])
        cards[name]=branches
        if name not in source_policy['verifiedNames']:
            source_policy['verifiedNames'].append(name);source_policy['preferredPrintings'][name]=p['printing'];source_policy.setdefault('colorIdentities',{})[name]=sorted(set(symbols))
    source_policy['candidateNames']=[n for n in source_policy['candidateNames'] if n not in source_policy['verifiedNames']]
    policy_path=a.output/'qualified-research-policy.json';policy_path.write_text(json.dumps(source_policy,indent=2),encoding='utf8')
    suite=dict(schema=2,name='Independent native-text single-target temporary pumps',cards=cards,cases=cases,scope='Fixed positive single-target creature pumps: payments, target ownership/hexproof, cancellation, invalidation, instantaneous resolution and cleanup expiration. Not complete interaction coverage.')
    validate(suite);(a.output/'generated-suite.json').write_text(json.dumps(suite,indent=2),encoding='utf8')
    (a.output/'additional-proposals.json').write_text(json.dumps(dict(schema=1,provenance=provenance,qualifierSource=str(Path(__file__).resolve()),qualifierSha256=sha(Path(__file__)),proposals=proposals,newAdmissions=0,executedCases=0),indent=2),encoding='utf8')
    clone(SimpleNamespace(source_config=a.source_config,source_policy=a.source_policy,qualified_policy=policy_path,output=a.output/'prepared',javac=a.javac))
    receipt=dict(cards=len(cards),cases=len(cases),newAdmissions=0,scope=suite['scope']);(a.output/'generation.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps(receipt))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('audit','mappings','catalogue','database','scripts','source-config','source-policy','output','javac'):p.add_argument('--'+key,type=Path,required=True)
    prepare(p.parse_args())
