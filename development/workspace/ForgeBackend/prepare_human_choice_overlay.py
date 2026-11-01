"""Prepare a private experimental choice overlay without widening admission.
Inputs and output contain locally derived game metadata; do not commit them.
"""
import argparse,json,hashlib,copy
from pathlib import Path
from experimental_cards import apply_human_choices
p=argparse.ArgumentParser(description=__doc__)
for k in ('base','rebuilt','experimental','output'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--incremental',action='store_true',help='Preserve existing bindings when base already contains the previous overlay')
a=p.parse_args();base=json.loads(a.base.read_text());rebuilt=json.loads(a.rebuilt.read_text());experimental=json.loads(a.experimental.read_text())
if a.output.exists() or a.output.with_suffix(a.output.suffix+'.pending').exists():raise ValueError('Use a new overlay output; preserve existing evidence')
for key in ('sourceDatabaseSha256','sourceForgeScriptsSha256'):
    if base.get(key)!=rebuilt.get(key) or base.get(key)!=experimental.get(key):raise ValueError('Pinned source drift: '+key)
fields=('abilityBindings','modalBinding','targetPromptId','genericChoiceBinding');overrides={}
for name,card in base['cards'].items():
    if name not in rebuilt['cards']:raise ValueError('Rebuilt bindings dropped an existing mapping: '+name)
    other=rebuilt['cards'][name]
    if card['grpId']!=other['grpId'] or card.get('forgeScriptSha256')!=other.get('forgeScriptSha256'):raise ValueError('Rebuilt primary identity drift: '+name)
    changed={key:other[key] for key in fields if key in other and card.get(key)!=other[key]}
    if changed:overrides[name]=dict(grpId=card['grpId'],forgeScriptSha256=card.get('forgeScriptSha256'),fields=changed)
overlay=dict(schema=1,enabled=True,cardOverrides=overrides,presentationObjects={n:c for n,c in rebuilt['cards'].items() if n not in base['cards']},provenance=rebuilt['humanChoiceBindingProvenance'])
for key in ('sourceDatabaseSha256','sourceForgeScriptsSha256','keywordAbilityIds','typeEnumIds','cardNameIds'):overlay[key]=rebuilt[key]
old=experimental.get('humanChoices')
check_base=copy.deepcopy(base)
if a.incremental:
    if not isinstance(old,dict) or old.get('schema')!=1 or old.get('enabled') is not True:raise ValueError('Incremental preparation requires an existing enabled overlay')
    for key in ('sourceDatabaseSha256','sourceForgeScriptsSha256','keywordAbilityIds','typeEnumIds','cardNameIds'):
        if old.get(key)!=base.get(key):raise ValueError('Incremental base differs from existing overlay: '+key)
    for name,value in old['cardOverrides'].items():
        card=base['cards'].get(name,{})
        if card.get('grpId')!=value['grpId'] or card.get('forgeScriptSha256')!=value['forgeScriptSha256'] or any(card.get(k)!=v for k,v in value['fields'].items()):raise ValueError('Incremental base is missing an existing binding: '+name)
    for name,value in old['presentationObjects'].items():
        if base['cards'].get(name)!=value:raise ValueError('Incremental base is missing an existing presentation object: '+name)
        del check_base['cards'][name]
    composed=copy.deepcopy(old)
    for name,value in overlay['cardOverrides'].items():
        if name in composed['cardOverrides']:composed['cardOverrides'][name]['fields'].update(value['fields'])
        else:composed['cardOverrides'][name]=value
    composed['presentationObjects'].update(overlay['presentationObjects'])
    for key in ('keywordAbilityIds','typeEnumIds','cardNameIds'):composed[key]=overlay[key]
    digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    provenance=overlay['provenance']
    composed.setdefault('provenance',{}).setdefault('incrementalUpdates',[]).append(dict(baseOverlaySha256=digest(old),deltaOverlaySha256=digest(overlay),projectionSha256=provenance.get('projectionSha256'),changedCards=sorted(overrides)))
    overlay=composed
elif isinstance(old,dict) and (set(old.get('cardOverrides',{}))-set(overrides) or set(old.get('presentationObjects',{}))-set(overlay['presentationObjects'])):
    raise ValueError('Preparation would drop existing bindings; use an unbound base or explicit --incremental')
checked=apply_human_choices(check_base,overlay)
if {n for n,c in checked['cards'].items() if c.get('admitted')}!={n for n,c in base['cards'].items() if c.get('admitted')}:raise ValueError('Presentation overlay changed admission')
if checked['cards']!=rebuilt['cards']:raise ValueError('Prepared overlay does not reconstruct the complete expected card presentation')
experimental['humanChoices']=overlay
pending=a.output.with_suffix(a.output.suffix+'.pending');pending.write_text(json.dumps(experimental,indent=2));pending.replace(a.output)
print(json.dumps(dict(primaryBindings=len(overrides),totalPrimaryBindings=len(overlay['cardOverrides']),additionalPresentationObjects=len(overlay['presentationObjects']),incremental=a.incremental,newAdmissions=0,gameplayVerified=False,output=str(a.output))))
