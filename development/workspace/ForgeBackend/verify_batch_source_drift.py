"""Real mid-run mutation and resume rejection in a disposable source copy.

The active repository, installed client, native lab and owned data are never
mutated. Each probe runs real Forge inputs against a separately prepared rules
runtime and modifies only a copied Python file or copied suite on D:.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from run_background_validation import ChildJob

HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run(a):
    a.output.mkdir(parents=True,exist_ok=False)
    root=Path(json.loads(a.config.read_text(encoding='utf8'))['privateRoot'])
    if (root/'native-lab/MTGA.exe').exists():raise ValueError('Independent test runtime required')
    originals={str(p):sha(p) for p in HERE.glob('*.py')}
    original_suite=a.suite.read_bytes();checks=[]
    def check(label,value):
        checks.append(dict(check=label,passed=bool(value)))
        if not value:raise AssertionError(label)
    for kind in ('source','suite'):
        folder=a.output/kind;shadow=folder/'repo/ForgeBackend';shadow.mkdir(parents=True)
        for pattern in ('*.py','*.java'):
            for source in HERE.glob(pattern):shutil.copy2(source,shadow/source.name)
        suite=shadow/'card_batch_suites/probe.json';suite.parent.mkdir();suite.write_bytes(original_suite)
        output=folder/'results'
        command=[sys.executable,'-X','utf8','-B',str(shadow/'run_card_batches.py'),'--config',str(a.config.resolve()),'--policy',str(a.policy.resolve()),'--suite',str(suite.resolve()),'--execution','cold','--output',str(output.resolve())]
        previous=set((root/'research').glob('combat-check-*'))
        with (folder/'driver.log').open('w',encoding='utf8') as log:
            job=ChildJob();process=subprocess.Popen(command,cwd=folder/'repo',stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);job.attach(process)
            try:
                end=time.monotonic()+60
                while time.monotonic()<end:
                    new=set((root/'research').glob('combat-check-*'))-previous
                    if any((p/'state.json').exists() for p in new):break
                    if process.poll() is not None:raise RuntimeError('Driver ended before injected mutation: '+(folder/'driver.log').read_text())
                    time.sleep(.02)
                else:raise TimeoutError('No real case reached its initial state')
                target=shadow/'card_batch_case.py' if kind=='source' else suite
                before=sha(target)
                with target.open('ab') as changed:changed.write(b'\n# deliberate shadow-source mutation\n' if kind=='source' else b'\n ')
                mutation=dict(path=str(target),before=before,after=sha(target),when='After first real game state appeared')
                (folder/'mutation.json').write_text(json.dumps(mutation,indent=2),encoding='utf8')
                code=process.wait(timeout=120)
            finally:
                job.close()
                if process.poll() is None:process.wait(timeout=10)
        report=json.loads((output/'report.json').read_text())
        check(kind+' mutation prevents a passing batch',code==1 and report['status']=='needs-attention')
        check(kind+' mutation stops before another case',len(report['cases'])==1 and report['summary']['notRun']>0 and report['cases'][0]['category']=='provenance')
        check(kind+' mutation identifies the exact changed path',str(target.resolve()) in report['stoppedEarly']['paths'])
        snapshot=Path(report['sourceArchive'])/target.relative_to(folder/'repo')
        check(kind+' original executed source bytes remain recoverable',snapshot.is_file() and sha(snapshot)==before)
        with (folder/'resume.log').open('w',encoding='utf8') as log:
            resume=subprocess.run(command+['--resume'],cwd=folder/'repo',stdout=log,stderr=subprocess.STDOUT,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        check(kind+' changed inputs cannot silently resume old evidence',resume.returncode!=0 and 'Source, inputs or runtime changed' in (folder/'resume.log').read_text())
    check('All active repository Python sources are unchanged',all(Path(p).is_file() and sha(Path(p))==h for p,h in originals.items()))
    check('Original authored suite is unchanged',a.suite.read_bytes()==original_suite)
    (a.output/'report.json').write_text(json.dumps(dict(checks=len(checks),results=checks,scope='Real mid-run source/input fault injection and resume boundaries in disposable copies; no admission changes.'),indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','suite','output'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
