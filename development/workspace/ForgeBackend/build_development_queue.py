"""Prioritize shared bridge gaps by observed catalogue impact, never admission."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from runtime_paths import ROOT, SUPPORT_POLICY


def build():
    folder=ROOT/'research/card-coverage'
    path=folder/'card-compatibility.json'
    data=json.loads(path.read_text(encoding='utf8'))
    if data['summary']['provenance']['policySha256']!=hashlib.sha256(SUPPORT_POLICY.read_bytes()).hexdigest():
        raise ValueError('Audit no longer matches the selected admission policy.')
    pending=[c for c in data['cards'] if not c['admitted']]
    groups=[]
    for code,issue in data['issues'].items():
        if not code.startswith('bridge.'):
            continue
        affected=[c for c in pending if code in c['blockers']]
        single=[c for c in affected if {b for b in c['blockers'] if not b.startswith('verification.')}=={code}]
        if affected:
            groups.append(dict(capability=code,description=issue['description'],affectedNames=len(affected),
                               onlyDetectedImplementationBlocker=len(single),
                               examples=[c['name'] for c in affected[:8]],
                               implementation=issue['implementation']))
    groups.sort(key=lambda row:(-row['onlyDetectedImplementationBlocker'],-row['affectedNames'],row['capability']))
    result=dict(schema=1,auditSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                provenance=data['summary']['provenance'],
                catalogue=dict(names=len(data['cards']),printings=data['summary']['arenaPrintings'],
                               mappingCounts=data['summary']['mappingCounts'],constructionCounts=data['summary']['constructionCounts']),
                capabilities=groups,
                noDetectedImplementationBlockers=[c['name'] for c in pending if all(b.startswith('verification.') for b in c['blockers'])],
                unmatchedNames=data['summary']['unmatchedNames'],
                effects=dict(Counter(api for c in pending for api in c['apis'])),
                scope='Conservative structural priorities, not a prediction of playable cards. Counts overlap; fixing one blocker does not prove rules correctness, assets or native UI.')
    (folder/'development-queue.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
    lines=['# Shared card-support implementation queue','',result['scope'],'',
           '| Shared capability | Names affected | Only detected implementation blocker |',
           '| --- | ---: | ---: |']
    lines += [f"| {r['capability']} | {r['affectedNames']} | {r['onlyDetectedImplementationBlocker']} |" for r in groups]
    lines += ['', 'Even cards with no detected implementation blocker still require rules, native presentation and sequence verification. No admission changed.','']
    (folder/'Development-Queue.md').write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps(dict(capabilities=len(groups),queue=str(folder/'development-queue.json'),top=groups[:5]),indent=2))
    return result


if __name__=='__main__':
    build()
