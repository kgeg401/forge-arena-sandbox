"""Sequential, resource-bounded catalogue and rules validation. Never launches Arena.

Uses an existing independent developer runtime. Results stay private and no
GitHub publication occurs. Each run pins its policy and records reproducible
inputs, source identities, logs, per-engine assertions and runtime failures.
"""
import argparse
import ctypes
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
from headless_resources import process_flags

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, data):
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(data, indent=2), encoding='utf8')
    pending.replace(path)


def lower_resources():
    if os.name != 'nt':
        return
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    process = kernel.GetCurrentProcess()
    kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    if not kernel.SetPriorityClass(process, 0x4000):
        raise ctypes.WinError(ctypes.get_last_error())
    mask = ctypes.c_size_t(); system = ctypes.c_size_t()
    kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.GetProcessAffinityMask(process, ctypes.byref(mask), ctypes.byref(system)):
        raise ctypes.WinError(ctypes.get_last_error())
    bits = [1 << n for n in range(ctypes.sizeof(mask)*8) if mask.value & (1 << n)]
    if not kernel.SetProcessAffinityMask(process, sum(bits[:2])):
        raise ctypes.WinError(ctypes.get_last_error())


class ChildJob:
    """Closing the job kills only this test driver's remaining descendants."""
    def __init__(self):
        self.handle = None
        if os.name != 'nt':
            return
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),('Flags',w.DWORD),('MinWS',ctypes.c_size_t),('MaxWS',ctypes.c_size_t),('Active',w.DWORD),('Affinity',ctypes.c_size_t),('Priority',w.DWORD),('Scheduling',w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(n,ctypes.c_uint64) for n in ('ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes')]
        class Extended(ctypes.Structure):
            _fields_ = [('Basic',Basic),('IO',IO),('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),('PeakProcessMemory',ctypes.c_size_t),('PeakJobMemory',ctypes.c_size_t)]
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p,w.LPCWSTR];self.kernel.CreateJobObjectW.restype = w.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE,w.HANDLE]
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None,None)
        info = Extended();info.Basic.Flags = 0x2000
        if not self.handle or not self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            self.close();raise ctypes.WinError(ctypes.get_last_error())

    def attach(self, process):
        if self.handle and not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            process.terminate();process.wait(timeout=5)
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle);self.handle = None


