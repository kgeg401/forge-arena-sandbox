"""Normally shuffled games for the plain-creature family, across five decks."""
import json
from pathlib import Path
import subprocess
import sys
from runtime_paths import ROOT
from headless_resources import process_flags

repo=Path(__file__).resolve().parents[1]
decks=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\research\broad-card-support\normal-decks')
out=ROOT/'research/plain-family-checks';out.mkdir(exist_ok=True)
reports=[]
for index,name in enumerate(('Green','Black','Red','Blue','Five-color')):
    log=out/(name+'-normal-match.log')
    with log.open('w',encoding='utf8') as file:
        result=subprocess.run([sys.executable,'-B',str(repo/'ForgeBackend/verify_normal_duel.py'),str(8100+index),'custom-duel',str(decks/(name+'.txt')),str(repo/'decks/White-Lifegain.txt')],cwd=repo,stdout=file,stderr=subprocess.STDOUT,creationflags=process_flags(),timeout=240)
    if result.returncode:raise RuntimeError(name+' full game failed: '+log.read_text(encoding='utf8')[-5000:])
    reports.append(dict(deck=name,seed=8100+index,passed=True,log=str(log)))
    print(json.dumps(reports[-1]),flush=True)
(out/'normal-matches.json').write_text(json.dumps(dict(matches=reports,scope='Normally shuffled full Forge matches with input-only decisions; native rendered games and full interaction coverage are separate.'),indent=2))
