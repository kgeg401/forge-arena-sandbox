"""Actual land-drop/commander casts and first-wave timing through native handlers."""
import argparse,json,time,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

CASES=[('Isamaru, Hound of Konda',1,[('Plains',99)]),('Emry, Lurker of the Loch',3,[('Island',99)]),('The Gitrog Monster',5,[('Forest',50),('Swamp',49)]),('Darien, King of Kjeldor',6,[('Plains',99)])]

def run(case,a):
    name,mv,lands=case;e=None;trace=[]
    try:
        deck=dict(name='Commander preparation boundary',format='commander-40',commander=dict(name=name,count=1),cards=[dict(name=n,count=c) for n,c in lands])
        e=NativeEngine('zombie-horde',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,localDeck=deck)
        e.check('Forty starting life',e.state['startingLifeTotal']==40)
        e.check('Prep budget uses original commander mana value',e.state['horde']['preparationTurns']==mv)
        cast=False;land_plays=0;end=time.monotonic()+100
        for _ in range(180):
            s=e.state;assert not s['fidelityGap'],s['fidelityGap']
            if any(v['kind']=='horde-wave' for v in s['events']):break
            assert time.monotonic()<end,'Bounded preparation scenario timed out'
            d=s.get('decision')
            if d:
                if d['kind']=='mulligan':execute(e,trace,'submit_mulligan',decisionToken=d['token'],assignments=[dict(keep=True)])
                else:raise AssertionError('Unexpected opening decision: '+str(d))
            elif s['legalLands']:
                offered={c['forgeId']:c['name'] for c in s['hand']}
                played={c['name'] for c in s['battlefield'] if c['controller']==1}
                missing={'Forest','Swamp'}-played if name=='The Gitrog Monster' else set()
                chosen=next((i for i in s['legalLands'] if offered[i] in missing),s['legalLands'][0])
                execute(e,trace,'play_land',chosen);land_plays+=1
            elif not cast and any(c['name']==name and c['zone']=='Command' and c['forgeId'] in s['legalCasts'] for c in s['command']):
                c=next(c for c in s['command'] if c['name']==name)
                execute(e,trace,'cast_spell',c['forgeId']);cast=True
            else:execute(e,trace,'pass_priority')
        waves=[v for v in e.state['events'] if v['kind']=='horde-wave']
        e.check('First Horde wave follows all preparation turns',bool(waves) and waves[0]['turn']==mv+1)
        e.check('Original commander was cast before the first wave',cast)
        e.check('At least commander mana-value land drops were available',land_plays>=mv)
        return dict(commander=name,passed=True,checks=e.checks,evidence=str(e.ipc),trace=trace)
    except Exception as error:return dict(commander=name,passed=False,error=repr(error),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None,trace=trace)
    finally:
        if e:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('worker','managed','fixture','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[]
    for i,c in enumerate(CASES):
        r=run(c,a);(a.out/(str(i)+'.json')).write_text(json.dumps(r,indent=2));rows.append(r);print(json.dumps(dict(commander=r['commander'],passed=r['passed'],error=(r.get('error') or '')[:200])),flush=True)
    (a.out/'report.json').write_text(json.dumps(rows,indent=2));raise SystemExit(0 if all(r['passed'] for r in rows) else 1)
