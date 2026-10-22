"""Bounded, restartable gameplay batches. Never changes card admission or launches Arena."""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf8')
    pending.replace(path)


def changed(identities):
    return [str(p) for name,digest in identities.items() if not (p:=Path(name)).is_file() or sha(p)!=digest]


def validate(suite):
    if suite.get('schema')==2:
        from validate_card_scenario import validate as validate_scenario
        return validate_scenario(suite)
    if suite.get('schema') != 1 or not suite.get('cards') or not suite.get('cases'):
        raise ValueError('A nonempty schema-1 suite with explicit coverage is required')
    names = set(suite['cards'])
    ids = set()
    fixtures = {'fixtureHand':8, 'fixtureLands':100, 'fixtureBattlefield':8,
                'fixtureOpponentBattlefield':8, 'fixtureGraveyard':40, 'fixtureOpponentGraveyard':40}
    for name, branches in suite['cards'].items():
        if not branches or len(branches) != len(set(branches)):
            raise ValueError('Each card needs distinct required branches: '+name)
    for case in suite['cases']:
        key = case['id']
        if not key or len(key) > 100 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in key) or key in ids:
            raise ValueError('Distinct path-safe case IDs required')
        ids.add(key)
        if case['card'] not in names or not case['covers'] or not set(case['covers']) <= set(suite['cards'][case['card']]):
            raise ValueError('Unknown card or coverage branch')
        f = case['fixture']
        if not {'fixtureHand','fixtureLands'} <= set(f) or set(f)-set(fixtures):
            raise ValueError('Unsupported initial fixture')
        if any(not isinstance(values, list) or len(values) > fixtures[k] or any(not isinstance(n,str) or not n for n in values) for k,values in f.items()):
            raise ValueError('Fixture exceeds research bounds')
        if not case['steps'] or not any(s.get('op') in ('cast','deny') and s.get('card') == case['card'] for s in case['steps']):
            raise ValueError('A case must exercise a cast request for its declared card')
        for step in case['steps']:
            op = step.get('op')
            if op == 'phase':
                if set(step) != {'op','phase'} or step['phase'] != 'COMBAT_BEGIN':
                    raise ValueError('Only bounded combat-phase advancement is implemented')
            elif op == 'deny':
                if set(step) != {'op','card'}:
                    raise ValueError('Invalid timing denial')
            elif op == 'cast':
                if not {'op','card','mana','draw','life'} <= set(step) or set(step)-{'op','card','mana','draw','life','zone'}:
                    raise ValueError('Every cast needs independently authored expected results')
                if any(type(step[k]) is not int or step[k] < 0 for k in ('mana','draw','life')) or step.get('zone','graveyard') not in ('graveyard','battlefield'):
                    raise ValueError('Invalid cast oracle')
            else:
                raise ValueError('Unsupported step')
    return suite


def summarize(report, suite):
    by_id = {c['id']:c for c in suite['cases']}
    covered = defaultdict(set)
    failures = defaultdict(list)
    for row in report['cases']:
        if row['status'] == 'passed':
            c = by_id[row['id']]
            covered[c['card']].update(c['covers'])
        else:
            failures[row.get('category','infrastructure')].append(row['id'])
    report['summary'] = dict(totalCases=len(suite['cases']), completed=len(report['cases']),
        notRun=len(suite['cases'])-len(report['cases']),
        statuses=dict(Counter(r['status'] for r in report['cases'])),
        assertions=sum(r.get('checks',0) for r in report['cases']), failuresByCategory=dict(failures),
        cards={name:dict(passedBranches=sorted(covered[name]), missingBranches=sorted(set(branches)-covered[name]),
                       headlessBranchesComplete=set(branches) <= covered[name], admitted=False,
                       remainingGates=['Arena/Forge rules equivalence review','native art and controls','complete shuffled matches'])
               for name,branches in suite['cards'].items()})


