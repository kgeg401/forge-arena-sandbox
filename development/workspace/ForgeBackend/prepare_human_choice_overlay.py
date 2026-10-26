"""Prepare a private experimental choice overlay without widening admission.
Inputs and output contain locally derived game metadata; do not commit them.
"""
import argparse,json,hashlib,copy
from pathlib import Path
from experimental_cards import apply_human_choices
p=argparse.ArgumentParser(description=__doc__)
for k in ('base','rebuilt','experimental','output'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();base=json.loads(a.base.read_text());rebuilt=json.loads(a.rebuilt.read_text());experimental=json.loads(a.experimental.read_text())
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
checked=apply_human_choices(copy.deepcopy(base),overlay)
if {n for n,c in checked['cards'].items() if c.get('admitted')}!={n for n,c in base['cards'].items() if c.get('admitted')}:raise ValueError('Presentation overlay changed admission')
experimental['humanChoices']=overlay
pending=a.output.with_suffix(a.output.suffix+'.pending');pending.write_text(json.dumps(experimental,indent=2));pending.replace(a.output)
print(json.dumps(dict(primaryBindings=len(overrides),additionalPresentationObjects=len(overlay['presentationObjects']),newAdmissions=0,gameplayVerified=False,output=str(a.output))))
