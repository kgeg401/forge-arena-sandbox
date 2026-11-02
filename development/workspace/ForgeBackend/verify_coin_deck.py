"""Bounded coin-engine interactions through original native handlers and Forge.

Only initial zones/life are fixtures. Rolls, payments, stack, triggers and wins
come from Forge; this is not a complete deck or competitive-strength claim.
"""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

def run(a,case):
    e=None;trace=[];report={}
    def choices(c,s):
        if c['type']=='number':return [dict(number=min(5,c['max']))]
        if c['type']=='confirm':return [dict(accept=True)]
        opts=c.get('options',[])
        free=next((v for v in opts if '(without paying its mana cost)' in v.get('label','')),None)
        if free:return [dict(choiceId=free['choiceId'])]
        desired='Tails' if 'Call coin flip' in c.get('prompt','') else 'Keep winning flip'
        if any(v.get('label')==desired for v in opts):return [dict(choiceId=next(v['choiceId'] for v in opts if v.get('label')==desired))]
        if c['type']=='number-options':return [dict(choiceId=max(opts,key=lambda v:v.get('number',0))['choiceId'])]
        return None
    try:
        is_yusri=case.startswith('yusri');source="Yusri, Fortune's Flame" if is_yusri else 'Frenetic Efreet'
        board=[source,'Tavern Scoundrel','Chance Encounter']+([] if case=='yusri-plain' else ["Krark's Thumb"])
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,
            fixtureHand=[],fixtureLands=[],fixtureBattlefield=board,
            fixtureBattlefieldReady=True,fixtureLibrary=['Lightning Bolt']*70,fixtureLocalLife=40)
        initial_life=e.state['life'];initial_hand=len(e.state['hand'])
        if case=='frenetic':
            id=next(c['forgeId'] for c in e.state['battlefield'] if c['name']==source)
            for _ in range(24):
                ability=next(v for v in e.state['legalActivations'] if v['forgeId']==id)
                execute(e,trace,'activate_ability',id,abilityId=ability['abilityId'],_choice_policy=choices)
            e.check('Twenty-four genuine activated abilities coexist on the stack',len(e.state['stackOrder'])==24)
        for step in range(160):
            s=e.state;flips=[v for v in s['events'] if v['kind']=='coin-flip']
            if len(flips)==(5 if is_yusri else 24) and not s['stackOrder']:break
            execute(e,trace,'pass_priority',_attack_seat=2,_choice_policy=choices)
        else:raise AssertionError('Coin engine did not reach its bounded settled stack')
        s=e.state;flips=[v for v in s['events'] if v['kind']=='coin-flip']
        calls=[v for v in trace if v.get('kind')=='choice-assignments' and 'Call coin flip' in (v.get('prompt') or '')]
        multiplier=1 if case=='yusri-plain' else 2
        e.check('Each logical flip retains all physical tosses',all(len(v.get('tosses',[]))==multiplier for v in flips),[(v['id'],v.get('tosses')) for v in flips])
        e.check('The kept result is one of the observed tosses',all(v['heads'] in v['tosses'] for v in flips))
        native_flips=[json.loads(line)['value'] for line in (e.native_folder/'native-model.jsonl').read_text(encoding='utf-8-sig').splitlines() if json.loads(line).get('kind')=='native-coin-flip']
        parsed=[(v['seat'],head) for v in native_flips for head in v['heads']]
        e.check('Original native parser receives each actual flip once, in order',parsed==[(v['seat'],head) for v in flips for head in v['tosses']])
        e.check('Native coin events retain a source identity',all(v['sourceId']>0 for v in native_flips))
        e.check('One complete coin reveal per resolved ability',len(native_flips)==(1 if is_yusri else 24),dict(actual=len(native_flips),expected=1 if is_yusri else 24))
        # The test deliberately calls Tails, catching a Thumb implementation
        # that incorrectly treats Heads as a win regardless of the player's call.
        wins=sum(not v['heads'] for v in flips)
        chance=next(c for c in s['battlefield'] if c['name']=='Chance Encounter')
        luck=sum(c['count'] for c in chance['counters'] if c['type']=='LUCK')
        treasures=[c for c in s['battlefield'] if 'Treasure' in c.get('currentSubtypes',c.get('subtypes',[]))]
        e.check('Every resolved flip records its actual native result',len(flips)==(5 if is_yusri else 24))
        e.check('Actual coin calls are presented as native choices',len(calls)==len(flips))
        e.check('Chance Encounter counts exactly the winning calls',luck==wins)
        e.check('Tavern Scoundrel creates exactly two Treasures per winning call',len(treasures)==2*wins)
        if is_yusri:
            e.check('Yusri draws once per win',len(s['hand'])==initial_hand+wins)
            e.check('Yusri deals two damage per loss',s['life']==initial_life-2*(5-wins))
            if wins==5:
                shock=next(c for c in s['hand'] if c['name']=='Lightning Bolt')
                e.check('Five wins makes the drawn spell castable',shock['forgeId'] in s['legalCasts'])
                execute(e,trace,'cast_spell',shock['forgeId'],_choice_policy=choices,_target_seat=2)
                for _ in range(12):
                    if not e.state['stackOrder']:break
                    execute(e,trace,'pass_priority',_choice_policy=choices)
                e.check('Yusri free-cast spell resolves through the native handler',any(c['forgeId']==shock['forgeId'] for c in e.state['graveyard']))
                e.check('Free casting consumes no Treasure or other mana source',len([c for c in e.state['battlefield'] if 'Treasure' in c.get('currentSubtypes',c.get('subtypes',[]))])==len(treasures) and not any(v['kind']=='sacrificed' for v in e.state['events']))
        elif wins>=10:
            for _ in range(30):
                if e.state['gameOver']:break
                execute(e,trace,'pass_priority',_choice_policy=choices,_attack_policy=lambda d,s:[])
            e.check('Chance Encounter wins on the next actual upkeep',e.state['gameOver'] and next(p for p in e.state['players'] if p['seat']==1)['won'])
        e.check('No unresolved choice or fidelity gap remains',not s.get('decision') and not s['fidelityGap'])
        report=dict(case=case,passed=True,flips=len(flips),physicalTosses=sum(len(v['tosses']) for v in flips),tossGroups=[v['tosses'] for v in flips],wins=wins,treasures=len(treasures),luck=luck,checks=e.checks,evidence=str(e.ipc),scope=__doc__)
    except BaseException as error:report=dict(case=case,passed=False,error=repr(error),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
        (a.output/(case+'.json')).write_text(json.dumps(report,indent=2));(a.output/(case+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('checks','traceback','scope')}),flush=True)
    return report['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--case',choices=['yusri','yusri-plain','frenetic'],required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    raise SystemExit(0 if run(a,a.case) else 1)
