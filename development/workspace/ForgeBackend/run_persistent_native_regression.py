"""Run an existing input/oracle regression through the persistent native client.

Native driver rejects invalid UI submissions before calling the handler; direct
backend enforcement remains separately covered by the original regression run.
No Unity, rendered game, assets database or network connection is created.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import functools
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import traceback


ALLOWED={'verify_blue.py','verify_counter.py','verify_draw.py','verify_targets.py','verify_opening.py','verify_starting_player.py','verify_normal_duel.py','verify_damage_assignment.py','verify_terminal.py'}
ALLOWED.update('verify_'+key+'.py' for key in ('emry_mechanics','emry_brawl','emry_artifact_land','emry_legend','emry_target_invalidation','emry_library_boundary','emry_commander_bounce','emry_commander_exile','paradox_engine'))


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--script',choices=sorted(ALLOWED),required=True);p.add_argument('--seed',type=int);a=p.parse_args()
    if a.seed is not None and (a.script!='verify_normal_duel.py' or not 1<=a.seed<2**31):p.error('Seed override supports bounded normal-duel regression seeds only')
    os.environ.update(FORGE_ARENA_CONFIG=str(a.config.resolve()),FORGE_ARENA_POLICY=str(a.policy.resolve()),DOTNET_PROCESSOR_COUNT='2')
    import engine_test_client
    from native_engine_test_client import NativeEngine
    from runtime_paths import ROOT
    preparation=json.loads((ROOT.parent/'preparation.json').read_text());source=Path(__file__).with_name('ForgeLandEngine.java')
    if preparation['sourceSha256']!=sha(source):raise RuntimeError('Compile the current engine before native regression')
    a.output.mkdir(parents=True,exist_ok=False);sessions=[];error=None
    def create(*args,**kwargs):
        engine=NativeEngine(*args,worker=a.worker,managed=a.managed,fixture=a.fixture,**kwargs);sessions.append(engine);return engine
    engine_test_client.Engine=create
    script=Path(__file__).with_name(a.script);original=sys.argv;sys.argv=[str(script)]+([str(a.seed)] if a.seed is not None else [])
    scripts={str(path):sha(path) for path in [script,Path(__file__),Path(__file__).with_name('engine_test_client.py'),Path(__file__).with_name('native_engine_test_client.py'),Path(__file__).with_name('emry_test_client.py')]}
    binaries={str(f):sha(f) for f in a.worker.parent.glob('*.dll')}
    try:
        with (a.output/'run.log').open('w',encoding='utf8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):runpy.run_path(str(script),run_name='__main__')
    except Exception as failure:error=dict(message=str(failure)[:1000],traceback=traceback.format_exc())
    finally:
        sys.argv=original
        for engine in sessions:
            if engine.process.poll() is None or engine.native_process.poll() is None:
                try:engine.close()
                except Exception as cleanup:
                    if error is None:error=dict(message='Owned test process cleanup failed: '+str(cleanup),traceback=traceback.format_exc())
                    else:error['cleanupError']=str(cleanup)
    rows=[]
    for engine in sessions:
        done=engine.native_folder/'completed.json'
        rows.append(dict(evidence=str(engine.ipc),checks=engine.checks,nativeCompletion=json.loads(done.read_text()) if done.exists() else None,javaExited=engine.process.poll() is not None,nativeExited=engine.native_process.poll() is not None))
    if any(sha(Path(f))!=digest for f,digest in {**binaries,**scripts}.items()) or sha(source)!=preparation['sourceSha256']:error=dict(message='Test binaries/source changed during the run')
    result=dict(seed=a.seed,passed=error is None and bool(rows) and all(r['javaExited'] and r['nativeExited'] and r['nativeCompletion'] for r in rows),script=a.script,scriptSha256=scripts[str(script)],testSourceHashes=scripts,engineSourceSha256=preparation['sourceSha256'],nativeBinaries=binaries,sessions=rows,error=error,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
    (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(dict(script=a.script,passed=result['passed'],sessions=len(rows),error=error['message'][:300] if error else None,report=str(a.output/'report.json'))));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
