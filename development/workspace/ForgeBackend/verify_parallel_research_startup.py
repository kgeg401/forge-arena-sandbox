"""Exercise concurrent first-start native sessions after private profile preparation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from headless_resources import run_owned


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--parallel',type=int,default=4);a=p.parse_args()
    if not 2<=a.parallel<=4:p.error('Use 2-4 isolated startup sessions')
    config=json.loads(a.config.read_text());root=Path(config['privateRoot']);preparation=root.parent/'preparation.json';profile=root.parent/'profile-preparation.json'
    receipt=json.loads(preparation.read_text());directories=json.loads(profile.read_text())
    if not receipt['researchOnly'] or receipt['profilePreparationSha256']!=sha(profile) or not directories['prepared']:raise ValueError('Prepared private profile receipt required')
    for value in directories['directories']:
        path=Path(value).resolve()
        if not path.is_relative_to((root/'forge-runtime').resolve()) or not path.is_dir():raise ValueError('Prepared profile directory is missing or outside the private runtime')
    a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    common=[item for key in ('config','policy','worker','managed','fixture') for item in ('--'+key,str(getattr(a,key)))]
    def run(index):
        folder=a.output/str(index);began=time.monotonic()
        try:
            with (a.output/(str(index)+'.log')).open('w',encoding='utf8') as log:
                result=run_owned([os.sys.executable,'-X','utf8','-B',str(Path(__file__).with_name('verify_native_worker_contracts.py')),*common,'--output',str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=150)
        except subprocess.TimeoutExpired:return dict(id=index,exitCode=-1,passed=False,error='Owned startup test deadline reached',seconds=round(time.monotonic()-began,3))
        report=folder/'report.json'
        return dict(id=index,exitCode=result.returncode,seconds=round(time.monotonic()-began,3),report=str(report),reportSha256=sha(report) if report.exists() else None,passed=result.returncode==0 and report.exists() and json.loads(report.read_text())['passed'])
    with ThreadPoolExecutor(max_workers=a.parallel) as executor:rows=list(executor.map(run,range(a.parallel)))
    result=dict(passed=all(r['passed'] for r in rows),parallelSessions=a.parallel,seconds=round(time.monotonic()-start,3),results=rows,profilePreparationSha256=sha(profile),runtimePreparationSha256=sha(preparation),finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
    (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
