"""Reject unsafe/unsupported setups without changing source installs."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from types import SimpleNamespace
import json, uuid
from install_tester import inspect_install, install

ROOT=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\research\packaging')/('setup-check-'+uuid.uuid4().hex[:8]);ROOT.mkdir(parents=True)
PACKAGE=Path(sys.argv[1])
arena=Path(r'D:\GAMES\MTGA');forge=Path.home()/'Games/Forge';java=Path.home()/'Games/ForgeRuntime-Java17/jdk-17.0.20.1+1';loader=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\tools\BepInEx-5.4.23.5')
checks=[]
def rejected(label,action):
    try:action()
    except (ValueError,OSError):checks.append(dict(check=label,passed=True))
    else:raise AssertionError('Unsafe setup accepted: '+label)
existing=ROOT/'existing';existing.mkdir();sentinel=existing/'keep.txt';sentinel.write_text('preserve this existing folder')
rejected('Existing destination is never overwritten',lambda:inspect_install(arena,forge,java,loader,existing,PACKAGE))
assert sentinel.read_text()=='preserve this existing folder'
rejected('A child of the retail Arena tree is rejected before copy',lambda:inspect_install(arena,forge,java,loader,arena/'never-create-this-sandbox-test',PACKAGE))
assert not (arena/'never-create-this-sandbox-test').exists()
rejected('A parent of the retail Arena tree is rejected',lambda:inspect_install(arena,forge,java,loader,arena.parent,PACKAGE))
bad=ROOT/'wrong-client';bad.mkdir();(bad/'MTGA.exe').write_bytes(b'not a supported client')
destination=ROOT/'must-not-be-created'
rejected('Wrong client hash fails before creating destination',lambda:inspect_install(bad,forge,java,loader,destination,PACKAGE))
assert not destination.exists()
args=SimpleNamespace(arena=str(arena),forge=str(forge),java=str(java),loader=str(loader),destination=str(destination),package=str(PACKAGE),check_only=False,repository='../untrusted/repository')
rejected('Invalid updater repository fails before creating destination',lambda:install(args))
assert not destination.exists()
result=dict(scope='Negative setup tests with actual pinned package; no client copy/launch',checks=checks,total=len(checks),evidence=str(ROOT))
(ROOT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(checks=len(checks),evidence=str(ROOT)),indent=2))
