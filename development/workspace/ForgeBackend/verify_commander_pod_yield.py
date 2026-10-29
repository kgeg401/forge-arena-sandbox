"""Explicit native turn-yield across three opponents with a playable instant.

Setup uses real Forge mulligan, land and priority actions. The probe then owns
the native protocol and submits every yielded pass via the original handlers.
"""
from pathlib import Path
import argparse,os,json,subprocess,traceback
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','probe','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from engine_test_client import Engine
from runtime_paths import ROOT
from headless_resources import run_owned
a.output.mkdir(parents=True,exist_ok=False);results=[]
def deck(commander,land):return dict(name='Pod yield test',format='commander-40',commander=dict(name=commander,count=1),cards=[dict(name=land,count=99)],experimental=True)
for mode in ['pod-yield','pod-yield-unless']:
 e=None
 try:
  local=deck('Emry, Lurker of the Loch','Island');local['cards']=[dict(name='Island',count=98),dict(name='Visions of Beyond',count=1)]
  e=Engine('commander-pod',localDeck=local,opponentDecks=[deck('Isamaru, Hound of Konda','Plains')]*3,randomSeed=5,startingPlayerPolicy='local-first')
  assert any(c['name']=='Visions of Beyond' for c in e.state['hand']), 'Fixture seed did not draw the intended instant'
  def send(op,**fields):
   reply=e.send(op,**fields);assert reply['accepted'],reply['reason']
  send('submit_mulligan',decisionToken=e.state['decision']['token'],assignments=[dict(keep=True)])
  for _ in range(30):
   if e.state['phase']=='MAIN1':break
   send('pass_priority')
  send('play_land',forgeId=e.state['legalLands'][0])
  for _ in range(30):
   if e.state['activeSeat']==2:break
   send('pass_priority')
  assert e.state['activeSeat']==2 and e.state['legalCasts'],'Setup did not leave a real instant response'
  report=a.output/(mode+'.json')
  with (a.output/(mode+'.log')).open('w',encoding='utf8') as log:r=run_owned(['dotnet',str(a.probe),str(a.managed),str(ROOT/'native-lab'),str(e.ipc),str(a.fixture),mode,str(report)],timeout=45,stdout=log,stderr=subprocess.STDOUT)
  result=dict(mode=mode,passed=r.returncode==0 and report.exists() and json.loads(report.read_text())['passed'],returncode=r.returncode,evidence=str(e.ipc),report=str(report))
 except BaseException as error:result=dict(mode=mode,passed=False,error=repr(error),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
 finally:
  if e:e.close()
 results.append(result);print(json.dumps(result),flush=True)
report=dict(passed=all(r['passed'] for r in results),results=results);(a.output/'report.json').write_text(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
