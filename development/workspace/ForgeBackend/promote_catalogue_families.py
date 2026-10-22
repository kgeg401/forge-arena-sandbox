"""Review sealed, source-qualified families and emit a separate playable policy.

Admission requires per-card rules cases, native identity/assets and native casts.
Complete-match and shared choice controls may be evidenced by a representative
with the same mechanic. This is bounded support, not all-interaction parity.
No client mutation or publication is performed here.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def review(a):
    if a.output.exists():
        raise ValueError('Preserve prior reviews; choose a new output directory')
    a.output.mkdir(parents=True)
    ledger = load(a.evidence/'ledger-final/card-evidence-ledger.json')
    seal = load(a.evidence/'checkpoint-seal.json')
    if seal['status'] != 'passed' or seal['ledgerSha256'] != sha(a.evidence/'ledger-final/card-evidence-ledger.json'):
        raise ValueError('Unsealed source ledger')
    # Reuse evidence only when both it and the actual implementation are intact.
    for name in ('ForgeBackend/ForgeLandEngine.java', 'NativeHost/ForgeLandBridge.cs', 'NativeHost/Plugin.cs'):
        if sha(Path(__file__).resolve().parents[1]/name) != seal['sourceHashes'][name]:
            raise ValueError('Implementation changed since sealed evidence: '+name)
    artifacts = ledger['artifacts']
    failed = [path for path, digest in artifacts.items() if not Path(path).is_file() or sha(path) != digest]
    if failed:
        raise ValueError('Evidence drift: '+repr(failed[:5]))
    base = load(a.base_policy)
    qualified = load(a.research_policy)
    if base.get('researchOnly') or not qualified.get('researchOnly'):
        raise ValueError('Expected production baseline and qualified research policy')
    initial = set(base['verifiedNames'])
    rows = {c['name']:c for c in ledger['cards']}
    accepted, rejected = [], []
    groups = {
        'simple-creature-cast-v1': ['Colossal Dreadmaw', 'Fleetfoot Dancer', 'Swiftblade Vindicator', 'Shorecomber Crab'],
        'fixed-untargeted-draw-life-v1': ['Revitalize', 'Ritual of Rejuvenation'],
        'fixed-target-pump-v1': ['Giant Growth', 'Infuriate'],
    }
    for template, reps in groups.items():
        for name in reps:
            if not rows[name]['completeMatches']:
                raise ValueError('Missing representative complete match: '+name)
    for card in ledger['cards']:
        name = card['name']
        if name in initial or name not in qualified['verifiedNames']:
            continue
        proposal = card.get('sourceQualifiedProposal')
        template = proposal['template'] if proposal else None
        missing = []
        if template not in groups:
            missing.append('No reviewed exact-source family or complete conditional branch suite')
        else:
            branches = set(card['passingDeclaredBranches'])
            if not card['nativeAssets']: missing.append('Original selected-printing artwork/model check')
            if not card['nativeControls']: missing.append('Original cast/resolve control check')
            if not card['engineCases'] or any(c['status'] != 'passed' for c in card['engineCases']):
                missing.append('Passing per-card gameplay cases')
            required = ({'cancel','combat-timing','friendly-expiration','enemy-expiration','hexproof-owner','invalidated-target','underfunded','wrong-color'}
                        if template == 'fixed-target-pump-v1' else
                        {'main-cast-stats','cast-arrival-attack-timing','ready-unblocked-attack','block-vanilla-four-four'}
                        if template == 'simple-creature-cast-v1' else {'main-resolution-amounts','combat-cast'})
            if not required <= branches: missing.append('Branches: '+', '.join(sorted(required-branches)))
            if template == 'simple-creature-cast-v1' and name != 'Shorecomber Crab':
                trample = {'trample-single-max','trample-single-overkill','trample-multiple-max'}
                if not trample <= branches: missing.append('Per-card trample allocation branches')
            if qualified['preferredPrintings'].get(name) != proposal['printing']:
                missing.append('Qualified printing differs')
        row = dict(name=name, template=template, missing=missing,
                   branches=card['passingDeclaredBranches'], cases=len(card['engineCases']),
                   assertions=sum(c['assertions'] for c in card['engineCases']),
                   printing=proposal['printing'] if proposal else None,
                   completeMatchScope='Per-card observation' if card['completeMatches'] else 'Shared source-exact mechanic representatives',
                   representatives=groups.get(template, []))
        (rejected if missing else accepted).append(row)
    if not accepted:
        raise ValueError('No qualifying cards; baseline preserved')
    policy = deepcopy(base)
    for row in accepted:
        name = row['name']
        policy['verifiedNames'].append(name)
        for key in ('preferredPrintings','colorIdentities'):
            policy.setdefault(key,{})[name] = qualified[key][name]
    policy['candidateNames'] = [n for n in policy['candidateNames'] if n not in policy['verifiedNames']]
    for template, reps in groups.items():
        names = sorted(r['name'] for r in accepted if r['template'] == template)
        if names:
            policy.setdefault('verificationFamilies',[]).append(dict(
                id=template+'-delivery-20261022', names=names,
                rules='Exact native words/costs/stats matched to plain Forge scripts; each card has source-authored gameplay branches',
                decisions='Original native cast/resolve for every card; shared trample allocation or per-pump target/cancel/submit/expiration as applicable',
                assets='Each pinned printing: original model and exact effective artwork',
                sequences='Complete shuffled matches with mechanic representatives: '+', '.join(reps),
                scope='Bounded supported family; not arbitrary interactions, other printings, retail legality or animation parity'))
    out = a.output/'verified-policy.json'
    out.write_text(json.dumps(policy,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    receipt = dict(schema=1,utc=datetime.now(timezone.utc).isoformat(),previous=len(initial),added=len(accepted),
                   verified=len(policy['verifiedNames']),accepted=accepted,rejected=rejected,
                   ledgerSha256=sha(a.evidence/'ledger-final/card-evidence-ledger.json'),
                   checkedArtifacts=len(artifacts),baselinePolicySha256=sha(a.base_policy),
                   researchPolicySha256=sha(a.research_policy),policySha256=sha(out),
                   status='review-passed-awaiting-production-regression-and-install',published=False)
    (a.output/'review.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('accepted','rejected')},indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('evidence','base-policy','research-policy','output'):
        p.add_argument('--'+name,type=Path,required=True)
    review(p.parse_args())
