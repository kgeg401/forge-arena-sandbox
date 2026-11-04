"""Seeded win lines through the shipped native parser/action handlers and Forge."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

p=argparse.ArgumentParser()
for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--case',choices=['real-line','staff-copy'],required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
e=None;trace=[];color='blue';x=12
library=['Forest','Island','Yoked Ox','Field Creeper','Impassioned Orator','Savannah Lions','Lightning Greaves','Prosperous Innkeeper']
settings=dict(fixtureHand=['Villainous Wealth','Twincast'] if a.case=='staff-copy' else ['Freed from the Real','Villainous Wealth'],fixtureLands=['Forest']*15+['Island']*15+['Swamp']*15 if a.case!='real-line' else ['Island']*3,fixtureBattlefield=['Twinning Staff'] if a.case=='staff-copy' else [],fixtureBattlefieldReady=True,fixtureCommander='Zaxara, the Exemplary',fixtureCommanderInPlay=True,fixtureLibrary=['Forest']*20,fixtureOpponentLibrary=library,fixtureOpponentBattlefield=[],fixtureOpponentPolicy='passive',fixtureLocalLife=40)
def choices(c,s):
 if c['type']=='number' and 'Choose X' in c.get('prompt',''):return [dict(number=min(x,c['max']))]
 if c['type']=='confirm':return [dict(accept=not ('draw' in c.get('prompt','').lower() and not s.get('libraryCount',1)))]
 if c['type']=='colors':
  pick=next(o for o in c['options'] if o.get('color','').lower()==color);return [dict(choiceId=pick['choiceId'])]
 if c['type'] in ('cards-effect','cards-zone','options','entities'):
  return [dict(choiceId=o['choiceId']) for o in c['options'][:max(c.get('min',0),min(1,c.get('max',1)))]]
 return None
def targets(spec,s):
 cards={c['forgeId']:c for zone in ['hand','battlefield','stack','graveyard'] for c in s.get(zone,[])}
 if spec.get('minTargets',0)==0 and not spec['options']:return []
 spell=[o for o in spec['options'] if cards.get(o['forgeId'],{}).get('name')=='Villainous Wealth' and cards.get(o['forgeId'],{}).get('zone')=='Stack']
 aura=[o for o in spec['options'] if cards.get(o['forgeId'],{}).get('name')=='Zaxara, the Exemplary']
 players=[o for o in spec['options'] if o.get('targetSeat')==2]
 return (spell or players or aura or spec['options'])[:max(1,spec['minTargets'])]
def act(op,id=0,**kw):execute(e,trace,op,id,_choice_policy=choices,_target_policy=targets,_attack_seat=2,**kw)
def settle():
 for _ in range(80):
  if not e.state['stackOrder'] or e.state['gameOver']:return
  act('pass_priority')
 raise AssertionError('Stack bound exceeded')
def card(name):return next(c for c in e.state['battlefield'] if c['name']==name)
def cast(name,resolve=True):
 act('cast_spell',next(c['forgeId'] for c in e.state['hand'] if c['name']==name))
 if resolve:settle()
def activate(name,text):
 id=card(name)['forgeId'];offer=next(o for o in e.state['legalActivations'] if o['forgeId']==id and text.lower() in json.dumps(o).lower());act('activate_ability',id,abilityId=offer['abilityId']);settle()
def library_ids():return [c['forgeId'] for c in e.state['hidden'] if c['owner']==2 and c['zone']=='Library']
try:
 e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,**settings)
 before=library_ids();e.check('Eight original opponent library objects are in the seeded position',len(before)==len(library))
 if a.case=='real-line':
  cast('Freed from the Real')
  def tap():
   id=card('Zaxara, the Exemplary')['forgeId'];offer=next(o for o in e.state['legalManaOffers'] if o['forgeId']==id);act('activate_mana',id,abilityId=offer['abilityId'])
  tap();initial=e.state['manaTotal']
  for _ in range(10):activate('Freed from the Real','untap');tap()
  e.check('Ten actual paid untap/tap cycles each net one mana',e.state['manaTotal']==initial+10)
  for color in ('green','black'):activate('Freed from the Real','untap');tap()
  x=len(library);cast('Villainous Wealth')
  e.check('Wealth consumes every original opposing library object',not library_ids() and set(before)<={c['forgeId'] for zone in ['exile','battlefield','stack','graveyard'] for c in e.state.get(zone,[])})
  e.check('Free-cast stolen creatures are controlled by us but still opponent-owned',all(any(c['name']==name and c['controller']==1 and c['owner']==2 for c in e.state['battlefield']) for name in ['Yoked Ox','Field Creeper']))
  for _ in range(100):
   if e.state['gameOver']:break
   act('pass_priority',_attack_policy=lambda d,s:[])
  e.check('The real emptied library loses on a subsequent draw',e.state['gameOver'] and next(v for v in e.state['players'] if v['seat']==1)['won'])
 else:
  x=8;cast('Villainous Wealth',False);cast('Twincast',False)
  for _ in range(20):
   if sum(c['name']=='Villainous Wealth' for c in e.state['stack'])>=3:break
   act('pass_priority')
  e.check('Twinning Staff adds two Wealth copies alongside the original',sum(c['name']=='Villainous Wealth' for c in e.state['stack'])==3)
  settle();e.check('Copied Wealth resolves through native choices without a gap',not e.state['fidelityGap'])
 result=dict(passed=True,case=a.case,checks=e.checks,evidence=str(e.ipc),scope='Explicit seeded position. Real Forge costs/effects, shipped native handlers; no normal-shuffle or full-deck certification.')
except Exception as error:result=dict(passed=False,case=a.case,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
finally:
 if e:e.close()
(a.output/'report.json').write_text(json.dumps(result,indent=2));(a.output/'choices.json').write_text(json.dumps(trace,indent=2));print(json.dumps(dict(passed=result['passed'],case=a.case,error=result.get('error','')[:450],checks=len(result['checks']),evidence=result['evidence'])));raise SystemExit(0 if result['passed'] else 1)
