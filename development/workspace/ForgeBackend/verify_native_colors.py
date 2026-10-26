"""Color choices plus independent protection-legality and expiry checks.

All valid gameplay submissions go through original Arena request handlers in
one session per case. Forge owns costs, target restrictions and duration.
Native keyword badge/rendering parity is explicitly outside this test.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import traceback


COLORS=['white','blue','black','red','green']
PROBES={'white':('Pacifism',['Plains']*3),'blue':('Unsummon',['Island']*2),'black':('Murder',['Swamp']*3),'red':('Infuriate',['Mountain']*2),'green':('Giant Growth',['Forest']*2)}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(card,color,factory):
    e=None
    try:
        probe,lands=PROBES[color]
        e=factory('card-family',randomSeed=7274,fixtureHand=[card,probe],fixtureLands=['Plains']*2+lands,
                  fixtureLibrary=['Forest','Mountain','Plains','Island','Swamp','Forest'],fixtureBattlefield=['Savannah Lions','Grizzly Bears'])
        def check(label,value):e.check(label,value)
        target=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Savannah Lions')
        unprotected=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears')
        spell=next(c['forgeId'] for c in e.state['hand'] if c['name']==card)
        probe_id=next(c['forgeId'] for c in e.state['hand'] if c['name']==probe)
        initial_library=[c['forgeId'] for c in e.state['hidden'] if c['zone']=='Library' and c['owner']==1]
        seen=[]
        def transact(op,identity=0):
            parent=e.begin(op,identity);end=time.monotonic()+20
            while time.monotonic()<end:
                if (e.ipc/'responses'/(parent+'.json')).exists():
                    check('Native submission reaches the real accepted Forge boundary',e.finish(parent)['accepted']);return
                try:message=json.loads((e.ipc/'decision.json').read_text())
                except (FileNotFoundError,PermissionError,json.JSONDecodeError):message=None
                if message and message['parentRequestId']==parent:
                    e.state=message['state'];d=e.state['decision'];fields=dict(decisionToken=d['token'])
                    check('No unresolved human callback was hidden',not e.state['fidelityGap'])
                    if d['kind']=='targets':
                        check('Initial protection target is actually offered',target in [c.get('forgeId') for c in d['options']])
                        check('Native target update succeeds',e.send('select_targets',assignments=[dict(forgeId=target)],**fields)['accepted'])
                        check('Native target submission succeeds',e.send('submit_targets',**fields)['accepted'])
                        seen.append('target')
                    elif d['kind']=='choice' and d['choice']['type']=='colors':
                        spec=d['choice'];options=spec['options'];seen.append('color')
                        check('Actual callback offers exactly the five Magic colors',sorted(o['color'].lower() for o in options)==sorted(COLORS) and spec['min']==spec['max']==1)
                        selected=next(o['choiceId'] for o in options if o['color'].lower()==color)
                        for values in ([],[dict(choiceId=selected)]*2,[dict(choiceId=9999)],[dict(choiceId=1.5)]):
                            reply=e.send('submit_choice',assignments=values,**fields);check('Malformed native color selection preserves the pending choice',not reply['accepted'] and e.state['decision']['token']==d['token'])
                        check('Original native color chooser accepts the selected offered color',e.send('submit_choice',assignments=[dict(choiceId=selected)],**fields)['accepted'])
                    elif d['kind']=='choice' and d['choice']['type']=='partition':
                        spec=d['choice'];seen.append('scry')
                        check('Scry follows protection and preserves the original peeked object',seen==['target','color','scry'] and len(spec['options'])==1 and spec['options'][0]['forgeId']==initial_library[0])
                        check('Original native scry keeps the intended card on top',e.send('submit_choice',assignments=[dict(choiceId=spec['options'][0]['choiceId'],group='top')],**fields)['accepted'])
                    else:raise AssertionError('Unexpected callback '+json.dumps(d))
                time.sleep(.025)
            raise TimeoutError('Color operation did not complete')
        transact('cast_spell',spell)
        for _ in range(12):
            if any(c['forgeId']==spell for c in e.state['graveyard']):break
            transact('pass_priority')
        check('Protection spell really resolves to graveyard',any(c['forgeId']==spell for c in e.state['graveyard']))
        check('Expected complete decision sequence occurred',seen==(['target','color','scry'] if card=='Gods Willing' else ['color']))
        if any("keywordGrants" in c for c in e.state["battlefield"]):
            protected=next(c for c in e.state["battlefield"] if c["forgeId"]==target)
            check("Observed active keyword grant retains the independent chosen color and actual source",[(g["keyword"].lower(),g["sourceForgeId"]) for g in protected["keywordGrants"]]==[("protection from "+color,spell)])
        check('No hidden library reordering occurs',[c['forgeId'] for c in e.state['hidden'] if c['zone']=='Library' and c['owner']==1]==initial_library)
        def offered_probe(expect_protection):
            hand_before=[c['forgeId'] for c in e.state['hand']];tapped_before=[c['forgeId'] for c in e.state['battlefield'] if c['tapped']]
            parent=e.begin('cast_spell',probe_id);d=e.state.get('decision')
            check('Native probe is a real prepayment target request',d is not None and d['kind']=='targets')
            offered=[o.get('forgeId') for o in d['options']]
            check('Independent color-protection target legality is correct',(target not in offered) if expect_protection else target in offered)
            check('Unprotected creature remains legal in the same actual target list',unprotected in offered)
            fields=dict(decisionToken=d['token'])
            if expect_protection:
                reply=e.send('select_targets',assignments=[dict(forgeId=target)],**fields)
                check('Protected target cannot be selected through the native handler',not reply['accepted'] and e.state['decision']['token']==d['token'])
            check('Native cancellation succeeds before payment',e.send('cancel_targets',**fields)['accepted'])
            check('Canceled native cast reaches its Forge boundary',e.finish(parent)['accepted'])
            check('Cancellation preserves source and mana',[c['forgeId'] for c in e.state['hand']]==hand_before and [c['forgeId'] for c in e.state['battlefield'] if c['tapped']]==tapped_before)
        offered_probe(True)
        start_turn=e.state['turn']
        for _ in range(40):
            if e.state['turn']>start_turn and e.state['activeSeat']==1 and e.state['phase']=='MAIN1':break
            transact('pass_priority')
        check('Real Forge phase loop reaches the next local main phase',e.state['turn']>start_turn and e.state['activeSeat']==1 and e.state['phase']=='MAIN1')
        offered_probe(False)
        check('No unintended outcome or fidelity gap',not e.state['gameOver'] and not e.state['fidelityGap'])
        return dict(id=card+'-'+color,passed=True,checks=len(e.checks),evidence=str(e.ipc))
    except Exception as failure:return dict(id=card+'-'+color,passed=False,error=str(failure)[:2000],traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--color',choices=COLORS,action='append');p.add_argument('--card',choices=['Gods Willing','Brave the Elements'],action='append');a=p.parse_args()
    os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy))
    from native_engine_test_client import NativeEngine
    from runtime_paths import ROOT
    preparation=json.loads((ROOT.parent/'preparation.json').read_text());source=ROOT.parent/'sources/ForgeBackend/ForgeLandEngine.java'
    if preparation['sourceSha256']!=sha(source):raise RuntimeError('Prepared source bytes changed')
    a.output.mkdir(parents=True,exist_ok=False);hashes={str(f):sha(f) for f in a.worker.parent.glob('*.dll')}
    factory=lambda scenario,**settings:NativeEngine(scenario,worker=a.worker,managed=a.managed,fixture=a.fixture,**settings)
    rows=[]
    for card in a.card or ['Gods Willing','Brave the Elements']:
        for color in a.color or COLORS:
            row=run_case(card,color,factory);rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='traceback'}),flush=True)
    if any(sha(Path(path))!=digest for path,digest in hashes.items()) or sha(source)!=preparation['sourceSha256']:raise RuntimeError('Pinned test bytes changed during run')
    result=dict(passed=all(r['passed'] for r in rows),cases=rows,sourceSha256=preparation['sourceSha256'],nativeBinaries=hashes,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
    (a.output/'report.json').write_text(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
