"""Bounded serial regression campaign against one prepared private runtime.

Each game owns fresh rules/native processes and a private IPC folder. Results
are written after every job; failed evidence is retained. No installed client,
game window, GPU, installer, release or production admission is changed.
"""
import argparse
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
    p.add_argument('--group',choices=['decisions','normal','emry','matrix'],required=True);p.add_argument('--max-seconds',type=int,default=2700);a=p.parse_args()
    if not 60<=a.max_seconds<=3600:p.error('Use a bounded campaign of60-3600seconds')
    a.output.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'FORGE_ARENA_CONFIG':str(a.config),'FORGE_ARENA_POLICY':str(a.policy),'DOTNET_PROCESSOR_COUNT':'2','PYTHONIOENCODING':'utf8'}
    common=['--config',str(a.config),'--policy',str(a.policy),'--worker',str(a.worker),'--managed',str(a.managed),'--fixture',str(a.fixture)]
    native=['--snapshot-source','--native-worker',str(a.worker),'--native-managed',str(a.managed),'--native-fixture',str(a.fixture)]
    jobs=[]
    def job(name,script,args=(),timeout=300):jobs.append((name,script,list(args),timeout))
    if a.group=='decisions':
        job('contracts','verify_native_worker_contracts.py',common+['--output',str(a.output/'contracts')])
        job('shared','verify_shared_choices.py',native+['--output',str(a.output/'shared')],600)
        for key in ('attachments','colors','discard','keywords','characteristics','ability_choices','exile_order','protection_attachments'):
            job(key,'verify_native_'+key+'.py',common+['--output',str(a.output/key)],400)
        for key in ('research_payment_boundary','unsupported_choice'):
            job(key,'verify_'+key+'.py',['--config',str(a.config),'--policy',str(a.policy),'--output',str(a.output/key)])
    elif a.group=='matrix':job('matrix','verify_shared_choice_matrix.py',native+['--output',str(a.output/'matrix')],1800)
    elif a.group=='normal':
        for key in ('opening','starting_player','blue','counter','draw','targets','damage_assignment'):
            job(key,'run_persistent_native_regression.py',common+['--script','verify_'+key+'.py','--output',str(a.output/key)])
        for seed in (7274,113,5,42,2026,104729,271828,314159,161803,99991,55555,8675309):
            job('duel-'+str(seed),'run_persistent_native_regression.py',common+['--script','verify_normal_duel.py','--seed',str(seed),'--output',str(a.output/('duel-'+str(seed)))],180)
        job('terminal-direct','verify_terminal.py')
    else:
        for key in ('emry_mechanics','emry_brawl','emry_artifact_land','emry_legend','emry_target_invalidation','emry_library_boundary','emry_commander_bounce','emry_commander_exile','paradox_engine'):
            job(key,'run_persistent_native_regression.py',common+['--script','verify_'+key+'.py','--output',str(a.output/key)],timeout=300)
    folder=Path(__file__).resolve().parent;config=json.loads(a.config.read_text());root=Path(config['privateRoot']);prep=root.parent/'preparation.json'
    hashes={str(path):sha(path) for path in [prep,a.config,a.policy,*a.worker.parent.glob('*.dll')]};rows=[];start=time.monotonic();timed_out=False
    for name,script,args,timeout in jobs:
        remaining=a.max_seconds-(time.monotonic()-start)
        if remaining<30:timed_out=True;break
        began=time.monotonic();error=None
        try:
            with (a.output/(name+'.log')).open('w',encoding='utf8') as log:
                result=run_owned([os.sys.executable,'-X','utf8','-B',str(folder/script),*args],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=min(timeout,remaining))
            code=result.returncode
        except subprocess.TimeoutExpired:error='Bounded test deadline reached';code=-1;timed_out=True
        row=dict(id=name,script=script,exitCode=code,seconds=round(time.monotonic()-began,3),error=error);rows.append(row);print(json.dumps(row),flush=True)
        drift=any(sha(Path(path))!=digest for path,digest in hashes.items())
        result=dict(passed=not drift and not timed_out and len(rows)==len(jobs) and all(r['exitCode']==0 for r in rows),group=a.group,results=rows,plannedJobs=len(jobs),timedOut=timed_out,artifactDrift=drift,pinnedArtifacts=hashes,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
        (a.output/'report.json').write_text(json.dumps(result,indent=2))
        if timed_out or drift:break
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
