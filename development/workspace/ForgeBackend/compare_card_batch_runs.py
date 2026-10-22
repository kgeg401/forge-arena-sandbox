"""Compare full input/response state traces, not just assertion totals.

Session/request/decision UUIDs are renamed bijectively in encounter order.
No positions, life, cards, costs, event order, identifiers or outcomes are dropped.
This checks execution equivalence; Forge compared with Forge is not an
independent oracle for the correctness of Magic's rules.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_trace(path):
    records=[json.loads(line) for line in path.read_text(encoding='utf8').splitlines() if line]
    aliases={}
    def walk(value):
        if isinstance(value,dict):return {k:walk(v) for k,v in value.items()}
        if isinstance(value,list):return [walk(v) for v in value]
        if isinstance(value,str) and re.fullmatch(r'[a-f0-9]{32}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',value):
            if value not in aliases:aliases[value]='uuid-'+str(len(aliases)+1)
            return aliases[value]
        return value
    return walk(records)


def difference(left,right,path='$'):
    if type(left)!=type(right):return dict(path=path,left=left,right=right)
    if isinstance(left,dict):
        if left.keys()!=right.keys():return dict(path=path,leftKeys=sorted(left),rightKeys=sorted(right))
        for k in left:
            d=difference(left[k],right[k],path+'.'+k)
            if d:return d
    elif isinstance(left,list):
        if len(left)!=len(right):return dict(path=path,leftLength=len(left),rightLength=len(right))
        for i,(a,b) in enumerate(zip(left,right)):
            d=difference(a,b,path+'['+str(i)+']')
            if d:return d
    elif left!=right:return dict(path=path,left=left,right=right)
    return None


def compare(a):
    if a.output.exists():raise ValueError('Preserve earlier comparison evidence')
    left=json.loads(a.left.read_text(encoding='utf8'));right=json.loads(a.right.read_text(encoding='utf8'))
    if left['status']!='passed' or right['status']!='passed':raise ValueError('Both runs must finish and pass')
    lrows={r['id']:r for r in left['cases']};rrows={r['id']:r for r in right['cases']}
    superset=getattr(a,'allow_right_superset',False)
    if set(lrows)!=set(rrows) and not (superset and set(lrows)<=set(rrows)):raise ValueError('Compare identical case sets or explicitly allow a right-side superset')
    def definitions(report):
        suites=[]
        for path,digest in report['identities'].items():
            p=Path(path)
            if p.suffix!='.json':continue
            if not p.is_file() or sha(p)!=digest:
                if report.get('sourceArchive') and 'ForgeBackend' in p.parts:
                    saved=Path(report['sourceArchive'])/Path(*p.parts[p.parts.index('ForgeBackend'):])
                    if saved.is_file() and sha(saved)==digest:p=saved
                    else:raise ValueError('Pinned JSON input and its source snapshot changed: '+path)
                else:raise ValueError('Pinned JSON input changed after execution: '+path)
            value=json.loads(p.read_text(encoding='utf8'))
            if isinstance(value,dict) and isinstance(value.get('cards'),dict) and isinstance(value.get('cases'),list):
                if sha(p)!=digest:raise ValueError('Suite changed after execution: '+path)
                suites.append(value)
        if len(suites)!=1:raise ValueError('Expected one pinned suite definition')
        return {c['id']:c for c in suites[0]['cases']}
    ldefs=definitions(left);rdefs=definitions(right)
    common=set(left['identities'])&set(right['identities'])
    if any(left['identities'][p]!=right['identities'][p] for p in common):raise ValueError('Runs used different shared source or inputs')
    def dependency_roles(report):
        result={}
        for path,digest in report['identities'].items():
            name=Path(path).name
            if name.endswith('.class') or name in ('forge.jar','gson.jar','research-policy.json'):
                result.setdefault(name,set()).add(digest)
        return result
    ld=dependency_roles(left);rd=dependency_roles(right)
    if any(ld[name]!=rd[name] for name in ld.keys()&rd.keys()):raise ValueError('Copied runtime dependencies or compiled classes differ across roots')
    checks=[]
    for key in sorted(lrows):
        if ldefs[key]!=rdefs[key]:raise ValueError('Different authored case definitions: '+key)
        lp=Path(lrows[key]['evidence']);rp=Path(rrows[key]['evidence'])
        if json.loads((lp/'scenario.json').read_text())!=json.loads((rp/'scenario.json').read_text()):raise ValueError('Different fixture inputs: '+key)
        lc=json.loads((lp/'checks.json').read_text(encoding='utf8'));rc=json.loads((rp/'checks.json').read_text(encoding='utf8'))
        assert lc==rc and all(c['passed'] for c in lc)
        trace_left=canonical_trace(lp/'engine-journal.jsonl');trace_right=canonical_trace(rp/'engine-journal.jsonl')
        d=difference(trace_left,trace_right)
        checks.append(dict(case=key,passed=d is None,difference=d,traceRecords=len(trace_left),
            leftJournalSha256=sha(lp/'engine-journal.jsonl'),rightJournalSha256=sha(rp/'engine-journal.jsonl')))
    result=dict(schema=1,passed=all(c['passed'] for c in checks),cases=len(checks),traceRecords=sum(c['traceRecords'] for c in checks),
        leftReportSha256=sha(a.left),rightReportSha256=sha(a.right),checks=checks,
        normalization='Bijective UUID renaming only; every other field and sequence remains exact.',
        scope='Execution equivalence only. This does not independently validate Forge rules or admit a card.')
    a.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(report=str(a.output),passed=result['passed'],cases=result['cases'],traceRecords=result['traceRecords'])))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('left','right','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--allow-right-superset',action='store_true')
    raise SystemExit(compare(p.parse_args()))
