"""Reject invented cards while retaining real paper-card presentation support."""
import copy,hashlib,json,sys,tempfile,types
from pathlib import Path
from unittest.mock import patch
from experimental_cards import load_experimental
checks=[]
with tempfile.TemporaryDirectory(prefix='forge-real-cards-') as folder:
 root=Path(folder);db=root/'db';scripts=root/'scripts';policy=root/'policy.json'
 db.write_bytes(b'owned database fixture');scripts.write_bytes(b'owned scripts fixture');policy.write_text('{"verifiedNames":[]}')
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 card=dict(grpId=2000001,forgeScriptSha256='a'*64,token=False,admitted=True,experimental=True,verified=False,paperOnly=True,colorIdentity=['U'],types=['Instant'])
 value=dict(schema=1,enabled=True,sourceDatabaseSha256=sha(db),sourceForgeScriptsSha256=sha(scripts),policySha256=sha(policy),cards={'Twincast':card},blockedCards={})
 module=types.ModuleType('runtime_paths');module.DB=db;module.FORGE_SCRIPTS=scripts;module.SUPPORT_POLICY=policy;module.ARENA_BUILD={'experimentalFile':'fixture.json'}
 path=root/'fixture.json'
 def load(v):path.write_text(json.dumps(v));return load_experimental(path)
 with patch.dict(sys.modules,{'runtime_paths':module}):
  assert load(value)['cards']['Twincast']['paperOnly'];checks.append('Real paper card presentation remains available')
  for label,mutate in [('custom rule inventory',lambda v:v.update(sandboxCustomRules={'Invented':{'script':'Name:Invented\n'}})),('custom-marked card without rule',lambda v:v['cards']['Twincast'].update(sandboxCustom=True))]:
   bad=copy.deepcopy(value);mutate(bad)
   try:load(bad)
   except ValueError as error:assert 'Invented custom cards are disabled' in str(error);checks.append('Rejects '+label)
   else:raise AssertionError('Accepted '+label)
print(json.dumps(dict(passed=True,checks=checks)))
