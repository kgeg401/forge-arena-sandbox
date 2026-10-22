"""Qualify source data afresh, generate bounded cases, build a research runtime.

No hand-edited proposal file supplies expected results: native English text,
native stats and Forge definitions are re-read by the independent qualifier.
"""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from build_card_test_catalogue import build
from clone_research_runtime import clone
from run_card_batches import validate

LANDS={'W':'Plains','U':'Island','B':'Swamp','R':'Mountain','G':'Forest'}


def prepare(a):
    if a.output.exists():raise ValueError('Choose a fresh generated-batch folder')
    a.output.mkdir(parents=True)
    build(SimpleNamespace(audit=a.audit,mappings=a.mappings,policy=a.baseline_policy,database=a.database,scripts=a.scripts,output=a.output/'qualification'))
    proposals=json.loads((a.output/'qualification/test-proposals.json').read_text(encoding='utf8'))['proposals']
    mappings=json.loads(a.mappings.read_text(encoding='utf8'))
    by_id={r['grpId']:r for r in mappings['printings']}
    policy=json.loads(a.baseline_policy.read_text(encoding='utf-8-sig'))
    original=set(policy['verifiedNames']);policy['researchOnly']=True
    cards={};cases=[]
    for p in proposals:
        name=p['name'];key=hashlib.sha256(name.encode('utf8')).hexdigest()[:16]
        if name not in original:
            policy['verifiedNames'].append(name);policy['preferredPrintings'][name]=p['printing']
            native=by_id[p['printing']]
            policy.setdefault('colorIdentities',{})[name]=[{'1':'W','2':'U','3':'B','4':'R','5':'G'}[v] for v in native['colors'].split(',') if v in ('1','2','3','4','5')]
        mana=p['printedCost'];symbols=mana['symbols'];filler=LANDS[symbols[0]] if symbols else 'Plains'
        lands=[LANDS[s] for s in symbols]+[filler]*mana['generic']
        creature=p['template']=='simple-creature-cast-v1'
        destination='battlefield' if creature and p['oracleCharacteristics']['toughness']>0 else 'graveyard'
        draw=sum(e['amount'] for e in p.get('oracleEffects',[]) if e['kind']=='Draw')
        life=sum(e['amount'] for e in p.get('oracleEffects',[]) if e['kind']=='GainLife')
        step=dict(op='cast',card=name,mana=mana['total'],draw=draw,life=life,zone=destination)
        if not creature:step['orderedEffects']=p['oracleEffects']
        steps=[step]
        if creature and destination=='battlefield':steps.append(dict(op='assert',objects=[dict(selector=dict(name=name,owner=1,zone='Battlefield'),values=p['oracleCharacteristics'])]))
        branches=['main-cast-stats' if creature else 'main-resolution-amounts']
        def case(suffix,branch,world,actions):
            cases.append(dict(id='g-'+key+'-'+suffix,card=name,covers=[branch],fixture=dict(fixtureHand=[name],fixtureLands=world),steps=actions,
                oracleSource=dict(template=p['template'],printing=p['printing'],scriptSha256=p['sourceScriptSha256'],nativeAbilityIds=p['nativeAbilityIds']),
                scope='Generated source-qualified bounded behavior only; remaining mechanics, native and complete-game gates are unverified.'))
        case('main',branches[0],lands,steps)
        if mana['total']:
            branches.append('underfunded-rejected');case('underfunded',branches[-1],lands[:-1],[dict(op='deny',card=name)])
        if symbols:
            missing=next((k for k in LANDS if k not in symbols),'W')
            branches.append('wrong-color-rejected');case('wrong-color',branches[-1],[LANDS[missing]]*mana['total'],[dict(op='deny',card=name)])
        flash='Instant' in p['nativeTypes'] or 'Flash' in p.get('keywords',[])
        branches.append('combat-cast' if flash else 'combat-rejected')
        actions=[dict(op='advance',phase='COMBAT_BEGIN',activeSeat=1,decisions=[])]+(steps if flash else [dict(op='deny',card=name)])
        case('combat',branches[-1],lands,actions)
        cards[name]=branches
    policy['candidateNames']=[n for n in policy['candidateNames'] if n not in set(policy['verifiedNames'])]
    path=a.output/'qualified-research-policy.json';path.write_text(json.dumps(policy,indent=2),encoding='utf8')
    suite=dict(schema=2,name='Generated independently source-qualified casting/timing',cards=cards,cases=cases,
        scope='Cast/timing/payment/stat or fixed-amount tests. Creature keyword mechanics and interactions, original native controls/assets and complete matches remain separate. No new admission.')
    validate(suite)
    (a.output/'generated-suite.json').write_text(json.dumps(suite,indent=2,ensure_ascii=False),encoding='utf8')
    clone(SimpleNamespace(source_config=a.source_config,source_policy=a.source_policy,qualified_policy=path,output=a.output/'prepared',javac=a.javac))
    receipt=dict(schema=1,cards=len(cards),cases=len(cases),existingAdmitted=len(original),researchNames=len(policy['verifiedNames']),newAdmissions=0,
        suite=str(a.output/'generated-suite.json'),config=str(a.output/'prepared/runtime-config.json'),policy=str(a.output/'prepared/research-policy.json'),
        nativeOracle='Amounts from exact native English clauses; stats from native metadata; compared independently with the Forge definition.',
        limitations=['Requirements are not exhaustive interaction coverage','A creature cast does not validate its keywords/combat','Native assets/controls and full matches remain required'])
    (a.output/'generated-batch.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('audit','mappings','baseline-policy','database','scripts','source-config','source-policy','output','javac'):p.add_argument('--'+key,type=Path,required=True)
    prepare(p.parse_args())
