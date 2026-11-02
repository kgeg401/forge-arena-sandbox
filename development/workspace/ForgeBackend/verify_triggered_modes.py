"""Native choices and independent outcomes for top-pool modal triggers."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

CASES=('cleric-life','cleric-destroy','cleric-exile','barbarian-treasure','barbarian-destroy','hull-spell','hull-permanent','hull-decline')
def run(a,key):
    e=None;trace=[];mode_choices=[];wanted=None
    source='Dawnbringer Cleric' if key.startswith('cleric') else 'Plundering Barbarian' if key.startswith('barbarian') else 'Hullbreaker Horror'
    settings=dict(fixtureHand=['Opt' if key.startswith('hull') else source],fixtureLands=[n for n in ('Plains','Island','Swamp','Mountain','Forest') for _ in range(4)],fixtureBattlefield=['Hullbreaker Horror'] if key.startswith('hull') else [],fixtureBattlefieldReady=True,fixtureOpponentBattlefield=['Sol Ring','Rhystic Study'],fixtureOpponentGraveyard=['Lightning Bolt'],fixtureLibrary=['Forest','Island','Plains','Mountain']*5)
    if key=='hull-spell':settings.update(fixtureOpponentSpell='Divination',fixtureOpponentLands=['Island']*3)
    needle={'cleric-life':'gain 2 life','cleric-destroy':'destroy target enchantment','cleric-exile':'exile target card','barbarian-treasure':'treasure token','barbarian-destroy':'destroy target artifact','hull-spell':'return target spell','hull-permanent':'return target nonland permanent','hull-decline':''}[key]
    def choices(c,s):
        if c['type']=='modes':
            options=c['options'];matches=[v for v in options if needle in v['label'].lower()]
            e.check('Modal trigger has original positive native parent and child identities',c.get('nativeParentAbilityId',0)>0 and all(v.get('nativeAbilityId',0)>0 for v in options))
            if key=='hull-decline':
                e.check('Hullbreaker permits choosing no mode',c['min']==0);mode_choices.append(dict(declined=True));return []
            e.check('The exact intended rules mode is uniquely offered',len(matches)==1)
            mode_choices.append(matches[0]);return [dict(choiceId=matches[0]['choiceId'])]
        if c['type']=='confirm':return [dict(accept=True)]
        if c['type']=='partition':return [dict(choiceId=v['choiceId'],group='top') for v in c['options']]
        return None
    def targets(d,s):return [v for v in d['options'] if v['forgeId']==wanted]
    def act(op,id=0,**kw):return execute(e,trace,op,id,_choice_policy=choices,_target_policy=targets,**kw)
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,**settings)
        before=[v['forgeId'] for v in e.state['hidden'] if v['zone']=='Library' and v['owner']==1]
        ring=next(v['forgeId'] for v in e.state['battlefield'] if v['name']=='Sol Ring');study=next(v['forgeId'] for v in e.state['battlefield'] if v['name']=='Rhystic Study')
        grave=next(v['forgeId'] for v in e.state['graveyard'] if v['name']=='Lightning Bolt');spell=e.state['hand'][0]['forgeId']
        wanted=study if key=='cleric-destroy' else grave if key=='cleric-exile' else next(v['forgeId'] for v in e.state['stack'] if v['name']=='Divination') if key=='hull-spell' else ring
        e.check('The real initial spell is legally castable',spell in e.state['legalCasts']);act('cast_spell',spell)
        for _ in range(45):
            if not e.state['stackOrder']:break
            act('pass_priority')
        else:raise AssertionError('Modal trigger stack did not settle')
        e.check('Native UI received and submitted the real modal trigger choice',len(mode_choices)==1)
        if key=='cleric-life':e.check('Gain-life mode changes life by exactly two and preserves alternatives',e.state['life']==22 and any(v['forgeId']==study for v in e.state['battlefield']) and any(v['forgeId']==grave for v in e.state['graveyard']))
        elif key in ('cleric-destroy','barbarian-destroy'):e.check('Destroy mode moves only its exact target to its owner graveyard',any(v['forgeId']==wanted and v['owner']==2 for v in e.state['graveyard']) and not any(v['forgeId']==wanted for v in e.state['battlefield']))
        elif key=='cleric-exile':e.check('Exile mode moves the original opposing graveyard card to exile',any(v['forgeId']==grave and v['owner']==2 for v in e.state['exile']))
        elif key=='barbarian-treasure':e.check('Treasure mode creates exactly one real artifact token while preserving the targetable ring',sum(bool(v.get('token')) and 'Treasure' in v['currentSubtypes'] for v in e.state['battlefield'])==1 and any(v['forgeId']==ring for v in e.state['battlefield']))
        elif key=='hull-spell':
            e.check('Spell-bounce mode returns the exact opposing spell, not our own Opt',any(v['forgeId']==wanted and v['owner']==2 and v['zone']=='Hand' for v in e.state['hidden']))
            e.check('Our own original Opt still resolves and draws its true top card',{v['forgeId'] for v in e.state['hand']}=={before[0]})
        elif key=='hull-permanent':
            e.check('Permanent-bounce mode returns the exact opposing artifact to hidden hand',any(v['forgeId']==ring and v['owner']==2 and v['zone']=='Hand' for v in e.state['hidden']))
            e.check('The original Opt still resolves, keeping then drawing its true top card',{v['forgeId'] for v in e.state['hand']}=={before[0]})
        elif key=='hull-decline':e.check('Declining all modes preserves opposing permanents and allows the original Opt draw',all(any(v['forgeId']==id for v in e.state['battlefield']) for id in (ring,study)) and {v['forgeId'] for v in e.state['hand']}=={before[0]})
        e.check('No chooser, unresolved stack, rules gap or dead owner remains',not e.state.get('decision') and not e.state['stackOrder'] and not e.state['fidelityGap'] and e.process.poll() is None)
        result=dict(case=key,passed=True,checks=e.checks,evidence=str(e.ipc))
    except Exception as error:result=dict(case=key,passed=False,error=repr(error)[:1800],traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
    (a.output/(key+'.json')).write_text(json.dumps(result,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps({k:result.get(k) for k in ('case','passed','error','evidence')}),flush=True);return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--case',choices=CASES,action='append');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    rows=[run(a,key) for key in (a.case or CASES)];raise SystemExit(0 if all(rows) else 1)
