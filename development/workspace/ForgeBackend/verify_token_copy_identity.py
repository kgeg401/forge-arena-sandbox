"""Saheeli turns a nontoken artifact into a Servo, then the copy expires."""
from pathlib import Path
import argparse,os,json,time
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[]
try:
    e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,
        fixtureHand=["Tormod's Crypt"],fixtureLands=[],fixtureBattlefield=['Saheeli, Sublime Artificer','Mox Amber'],
        fixtureCounters=[dict(seat=1,cardName='Saheeli, Sublime Artificer',occurrence=0,type='LOYALTY',count=5)],fixtureLibrary=['Plains']*20)
    mox=next(c for c in e.state['battlefield'] if c['name']=='Mox Amber')['forgeId']
    execute(e,trace,'cast_spell',e.state['hand'][0]['forgeId'])
    for _ in range(12):
        if not e.state['stack'] and not e.state['stackAbilities']:break
        execute(e,trace,'pass_priority')
    servo=next(c for c in e.state['battlefield'] if c.get('presentationKey')=='token:c_1_1_a_servo')['forgeId']
    saheeli=next(c for c in e.state['battlefield'] if c['name']=='Saheeli, Sublime Artificer')['forgeId']
    pending=[e.begin('activate_ability',saheeli,abilityId=133281)];seen=set();targets=[mox,servo];deadline=time.monotonic()+35
    while pending:
        assert time.monotonic()<deadline,'Target sequence deadline'
        for key in pending[:]:
            path=e.ipc/'responses'/(key+'.json')
            if path.exists():
                reply=json.loads(path.read_text());assert reply['accepted'],reply['reason'];e.state=reply['state'];pending.remove(key)
        path=e.ipc/'decision.json'
        if path.exists():
            d=json.loads(path.read_text());spec=d['state']['decision']
            if d['token'] not in seen:
                seen.add(d['token']);e.state=d['state'];assert spec['kind']=='targets' and targets,spec
                chosen=targets.pop(0);reply=e.send('select_targets',decisionToken=d['token'],assignments=[dict(forgeId=chosen)]);assert reply['accepted'],reply
                pending.append(e.begin('submit_targets',decisionToken=d['token']))
        time.sleep(.02)
    assert not targets
    for _ in range(12):
        if not e.state['stackAbilities']:break
        execute(e,trace,'pass_priority')
    copied=next(c for c in e.state['battlefield'] if c['forgeId']==mox)
    assert copied['name']=='Servo Token' and not copied['token'] and copied['presentationKey']=='token:c_1_1_a_servo',copied
    assert copied['power']==copied['toughness']==1 and copied['currentSubtypes']==['Servo']
    for _ in range(100):
        assert not e.state['fidelityGap'],e.state['fidelityGap']
        restored=next(c for c in e.state['battlefield'] if c['forgeId']==mox)
        if restored['name']=='Mox Amber':break
        execute(e,trace,'pass_priority')
    else:raise AssertionError('Temporary token copy did not expire')
    assert not restored['token'] and restored.get('presentationKey','Mox Amber')=='Mox Amber'
    report=dict(passed=True,copyKeepsCardInstance=True,copyKeepsNontokenStatus=True,tokenPresentation='token:c_1_1_a_servo',reverted=True,evidence=str(e.ipc))
    (a.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
finally:
    if e:
        (a.output/'trace.json').write_text(json.dumps(trace,indent=2),encoding='utf8');e.close()
