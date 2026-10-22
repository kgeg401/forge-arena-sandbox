"""Compact support diagnostics for decks; contains no rules text or game assets."""
import hashlib
import json
from pathlib import Path
from build_card_coverage import ROOT, POLICY
from card_support import FRIENDLY_ISSUES


def build():
    folder = ROOT/'research/card-coverage'
    audit = folder/'card-compatibility.json'
    data = json.loads(audit.read_text(encoding='utf8'))
    receipt=json.loads((folder/'construction-receipt.json').read_text())
    if data['summary']['provenance']['policySha256'] != hashlib.sha256(POLICY.read_bytes()).hexdigest():
        raise ValueError('Audit policy changed; regenerate the audit first.')
    result = dict(schema=1, provenance={**data['summary']['provenance'], 'forgeJarSha256':receipt['installedForgeJarSha256'], 'auditSha256': hashlib.sha256(audit.read_bytes()).hexdigest()},
                  issues={k: FRIENDLY_ISSUES[k] for k in data['issues']},
                  cards=[{k: c[k] for k in ('name', 'arenaGrpIds', 'status', 'construction', 'blockers')} for c in data['cards']],
                  scope='Diagnostics only; explicit bridge policy remains the sole admission authority.')
    target = ROOT/'native-lab/card-support-index.json'
    pending = target.with_suffix('.pending')
    pending.write_text(json.dumps(result, ensure_ascii=False), encoding='utf8')
    pending.replace(target)
    print(json.dumps(dict(cards=len(result['cards']), index=str(target), bytes=target.stat().st_size)))
    return result


if __name__ == '__main__':
    build()