def run(args):
    lower_resources()
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    root = Path(config['privateRoot']).resolve()
    if not root.is_dir() or not (root/'forge-runtime/forge.jar').is_file():
        raise ValueError('Select a prepared independent developer Forge runtime.')
    if (root/'native-lab/MTGA.exe').exists():
        raise ValueError('Use an independent rules-test runtime, not an installed playable sandbox.')
    runs = root/'research/background-runs';runs.mkdir(parents=True,exist_ok=True)
    # One driver owns the dedicated test runtime at a time.
    lock = (runs/'validation.lock').open('a+b');lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    run_dir = runs/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]);run_dir.mkdir()
    policy = subprocess.run(['git','show',args.policy_ref+':ForgeBackend/bridge_support.json'],cwd=REPO,capture_output=True,check=True).stdout
    (run_dir/'policy.json').write_bytes(policy)
    shutil.copy2(args.config,run_dir/'runtime-config.json')
    env = {**os.environ, 'FORGE_ARENA_CONFIG':str(run_dir/'runtime-config.json'), 'FORGE_ARENA_POLICY':str(run_dir/'policy.json'),
           'FORGE_ARENA_JAVAC':str(args.javac.resolve()), 'FORGE_ARENA_TEST_HEAP_MB':'1024', 'FORGE_ARENA_TEST_THREADS':'2',
           'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'}
    cp = ';'.join(map(str,[root/'build/ForgeBackend/classes',root/'forge-runtime/forge.jar',root/'forge-runtime/gson.jar']))
    stages = [('compile-rules', [str(args.javac.resolve()),'-J-Xmx512m','-J-XX:ActiveProcessorCount=2','-cp',cp,'-d',str(root/'build/ForgeBackend/classes'),str(HERE/'ForgeLandEngine.java')],90),
              ('catalogue-audit',[sys.executable,'-B',str(HERE/'run_card_audit.py')],420),
              ('deck-catalogue',[sys.executable,'-B',str(REPO/'DeckBackend/build_deck_catalog.py')],90),
              ('support-index',[sys.executable,'-B',str(HERE/'build_support_index.py')],90),
              ('source-mappings',[sys.executable,'-B',str(HERE/'verify_card_manifest.py')],30),
              ('support-boundaries',[sys.executable,'-B',str(HERE/'verify_card_support.py')],30)]
    families = {'mana':'verify_mana.py','spell-stack':'verify_spell.py','targeting':'verify_targets.py',
                'color-payment-and-bounce':'verify_blue.py','counterspells':'verify_counter.py','triggers':'verify_triggers.py',
                'tokens':'verify_hare.py','combat':'verify_combat_cases.py','combat-damage':'verify_damage_assignment.py',
                'draw':'verify_draw.py','discard':'verify_discard.py','mulligans':'verify_opening.py',
                'outcomes':'verify_outcomes.py','terminal-safety':'verify_terminal.py','concession':'verify_concede.py',
                'deck-import':'verify_deck_import.py'}
    stages += [(family,[sys.executable,'-B',str(HERE/script)],180) for family,script in families.items()]
    for seed,scenario in [(7274,'opening-duel'),(7275,'spell-duel'),(7276,'blue-duel')]:
        stages.append((f'complete-match-{scenario}-{seed}',[sys.executable,'-B',str(HERE/'verify_normal_duel.py'),str(seed),scenario],240))
    full_stage_names={s[0] for s in stages}
    prior=None
    if args.retry_report:
        prior=json.loads(args.retry_report.read_text(encoding='utf8'))
        if prior.get('status') not in ('passed','needs-attention') or {s['name'] for s in prior['stages']}!=full_stage_names:
            raise ValueError('Retry requires a completed full checkpoint; an incomplete audit needs a new full run.')
        if prior['policySha256']!=sha(run_dir/'policy.json') or prior['forgeJarSha256']!=sha(root/'forge-runtime/forge.jar') or prior['sourceHashes']['ForgeBackend/ForgeLandEngine.java']!=sha(HERE/'ForgeLandEngine.java'):
            raise ValueError('Rules engine or policy changed; retry requires a new full run.')
        failed={s['name'] for s in prior['stages'] if s['status']!='passed'}
        if not failed:raise ValueError('Nothing failed in that checkpoint; do not repeat passing work.')
        stages=[stage for stage in stages if stage[0] in failed]
    receipt = dict(schema=1,startedUtc=datetime.now(timezone.utc).isoformat(),status='running',
                   policyRef=args.policy_ref,policySha256=sha(run_dir/'policy.json'),
                   limits=dict(workers=1,cpuAffinityProcessors=2,javaProcessors=2,javaHeapMiB=1024,priority='below-normal',nativeGameLaunches=False),
                   sourceHashes={p.relative_to(REPO).as_posix():sha(p) for p in [*HERE.glob('*.py'),HERE/'ForgeLandEngine.java',HERE/'CardCapabilityProbe.java',REPO/'DeckBackend/build_deck_catalog.py']},
                   forgeJarSha256=sha(root/'forge-runtime/forge.jar'),stages=[],
                   scope='Targeted admitted-slice rules regression and catalogue audit; not all-card gameplay verification, native UI verification or a published release.')
    report = run_dir/'report.json';atomic(report,receipt)
    if prior:
        receipt['retryOf']=str(args.retry_report.resolve());receipt['retryReportSha256']=sha(args.retry_report)
        receipt['sourceChangesSinceOriginal']=[name for name,digest in receipt['sourceHashes'].items() if prior['sourceHashes'].get(name)!=digest]
        atomic(report,receipt)
    print(str(report),flush=True)
    try:
        for name,command,timeout in stages:
            before = set((root/'research').glob('*-check-*')) | set((root/'research').glob('combat-check-*'))
            row = dict(name=name,status='running',command=command,timeoutSeconds=timeout,startedUtc=datetime.now(timezone.utc).isoformat(),log=str(run_dir/(name+'.log')))
            receipt['stages'].append(row);atomic(report,receipt)
            print('Starting '+name,flush=True)
            job = ChildJob();process = None;started = time.monotonic()
            try:
                with Path(row['log']).open('w',encoding='utf8') as log:
                    process = subprocess.Popen(command,cwd=REPO,stdout=log,stderr=subprocess.STDOUT,env=env,creationflags=process_flags())
                    job.attach(process)
                    try:
                        code = process.wait(timeout=timeout)
                        row.update(status='passed' if code==0 else 'failed',exitCode=code)
                    except subprocess.TimeoutExpired:
                        row.update(status='timed-out',reproductionCommand=command)
            finally:
                job.close()
                if process is not None and process.poll() is None:
                    process.kill();process.wait(timeout=5)
            row['seconds'] = round(time.monotonic()-started,2)
            after = set((root/'research').glob('*-check-*')) | set((root/'research').glob('combat-check-*'))
            evidence = sorted(p for p in after-before if p.is_dir())
            row['engineEvidence'] = [str(p) for p in evidence]
            assertions = []
            for folder in evidence:
                path = folder/'checks.json'
                if path.exists():
                    assertions += json.loads(path.read_text())
                state = folder/'state.json'
                if state.exists():
                    snapshot = json.loads(state.read_text())
                    if snapshot.get('fidelityGap'):
                        row.setdefault('fidelityGaps',[]).append(dict(evidence=str(folder),gap=snapshot['fidelityGap']))
            row['recordedAssertions'] = len(assertions)
            row['failedAssertions'] = [c for c in assertions if not c['passed']]
            if row['failedAssertions'] or row.get('fidelityGaps'):
                row['status'] = 'failed'
            if row['status']!='passed':
                row['reproductionCommand']=command
                row['logTail']=Path(row['log']).read_text(encoding='utf8',errors='replace')[-6000:]
            atomic(report,receipt)
            print(name+': '+row['status'],flush=True)
            if name in ('compile-rules','catalogue-audit','deck-catalogue','support-index') and row['status']!='passed':
                break  # Never continue using stale evidence/runtime mappings.
        combined={s['name']:s for s in prior['stages']} if prior else {}
        combined.update({s['name']:s for s in receipt['stages']})
        receipt['status'] = 'passed' if set(combined)==full_stage_names and all(s['status']=='passed' for s in combined.values()) else 'needs-attention'
        receipt['recordedEngineAssertions'] = sum(s.get('recordedAssertions',0) for s in combined.values())
        if prior:
            receipt['combinedStages']=[dict(name=s['name'],status=s['status'],log=s['log']) for s in combined.values()]
        audit = root/'research/card-coverage'
        if audit.is_dir():
            shutil.copytree(audit,run_dir/'catalogue-snapshot')
        receipt['finishedUtc']=datetime.now(timezone.utc).isoformat();atomic(report,receipt)
        print(json.dumps(dict(status=receipt['status'],stages=len(receipt['stages']),engineAssertions=receipt['recordedEngineAssertions'],report=str(report)),indent=2),flush=True)
        return 0 if receipt['status']=='passed' else 1
    except BaseException as error:
        receipt.update(status='interrupted',error=repr(error),finishedUtc=datetime.now(timezone.utc).isoformat());atomic(report,receipt)
        raise
    finally:
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--javac',type=Path,required=True)
    parser.add_argument('--policy-ref',default='c14dc620228442eee67480d2f47a3953ac726bcf')
    parser.add_argument('--retry-report',type=Path,help='Replay only failed stages of a completed checkpoint; retain the original report.')
    sys.exit(run(parser.parse_args()))
