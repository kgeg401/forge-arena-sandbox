"""Original-handler strike steps, blocker deaths and remaining trample allocations."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

CASES=('first-strike','double-strike','double-trample')
def run(a,key):
 e=None;trace=[];report={};first=key=='first-strike';trample=key=='double-trample';name='Youthful Knight' if first else 'Fencing Ace';blocker='Savannah Lions' if first else 'Yoked Ox';allocations=[]
 try:
  e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,fixtureHand=['Charge Through'] if trample else [],fixtureLands=['Forest'],fixtureBattlefield=[name],fixtureOpponentBattlefield=[blocker],fixtureBattlefieldReady=True,fixtureOpponentPolicy='block-all',fixtureCounters=[dict(seat=1,cardName=name,occurrence=0,type='P1P1',count=2)] if trample else [],fixtureLibrary=['Forest']*20)
  source=next(c['forgeId'] for c in e.state['battlefield'] if c['name']==name);target=next(c['forgeId'] for c in e.state['battlefield'] if c['name']==blocker)
  def targets(d,s):return [v for v in d['options'] if v['forgeId']==source]
  def damage(d,s):
   allocations.append(dict(phase=s['phase'],options=d['options'],total=d['totalDamage']))
   return [dict(forgeId=v['forgeId'],amount=v['assignedDamage']) for v in d['options']]
  if trample:
   spell=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Charge Through');execute(e,trace,'cast_spell',spell,_target_policy=targets)
   for _ in range(10):
    if not e.state['stackOrder']:break
    execute(e,trace,'pass_priority',_target_policy=targets)
   e.check('Actual resolved spell grants trample while retaining double strike',any(c['forgeId']==source and c['power']==3 and {'Trample','Double Strike'}<=set(c['rulesKeywords']) for c in e.state['battlefield']))
  for _ in range(60):
   if e.state['phase']=='MAIN2':break
   execute(e,trace,'pass_priority',_attack_seat=2,_damage_policy=damage)
  else:raise AssertionError('Real strike combat failed to settle')
  hits=[v for v in e.state['events'] if v['kind']=='damage' and v.get('sourceForgeId')==source and v['amount']>0]
  expected=[('COMBAT_FIRST_STRIKE_DAMAGE',2,target)] if first else [('COMBAT_FIRST_STRIKE_DAMAGE',1,target),('COMBAT_DAMAGE',1,target)] if not trample else [('COMBAT_FIRST_STRIKE_DAMAGE',3,target),('COMBAT_DAMAGE',1,target),('COMBAT_DAMAGE',2,-1000002)]
  actual=[(v['phase'],v['amount'],v.get('targetForgeId',-1000000-v.get('targetSeat',0))) for v in hits]
  e.check('Exact damage targets and amounts occur in their actual separate Forge steps',actual==expected,actual)
  e.check('A blocker killed in first strike never retaliates',not first or not any(v.get('sourceForgeId')==target and v['kind']=='damage' and v['amount']>0 for v in e.state['events']))
  e.check('Original source survives the actual combat',any(c['forgeId']==source for c in e.state['battlefield']))
  e.check('Original blocker dies only when actually lethal',any(c['forgeId']==target for c in e.state['graveyard'])==(first or trample))
  e.check('Protecting player receives only actual excess',e.state['opponentLife']==(18 if trample else 20))
  if trample:
   e.check('Second damage choice accounts for three damage already marked in first strike',len(allocations)==2 and [next(v['lethalDamage'] for v in d['options'] if v['forgeId']==target) for d in allocations]==[4,1])
  e.check('No unsupported callbacks or pending decisions remain',not e.state['fidelityGap'] and not e.state.get('decision'))
  report=dict(case=key,passed=True,checks=e.checks,evidence=str(e.ipc),allocations=allocations)
 except Exception as error:report=dict(case=key,passed=False,error=repr(error)[:1400],traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
 finally:
  if e:e.close()
 (a.output/(key+'.json')).write_text(json.dumps(report,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps({k:report.get(k) for k in ('case','passed','error','evidence')}),flush=True);return report['passed']

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('worker','managed','fixture','output'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--case',choices=CASES,action='append');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 ok=[run(a,key) for key in a.case or CASES];raise SystemExit(0 if all(ok) else 1)
