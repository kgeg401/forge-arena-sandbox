"""Deliver seven previously authored conditional effects after exact source review.

The reviewed definitions implement respectively ferocious, same-named graveyard
copies, actual death history, addendum, distinct nonland mana values, post-draw
hand size, and a single graveyard's twenty-card threshold. Unknown definitions
never inherit this review. Native controls are the existing untargeted pathway.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import zipfile
from build_card_test_catalogue import cost,sha,parse
from prepare_generated_removal_batches import clean,LANDS
from clone_research_runtime import clone
from validate_card_scenario import validate

REVIEWED={
 'Feed the Clan':('522deafb32327eb2392619bd49da3ffda77bac79be85f780ff4c916b489d25ea','You gain 5 life. Ferocious — You gain 10 life instead if you control a creature with power 4 or greater.'),
 'Frantic Inventory':('8d79e9c7a2260e1c49626677f9081e02d116a7f0bcf0a01a5bdc409ea885d372','Draw a card, then draw cards equal to the number of cards named Frantic Inventory in your graveyard.'),
 'Life Goes On':('b1d05ddd306b4536bccdc16d0d582f3426c4b21fdc11f0a14d869df529bc8389','You gain 4 life. If a creature died this turn, you gain 8 life instead.'),
 "Sphinx's Insight":('d3330f1fb9a6a4ac67fbb09793b2f86138cb181a94e440642ba064d4a5af3d8e','Draw two cards. Addendum — If you cast this spell during your main phase, you gain 2 life.'),
 'Sudden Insight':('d7a3b583db5d31693b886dc02b1a3703b331c9a9571959ecade775da399adbdf','Draw a card for each different mana value among nonland cards in your graveyard.'),
 'Union of the Third Path':('4f094588e304941f07ba7dad10e13f6fe68ecfefd2882b0cda5f537b78c690c3','Draw a card, then you gain life equal to the number of cards in your hand.'),
 'Visions of Beyond':('b9cce71a53434e1ace201839d050b65280fa79594195a3aebd5bd1645debde8d','Draw a card. If a graveyard has twenty or more cards in it, draw three cards instead.'),
}


def prepare(a):
    if a.output.exists():raise ValueError('Fresh conditional evidence directory required')
    mappings=json.loads(a.mappings.read_text(encoding='utf8'));catalogue=json.loads(a.catalogue.read_text(encoding='utf8'));provenance=catalogue['provenance']
    if provenance['mappingsSha256']!=sha(a.mappings) or provenance['databaseSha256']!=sha(a.database) or provenance['scriptsSha256']!=sha(a.scripts):raise ValueError('Source inputs differ')
    policy=json.loads(a.source_policy.read_text(encoding='utf8'))
    if policy.get('researchOnly') is not True:raise ValueError('Independent research source required')
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True);proposals=[]
    with zipfile.ZipFile(a.scripts) as archive:
        for name,(expected_hash,expected_text) in REVIEWED.items():
            candidates=sorted((p for p in mappings['printings'] if p['name']==name and not p['digitalOnly'] and not p['rebalanced'] and not p['linkedFaces']),key=lambda p:p['grpId']);found=False
            for printing in candidates:
                if len(printing['forgeScripts'])!=1 or printing['types']!=['Instant'] or printing['supertypes']:continue
                raw=archive.read(printing['forgeScripts'][0]);fields=parse(raw.decode('utf-8-sig'))['fields']
                if hashlib.sha256(raw).hexdigest()!=expected_hash:continue
                hidden=db.execute('SELECT HiddenAbilityIds FROM Cards WHERE GrpId=?',(printing['grpId'],)).fetchone()[0]
                text=[db.execute('SELECT l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId WHERE a.Id=? AND l.Formatted=1',(i,)).fetchall() for i in printing['abilityIds']]
                if hidden or any(len(v)!=1 for v in text) or ' '.join(clean(v[0][0]) for v in text)!=expected_text:continue
                mana=cost(printing);tokens=' '.join(fields.get('ManaCost',[])).split()
                if not mana or sum(int(v) for v in tokens if v.isdecimal())!=mana['generic'] or sorted(v for v in tokens if v in LANDS)!=sorted(mana['symbols']):continue
                proposals.append(dict(name=name,template='conditional-untargeted-draw-life-v1',printing=printing['grpId'],nativeTypes=['Instant'],nativeTexts=[expected_text],nativeAbilityIds=printing['abilityIds'],printedCost=mana,sourceScriptSha256=expected_hash,review='Exact pinned formula definition and independently authored boundary/history scenarios; no unknown formula fallback'))
                if name not in policy['verifiedNames']:policy['verifiedNames'].append(name)
                policy['preferredPrintings'][name]=printing['grpId'];policy.setdefault('colorIdentities',{})[name]=sorted(set(mana['symbols']));found=True;break
            if not found:raise ValueError('No exact reviewed source pair: '+name)
    db.close();cases=[]
    for filename in ('draw-life.json','decisions-history.json','draw-life-chain.json'):
        suite=json.loads((Path(__file__).parent/'card_batch_suites'/filename).read_text())
        for c in suite['cases']:
            if c['card'] not in REVIEWED:continue
            c=deepcopy(c)
            for step in c['steps']:
                if step['op']=='phase':step.update(op='advance',phase='COMBAT_BEGIN',activeSeat=1,decisions=[])
                if c['id']=='frantic-chained' and step.get('op')=='cast':
                    step['selector']=dict(name=step['card'],owner=1,zone='Hand',index=0)
            cases.append(c)
    for p in proposals:
        name=p['name'];mana=p['printedCost'];lands=[LANDS[s] for s in mana['symbols']]+[LANDS[mana['symbols'][0]]]*mana['generic'];key=hashlib.sha256(name.encode()).hexdigest()[:16]
        cases.append(dict(id='conditional-'+key+'-underfunded',card=name,covers=['underfunded'],fixture=dict(fixtureHand=[name],fixtureLands=lands[:-1]),steps=[dict(op='deny',card=name)]))
        first=next(c for c in cases if c['card']==name and len(c['steps'])==1 and c['steps'][0]['op']=='cast')
        c=deepcopy(first);c.update(id='conditional-'+key+'-combat',covers=['combat-cast']);c['steps'].insert(0,dict(op='advance',phase='COMBAT_BEGIN',activeSeat=1,decisions=[]))
        if name=="Sphinx's Insight":c['steps'][1]['life']=0
        cases.append(c)
    cards={name:sorted({b for c in cases if c['card']==name for b in c['covers']}) for name in REVIEWED}
    suite=dict(schema=2,name='Reviewed native conditional draw/life formulas',cards=cards,cases=cases);validate(suite)
    a.output.mkdir(parents=True)
    for filename,value in [('qualified-research-policy.json',policy),('generated-suite.json',suite),('additional-proposals.json',dict(schema=1,provenance=provenance,qualifierSource=str(Path(__file__).resolve()),qualifierSha256=sha(Path(__file__)),proposals=proposals,newAdmissions=0))]:
        (a.output/filename).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf8')
    clone(SimpleNamespace(source_config=a.source_config,source_policy=a.source_policy,qualified_policy=a.output/'qualified-research-policy.json',output=a.output/'prepared',javac=a.javac))
    print(json.dumps(dict(cards=len(cards),cases=len(cases))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('mappings','catalogue','database','scripts','source-config','source-policy','output','javac'):p.add_argument('--'+key,type=Path,required=True)
    prepare(p.parse_args())
