"""Consolidate explicit failed-case reruns; preserve every original report.

Only failed cases may be replaced. Source, native binaries and authored input
definitions must match. This tool neither edits evidence nor admits cards.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--correction',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Use a fresh consolidated report path')
    base=read(a.base);rows={r['id']:r for r in base['cases']};definitions={r['id']:r for r in base['inputs']}
    if len(rows)!=len(base['cases']) or len(definitions)!=len(base['inputs']) or set(rows)!=set(definitions):raise ValueError('Base cases and input identities must match exactly')
    provenance=[dict(role='base',path=str(a.base.resolve()),sha256=sha(a.base))];replacements=[]
    for path in a.correction:
        correction=read(path)
        if not correction['passed'] or not correction['cases']:raise ValueError('Correction must have executed successful cases')
        for key in ('sourceSha256','nativeBinarySha256','persistentNativeSession','nativeResponseRoundTrip'):
            if correction.get(key)!=base.get(key):raise ValueError('Correction changed pinned engine/native semantics: '+key)
        inputs={r['id']:r for r in correction['inputs']}
        for row in correction['cases']:
            key=row['id']
            if key not in rows or rows[key]['passed'] or not row['passed'] or definitions[key]!=inputs.get(key):raise ValueError('Only an unchanged authored failed case can be corrected: '+key)
            checks=read(Path(row['evidence'])/'checks.json')
            if not checks or len(checks)!=row['checks'] or not all(c['passed'] for c in checks):raise ValueError('Correction lacks its actual successful assertions')
            replacements.append(dict(id=key,failedEvidence=rows[key].get('evidence'),correctedEvidence=row['evidence'],report=str(path.resolve())))
            rows[key]=row
        provenance.append(dict(role='correction',path=str(path.resolve()),sha256=sha(path)))
    result=dict(base);result.update(passed=all(r['passed'] for r in rows.values()),cases=[rows[r['id']] for r in base['cases']],consolidated=True,provenance=provenance,replacements=replacements,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(dict(passed=result['passed'],cases=len(rows),corrections=len(replacements),report=str(a.output))));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