def run(a):
    from run_background_validation import ChildJob, lower_resources
    from headless_resources import process_flags
    lower_resources()
    execution=getattr(a,'execution','cold')
    if execution=='warm':
        # Warm execution imports the engine client in this process. Establish
        # its configuration before runtime_paths can cache module constants.
        os.environ['FORGE_ARENA_CONFIG']=str(a.config.resolve())
        os.environ['FORGE_ARENA_POLICY']=str(a.policy.resolve())
    config = json.loads(a.config.read_text(encoding='utf-8-sig'))
    root = Path(config['privateRoot']).resolve()
    manifest_path = root/'native-lab/bridge-card-manifest.json'
    policy = json.loads(a.policy.read_text(encoding='utf-8-sig'))
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    if config.get('schema') != 1 or not policy.get('researchOnly') or not manifest.get('researchOnly') or (root/'native-lab/MTGA.exe').exists():
        raise ValueError('Only an independent research runtime is allowed')
    if manifest['policySha256'] != sha(a.policy):
        raise ValueError('Research policy differs from generated source mapping')
    build_path=root.parent/'preparation.json'
    build=json.loads(build_path.read_text(encoding='utf8'))
    actual_classes={p.name:sha(p) for p in sorted((root/'build/ForgeBackend/classes').glob('ForgeLandEngine*.class'))}
    if (not build.get('researchOnly') or build['sourceSha256']!=sha(HERE/'ForgeLandEngine.java') or
        not actual_classes or build['classes']!=actual_classes or
        build['forgeJarSha256']!=sha(root/'forge-runtime/forge.jar') or build['gsonJarSha256']!=sha(root/'forge-runtime/gson.jar')):
        raise ValueError('Engine build does not match its source/dependency receipt; prepare a fresh runtime')
    suite = validate(json.loads(a.suite.read_text(encoding='utf8')))
    fixture_names = {n for c in suite['cases'] for values in c['fixture'].values() if isinstance(values,list) for n in values}
    step_names = {s['card'] for c in suite['cases'] for s in c['steps'] if 'card' in s}
    if not fixture_names | step_names <= set(policy['verifiedNames']):
        raise ValueError('Suite contains unmapped research identities')
    from runtime_paths import DATABASE_NAME
    database = Path(config.get('catalogueInstall',config['arenaInstall']))/'MTGA_Data/Downloads/Raw'/DATABASE_NAME
    scripts = Path(config.get('forgeResourcesRoot',str(root/'forge-runtime')))/'res/cardsfolder/cardsfolder.zip'
    identities = {str(p.resolve()):sha(p) for p in [a.config,a.policy,a.suite,manifest_path,build_path,database,scripts,
        HERE/'ForgeLandEngine.java',HERE/'engine_test_client.py',HERE/'runtime_paths.py',HERE/'headless_resources.py',
        HERE/'run_background_validation.py',Path(__file__).resolve(),HERE/'card_batch_case.py',
        root/'forge-runtime/forge.jar',root/'forge-runtime/gson.jar',
        *sorted((root/'build/ForgeBackend/classes').glob('ForgeLandEngine*.class'))]}
    if manifest['sourceDatabaseSha256'] != sha(database) or manifest['sourceForgeScriptsSha256'] != sha(scripts):
        raise ValueError('Owned database or scripts changed after mapping')
    if suite['schema']==2:
        for p in (HERE/'card_batch_scenario.py',HERE/'validate_card_scenario.py'):
            identities[str(p.resolve())]=sha(p)
    if not (root/'build/ForgeBackend/classes/ForgeLandEngine.class').is_file():
        raise ValueError('Compile the independent rules engine first')
    if execution=='warm':
        worker_classes={p.name:sha(p) for p in sorted((root/'build/ForgeBackend/classes').glob('ResearchGameWorker*.class'))}
        if (not worker_classes or build.get('workerClasses')!=worker_classes or
            build.get('workerSourceSha256')!=sha(HERE/'ResearchGameWorker.java')):
            raise ValueError('Prepare the current research worker before using warm execution')
        for p in [HERE/'ResearchGameWorker.java',HERE/'warm_game_worker.py',*sorted((root/'build/ForgeBackend/classes').glob('ResearchGameWorker*.class'))]:
            identities[str(p.resolve())]=sha(p)
    # Same lock as the full rules runner: no two drivers share mutable resources.
    locks=root/'research/background-runs';locks.mkdir(parents=True,exist_ok=True)
    with (locks/'validation.lock').open('a+b') as lock, ExitStack() as cleanup:
        lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        path=a.output/'report.json'
        if a.resume or a.retry_failed:
            report=json.loads(path.read_text(encoding='utf8'))
            if report['identities'] != identities:
                raise ValueError('Source, inputs or runtime changed; use a new output directory')
            if report.get('execution','cold')!=execution:
                raise ValueError('Execution mode changed; use a new output directory')
        else:
            a.output.mkdir(parents=True,exist_ok=False)
            report=dict(schema=1, startedUtc=datetime.now(timezone.utc).isoformat(), status='running',
                        identities=identities, cases=[], researchOnly=True, admittedCards=0,
                        execution=execution,
                        limits=dict(workers=1,javaHeapMiB=1024,javaProcessors=2,caseTimeoutSeconds=a.timeout),
                        scope='Actual input-driven Forge cases. Passing a case never admits a card or proves native presentation, all interactions or complete matches.')
            archive=a.output/'source'
            for name,digest in identities.items():
                original=Path(name)
                if HERE in original.parents:
                    copy=archive/original.relative_to(HERE.parent);copy.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,copy)
                    if sha(copy)!=digest:raise ValueError('Source changed while preserving its exact bytes')
            report['sourceArchive']=str(archive.resolve())
        # These small mutable inputs are rechecked around each case. Large
        # source databases/resources and binaries are verified at both ends.
        guarded={name:digest for name,digest in identities.items() if HERE in Path(name).parents or Path(name) in (a.config.resolve(),a.policy.resolve(),a.suite.resolve(),manifest_path,build_path)}
        done={r['id']:r for r in report['cases']}
        if len(done)!=len(report['cases']) or not set(done) <= {c['id'] for c in suite['cases']}:
            raise ValueError('Duplicate or foreign case results in checkpoint')
        env={**os.environ,'FORGE_ARENA_CONFIG':str(a.config.resolve()),'FORGE_ARENA_POLICY':str(a.policy.resolve()),
             'FORGE_ARENA_TEST_HEAP_MB':'1024','FORGE_ARENA_TEST_THREADS':'2','PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1'}
        pool=None
        if execution=='warm':
            from runtime_paths import ROOT as active_root
            if active_root!=root:raise ValueError('Warm client module was imported under another runtime')
            from warm_game_worker import WarmPool
            pool=cleanup.enter_context(WarmPool(a.output/('warm-workers-'+uuid.uuid4().hex[:8]),getattr(a,'warm_max_cases',25)))
            report.setdefault('warmWorkerRuns',[]).append(str(pool.folder))
        report['status']='running'
        report.pop('stoppedEarly',None)
        summarize(report,suite);save(path,report)
        last_failure=None;consecutive=0
        for case in suite['cases']:
            old=done.get(case['id'])
            if old and (not a.retry_failed or old['status']=='passed'):
                continue
            drift=changed(guarded)
            if drift:
                report['stoppedEarly']=dict(reason='Source or input changed during execution',paths=drift);save(path,report);break
            attempt=1+(old.get('attempt',1) if old else 0)
            result_path=a.output/(case['id']+f'-{attempt}.json')
            log=a.output/(case['id']+f'-{attempt}.log')
            start=time.monotonic();job=ChildJob()
            report['activeCase']=case['id'];save(path,report)
            try:
                if pool:
                    row=pool.execute(case,a.timeout,suite['schema'])
                    save(result_path,row)
                    log.write_text(json.dumps(dict(case=case['id'],**row),indent=2),encoding='utf8')
                else:
                  with log.open('w',encoding='utf8') as stream:
                    proc=subprocess.Popen([sys.executable,'-X','utf8','-B',str(HERE/'card_batch_case.py'),
                        '--suite',str(a.suite.resolve()),'--case',case['id'],'--output',str(result_path.resolve())],
                        env=env,cwd=HERE.parent,stdout=stream,stderr=subprocess.STDOUT,creationflags=process_flags())
                    job.attach(proc)
                    try:
                        code=proc.wait(timeout=a.timeout)
                    except subprocess.TimeoutExpired:
                        job.close();proc.wait(timeout=10)
                        row=dict(status='failed',category='timeout',error='Bounded case timeout; test descendants stopped',checks=0)
                    else:
                        row=json.loads(result_path.read_text(encoding='utf8')) if result_path.exists() else dict(status='failed',category='infrastructure',error='Worker exited without a result',checks=0)
                        if code != (0 if row['status']=='passed' else 1):
                            row=dict(status='failed',category='infrastructure',error='Worker exit/result disagreement',checks=0)
            finally:
                job.close()
            drift=changed(guarded)
            if drift:
                row.update(status='failed',category='provenance',error='Source or input changed while this case ran',changedPaths=drift)
                report['stoppedEarly']=dict(reason='Source or input changed during execution',paths=drift)
            if old:
                report.setdefault('previousAttempts',[]).append(old)
                report['cases']=[r for r in report['cases'] if r['id']!=case['id']]
            row.update(id=case['id'],card=case['card'],attempt=attempt,seconds=round(time.monotonic()-start,3),log=str(log),result=str(result_path))
            report['cases'].append(row);report['activeCase']=None
            summarize(report,suite);save(path,report)
            if row['status']!='passed' or len(report['cases'])%getattr(a,'progress_every',25)==0 or len(report['cases'])==len(suite['cases']):
                print(json.dumps(dict(case=case['id'],status=row['status'],category=row.get('category'),completed=len(report['cases']),total=len(suite['cases']))),flush=True)
            if drift:break
            fingerprint=(row.get('category'),row.get('fidelityGap') or row.get('error')) if row['status']!='passed' and row.get('category') in ('controller','infrastructure','timeout') else None
            consecutive=consecutive+1 if fingerprint and fingerprint==last_failure else (1 if fingerprint else 0)
            last_failure=fingerprint
            limit=getattr(a,'systemic_failure_limit',3)
            if limit and consecutive>=limit:
                report['stoppedEarly']=dict(reason='Repeated identical systemic failure',consecutive=consecutive,category=fingerprint[0],detail=fingerprint[1])
                save(path,report);break
        drift=changed(identities)
        if drift:report['stoppedEarly']=dict(reason='Final provenance revalidation failed',paths=drift)
        report['status']='passed' if not report.get('stoppedEarly') and len(report['cases'])==len(suite['cases']) and all(r['status']=='passed' for r in report['cases']) else 'needs-attention'
        report['finishedUtc']=datetime.now(timezone.utc).isoformat()
        summarize(report,suite);save(path,report)
        lines=['# Headless card batch results','',f"{len(report['cases'])} cases; {report['summary']['assertions']} assertions; {report['status']}.",'',
               'No cards admitted. Native UI/artwork, rules equivalence and full-game gates remain separate.','',
               '| Card | Passed branches | Missing headless branches |','| --- | --- | --- |']
        lines += ['| '+name+' | '+', '.join(c['passedBranches'])+' | '+(', '.join(c['missingBranches']) or 'None in this suite')+' |' for name,c in report['summary']['cards'].items()]
        lines += ['','## Failure groups','']+[category+': '+', '.join(ids) for category,ids in report['summary']['failuresByCategory'].items()]
        (a.output/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
        compact={k:v for k,v in report['summary'].items() if k!='cards'}
        compact['cardNames']=len(report['summary']['cards'])
        compact['allDeclaredBranchesPassed']=sum(c['headlessBranchesComplete'] for c in report['summary']['cards'].values())
        print(json.dumps(dict(report=str(path),**compact)),flush=True)
        return 0 if report['status']=='passed' else 1


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','suite','output'):
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--timeout',type=int,default=90)
    p.add_argument('--execution',choices=('cold','warm'),default='cold',help='Cold remains the reference; warm is a research-only database reuse experiment')
    p.add_argument('--warm-max-cases',type=int,default=25)
    p.add_argument('--progress-every',type=int,default=25,help='Print every N completed cases and every failure; full details remain in report.json')
    p.add_argument('--systemic-failure-limit',type=int,default=3,help='Stop repeated identical controller/infrastructure failures; 0 explicitly disables this circuit breaker')
    group=p.add_mutually_exclusive_group();group.add_argument('--resume',action='store_true');group.add_argument('--retry-failed',action='store_true')
    a=p.parse_args()
    if not 15 <= a.timeout <= 300:
        p.error('Case timeout must be between 15 and 300 seconds')
    if not 1 <= a.warm_max_cases <= 200:p.error('Warm worker retirement bound must be 1..200 cases')
    if not 1 <= a.progress_every <= 1000:p.error('Progress interval must be 1..1000')
    if not 0 <= a.systemic_failure_limit <= 100:p.error('Systemic failure limit must be 0..100')
    raise SystemExit(run(a))
