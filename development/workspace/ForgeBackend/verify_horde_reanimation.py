"""Bounded real Horde openings and revival through original native handlers.

Only initial decks/seed are supplied. No runtime state, damage, mana, targets,
or zone changes are injected. Small Horde pools are research-only fixtures.
"""
import argparse,json,time,traceback
from pathlib import Path

def run(case,args):
 from native_engine_test_client import NativeEngine
 from native_test_policy import execute
 engine=None;trace=[]
 try:
  settings=dict(randomSeed=7274,localDeck=dict(name='Horde revival test',cards=[dict(name='Mountain',count=16),dict(name='Lightning Bolt',count=24)]))
  spells={'gravedigger':'Gravedigger','ghoulraiser':'Ghoulraiser','rise-from-grave':'Rise from the Grave','diregraf-rebirth':'Diregraf Rebirth','mass-revival':'Rise of the Dark Realms','butler':'Undead Butler','horror':'Phyrexian Gargantua','lords':'Death Baron'}
  if case=='no-target':
   settings['localDeck']=dict(name='No-target revival boundary',cards=[dict(name='Forest',count=40)])
   settings['hordeFixturePool']=['Rise from the Grave']*3
  elif case!='opening':settings['hordeFixturePool']=['Walking Corpse']*8+[spells[case]]*4
  engine=NativeEngine('zombie-horde',worker=args.worker,managed=args.managed,fixture=args.fixture,**settings)
  initial=engine.state;engine.check('Survivor starts with 40 life',initial['life']==40 and initial['startingLifeTotal']==40)
  if case=='opening':
   engine.check('Actual Horde library contains 200 cards',initial['horde']['initialCards']==200 and initial['horde']['remainingCards']==200)
   return dict(case=case,passed=True,checks=engine.checks,initial=initial,evidence=str(engine.ipc))
  deadline=time.monotonic()+130;face_burns=0;success=False;observed_cast=False
  def transitions():return engine.state['researchTrace']
  for step in range(350):
   s=engine.state;assert not s['fidelityGap'],s['fidelityGap']
   events=transitions();returns=[e for e in events if e['kind']=='zone-change' and e['ownerSeat']==2 and e['from']=='Graveyard' and e['to']==('Hand' if case in ('gravedigger','ghoulraiser','butler') else 'Battlefield')]
   controlled={c['forgeId'] for c in s['battlefield'] if c['controller']==2}
   if case=='no-target':success=any(e['kind']=='horde-uncastable-discard' for e in s['events']) and any(c['name']=='Rise from the Grave' and c['owner']==2 for c in s['graveyard'])
   elif case=='mass-revival':success=len({e['forgeId'] for e in returns}&controlled)>=2
   elif case=='butler':
    butlers={c['forgeId'] for c in s['exile'] if c['name']=='Undead Butler' and c['owner']==2}
    success=bool(returns) and any(e['kind']=='zone-change' and e['ownerSeat']==2 and e['from']=='Graveyard' and e['to']=='Exile' and e['forgeId'] in butlers for e in events)
   elif case=='horror':success=any(c['name']==spells[case] and c['controller']==2 for c in s['battlefield']) and len([e for e in events if e['kind']=='zone-change' and e['ownerSeat']==2 and e['from']=='Library' and e['to']=='Hand'])>=3
   elif case=='lords':success=any(c['controller']==2 and c['name']=='Walking Corpse' and c['power']>=3 and 'Deathtouch' in c['rulesKeywords'] for c in s['battlefield'])
   else:success=bool(returns) and (case in ('gravedigger','ghoulraiser') or bool({e['forgeId'] for e in returns}&controlled))
   if success:break
   assert not s['gameOver'],'Game ended before revival evidence'
   assert time.monotonic()<deadline,'Bounded revival case timed out'
   d=s.get('decision')
   if d:
    if d['kind']=='mulligan':execute(engine,trace,'submit_mulligan',decisionToken=d['token'],assignments=[dict(keep=True)])
    elif d['kind'] in ('discard','mulligan_bottom'):execute(engine,trace,'submit_'+d['kind'],decisionToken=d['token'],assignments=[dict(forgeId=o['forgeId']) for o in d['options'][:d['count']]])
    else:raise AssertionError('Unexpected free-standing human decision: '+str(d))
   elif s['legalLands']:execute(engine,trace,'play_land',s['legalLands'][0])
   elif s['legalCasts'] and (face_burns<(2 if case=='mass-revival' else 1) or any(c['controller']==2 and c['name']==spells.get(case) for c in s['battlefield']) and case not in ('horror','lords')):
    face=face_burns<(2 if case=='mass-revival' else 1)
    def target(spec,state):
     if face:return [next(o for o in spec['options'] if o.get('targetSeat')==2)]
     enemies={c['forgeId'] for c in state['battlefield'] if c['controller']==2 and c['name']==spells[case]}
     return [next(o for o in spec['options'] if o.get('forgeId') in enemies)]
    execute(engine,trace,'cast_spell',s['legalCasts'][0],_target_policy=target)
    if face:face_burns+=1
   else:execute(engine,trace,'pass_priority')
  engine.check('Real '+case+' effect observed',success)
  return dict(case=case,passed=True,checks=engine.checks,final=engine.state,trace=trace,evidence=str(engine.ipc),scope='Research starting pool; real opening, casts, stack, effects and original input handlers')
 except Exception as error:return dict(case=case,passed=False,error=repr(error),traceback=traceback.format_exc(),final=engine.state if engine else None,evidence=str(engine.ipc) if engine else None,trace=trace)
 finally:
  if engine:engine.close()

def main():
 p=argparse.ArgumentParser();[p.add_argument('--'+n,type=Path,required=True) for n in ('worker','managed','fixture','out')];p.add_argument('--cases',nargs='+',default=['opening','gravedigger','ghoulraiser','rise-from-grave','diregraf-rebirth','mass-revival','butler','horror','lords']);a=p.parse_args();a.out.mkdir(exist_ok=False)
 rows=[]
 for case in a.cases:
  r=run(case,a);(a.out/(case+'.json')).write_text(json.dumps(r,indent=2),encoding='utf8');rows.append({k:r.get(k) for k in ('case','passed','error','evidence')});print(json.dumps(rows[-1]),flush=True)
 (a.out/'report.json').write_text(json.dumps(rows,indent=2));raise SystemExit(0 if all(r['passed'] for r in rows) else 1)
if __name__=='__main__':main()
