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
info=read(C/'release-info.json');experimental=read(C/'ForgeBackend/experimental-admission.json');requirements=read(C/'requirements.json')
verified=set(p['verifiedNames']);extra=set(experimental['cards'])
check('Experimental inventory is enabled and matches release metadata',experimental['enabled'] is True and info['experimentalAdmission'] is True and extra==set(info['experimentalNames']))
check('Experimental access never promotes or duplicates verified names',not verified&extra and all(c.get('experimental') is True and c.get('verified') is False and c.get('admitted') is True for c in experimental['cards'].values()))
check('Blocked cards remain outside both admitted inventories',not set(experimental['blockedCards'])&(verified|extra))
check('Experimental overlay is pinned to the same policy',experimental['policySha256']==sha(policy))
database_hashes={v for build in [requirements,*requirements.get('arenaVariants',[])] for k,v in build['arenaFiles'].items() if 'Raw_CardDatabase_' in k}
check('Experimental identities use the packaged Arena database',experimental['sourceDatabaseSha256'] in database_hashes)
script_hashes={v['files'].get('res/cardsfolder/cardsfolder.zip') for v in requirements['forgeVariants']}
check('Experimental rules use a supported pinned Forge script set',experimental['sourceForgeScriptsSha256'] in script_hashes)
choices=experimental['humanChoices']
check('Human choice bindings retain the same catalogue and script identities',choices['sourceDatabaseSha256']==experimental['sourceDatabaseSha256'] and choices['sourceForgeScriptsSha256']==experimental['sourceForgeScriptsSha256'])
check('Exported package identifies this exact authored source commit',info['gameplaySource']==s['localSourceCommit']==s['packageSourceCommit'])
check('Published projection input labels are portable',all(Path(k).name==k and ':' not in k and '\\' not in k for k in choices['provenance']['source']['inputs']))
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
print(json.dumps(dict(passed=True,checks=len(checks),sourceFiles=len(s['files']),verified=len(verified),experimental=len(extra),primary=len(verified|extra),version=info['version']),indent=2))

for build in requirements.get('arenaVariants',[]):
 cfg=read(C/'ForgeBackend'/build['experimentalFile'])
 check('Variant catalogue fingerprint: '+build['id'],cfg['sourceDatabaseSha256']==cfg['humanChoices']['sourceDatabaseSha256']==build['databaseSha256'])
 check('Variant retains primary card definitions: '+build['id'],cfg['cards']==experimental['cards'])
 for key in ['cardOverrides','presentationObjects','keywordAbilityIds','typeEnumIds','cardNameIds']:
  check('Variant retains presentation '+build['id']+' '+key,cfg['humanChoices'][key]==choices[key])

legacy=next(v for v in requirements["arenaVariants"] if v["id"]=="arena-14517")
check("Legacy updater bootstrap retains the original Arena fingerprint",requirements["arenaFiles"]==legacy["arenaFiles"] and requirements["arenaBuild"]==legacy["arenaBuild"])
