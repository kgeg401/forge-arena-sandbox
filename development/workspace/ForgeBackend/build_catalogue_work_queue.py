"""Group remaining catalogue work by joint capability gaps, never grant admission.

A card can need several adapters. Overlapping blocker totals are not numbers
of cards that become playable after implementing any one adapter.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(a):
    if a.output.exists():
        raise ValueError('Select a new work-queue folder')
    audit = json.loads(a.audit.read_text(encoding='utf8'))
    policy = json.loads(a.policy.read_text(encoding='utf-8-sig'))
    if policy.get('researchOnly') or audit['summary']['provenance']['policySha256'] != sha(a.policy):
        raise ValueError('Use an audit pinned to an independently verified policy')
    names = set(policy['verifiedNames'])
    cards = audit['cards']
    assert len({c['name'] for c in cards}) == len(cards) == audit['summary']['arenaNames']
    assert {c['name'] for c in cards if c['admitted']} == names
    grouped = defaultdict(list)
    counts = Counter()
    ready_for_review = []
    missing_rules = []
    for card in cards:
        if card['admitted']:
            continue
        assert {'verification.rules_text', 'verification.native_assets', 'verification.sequence'} <= set(card['blockers'])
        gaps = tuple(sorted(b for b in card['blockers'] if not b.startswith('verification.')))
        grouped[gaps].append(card['name'])
        counts.update(gaps)
        if not gaps:
            ready_for_review.append(dict(name=card['name'], apis=card['apis'], scripts=card['forgeScripts'],
                sourceScriptSha256=card['sourceForgeScriptSha256'], requiredGates=['rules equivalence', 'costs and timing', 'conditional branches', 'original native assets and controls', 'full shuffled sequences']))
        if any(b.startswith('mapping.') for b in gaps):
            missing_rules.append(card['name'])
    groups = [dict(blockers=list(gaps), cards=len(group), names=sorted(group, key=str.casefold)) for gaps, group in grouped.items()]
    groups.sort(key=lambda g: (len(g['blockers']), -g['cards'], g['blockers']))
    assert sum(g['cards'] for g in groups) == len(cards)-len(names)
    result = dict(schema=1, utc=datetime.now(timezone.utc).isoformat(), catalogue=len(cards), admitted=len(names), remaining=len(cards)-len(names),
        existingEffectCandidates=ready_for_review, overlappingBlockerCounts=dict(counts.most_common()),
        soleImplementationBlockerCounts={g['blockers'][0]:g['cards'] for g in groups if len(g['blockers']) == 1},
        jointCapabilityGroups=groups, mappingReviewNames=missing_rules,
        provenance=dict(auditSha256=sha(a.audit), policySha256=sha(a.policy), engineAudit=audit['summary']['provenance']),
        scope='Conservative structural planning only. No card is admitted, executed, downloaded or declared playable by this report; all verification gates remain required.')
    a.output.mkdir(parents=True)
    (a.output/'work-queue.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf8')
    lines = ['# Catalogue implementation work queue', '',
        f"{result['catalogue']:,} source-indexed names; {result['admitted']:,} bounded verified main-deck names; {result['remaining']:,} remaining.", '',
        'This report groups work; it does not grant support. Blocker totals overlap.', '',
        '## Existing-effect candidates needing full verification', '',
        'No additional implementation blocker was detected for these cards. This is a conservative source scan, not proof that every dynamic choice or conditional branch is already handled.', '']
    lines += ['- '+c['name']+' — '+', '.join(c['apis']) for c in ready_for_review]
    lines += ['', '## Smallest joint capability sets', '', '| Missing implementation capabilities | Names requiring this exact set |', '| --- | ---: |']
    lines += ['| '+(', '.join(g['blockers']) or 'No static implementation blocker detected')+' | '+str(g['cards'])+' |' for g in groups[:20]]
    lines += ['', 'Source equivalence, native interaction and complete-sequence gates remain necessary after adapters exist. Conditional effects need both branches. Missing-script and constructor failures remain separate from interface work.', '',
        '## Mapping review', '']
    lines += ['- '+name for name in missing_rules]
    (a.output/'WORK-QUEUE.md').write_text('\n'.join(lines)+'\n', encoding='utf8')
    print(json.dumps(dict(catalogue=result['catalogue'], admitted=result['admitted'], remaining=result['remaining'],
        existingEffectCandidates=len(ready_for_review), jointGroups=len(groups), report=str(a.output/'WORK-QUEUE.md'))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--policy', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    build(p.parse_args())
