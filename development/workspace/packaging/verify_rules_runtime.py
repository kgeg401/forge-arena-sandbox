"""Private dependency upgrade, interrupted-switch recovery and rollback fixtures."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import tempfile,json,shutil
from unittest.mock import patch
from tester_common import sha
from rules_runtime import ensure_rules_runtime,restore_compatible,recover

root=Path(tempfile.mkdtemp(prefix='forge-rules-upgrade-'));data=root/'data';data.mkdir();app=root/'app';app.mkdir()
old=data/'forge-runtime';old.mkdir();(old/'forge.jar').write_bytes(b'old engine');(old/'gson.jar').write_bytes(b'unchanged gson')
(old/'user').mkdir();(old/'user/prefs').write_bytes(b'keep forge user preferences')
profile=data/'native-lab/local-profile';profile.mkdir(parents=True);(profile/'decks.json').write_bytes(b'preserve exact deck bytes')
source=root/'download';(source/'res/cardsfolder').mkdir(parents=True);(source/'new.jar').write_bytes(b'new engine');(source/'res/cardsfolder/cardsfolder.zip').write_bytes(b'new scripts')
previous=dict(id='old',jar='old.jar',files={'old.jar':sha(old/'forge.jar')})
preferred=dict(id='new',jar='new.jar',files={n:sha(source/n) for n in ['new.jar','res/cardsfolder/cardsfolder.zip']})
req=dict(forgeVariants=[previous,preferred],preferredForgeVariant='new');(app/'requirements.json').write_text(json.dumps(req))
(app/'dependencies-lock.json').write_text(json.dumps(dict(dependencies=dict(forge=dict(files=preferred['files'],digest='pinned-fixture')))))
config=dict(privateRoot=str(data));checks=[]
with patch('rules_runtime.prepare',return_value=source),patch('update_tester.require_stopped') as stopped:
    assert ensure_rules_runtime(app,config)['id']=='new';assert stopped.call_count==1;checks.append('upgrade verifies and selects preferred runtime')
    assert (old/'gson.jar').read_bytes()==b'unchanged gson' and (old/'user/prefs').read_bytes()==b'keep forge user preferences';checks.append('retains Gson and Forge user preferences')
    assert (profile/'decks.json').read_bytes()==b'preserve exact deck bytes';checks.append('profile is byte identical')
    assert ensure_rules_runtime(app,config)['id']=='new' and stopped.call_count==1;checks.append('repeat startup is idempotent')
    assert restore_compatible(data,dict(forgeVariants=[previous]))['id']=='old';checks.append('rollback restores retained old engine')
    assert restore_compatible(data,dict(forgeVariants=[preferred]))['id']=='new';checks.append('forward restore retains both runtimes')
    backup=data/'forge-runtime-backups/interrupted';old.rename(backup)
    (data/'rules-runtime-switch.json').write_text(json.dumps(dict(backup=str(backup),candidate=str(data/'unused'))));recover(data)
    assert (old/'forge.jar').read_bytes()==b'new engine';checks.append('interruption after old-directory rename recovers')
    (source/'new.jar').write_bytes(b'tampered download')
    restore_compatible(data,dict(forgeVariants=[previous]));before=(old/'forge.jar').read_bytes()
    try:ensure_rules_runtime(app,config)
    except ValueError:pass
    else:raise AssertionError('Tampered prerequisite accepted')
    assert (old/'forge.jar').read_bytes()==before;checks.append('invalid staged engine preserves active runtime')
result=dict(passed=True,checks=checks,evidence=str(root));(root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
