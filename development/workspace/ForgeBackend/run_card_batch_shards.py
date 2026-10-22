"""Run whole-card partitions in isolated research runtimes with explicit CPU pairs.

Only immutable Forge resources are shared. Every worker has its own classes,
manifest, mutable profile/cache, lock, games, IPC and process job. Original
suite expectations are partitioned unchanged; no shard can admit a card.
"""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import shutil
from types import SimpleNamespace
from clone_research_runtime import clone
from run_card_batches import validate,sha
from run_background_validation import ChildJob

HERE=Path(__file__).resolve().parent


def partitions(suite,count):
    by=defaultdict(list)
    for case in suite['cases']:by[case['card']].append(case)
    if not 1<=count<=min(4,len(by)):raise ValueError('Use one to four nonempty card partitions')
    groups=[[] for _ in range(count)];weights=[0]*count
    for name in sorted(by,key=lambda n:(-len(by[n]),n.casefold())):
        index=min(range(count),key=lambda i:(weights[i],i));groups[index].append(name);weights[index]+=len(by[name])
    results=[]
    for names in groups:
        value={**suite,'cards':{n:suite['cards'][n] for n in names},'cases':[c for c in suite['cases'] if c['card'] in names]}
        validate(value);results.append(value)
    actual=[c for part in results for c in part['cases']]
    original={c['id']:c for c in suite['cases']}
    if len(actual)!=len(original) or {c['id']:c for c in actual}!=original:raise ValueError('Partition lost, duplicated or changed authored cases')
    return results


def run(a):
    if a.output.exists():raise ValueError('Fresh shard experiment folder required')
    if len(a.cpu_mask)!=a.workers or any(m<=0 or m.bit_count()!=2 for m in a.cpu_mask):raise ValueError('Each worker needs exactly one two-processor mask')
    if any(left&right for i,left in enumerate(a.cpu_mask) for right in a.cpu_mask[i+1:]):raise ValueError('Worker CPU allocations must be disjoint')
    suite=validate(json.loads(a.suite.read_text(encoding='utf8')));parts=partitions(suite,a.workers)
    a.output.mkdir(parents=True);receipts=[]
    identities={str(p.resolve()):sha(p) for p in (a.suite,a.source_config,a.source_policy,Path(__file__),HERE/'run_research_process.py',HERE/'clone_research_runtime.py')}
    archive=a.output/'source'
    for name,digest in identities.items():
        original=Path(name)
        if HERE in original.parents:
            target=archive/original.relative_to(HERE.parent);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,target)
            if sha(target)!=digest:raise ValueError('Source changed during partition preparation')
    for index,part in enumerate(parts):
        folder=a.output/('shard-'+str(index+1));folder.mkdir();path=folder/'suite.json';path.write_text(json.dumps(part,indent=2,ensure_ascii=False),encoding='utf8')
        clone(SimpleNamespace(source_config=a.source_config,source_policy=a.source_policy,output=folder/'prepared',javac=a.javac))
        receipts.append(dict(index=index+1,folder=str(folder),suite=str(path),cases=len(part['cases']),cards=list(part['cards']),cpuMask=a.cpu_mask[index],status='prepared'))
    profile_paths=[]
    for row in receipts:
        config=json.loads((Path(row['folder'])/'prepared/runtime-config.json').read_text());profile_paths.append(Path(config['privateRoot']).resolve())
    if len(set(profile_paths))!=len(profile_paths):raise ValueError('Shards must not share runtime/cache ownership')
    status=dict(schema=1,startedUtc=datetime.now(timezone.utc).isoformat(),status='running',identities=identities,sourceArchive=str(archive.resolve()),sourceSuiteCases=len(suite['cases']),sourceSuiteCards=len(suite['cards']),shards=receipts,
        scope='Partitioned research execution only; independent profiles/caches and original expectations. No admission or publication.')
    report=a.output/'report.json'
    def save():report.write_text(json.dumps(status,indent=2),encoding='utf8')
    save();active=[];start=time.monotonic()
    try:
        for row in receipts:
            folder=Path(row['folder']);log=(folder/'driver.log').open('w',encoding='utf8');job=ChildJob()
            command=[sys.executable,'-X','utf8','-B',str(HERE/'run_research_process.py'),'--cpu-mask',hex(row['cpuMask']),'--receipt',str(folder/'cpu-allocation.json'),str(HERE/'run_card_batches.py'),
                '--config',str(folder/'prepared/runtime-config.json'),'--policy',str(folder/'prepared/research-policy.json'),'--suite',row['suite'],'--execution','warm','--warm-max-cases',str(a.warm_max_cases),'--output',str(folder/'results')]
            process=subprocess.Popen(command,cwd=HERE.parent,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);job.attach(process)
            row.update(status='running',pid=process.pid,command=command);active.append((row,process,job,log));save()
        while any(p.poll() is None for _,p,_,_ in active):
            if time.monotonic()-start>a.seconds:raise TimeoutError('Whole shard experiment exceeded its explicit bound')
            if any(sha(Path(path))!=digest for path,digest in identities.items()):raise ValueError('Partition source/input changed during execution')
            time.sleep(.2)
        for row,process,_,_ in active:
            path=Path(row['folder'])/'results/report.json'
            child=json.loads(path.read_text()) if path.exists() else {}
            row.update(status='passed' if process.returncode==0 and child.get('status')=='passed' else 'failed',exitCode=process.returncode,report=str(path),reportSha256=sha(path) if path.exists() else None)
        seen={};passed=set();assertions=0;case_statuses=Counter()
        definitions={c['id']:c for c in suite['cases']}
        for row in receipts:
            if not Path(row['report']).exists():continue
            child=json.loads(Path(row['report']).read_text())
            if child['identities'].get(str(Path(row['suite']).resolve()))!=sha(Path(row['suite'])):raise ValueError('Child suite differs from its original partition')
            for case in child['cases']:
                if case['id'] in seen or case['id'] not in definitions or case['card']!=definitions[case['id']]['card']:raise ValueError('Duplicate, unknown or mislabeled executed case across shards')
                seen[case['id']]=row['index']
                case_statuses[case['status']]+=1;assertions+=case.get('checks',0)
                if case['status']=='passed':passed.add(case['id'])
        expected={c['id'] for c in suite['cases']}
        status.update(status='passed' if all(r['status']=='passed' for r in receipts) and passed==expected else 'needs-attention',executedCases=len(seen),notRun=len(expected-set(seen)),notPassed=len(expected-passed),caseStatuses=dict(case_statuses),assertions=assertions,seconds=round(time.monotonic()-start,3),finishedUtc=datetime.now(timezone.utc).isoformat(),newAdmissions=0)
        save();print(json.dumps({k:v for k,v in status.items() if k not in ('shards','identities')}),flush=True)
        return 0 if status['status']=='passed' else 1
    except BaseException as error:
        status.update(status='interrupted',error=repr(error),finishedUtc=datetime.now(timezone.utc).isoformat());save();raise
    finally:
        for _,process,job,log in active:
            job.close()
            if process.poll() is None:process.wait(timeout=10)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source-config','source-policy','suite','output','javac'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--workers',type=int,default=2);p.add_argument('--cpu-mask',type=lambda v:int(v,0),action='append',required=True)
    p.add_argument('--warm-max-cases',type=int,default=100);p.add_argument('--seconds',type=int,default=1800)
    a=p.parse_args()
    if not 1<=a.workers<=4 or not 1<=a.warm_max_cases<=200 or not 60<=a.seconds<=7200:p.error('Use1..4workers,1..200cases/worker lifetime,60..7200seconds total bound')
    raise SystemExit(run(a))
