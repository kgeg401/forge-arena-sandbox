"""A real infect Aura and ordinary control must not double-present damage as both counters and marked damage."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

def run(a,key):
 e=None;trace=[];report={};infect=key=='infect'
 try:
  e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,fixtureHand=['Phyresis'] if infect else [],fixtureLands=['Swamp']*2,fixtureBattlefield=['Grizzly Bears'],fixtureOpponentBattlefield=['Aegis Turtle'],fixtureBattlefieldReady=True,fixtureOpponentPolicy='block-all',fixtureLibrary=['Forest']*20)
  source=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears');target=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Aegis Turtle')
  def targets(d,s):return [v for v in d['options'] if v['forgeId']==source]
  if infect:
   spell=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Phyresis');execute(e,trace,'cast_spell',spell,_target_policy=targets)
   for _ in range(10):
    if not e.state['stackOrder']:break
    execute(e,trace,'pass_priority',_target_policy=targets)
   e.check('Original Aura actually grants infect to the chosen Bear',any(c['forgeId']==source and 'Infect' in c['rulesKeywords'] for c in e.state['battlefield']))
  for _ in range(60):
   if e.state['phase']=='MAIN2':break
   execute(e,trace,'pass_priority',_attack_seat=2)
  else:raise AssertionError('Real blocked combat failed to settle')
  card=next(c for c in e.state['battlefield'] if c['forgeId']==target)
  e.check('Actual creature counters and marked damage follow Forge',card['damage']==(0 if infect else 2) and sum(c['count'] for c in card['counters'] if c['type']=='M1M1')==(2 if infect else 0))
  impacts=[v for v in e.state['events'] if v['kind']=='damage' and v.get('sourceForgeId')==source and v.get('targetForgeId')==target]
  e.check('Real combat produces exactly one two-damage impact',len(impacts)==1 and impacts[0]['amount']==2 and impacts[0]['combat'])
  native=[json.loads(v)['value'] for v in (e.native_folder/'native-model.jsonl').read_text().splitlines() if json.loads(v)['kind']=='native-update']
  views=[c for row in native for c in row['cards'] if c['id']==1000+target];counter_views=[c for c in views if any(v['count']==2 for v in c['counters'])] if infect else [c for c in views if c['damage']==2]
  e.check('Native model actually reaches the post-damage creature state',bool(counter_views))
  e.check('Original native creature damage matches Forge instead of marking infect damage twice',all(c['damage']==(0 if infect else 2) for c in counter_views))
  e.check('No unsupported or orphaned choice remains',not e.state['fidelityGap'] and not e.state.get('decision'))
  report=dict(case=key,passed=True,checks=e.checks,evidence=str(e.ipc))
 except Exception as error:report=dict(case=key,passed=False,error=repr(error)[:1400],traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
 finally:
  if e:e.close()
 (a.output/(key+'.json')).write_text(json.dumps(report,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps({k:report.get(k) for k in ('case','passed','error','evidence')}),flush=True);return report['passed']

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('worker','managed','fixture','output'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--case',choices=('normal','infect'),action='append');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 ok=[run(a,key) for key in a.case or ('normal','infect')];raise SystemExit(0 if all(ok) else 1)
