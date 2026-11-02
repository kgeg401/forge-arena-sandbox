"""Original-handler combat against non-player defenders, with seeded initial zones.

Forge owns attack legality, blocking, assignment, damage and state-based deaths.
No intermediate damage, loyalty, life or native presentation state is injected.
"""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

def run(a,key):
    e=None;trace=[];walker_name='Jace, Wielder of Mysteries';report={}
    try:
        blocked=key.startswith('blocked-');overassign=key=='blocked-all-to-bear';partial=key=='blocked-partial-pw';expected=0 if overassign else 3 if partial else 4 if blocked else 6
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,
            fixtureHand=[],fixtureLands=[],fixtureBattlefield=['Colossal Dreadmaw'],fixtureBattlefieldReady=True,
            fixtureOpponentBattlefield=[walker_name]+(['Grizzly Bears'] if blocked else []),fixtureOpponentPolicy='block-all',
            fixtureCounters=[dict(seat=2,cardName=walker_name,occurrence=0,type='LOYALTY',count=4)],fixtureLibrary=['Forest']*20)
        source=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Colossal Dreadmaw');walker=next(c['forgeId'] for c in e.state['battlefield'] if c['name']==walker_name)
        e.check('Actual initial planeswalker has four loyalty',next(c for c in e.state['battlefield'] if c['forgeId']==walker)['loyalty']==4)
        def attack(d,s):
            offer=next(v for v in d['options'] if v['forgeId']==source)
            e.check('Original attacker legally offers the actual planeswalker recipient',any(v['targetSeat']==2 and v['targetForgeId']==walker for v in offer['attackTargets']))
            return [dict(forgeId=source,targetSeat=2,targetForgeId=walker)]
        def damage(d,s):
            bear=next(c['forgeId'] for c in s['battlefield'] if c['name']=='Grizzly Bears')
            e.check('Defender card is offered without a player spillover substitute',{v['forgeId'] for v in d['options']}=={bear,walker})
            return [dict(forgeId=v['forgeId'],amount=expected if v['forgeId']==walker else 6-expected) for v in d['options']]
        for _ in range(70):
            if e.state['phase']=='MAIN2':break
            execute(e,trace,'pass_priority',_attack_policy=attack,_damage_policy=damage if blocked else None)
        else:raise AssertionError('Combat did not reach its second main phase')
        e.check('Trample damage to a planeswalker cannot spill into its controller',e.state['opponentLife']==20)
        e.check('Original planeswalker survives exactly when assigned damage is below loyalty',any(c['forgeId']==walker for c in e.state['graveyard'])==(expected>=4))
        hits=[v for v in e.state['events'] if v['kind']=='damage' and v.get('combat') and v.get('sourceForgeId')==source]
        loyalty=[v for v in e.state['events'] if v['kind']=='counter-change' and v.get('targetForgeId')==walker and v.get('counterType')=='LOYALTY']
        e.check('Actual loyalty loss is independently bounded by original four counters',sum(v['before']-v['after'] for v in loyalty)==min(4,expected))
        impacts=[v for v in hits if v.get('targetForgeId')==walker]
        e.check('Post-prevention presentation observes exact damage without duplicate impacts',len(impacts)==int(expected>0) and sum(v['amount'] for v in impacts)==expected)
        e.check('Planeswalker impact never marks creature-style damage',all(v.get('markDamage') is False for v in impacts))
        native=[json.loads(v)['value'] for v in (e.native_folder/'native-model.jsonl').read_text().splitlines() if json.loads(v)['kind']=='native-update']
        actual=[v for row in native for v in row['damageEvents'] if v['target']==1000+walker and v['source']==1000+source]
        e.check('Original Arena parser emits the same exact combat impact',len(actual)==int(expected>0) and sum(v['amount'] for v in actual)==expected and all(v['type']=='Combat' for v in actual))
        e.check('Original native planeswalker model has no falsely marked creature damage',all(c['damage']==0 for row in native for c in row['cards'] if c['id']==1000+walker))
        if blocked:
            e.check('The original blocking Bear dies from chosen real assignment',any(c['name']=='Grizzly Bears' and c['owner']==2 for c in e.state['graveyard']) and any(v.get('amount')==6-expected and v.get('targetForgeId')!=walker for v in hits))
            e.check('Blocked trample uses a real native damage-allocation request',any(v.get('kind')=='assign_damage' for v in trace))
        e.check('Original attacker survives the real combat',any(c['forgeId']==source for c in e.state['battlefield']))
        e.check('No unsupported callbacks or orphaned decision remain',not e.state['fidelityGap'] and not e.state.get('decision'))
        report=dict(case=key,passed=True,checks=e.checks,evidence=str(e.ipc),scope=__doc__)
    except Exception as error:report=dict(case=key,passed=False,error=repr(error)[:1400],traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
    (a.output/(key+'.json')).write_text(json.dumps(report,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps({k:report.get(k) for k in ('case','passed','error','evidence')}),flush=True);return report['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('worker','managed','fixture','output'):p.add_argument('--'+k,type=Path,required=True)
    cases=('unblocked-pw','blocked-pw','blocked-partial-pw','blocked-all-to-bear')
    p.add_argument('--case',choices=cases,action='append');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    results=[run(a,key) for key in (a.case or cases)];raise SystemExit(0 if all(results) else 1)
