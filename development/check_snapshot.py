"""Validate the public source snapshot against the packaged runtime contract."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];D=R/'development';W=D/'workspace';C=R/'client'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
s=read(D/'source-snapshot.json');checks=[]
def check(label,value):
 assert value,label
 checks.append(label)
for name,digest in s['files'].items():
 path=(W/name).resolve();check('Snapshot identity: '+name,W.resolve() in path.parents and path.is_file() and sha(path)==digest)
policy=C/'ForgeBackend/bridge_support.json';p=read(policy)
check('Production policy exactly matches the workspace and snapshot',sha(policy)==sha(W/'ForgeBackend/bridge_support.json')==s['productionPolicySha256'])
check('Declared production count matches real unique names',len(p['verifiedNames'])==len(set(p['verifiedNames']))==s['productionCards'])
check('Runtime release and source policy admit identical names',set(read(C/'release-info.json')['admittedNames'])==set(p['verifiedNames']))
check('Support diagnostic index matches the production policy',read(C/'ForgeBackend/card-support-index.json')['provenance']['policySha256']==sha(policy))
check('Paradox remains explicitly disabled research',read(W/'ForgeBackend/draft_policies/paradox-engine.json')['researchOnly'] is True and 'Paradox Engine' not in p['verifiedNames'])
for group in ['ForgeBackend','DeckBackend','PackBackend']:
 for f in (C/group).glob('*.py'):check('Runtime source identity: '+group+'/'+f.name,sha(f)==sha(W/group/f.name))
for f in (C/'adapter-source').rglob('*.cs'):
 rel=f.relative_to(C/'adapter-source')
 if set(rel.parts)&{'build','bin','obj'}:continue
 source=W/rel
 if not source.is_file():source=W/'packaging'/f.name
 check('Native source identity: '+str(rel),source.is_file() and sha(f)==sha(source))
check('Rules bridge source identity',sha(C/'adapter-source/ForgeLandEngine.java')==sha(W/'ForgeBackend/ForgeLandEngine.java'))
print(json.dumps(dict(passed=True,checks=len(checks),sourceFiles=len(s['files']),cards=len(p['verifiedNames']),version=read(C/'release-info.json')['version']),indent=2))
