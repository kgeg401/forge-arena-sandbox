"""Real paid 304-trigger stack: cancel/resume or a mandatory optional-trigger choice.

Runs original Arena request handlers with Forge rules in a private research root.
This is a seeded interaction check, not a rendered performance guarantee.
"""
import argparse,json,time,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

p=argparse.ArgumentParser(description=__doc__)
for name in ('worker','managed','fixture','output'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--case',choices=('cancel','choice'),required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[];report={};seenFast=False

def refresh():
    e.native_status=e.native_wait(e.native_folder/'status.json');e.state=e.native_status['state'];return e.native_status

def wait(predicate,seconds=90):
    global seenFast
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        s=refresh()
        seenFast|=s['loop']['fastResolving']
        if predicate(s):return s
        assert not s.get('gap'),s.get('gap')
        time.sleep(.025)
    raise TimeoutError('Large-stack boundary was not reached')

try:
    sources=['Impassioned Orator']*3+["Soul's Attendant"] if a.case=='choice' else ['Impassioned Orator']*4
    e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,fixtureHand=['Secure the Wastes','Opt'],fixtureLands=['Plains']*24+['Island'],fixtureBattlefield=sources+['Doubling Season','Parallel Lives'],fixtureBattlefieldReady=True,fixtureOpponentPolicy='passive',randomSeed=7117,autoOrderTriggers=True,autoChooseReplacementEffects=True)
    def choice(c,s):
        if c['type']=='number':return [dict(number=19)]
    spell=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Secure the Wastes')
    execute(e,trace,'cast_spell',spell,_choice_policy=choice);execute(e,trace,'pass_priority')
    e.check('All 304 actual triggers exist',len(e.state['stackOrder'])==304)
    initialLife=e.state['life']
    start=e.native_call('fast_stack_start');assert start['accepted'],start
    if a.case=='choice':
        status=wait(lambda s:bool(s['state'].get('decision')))
        e.check('Fast progression was active before the later optional trigger',seenFast)
        e.check('Optional trigger retains the actual confirmation',status['state']['decision']['kind']=='choice' and status['state']['decision']['choice']['type']=='confirm')
        e.check('Acceleration stops for the player decision',not status['loop']['fastResolving'] and not status['state'].get('actionOffersDeferred'))
        before=status['state'];time.sleep(.25);refresh()
        e.check('The unanswered choice remains pending',e.state['decision']['token']==before['decision']['token'] and e.state['life']==before['life'])
    else:
        status=wait(lambda s:s['loop']['fastResolving'] and len(s['state']['stackOrder'])<=288)
        wrong=e.native_call('fast_stack_cancel',fastRunId='wrong-run')
        e.check('An unrelated cancellation cannot stop this batch',not wrong['accepted'])
        refresh();cancel=e.native_call('fast_stack_cancel',fastRunId=e.native_status['loop']['fastRunId']);assert cancel['accepted'],cancel
        status=wait(lambda s:not s['loop']['fastResolving'] and not s['state'].get('actionOffersDeferred') and s['interaction']=='ActionsAvailableRequest')
        left=len(e.state['stackOrder']);life=e.state['life'];time.sleep(.3);refresh()
        e.check('Cancel holds the same remaining stack',0<left<304 and len(e.state['stackOrder'])==left and e.state['life']==life)
        opt=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Opt')
        e.check('Fresh instant availability returns on cancel',opt in e.state['legalCasts'] and e.native_status['castAvailability'])
        start=e.native_call('fast_stack_start');assert start['accepted'],start
        wait(lambda s:not s['state']['stackOrder'])
        e.check('Resume resolves every original trigger exactly once',e.state['life']==initialLife+304 and len([x for x in e.state['events'] if x['kind']=='life-gain'])==304)
        e.check('Control returns at the same main phase',not e.native_status['loop']['fastResolving'] and not e.state.get('actionOffersDeferred') and e.state['phase']=='MAIN1')
    report=dict(passed=True,case=a.case,checks=e.checks,evidence=str(e.ipc),scope=__doc__)
except Exception as error:
    report=dict(passed=False,case=a.case,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
finally:
    if e:e.close()
    (a.output/'report.json').write_text(json.dumps(report,indent=2));(a.output/'trace.json').write_text(json.dumps(trace))
print(json.dumps({k:v for k,v in report.items() if k not in ('checks','scope','traceback')}));raise SystemExit(0 if report['passed'] else 1)
