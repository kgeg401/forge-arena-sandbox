"""Bound generic choice + reveal-until outcomes through original Arena controls.

Abundant Harvest's land/nonland prompt and labels are source-bound. The original
UI's pure option translator and workflow selector are also executed without
constructing/applying a rendered workflow or starting Unity.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time
import traceback


CASES=[
    dict(id='land-after-nonlands',kind='Land',library=['Grizzly Bears','Cancel','Forest','Plains','Island']),
    dict(id='nonland-after-lands',kind='Nonland',library=['Forest','Mountain','Grizzly Bears','Cancel','Plains']),
    dict(id='land-first',kind='Land',library=['Forest','Grizzly Bears','Cancel']),
    dict(id='nonland-first',kind='Nonland',library=['Grizzly Bears','Forest','Mountain']),
    dict(id='land-not-found',kind='Land',library=['Grizzly Bears','Cancel','Divination']),
    dict(id='nonland-not-found',kind='Nonland',library=['Forest','Mountain','Plains']),
    dict(id='duplicate-original-lands',kind='Nonland',library=['Forest','Forest','Grizzly Bears','Cancel']),
    dict(id='last-original-card',kind='Nonland',library=['Grizzly Bears']),
    dict(id='empty-library',kind='Land',library=[]),
]
BASICS={'Forest','Mountain','Plains','Island','Swamp'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(case,factory,full_human_choices=False):
    e=None
    try:
        expected_found=next((i for i,n in enumerate(case['library']) if (n in BASICS)==(case['kind']=='Land')),None)
        revealed_indices=list(range(len(case['library']) if expected_found is None else expected_found+1))
        untouched=list(range(expected_found+1,len(case['library']))) if expected_found is not None else []
        remainder=[i for i in revealed_indices if i!=expected_found]
        e=factory('card-family',randomSeed=7274,fixtureHand=['Abundant Harvest'],fixtureLands=['Forest'],fixtureLibrary=case['library'])
        def check(label,value):e.check(label,value)
        original=[c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library'];source=e.state['hand'][0]['forgeId'];seen=[];revealed=[]
        def transact(op,identity=0):
            parent=e.begin(op,identity);end=time.monotonic()+20
            while time.monotonic()<end:
                if (e.ipc/'responses'/(parent+'.json')).exists():check('Native command reaches an accepted real Forge boundary',e.finish(parent)['accepted']);return
                try:message=json.loads((e.ipc/'decision.json').read_text())
                except (FileNotFoundError,PermissionError,json.JSONDecodeError):message=None
                if message and message['parentRequestId']==parent:
                    e.state=message['state'];d=e.state['decision'];fields=dict(decisionToken=d['token']);check('No callback is silently delegated',not e.state['fidelityGap'])
                    check('Every decision uses the explicit shared contract',d['kind']=='choice');spec=d['choice'];seen.append(spec['type'])
                    if spec['type']==('options' if full_human_choices else 'abilities'):
                        check('Original source descriptions and native prompt are preserved',[o['label'] for o in spec['options']]==['Land','Nonland'] and spec['nativePromptId']==(23 if full_human_choices else 12340) and spec['min']==spec['max']==1)
                        selected=next(o['choiceId'] for o in spec['options'] if o['label']==case['kind'])
                        for assignments in ([],[dict(choiceId=selected)]*2,[dict(choiceId=999)],[dict(choiceId=1.5)]):
                            check('Invalid native ability choices do not consume the handler',not e.send('submit_choice',assignments=assignments,**fields)['accepted'] and e.state['decision']['token']==d['token'])
                        check('Original native ability-choice handler submits the authored branch',e.send('submit_choice',assignments=[dict(choiceId=selected)],**fields)['accepted'])
                    elif spec['type']=='look':
                        ids=[o['forgeId'] for o in spec['options']];revealed.extend(ids)
                        check('Only the independently expected original reveal prefix is disclosed',all(identity in [original[i] for i in revealed_indices] for identity in ids) and len(set(revealed))==len(revealed))
                        check('Original look-only acknowledgement does not select an object',e.send('submit_choice',assignments=[],**fields)['accepted'])
                    else:raise AssertionError('Unexpected shared choice '+json.dumps(spec))
                time.sleep(.025)
            raise TimeoutError('Generic choice operation did not complete')
        transact('cast_spell',source)
        for _ in range(12):
            if any(c['forgeId']==source for c in e.state['graveyard']):break
            transact('pass_priority')
        check('Actual source really resolves to graveyard',any(c['forgeId']==source for c in e.state['graveyard']))
        check('Exactly the first original card of the chosen kind reaches hand',[c['forgeId'] for c in e.state['hand']]==([] if expected_found is None else [original[expected_found]]))
        actual=[c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library']
        check('Untouched original suffix remains the actual library prefix',actual[:len(untouched)]==[original[i] for i in untouched])
        check('Randomized bottom preserves every and only the unchosen original objects',sorted(actual[len(untouched):])==sorted(original[i] for i in remainder))
        check('Native reveal showed the complete independent prefix once in order',revealed==[original[i] for i in revealed_indices])
        choice_type='options' if full_human_choices else 'abilities'
        check('No hidden extra choice or missing generic decision occurs',seen.count(choice_type)==1 and set(seen)<={choice_type,'look'})
        rows=[json.loads(line) for line in (e.native_folder/'native-model.jsonl').read_text().splitlines()];ui=[r['value'] for r in rows if r['kind']=='original-choice-ui']
        check('Original native UI translator preserves both labels and selects its prompt-button workflow',bool(ui) and all(r['labels']==['Land','Nonland'] and r['nativeIds']==[0,1] and r['originalPromptButtonsSelected'] and not r['rendererStarted'] for r in ui))
        check('Exhaustive reveal without a draw never falsely loses the game',not e.state['gameOver'] and not e.state['fidelityGap'])
        return dict(id=case['id'],passed=True,checks=len(e.checks),evidence=str(e.ipc))
    except Exception as failure:return dict(id=case['id'],passed=False,error=str(failure)[:1000]+'\n'+str(failure)[-1000:],traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--case',choices=[c['id'] for c in CASES],action='append');a=p.parse_args();os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy))
    from native_engine_test_client import NativeEngine
    from runtime_paths import ROOT
    prep=json.loads((ROOT.parent/'preparation.json').read_text());source=ROOT.parent/'sources/ForgeBackend/ForgeLandEngine.java';assert sha(source)==prep['sourceSha256']
    a.output.mkdir(parents=True,exist_ok=False);hashes={str(f):sha(f) for f in a.worker.parent.glob('*.dll')};hashes[str(a.managed/'Core.dll')]=sha(a.managed/'Core.dll');rows=[]
    factory=lambda scenario,**settings:NativeEngine(scenario,worker=a.worker,managed=a.managed,fixture=a.fixture,**settings)
    full_human_choices=json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text()).get('fullHumanChoices') is True
    for case in CASES:
        if a.case and case['id'] not in a.case:continue
        row=run_case(case,factory,full_human_choices);rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='traceback'}),flush=True)
    if any(sha(Path(path))!=digest for path,digest in hashes.items()) or sha(source)!=prep['sourceSha256']:raise RuntimeError('Pinned test bytes changed during run')
    result=dict(passed=all(r['passed'] for r in rows),cases=rows,sourceSha256=prep['sourceSha256'],nativeBinaries=hashes,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__,renderedAcceptance=False,optionLanguage='Source-checked English; localized option labels are not yet mapped')
    (a.output/'report.json').write_text(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
