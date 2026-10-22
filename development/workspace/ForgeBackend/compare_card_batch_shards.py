"""Prove a sealed partitioned run equals the full serial input/state journals."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from compare_card_batch_runs import compare,sha


def run(a):
    if a.output.exists():raise ValueError('Preserve previous comparison evidence')
    shards=json.loads(a.shards.read_text());serial=json.loads(a.serial.read_text())
    if shards['status']!='passed' or serial['status']!='passed':raise ValueError('Both execution modes must finish and pass')
    expected={r['id'] for r in serial['cases']};actual=[];rows=[]
    for row in shards['shards']:
        report=Path(row['report'])
        if sha(report)!=row['reportSha256']:raise ValueError('A child result changed after sealing')
        child=json.loads(report.read_text());actual.extend(r['id'] for r in child['cases'])
    if len(actual)!=len(set(actual)) or set(actual)!=expected:raise ValueError('Shards have missing, duplicate or unexpected serial cases')
    a.output.mkdir(parents=True)
    for row in shards['shards']:
        output=a.output/('shard-'+str(row['index'])+'.json')
        code=compare(SimpleNamespace(left=Path(row['report']),right=a.serial,allow_right_superset=True,output=output))
        proof=json.loads(output.read_text());rows.append(dict(index=row['index'],passed=code==0,cases=proof['cases'],traceRecords=proof['traceRecords'],report=str(output),sha256=sha(output)))
    result=dict(passed=all(r['passed'] for r in rows),cases=len(actual),traceRecords=sum(r['traceRecords'] for r in rows),comparisons=rows,
        serialReportSha256=sha(a.serial),partitionReportSha256=sha(a.shards),newAdmissions=0,
        normalization='Bijective random UUID renaming only. All other state, IDs, inputs, event order and assertion results remain exact.',
        scope='Execution and partition equivalence for the declared scenarios; not an independent rules oracle or all-card support.')
    (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in result.items() if k!='comparisons'}))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('shards','serial','output'):p.add_argument('--'+key,type=Path,required=True)
    raise SystemExit(run(p.parse_args()))
