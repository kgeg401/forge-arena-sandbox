"""Real source-bound Akroma modal choices and temporary original native combat grants."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute
from runtime_paths import ROOT

def run(a,key):
    e=None;trace=[];choices=[];both=key=='commander-both';first=key=='first-mode';double=both or first;life=both or not first
    try:
        options=dict(randomSeed=7274,fixtureHand=["Akroma's Will"],fixtureLands=['Plains']*4,fixtureBattlefield=['Grizzly Bears'],fixtureOpponentBattlefield=['Giant Spider','Mammoth Spider'],fixtureOpponentPolicy='block-all',fixtureBattlefieldReady=True,fixtureLibrary=['Plains']*20)
        if both:options.update(fixtureCommander='Isamaru, Hound of Konda',fixtureCommanderInPlay=True)
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,**options)
        bear=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears');spell=next(c['forgeId'] for c in e.state['hand'] if c['name']=="Akroma's Will")
        def select(c,s):
            if c['type']!='modes':return None
            choices.append(c)
            selected=c['options'] if both else [c['options'][0 if first else 1]]
            return [dict(choiceId=v['choiceId']) for v in selected]
        execute(e,trace,'cast_spell',spell,_choice_policy=select)
        for _ in range(20):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',_choice_policy=select)
        else:raise AssertionError('Actual Akroma modal stack did not settle')
        e.check('Original modal handler receives actual one-or-both source limits',len(choices)==1 and choices[0]['min']==1 and choices[0]['max']==(2 if both else 1))
        metadata=json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text(encoding='utf-8-sig'))
        names=(['flying','vigilance','double strike'] if double else [])+(['lifelink','indestructible','protection from white','protection from blue','protection from black','protection from red','protection from green'] if life else [])
        expected={metadata['keywordAbilityIds'][n] for n in names}
        def native():return [json.loads(v)['value'] for v in (e.native_folder/'native-model.jsonl').read_text().splitlines() if json.loads(v)['kind']=='native-update'][-1]
        def grants():return {v['abilityId'] for c in native()['cards'] if c['id']==1000+bear for v in c['keywordGrants']}
        e.check('Every selected original native keyword is added, with no unselected mode',grants()==expected)
        buffed=e.state;attack={c['forgeId']:(2 if c['forgeId']==bear else 0) for c in e.state['battlefield'] if c['controller']==1}
        # First mode can be blocked by reach; the protection modes cannot. For
        # the first-mode control observe grants/expiry without forcing damage.
        for _ in range(50):
            if e.state['phase']=='MAIN2' and not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',_attack_seat=attack)
        else:raise AssertionError('Real Akroma combat did not reach second main')
        if life:
            expected_damage=4 if double else 2
            e.check('Actual color protection prevents the green reach blockers from blocking',e.state['opponentLife']==20-expected_damage and all(c['forgeId']!=bear or c['damage']==0 for c in e.state['battlefield']))
            e.check('Real double strike and lifelink use only the selected modes',e.state['life']==20+expected_damage)
            e.check('Vigilance only prevents tapping when its actual mode was selected',next(c['tapped'] for c in e.state['battlefield'] if c['forgeId']==bear)==(not double))
        combat=e.state
        for _ in range(80):
            if e.state['turn']>=3 and e.state['activeSeat']==1 and e.state['phase']=='MAIN1':break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Actual Akroma cleanup did not complete')
        # A blocked first-mode Bear can die; native death is an actual outcome,
        # while the protection cases preserve it for direct expiry comparison.
        if life:e.check('All temporary native mode grants expire at actual cleanup',not grants() and any(c['forgeId']==bear for c in e.state['battlefield']))
        e.check('No extra mode confirmation, unresolved decision or fidelity gap remains',not e.state.get('decision') and not e.state['fidelityGap'] and sum(v.get('type')=='modes' for v in trace)==1)
        result=dict(passed=True,case=key,checks=e.checks,buffedState=buffed,combatState=combat,finalState=e.state,modeChoices=choices,evidence=str(e.ipc))
    except Exception as error:result=dict(passed=False,case=key,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
    (a.output/(key+'.json')).write_text(json.dumps(result,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps({k:result.get(k) for k in ('case','passed','error','evidence')}),flush=True);return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('worker','managed','fixture','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--case',choices=['first-mode','second-mode','commander-both'],action='append')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);results=[run(a,key) for key in a.case or ['first-mode','second-mode','commander-both']];raise SystemExit(0 if all(results) else 1)
