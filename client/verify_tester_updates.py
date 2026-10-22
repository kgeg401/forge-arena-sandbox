"""Exercise update safety with disposable authored fixtures, not game assets."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json, os, stat, uuid, zipfile
from tester_common import sha, version, safe_relative, extract_verified, verify_tree, repository_name, metadata_recipe
from update_tester import apply_archive, rollback

ROOT=Path(os.environ.get('FORGE_ARENA_TEST_OUTPUT',__import__('tempfile').gettempdir()))/'forge-arena-tests'/('update-check-'+uuid.uuid4().hex[:8])
ROOT.mkdir(parents=True);checks=[]
def check(label,condition):
    if not condition:raise AssertionError(label)
    checks.append(dict(check=label,passed=True))
def rejected(label,action):
    try:action()
    except (ValueError,OSError,zipfile.BadZipFile):check(label,True)
    else:raise AssertionError('Unexpected acceptance: '+label)

check('Semantic prerelease numbers compare numerically',version('0.1.0-preview.10')>version('0.1.0-preview.2'))
check('A stable release sorts after its prereleases',version('0.1.0')>version('0.1.0-rc.20'))
check('New patch version supersedes older stable release',version('0.1.1')>version('0.1.0'))
check('Explicit GitHub repository identity is retained',repository_name('Card-Forge/forge')=='Card-Forge/forge')
recipe_app=ROOT/'authored-index-fixture'
for name in ('ForgeBackend/runtime_paths.py','ForgeBackend/deck_import.py','ForgeBackend/build_card_coverage.py','ForgeBackend/bridge_support.json','DeckBackend/build_deck_catalog.py'):
    p=recipe_app/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('authored metadata fixture '+name)
recipe_before=metadata_recipe(recipe_app)
check('Unchanged metadata inputs retain their fingerprint',metadata_recipe(recipe_app)==recipe_before)
(recipe_app/'DeckBackend/build_deck_catalog.py').write_text('changed generator; unchanged admission policy')
check('Generator-only updates invalidate derived metadata',metadata_recipe(recipe_app)!=recipe_before)
recipe_before=metadata_recipe(recipe_app)
(recipe_app/'ForgeBackend/bridge_support.json').write_text('changed explicit admission policy')
check('Admission-policy updates invalidate derived metadata',metadata_recipe(recipe_app)!=recipe_before)
for bad_repo in ('../repo','owner/..','owner/repo/extra','https://github.com/owner/repo','owner name/repo'):
    rejected('Reject unsafe repository identity '+bad_repo,lambda value=bad_repo:repository_name(value))
for unsafe in ('../escape','/absolute','C:/evil','folder\\evil','NUL.txt','folder/../escape','file.','file ','a//b'):
    rejected('Reject unsafe archive path '+unsafe,lambda n=unsafe:safe_relative(n))

install=ROOT/'Test Installation';data=install/'data';(data/'forge-runtime').mkdir(parents=True)
(data/'forge-runtime/forge.jar').write_bytes(b'authored fake engine fixture; not executable')
profile=data/'native-lab/local-profile';profile.mkdir(parents=True)
(profile/'decks.json').write_text('{"my deck":"never overwrite"}');(profile/'packs.json').write_text('{"cards":112,"packs":99}')
original={p.name:p.read_bytes() for p in profile.iterdir()}
config=dict(schema=1,profileSchema=1,privateRoot=str(data));(install/'sandbox-install.json').write_text(json.dumps(config))

def package(tag,name=None,wrong_engine=False,profile_schema=1):
    folder=ROOT/(name or ('package-'+tag));folder.mkdir()
    (folder/'application.txt').write_text('authored adapter version '+tag)
    requirements=dict(arenaFiles={},forgeJar='forge.jar',forgeFiles={'forge.jar':'0'*64 if wrong_engine else sha(data/'forge-runtime/forge.jar')},loaderFiles={})
    (folder/'requirements.json').write_text(json.dumps(requirements))
    manifest=dict(schema=1,version=tag,profileSchema=profile_schema,files={p.name:sha(p) for p in folder.iterdir()})
    (folder/'release-manifest.json').write_text(json.dumps(manifest))
    archive=folder.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in folder.iterdir():z.write(file,file.name)
    return folder,archive

old,old_zip=package('0.1.0');versions=install/'versions';versions.mkdir();old.rename(versions/'0.1.0')
(install/'active-version.json').write_text(json.dumps(dict(version='0.1.0',previous=None,profileSchema=1)))
next_folder,next_zip=package('0.1.1')
before=(install/'active-version.json').read_bytes()
rejected('Wrong download digest preserves current release',lambda:apply_archive(install,next_zip,'0'*64))
check('Digest failure leaves active-version bytes intact',(install/'active-version.json').read_bytes()==before)
rejected('Release/archive version mismatch is rejected',lambda:apply_archive(install,next_zip,expected_version='0.1.2'))
check('Version mismatch preserves current release',(install/'active-version.json').read_bytes()==before)
receipt=apply_archive(install,next_zip,sha(next_zip),'0.1.1')
check('Valid staged update switches to new version',json.loads((install/'active-version.json').read_text())['version']=='0.1.1')
check('Update retains the old version directory',(versions/'0.1.0/application.txt').exists())
check('Update preserves every profile byte',{p.name:p.read_bytes() for p in profile.iterdir()}==original)
backup=Path(receipt['profileBackup']);check('Update makes a complete profile backup',{p.name:p.read_bytes() for p in backup.iterdir()}==original)
rejected('Same version cannot overwrite installed version',lambda:apply_archive(install,next_zip))
rollback_receipt=rollback(install)
check('Rollback selects the retained old release',rollback_receipt['version']=='0.1.0')
check('Rollback preserves every profile byte',{p.name:p.read_bytes() for p in profile.iterdir()}==original)
before=(install/'active-version.json').read_bytes()
wrong_folder,wrong_zip=package('0.1.2',wrong_engine=True)
rejected('Incompatible engine update is rejected',lambda:apply_archive(install,wrong_zip))
check('Incompatibility preserves active release',(install/'active-version.json').read_bytes()==before)
schema_folder,schema_zip=package('0.1.3',profile_schema=2)
rejected('Unsupported profile migration is rejected',lambda:apply_archive(install,schema_zip))
check('Rejected migration preserves profile bytes',{p.name:p.read_bytes() for p in profile.iterdir()}==original)
tampered_folder,tampered_zip=package('0.1.4');(tampered_folder/'application.txt').write_text('tampered code')
rejected('Modified application fails manifest check',lambda:verify_tree(tampered_folder))
(next_folder/'unexpected.py').write_text('print("must not run")')
rejected('Unexpected code is rejected',lambda:verify_tree(next_folder))
bad=ROOT/'traversal.zip'
with zipfile.ZipFile(bad,'w') as z:z.writestr('../escaped.txt','never write outside staging')
rejected('Traversal ZIP is rejected before escape',lambda:extract_verified(bad,ROOT/'traversal-stage'))
check('Traversal did not write outside staging',not (ROOT/'escaped.txt').exists())
alias=ROOT/'case-alias.zip'
with zipfile.ZipFile(alias,'w') as z:z.writestr('file.txt','first');z.writestr('FILE.txt','alias')
rejected('Case-insensitive ZIP aliases are rejected',lambda:extract_verified(alias,ROOT/'case-alias-stage'))
link=ROOT/'symlink.zip'
with zipfile.ZipFile(link,'w') as z:
    entry=zipfile.ZipInfo('link');entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(entry,'../outside')
rejected('ZIP symbolic links are rejected',lambda:extract_verified(link,ROOT/'symlink-stage'))
check('All failed archives preserve the active release',(install/'active-version.json').read_bytes()==before)
check('All failures preserve every user-profile byte',{p.name:p.read_bytes() for p in profile.iterdir()}==original)
result=dict(scope='Authored update fixtures only; not a second-PC installation',checks=checks,total=len(checks),evidence=str(ROOT))
(ROOT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(checks=len(checks),evidence=str(ROOT)),indent=2))
