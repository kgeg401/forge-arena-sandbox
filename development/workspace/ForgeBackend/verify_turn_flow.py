"""Test automatic turn pacing against real Forge and owned native handlers.

No game/Unity scene is launched. Presentation readiness is controlled by the
probe; this establishes sequencing, not perceived animation smoothness.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','policy','probe','managed','fixture','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy))
    from engine_test_client import Engine
    from runtime_paths import ROOT
    from headless_resources import run_owned
    a.output.mkdir(parents=True,exist_ok=False)
    results=[]
    for mode,scenario in (('flow','starter'),('combat','attack-open'),('stop','starter'),('response','counter-ready'),('no-response','counter-ready-white'),('yield','starter'),('yield-turn','starter'),('resolve-all','counter-ready')):
        e=Engine(scenario)
        report=a.output/(mode+'.json')
        try:
            with (a.output/(mode+'.log')).open('w',encoding='utf8') as log:
                result=run_owned(['dotnet',str(a.probe),str(a.managed),str(ROOT/'native-lab'),str(e.ipc),str(a.fixture),mode,str(report)],timeout=45,stdout=log,stderr=subprocess.STDOUT)
            results.append(dict(mode=mode,passed=result.returncode==0 and report.exists() and json.loads(report.read_text())['passed'],returncode=result.returncode,report=str(report),evidence=str(e.ipc)))
        finally:e.close()
    summary=dict(passed=all(r['passed'] for r in results),results=results,scope=__doc__,utc=datetime.now(timezone.utc).isoformat(),binaries={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in a.probe.parent.glob('*.dll')})
    (a.output/'report.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary));raise SystemExit(0 if summary['passed'] else 1)


if __name__=='__main__':main()
