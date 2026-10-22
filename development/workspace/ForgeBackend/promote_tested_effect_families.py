"""Review source-exact effect batches for a separate, reversible local update."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
from build_card_evidence_ledger import load_run,load_matches,sha,read


def promote(a):
    if a.output.exists():raise ValueError('Choose a new review directory')
    base=read(a.base_policy);candidate=read(a.research_policy);config=read(a.families)
    if base.get('researchOnly') or not candidate.get('researchOnly'):raise ValueError('Expected production baseline and research candidate')
    accepted=[];evidence={};families=[]
    def record(path):
        path=Path(path);data=read(path);evidence[str(path.resolve())]=sha(path);return data
    for family in config['families']:
        proposals=record(family['proposals']);specs={p['name']:p for p in proposals['proposals']}
        if len(specs)!=len(proposals['proposals']) or proposals['newAdmissions']!=0 or not specs:raise ValueError('Empty, duplicate or already-admitting proposals')
        qualifier=Path(proposals['qualifierSource'])
        archives=[Path(p) for p in family.get('qualifierArchives',[])]
        qualified_source=next((p for p in [qualifier,*archives] if p.is_file() and sha(p)==proposals['qualifierSha256']),None)
        if qualified_source is None:raise ValueError('Qualification source unavailable')
        evidence[str(qualified_source.resolve())]=sha(qualified_source)
        run=load_run(Path(family['run']),[])
        if run['status']!='passed' or {r['card'] for r in run['cases']}!=set(specs):raise ValueError('Incomplete per-card rules batch')
        current=Path(__file__).with_name('ForgeLandEngine.java')
        raw_run=record(family['run'])
        if raw_run['identities'].get(str(current.resolve()))!=sha(current):raise ValueError('Rules batch uses a different rules source')
        evidence.update(run['artifacts'])
        comparison=record(family['coldComparison'])
        if comparison.get('passed') is not True or not comparison['cases'] or not all(c['passed'] for c in comparison['checks']):raise ValueError('Fresh/reused execution differs')
        cold=load_run(Path(family['cold']),[])
        if cold['status']!='passed' or comparison['leftReportSha256']!=sha(Path(family['cold'])) or comparison['rightReportSha256']!=sha(Path(family['run'])):raise ValueError('Fresh reference is not tied to these passing runs')
        evidence.update(cold['artifacts'])
        assets=record(family['assets'])
        if assets['passed']!=len(specs) or assets['cards']!=len(specs) or assets['failures'] or {c['name'] for c in assets['cardsChecked']}!=set(specs):raise ValueError('Native artwork/model evidence incomplete')
        if any(not c['passed'] or c['grpId']!=specs[c['name']]['printing'] for c in assets['cardsChecked']):raise ValueError('Native asset identity differs')
        native=record(family['native'])
        if native.get('status')!='passed':raise ValueError('Native family is not passed')
        for path,digest in native.get('identities',{}).items():
            if not Path(path).is_file() or sha(Path(path))!=digest:raise ValueError('Native input changed: '+path)
            evidence[str(Path(path).resolve())]=digest
        controls=[]
        if 'proof' in native:control_reports=[dict(report=native['proof'])]
        else:control_reports=native.get('batches',native.get('cases',[]))
        for row in control_reports:
            proof=record(row['report'])
            if proof.get('passed') is not True or not proof['results'] or len(proof['results'])!=proof['checks'] or not all(c['passed'] for c in proof['results']):raise ValueError('Native callback check failed')
            for name in ('state.json','engine-journal.jsonl','native-wire.jsonl'):
                artifact=Path(row['report']).parent/name
                if not artifact.is_file():raise ValueError('Missing underlying native observation: '+str(artifact))
                evidence[str(artifact.resolve())]=sha(artifact)
            controls.extend(proof['cards'])
        if len(controls)!=len(set(controls)) or set(controls)!=set(specs):raise ValueError('Every added card needs an original native control sequence')
        matches=load_matches(Path(family['matches']));evidence.update(matches['artifacts'])
        representatives=set(read(Path(family['matches']))['requiredCards'])
        if not representatives<=set(specs) or not representatives:raise ValueError('Unrelated full-game representatives')
        for name,p in specs.items():
            if name in base['verifiedNames'] or name in accepted:raise ValueError('Duplicate or already supported name')
            if p['printing']!=candidate['preferredPrintings'].get(name):raise ValueError('Candidate printing differs')
            if p['template']!=family['template']:raise ValueError('Wrong capability family')
            accepted.append(name)
        families.append(dict(id=family['template']+'-delivery-20261022',names=sorted(specs),
            rules='Exact native words, costs and pinned Forge definitions; each card has passing authored rules branches',
            decisions='Every added card: original native cast and resolution; relevant target, Cancel, Submit and expiration controls',
            assets='Every pinned printing: original model and exact effective source artwork',
            sequences='Complete input-only shuffled games with successful resolutions for both seats: '+', '.join(sorted(representatives)),
            scope='Bounded supported mechanics; not every Magic interaction, other printings, retail legality or animation parity'))
    if set(candidate['verifiedNames'])!=set(base['verifiedNames'])|set(accepted):raise ValueError('Candidate contains unreviewed cards')
    result=deepcopy(base)
    for name in accepted:
        result['verifiedNames'].append(name)
        for key in ('preferredPrintings','colorIdentities','targetPromptBindings'):
            if name in candidate.get(key,{}):result.setdefault(key,{})[name]=candidate[key][name]
    result['candidateNames']=[n for n in result['candidateNames'] if n not in result['verifiedNames']]
    result.setdefault('verificationFamilies',[]).extend(families)
    a.output.mkdir(parents=True);policy=a.output/'verified-policy.json';policy.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    receipt=dict(schema=1,utc=datetime.now(timezone.utc).isoformat(),previous=len(base['verifiedNames']),added=len(accepted),verified=len(result['verifiedNames']),names=accepted,
        rulesSourceSha256=sha(Path(__file__).with_name('ForgeLandEngine.java')),basePolicySha256=sha(a.base_policy),policySha256=sha(policy),evidence=evidence,
        status='review-passed-awaiting-production-regression-and-install',scope='Shared mechanic representatives supplement per-card source/rules/native evidence; no exhaustive support claim',published=False)
    (a.output/'review.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf8');print(json.dumps({k:v for k,v in receipt.items() if k not in ('evidence','names')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('base-policy','research-policy','families','output'):p.add_argument('--'+key,type=Path,required=True)
    promote(p.parse_args())
