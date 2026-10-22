"""Repeatable bounded construction + bridge audit; private results only."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, subprocess, sys
from build_card_coverage import ROOT, FORGE
from runtime_paths import JAVA_HOME
from headless_resources import java_options,process_flags

HERE=Path(__file__).resolve().parent
JAVA=JAVA_HOME/'bin'
OUT=ROOT/'research/card-coverage'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run():
    start=datetime.now(timezone.utc).isoformat()
    subprocess.run([sys.executable,'-B',str(HERE/'build_card_coverage.py')],check=True)
    classes=ROOT/'build/CardCapabilityProbe/classes';classes.mkdir(parents=True,exist_ok=True)
    cp=';'.join(map(str,[classes,ROOT/'build/ForgeBackend/classes',ROOT/'forge-runtime/forge.jar',ROOT/'forge-runtime/gson.jar']))
    compiler=os.environ.get('FORGE_ARENA_JAVAC',str(JAVA/'javac.exe'))
    subprocess.run([compiler,'-J-Xmx512m','-J-XX:ActiveProcessorCount=2','-cp',cp,'-d',str(classes),str(HERE/'CardCapabilityProbe.java')],check=True,timeout=60,creationflags=process_flags())
    pending=OUT/'forge-construction.pending.jsonl'
    with (OUT/'forge-construction.log').open('w',encoding='utf8') as log:
        subprocess.run([str(JAVA/'java.exe'),*java_options(),'-cp',cp,'CardCapabilityProbe',str(ROOT/'forge-runtime'),str(OUT/'forge-compile-input.json'),str(pending)],
                       stdout=log,stderr=subprocess.STDOUT,cwd=ROOT/'forge-runtime',timeout=300,check=True,creationflags=process_flags())
    expected=json.loads((OUT/'forge-compile-input.json').read_text(encoding='utf8'))['scripts']
    rows=[json.loads(line) for line in pending.read_text(encoding='utf8').splitlines()]
    if len(rows)!=len(expected) or {r['script']:r['sha256'] for r in rows}!={r['script']:r['sha256'] for r in expected}:raise ValueError('Constructor audit incomplete or stale')
    pending.replace(OUT/'forge-construction.jsonl')
    receipt=dict(startedUtc=start,finishedUtc=datetime.now(timezone.utc).isoformat(),exitCode=0,candidates=len(rows),
                 inputSha256=sha(OUT/'forge-compile-input.json'),outputSha256=sha(OUT/'forge-construction.jsonl'),
                 sourceSha256=sha(HERE/'CardCapabilityProbe.java'),classSha256=sha(classes/'CardCapabilityProbe.class'),
                 installedForgeJarSha256=sha(ROOT/'forge-runtime/forge.jar'),scriptsSha256=sha(FORGE),
                 scope='Card construction/trait inventory only; never resolves a spell or starts a match')
    (OUT/'construction-receipt.json').write_text(json.dumps(receipt,indent=2))
    subprocess.run([sys.executable,'-B',str(HERE/'build_compatibility_report.py')],check=True)
    subprocess.run([sys.executable,'-B',str(HERE/'verify_compatibility_report.py')],check=True)
    print('Private compatibility report:',OUT/'Card-Compatibility.html')

if __name__=='__main__':run()
