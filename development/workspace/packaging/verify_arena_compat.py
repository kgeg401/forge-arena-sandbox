"""Recognized builds pass; mixed, modified and unknown game files stay blocked."""
from pathlib import Path
import copy,json,tempfile,os,subprocess,sys
from arena_compat import select_arena
from tester_common import sha

checks=[]
def check(name,value):
    assert value,name
    checks.append(name)

with tempfile.TemporaryDirectory(prefix='forge-arena-builds-') as temp:
    root=Path(temp);variants=[]
    for tag in ('old','current'):
        game=root/tag
        for name,value in [('MTGA_Data/Managed/Core.dll',tag+' core'),('MTGA_Data/Downloads/Raw/database.mtga',tag+' cards'),('MTGA.exe',tag+' exe')]:
            file=game/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(value)
        variants.append(dict(id=tag,arenaBuild=tag,arenaFiles={str(p.relative_to(game)).replace('\\','/'):sha(p) for p in game.rglob('*') if p.is_file()}))
    req=dict(arenaVariants=variants,arenaFiles=variants[0]['arenaFiles'],loaderFiles={'retain':'this'})
    for tag in ('old','current'):
        selected=select_arena(req,root/tag)
        check(tag+' exact game fingerprint selects only its own build',selected['arenaVariant']==tag and selected['arenaFiles']==next(v['arenaFiles'] for v in variants if v['id']==tag))
        check(tag+' selection preserves unrelated prerequisites',selected['loaderFiles']==req['loaderFiles'])
    original=copy.deepcopy(req);select_arena(req,root/'current');check('Selection does not mutate the release requirements',req==original)
    current=root/'current';core=current/'MTGA_Data/Managed/Core.dll';database=current/'MTGA_Data/Downloads/Raw/database.mtga';exe=current/'MTGA.exe'
    def rejects(name,change):
        before={p:p.read_bytes() for p in (core,database,exe)};change()
        try:select_arena(req,current)
        except ValueError:pass
        else:raise AssertionError(name)
        check(name,True)
        for p,b in before.items():p.write_bytes(b)
    rejects('Unknown core is rejected',lambda:core.write_text('unknown core'))
    rejects('Known core with changed database is rejected',lambda:database.write_text('changed cards'))
    rejects('Mixed older database and current core is rejected',lambda:database.write_bytes((root/'old/MTGA_Data/Downloads/Raw/database.mtga').read_bytes()))
    rejects('Modified executable is rejected',lambda:exe.write_text('changed exe'))
    rejects('Missing required file is rejected',lambda:exe.unlink())
    try:select_arena(req,root/'missing')
    except ValueError:check('Empty or partial installation is rejected',True)
    else:raise AssertionError('Missing game passed')
    legacy=dict(arenaFiles={'fixture':'retained'})
    check('Older release fixtures retain their original exact-check path',select_arena(legacy,current)==legacy)
    steam=copy.deepcopy(variants[1]);steam['id']='current-steam'
    exe.write_text('steam exe');steam['arenaFiles']['MTGA.exe']=sha(exe);req['arenaVariants'].append(steam)
    check('Steam executable with identical libraries selects its exact store profile',select_arena(req,current)['arenaVariant']=='current-steam')
    database.write_text('changed cards')
    try:select_arena(req,current)
    except ValueError as error:check('Store executable does not waive card database validation',str(database.relative_to(current)).replace('\\','/') in str(error))
    else:raise AssertionError('Steam profile waived changed database')
    exe.write_text('unknown executable')
    try:select_arena(req,current)
    except ValueError as error:check('Nearest store profile reports actual differing file names','MTGA.exe' in str(error))
    else:raise AssertionError('Unknown executable passed')

with tempfile.TemporaryDirectory(prefix='forge-arena-catalogues-') as temp:
    root=Path(temp);raw=root/'game/MTGA_Data/Downloads/Raw';raw.mkdir(parents=True)
    runtime=Path(__file__).resolve().parents[1]/'ForgeBackend/runtime_paths.py'
    profiles=json.loads(runtime.with_name('arena-builds.json').read_text(encoding='utf8'))['builds']
    current=next(b for b in profiles if b['id']=='arena-14589')
    (raw/current['databaseName']).touch()
    config=root/'config.json';settings=dict(schema=1,privateRoot=str(root/'private'),arenaInstall=str(root/'game'),catalogueInstall=str(root/'game'))
    def catalogue(variant=None):
        config.write_text(json.dumps({**settings,**({'arenaVariant':variant} if variant else {})}),encoding='utf8')
        return subprocess.run([sys.executable,'-X','utf8','-B','-c','import runpy,sys; print(runpy.run_path(sys.argv[1])["ARENA_BUILD"]["id"])',str(runtime)],env={**os.environ,'FORGE_ARENA_CONFIG':str(config)},capture_output=True,text=True,timeout=20)
    result=catalogue();check('Identical store catalogues resolve without an explicit store selection',result.returncode==0 and result.stdout.strip()=='arena-14589')
    result=catalogue('arena-14589-steam');check('Saved Steam profile selects the shared current catalogue',result.returncode==0 and result.stdout.strip()=='arena-14589-steam')
    result=catalogue('unknown');check('Unknown configured store build stays rejected',result.returncode!=0)
    (raw/profiles[0]['databaseName']).touch()
    result=catalogue();check('Different catalogue versions still require explicit selection',result.returncode!=0)

print(json.dumps(dict(checks=len(checks),passed=checks),indent=2))
