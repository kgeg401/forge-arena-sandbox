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
DATABASE_NAME='Raw_CardDatabase_c344d0dccdfb898a5e3fd4101eedbd48.mtga'
DB=Path(CONFIG.get('catalogueInstall',str(ARENA)))/'MTGA_Data/Downloads/Raw'/DATABASE_NAME
FORGE_SCRIPTS=Path(CONFIG.get('forgeResourcesRoot',str(FORGE_INSTALL)))/'res/cardsfolder/cardsfolder.zip'
if ROOT==ARENA or ROOT in ARENA.parents or ARENA in ROOT.parents:raise ValueError('Sandbox and retail install must be independent trees')
