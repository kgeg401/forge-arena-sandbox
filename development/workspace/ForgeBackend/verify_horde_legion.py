"""Bounded Horde sequencing and Zombie synergies through original native inputs.

The smaller Horde libraries are explicit starting-pool fixtures, not full-game
or balance claims. Forge owns every cast, target, trigger, cost and zone change.
"""
import argparse,json,time,traceback
from pathlib import Path

CARDS={
 'champion':'Champion of the Perished','augur':'Undead Augur','rider':'Headless Rider',
 'captain':'Diregraf Captain','colossus':'Diregraf Colossus','servant':'Wayward Servant',
 'skaab':'Bladestitched Skaab','mastery':"Liliana's Mastery",'necro':'Necroduality',
 'graves':'Open the Graves','army':'Army of the Damned','archghoul':'Archghoul of Thraben',
 'removal':'Murder','no-self-removal':'Murder',
 'deferred-revival':'Rise from the Grave',
 'physical-nontoken-boundary':'Headless Rider',
 'artifact-only-removal':'Go for the Throat',
}
TOKEN='token:b_2_2_zombie'

def run(case,args):
 from native_engine_test_client import NativeEngine
 from native_test_policy import execute
 e=None;trace=[];seen=[];kills=0;proof={}
 try:
  name=CARDS[case]
  deck=[('Plains',16),('Ornithopter' if case=='artifact-only-removal' else 'Savannah Lions',24)] if case in ('removal','artifact-only-removal') else [('Forest',40)] if case=='no-self-removal' else [('Mountain',16),('Lightning Bolt',24)]
  pool=[TOKEN]*16+[name]*4
  if case in ('augur','rider','captain','graves','archghoul','necro'):pool+=['Walking Corpse']*4
  e=NativeEngine('zombie-horde',worker=args.worker,managed=args.managed,fixture=args.fixture,randomSeed=7274,
   localDeck=dict(name='Legion '+case,cards=[dict(name=n,count=c) for n,c in deck]),hordeFixturePool=pool)
  end=time.monotonic()+140;success=False
  for _ in range(420):
   s=e.state;assert not s['fidelityGap'],s['fidelityGap'];events=s['events'];public=s['researchTrace']
   board=[c for c in s['battlefield'] if c['controller']==2];engine=[c for c in board if c['name']==name]
   physical=[c for c in board if c.get('hordePhysicalTokenCard')];generated=[c for c in board if c.get('token') and not c.get('hordePhysicalTokenCard')]
   casts=[v for v in events if v['kind']=='horde-plan'];seen=[v['name'] for v in casts]
   deaths=[v for v in public if v['kind']=='zone-change' and v['ownerSeat']==2 and v['from']=='Battlefield' and v['to']=='Graveyard']
   draws=[v for v in public if v['kind']=='zone-change' and v['ownerSeat']==2 and v['from']=='Library' and v['to']=='Hand']
   if case=='champion':success=any(any(v['type']=='P1P1' and v['count']>0 for v in c['counters']) for c in engine)
   elif case=='skaab':success=bool(engine and physical) and all(c['power']>=3 for c in physical)
   elif case=='mastery':success=bool(engine) and len(generated)>=2 and all(c['power']>=3 and c['toughness']>=3 for c in generated)
   elif case=='army':success=len(generated)>=13 and all(c['tapped'] for c in generated)
   elif case=='necro':success=bool(engine) and any(c['name']=='Walking Corpse' for c in generated)
   elif case=='colossus':success=bool(engine and generated)
   elif case=='servant':success=bool(engine and physical) and any(v['kind']=='life-change' and v['targetSeat']==1 and v['after']<v['before'] and v['phase']=='MAIN1' and v['turn']>=4 for v in public)
   elif case in ('no-self-removal','artifact-only-removal'):success=any(v['kind']=='horde-uncastable-discard' and v.get('name')==name for v in events) and bool(physical) and not deaths and (case!='artifact-only-removal' or any(c['controller']==1 and c['name']=='Ornithopter' for c in s['battlefield']))
   elif case=='removal':success=any(v['kind']=='zone-change' and v['ownerSeat']==1 and v['from']=='Battlefield' and v['to']=='Graveyard' for v in public) and 'Murder' in seen
   elif kills:
    after=[v for v in public if v['ordinal']>proof['ordinal'] and v['turn']==proof['turn']]
    if case=='captain':success=bool(engine) and any(v['kind']=='life-change' and v['targetSeat']==1 and v['after']==v['before']-1 for v in after)
    elif case in ('rider','graves'):success=bool(engine) and bool({c['forgeId'] for c in generated}-set(proof['generatedBefore'])) and any(v['kind']=='spell-resolved' and v['sourceForgeId'] in proof['engineIds'] for v in after)
    elif case in ('augur','archghoul'):success=any(v['kind']=='zone-change' and v['ownerSeat']==2 and v['from']=='Library' and v['to']=='Hand' and v.get('sourceStackForgeId') for v in after) and any(v['kind']=='spell-resolved' and v['sourceForgeId'] in proof['engineIds'] for v in after)
    elif case=='deferred-revival':success=any(v['kind']=='zone-change' and v['forgeId']==proof['target'] and v['from']=='Graveyard' and v['to']=='Battlefield' for v in after)
    elif case=='physical-nontoken-boundary':success=bool(engine) and not generated and not s['stackOrder'] and any(v['kind']=='zone-change' and v['forgeId']==proof['target'] and v['from']=='Battlefield' and v['to']=='Graveyard' for v in after) and not any(v['kind']=='spell-resolved' and v['sourceForgeId'] in proof['engineIds'] for v in after)
   if success:break
   assert not s['gameOver'],'Game ended before the declared synergy was observed'
   assert time.monotonic()<end,'Bounded synergy case timed out'
   d=s.get('decision')
   if d:
    if d['kind']=='mulligan':execute(e,trace,'submit_mulligan',decisionToken=d['token'],assignments=[dict(keep=True)])
    elif d['kind'] in ('discard','mulligan_bottom'):execute(e,trace,'submit_'+d['kind'],decisionToken=d['token'],assignments=[dict(forgeId=o['forgeId']) for o in d['options'][:d['count']]])
    else:raise AssertionError('Unexpected free-standing decision: '+str(d))
   elif s['legalLands']:execute(e,trace,'play_land',s['legalLands'][0])
   elif case in ('removal','artifact-only-removal') and s['legalCasts']:execute(e,trace,'cast_spell',s['legalCasts'][0],_attack_policy=lambda d,s:[])
   elif case in ('augur','rider','captain','graves','archghoul','deferred-revival','physical-nontoken-boundary') and not kills and (engine or case=='deferred-revival') and any((c['name']=='Walking Corpse' if case in ('rider','graves') else c.get('hordePhysicalTokenCard')) for c in board) and s['legalCasts'] and (not s['stackOrder'] or case=='deferred-revival'):
    victims=[c for c in board if (c['name']=='Walking Corpse' if case in ('rider','graves') else c.get('hordePhysicalTokenCard'))]
    target=min(victims,key=lambda c:c['toughness']);proof=dict(ordinal=max(v['ordinal'] for v in public),target=target['forgeId'],generatedBefore=[c['forgeId'] for c in generated],engineIds=[c['forgeId'] for c in engine],wave=s['horde']['wave'],turn=s['turn']);kills+=1
    execute(e,trace,'cast_spell',s['legalCasts'][0],_target_policy=lambda d,s:[next(o for o in d['options'] if o.get('forgeId')==proof['target'])])
   else:execute(e,trace,'pass_priority',_attack_policy=lambda d,s:[])
  e.check('Real Horde '+case+' effect observed',success)
  pending=set();maximum=0
  for row in e.state['researchTrace']:
   if row['kind']!='zone-change' or row['ownerSeat']!=2:continue
   if row['to']=='Stack':pending.add(row['forgeId']);maximum=max(maximum,len(pending))
   if row['from']=='Stack':pending.discard(row['forgeId'])
  e.check('Real Horde spells enter the stack one at a time',maximum==1,dict(maximum=maximum))
  if case=='deferred-revival':
   e.check('Initially targetless revival waits and uses a fresh death in the same wave',proof['wave']==1 and e.state['horde']['wave']==1 and any(c['forgeId']==proof['target'] for c in e.state['battlefield']))
  if case in ('champion','colossus','servant','skaab','mastery'):
   first=next(v for v in e.state['events'] if v['kind']=='horde-plan')
   e.check('Synergy piece resolves before the wave physical Zombies',first['name']==name)
  return dict(case=case,passed=True,checks=e.checks,trace=trace,proof=proof,final=e.state,evidence=str(e.ipc),scope='Initial research pool; real native inputs and Forge effects, not full 500-card coverage')
 except Exception as ex:return dict(case=case,passed=False,error=repr(ex),traceback=traceback.format_exc(),trace=trace,proof=proof,final=e.state if e else None,evidence=str(e.ipc) if e else None)
 finally:
  if e:e.close()

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for k in ('worker','managed','fixture','out'):p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--cases',nargs='+',choices=list(CARDS),default=list(CARDS));a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[]
 for case in a.cases:
  r=run(case,a);(a.out/(case+'.json')).write_text(json.dumps(r,indent=2));rows.append({k:r.get(k) for k in ('case','passed','error','evidence')});print(json.dumps(rows[-1]),flush=True)
 (a.out/'report.json').write_text(json.dumps(rows,indent=2));raise SystemExit(0 if all(r['passed'] for r in rows) else 1)
