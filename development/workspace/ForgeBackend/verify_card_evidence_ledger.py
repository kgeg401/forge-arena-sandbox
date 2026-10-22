"""Mutate a real executed case to check evidence admission boundaries."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
from build_card_evidence_ledger import load_run,sha


def run(a):
    original=json.loads(a.report.read_text(encoding='utf8'))
    suite_path=next(Path(p) for p in original['identities'] if Path(p).suffix=='.json' and isinstance((value:=json.loads(Path(p).read_text(encoding='utf-8-sig'))),dict) and isinstance(value.get('cards'),dict) and isinstance(value.get('cases'),list))
    suite=json.loads(suite_path.read_text(encoding='utf8'));case=next(c for c in suite['cases'] if c['id']==original['cases'][0]['id']);row=original['cases'][0]
    checks=[];a.output.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='evidence-guards-',dir=a.output) as temporary:
        root=Path(temporary);evidence=root/'case';evidence.mkdir()
        source=Path(row['evidence'])
        pristine={n:(source/n).read_bytes() for n in ('checks.json','scenario.json','engine-journal.jsonl')}
        suite_file=root/'suite.json';report_file=root/'report.json'
        small_suite=dict(schema=suite['schema'],cards={case['card']:suite['cards'][case['card']]},cases=[case])
        small=deepcopy(original);small['cases']=[deepcopy(row)];small['cases'][0]['evidence']=str(evidence)
        small['identities'].pop(str(suite_path))
        small['summary'].update(totalCases=1,completed=1,notRun=0,assertions=row['checks'])
        def restore():
            for n,data in pristine.items():(evidence/n).write_bytes(data)
            suite_file.write_text(json.dumps(small_suite),encoding='utf8')
            data=deepcopy(small);data['identities'][str(suite_file)]=sha(suite_file)
            return data
        def evaluate(label,mutator=None,valid=False):
            data=restore()
            if mutator:mutator(data)
            report_file.write_text(json.dumps(data),encoding='utf8')
            rejected=False
            try:load_run(report_file,a.source_archive)
            except (ValueError,FileNotFoundError,KeyError):rejected=True
            if rejected==valid:raise AssertionError(label)
            checks.append(dict(check=label,passed=True))
        evaluate('An intact real case is accepted as narrow evidence',valid=True)
        evaluate('A research run cannot claim admissions',lambda r:r.update(admittedCards=1))
        evaluate('A duplicate case cannot inflate totals',lambda r:r['cases'].append(deepcopy(r['cases'][0])))
        evaluate('A wrong card label cannot transfer coverage',lambda r:r['cases'][0].update(card='Another card'))
        evaluate('Miscounted completed totals are rejected',lambda r:r['summary'].update(completed=2))
        evaluate('Miscounted assertion totals are rejected',lambda r:r['summary'].update(assertions=9999))
        evaluate('A running report cannot be reported complete',lambda r:r.update(status='running'))
        evaluate('Missing engine build provenance is rejected',lambda r:r['identities'].pop(next(p for p in r['identities'] if Path(p).name=='ForgeLandEngine.class')))
        def alter_checks(r):
            p=evidence/'checks.json';v=json.loads(p.read_text());v[0]['passed']=False;p.write_text(json.dumps(v))
        evaluate('A failed underlying assertion overrides a passing envelope',alter_checks)
        evaluate('A count differing from actual checks is rejected',lambda r:r['cases'][0].update(checks=1))
        evaluate('An empty journal is not executed gameplay',lambda r:(evidence/'engine-journal.jsonl').write_text(''))
        def final_state(key,value):
            def change(r):
                p=evidence/'engine-journal.jsonl';v=[json.loads(l) for l in p.read_text().splitlines()];final=next(v for v in reversed(v) if 'request' in v and 'response' in v)['response']['state']
                if key=='strict':final['researchControls']['strictHumanCallbacks']=value
                else:final[key]=value
                p.write_text('\n'.join(json.dumps(r) for r in v)+'\n')
            return change
        evaluate('A reported fidelity gap cannot become passing evidence',final_state('fidelityGap','unmapped test choice'))
        evaluate('An unguarded AI controller cannot count as human-choice proof',final_state('strict',False))
        def alter_fixture(r):
            p=evidence/'scenario.json';v=json.loads(p.read_text());v['randomSeed']+=1;p.write_text(json.dumps(v))
        evaluate('Different initial conditions are rejected',alter_fixture)
        def alter_source(r):
            key=next(p for p in r['identities'] if Path(p).name=='forge.jar');r['identities'][key]='0'*64
        evaluate('A changed rules dependency is rejected',alter_source)
    (a.output/'report.json').write_text(json.dumps(dict(checks=len(checks),results=checks,scope='Evidence mutation boundaries on a real executed case; no card admission.'),indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('report','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--source-archive',type=Path,action='append',default=[])
    run(p.parse_args())
