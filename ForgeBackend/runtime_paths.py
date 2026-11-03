"""Local defaults plus an explicit, validated portable tester configuration."""
from pathlib import Path
import json, os

CONFIG_PATH=os.environ.get('FORGE_ARENA_CONFIG')
CONFIG=json.loads(Path(CONFIG_PATH).read_text(encoding='utf-8-sig')) if CONFIG_PATH else {}
if CONFIG and CONFIG.get('schema')!=1:raise ValueError('Unsupported sandbox installation config')
ROOT=Path(CONFIG.get('privateRoot',r'D:\GAMES\CodexAssets\ForgeArenaSandbox')).resolve()
ARENA=Path(CONFIG.get('arenaInstall',r'D:\GAMES\MTGA')).resolve()
FORGE_INSTALL=Path(CONFIG.get('forgeInstall',str(Path.home()/'Games/Forge'))).resolve()
JAVA_HOME=Path(CONFIG.get('javaHome',str(Path.home()/'Games/ForgeRuntime-Java17/jdk-17.0.20.1+1'))).resolve()
_builds=json.loads(Path(__file__).with_name('arena-builds.json').read_text(encoding='utf8'))['builds']
_raw=Path(CONFIG.get('catalogueInstall',str(ARENA)))/'MTGA_Data/Downloads/Raw'
_matches=[b for b in _builds if b['id']==CONFIG['arenaVariant']] if CONFIG.get('arenaVariant') else [b for b in _builds if (_raw/b['databaseName']).is_file()]
if not CONFIG.get('arenaVariant'):
    # Store variants may share the exact catalogue and choice bindings.
    _catalogues={}
    for _build in _matches:_catalogues.setdefault((_build['databaseName'],_build['databaseSha256'],_build['experimentalFile']),_build)
    _matches=list(_catalogues.values())
if not _matches and not CONFIG.get('arenaVariant'):_matches=[_builds[0]]
if len(_matches)!=1:raise ValueError('Select exactly one supported Arena catalogue build in the installation config')
ARENA_BUILD=_matches[0]
DATABASE_NAME=ARENA_BUILD['databaseName']
DATABASE_SHA256=ARENA_BUILD['databaseSha256']
DB=_raw/DATABASE_NAME
FORGE_SCRIPTS=Path(CONFIG.get('forgeResourcesRoot',str(FORGE_INSTALL)))/'res/cardsfolder/cardsfolder.zip'
SUPPORT_POLICY=Path(os.environ.get('FORGE_ARENA_POLICY',str(Path(__file__).with_name('bridge_support.json')))).resolve()
if ROOT==ARENA or ROOT in ARENA.parents or ARENA in ROOT.parents:raise ValueError('Sandbox and retail install must be independent trees')
