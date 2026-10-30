"""Check private overlay regeneration and fail-closed identity boundaries."""
import argparse,copy,json,hashlib
from pathlib import Path
from experimental_cards import load_experimental,merge_manifest,apply_human_choices
p=argparse.ArgumentParser(description=__doc__)
for k in ('base','experimental','output'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();base=json.loads(a.base.read_text());experimental=load_experimental(a.experimental);results=[]
raw=copy.deepcopy(base)
for name in experimental['cards']:raw['cards'].pop(name,None)
merged=merge_manifest(raw,experimental)
assert merged['fullHumanChoices'] and len(merged['cards'])>len(base['cards'])
assert {n for n,c in merged['cards'].items() if c.get('admitted')}=={n for n,c in base['cards'].items() if c.get('admitted')}
results.append(dict(check='Regenerate original admission plus explicit human bindings',passed=True,newAdmissions=0))
for label in ('database-drift','script-drift','printing-drift','admission-overwrite','presentation-overwrite'):
    overlay=copy.deepcopy(experimental['humanChoices']);name=next(iter(overlay['cardOverrides']))
    if label=='database-drift':overlay['sourceDatabaseSha256']='0'*64
    elif label=='script-drift':overlay['cardOverrides'][name]['forgeScriptSha256']='0'*64
    elif label=='printing-drift':overlay['cardOverrides'][name]['grpId']+=1
    elif label=='admission-overwrite':overlay['cardOverrides'][name]['fields']['admitted']=True
    else:overlay['presentationObjects'][name]=dict(overlay['presentationObjects'][next(iter(overlay['presentationObjects']))])
    candidate=copy.deepcopy(base)
    try:apply_human_choices(candidate,overlay)
    except ValueError:assert candidate==base
    else:raise AssertionError('Invalid binding accepted: '+label)
    results.append(dict(check='Reject '+label+' before mutating the manifest',passed=True))
report=dict(passed=True,results=results,inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in (a.base,a.experimental,Path(__file__),Path(__file__).with_name('experimental_cards.py'))})
faces=[n for n,c in experimental['humanChoices']['presentationObjects'].items() if c.get('facePresentation')]
for label in ('missing-source-face','cyclic-source-face') if faces else ():
    overlay=copy.deepcopy(experimental['humanChoices']);name=faces[0]
    overlay['presentationObjects'][name]['parentName']=name if label=='cyclic-source-face' else '__absent_source__'
    candidate=copy.deepcopy(base)
    try:apply_human_choices(candidate,overlay)
    except ValueError:assert candidate==base
    else:raise AssertionError('Invalid face ancestry accepted: '+label)
    results.append(dict(check='Reject '+label+' before mutating the manifest',passed=True))
a.output.write_text(json.dumps(report,indent=2));print(json.dumps(dict(passed=True,checks=len(results),newAdmissions=0)))
