"""Seal the bounded deathtouch checkpoint only after independent evidence gates.

Reads private evidence, writes a NEW verified policy and a hash-linked receipt.
Never edits the working admission policy, deploys a client or publishes a build.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder', type=Path, required=True)
    p.add_argument('--base-policy', type=Path, required=True)
    p.add_argument('--regression-report', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    receipt_path = a.output.parent/'promotion-278.json'
    if a.output.exists() or receipt_path.exists():
        raise ValueError('Select a new checkpoint policy; prior evidence is immutable')
    evidence = []

    def read(path):
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        evidence.append(dict(path=str(path.resolve()), sha256=sha(path)))
        return data

    def checks(path):
        rows = read(path)
        assert rows and all(v['passed'] for v in rows), ('Failed or empty checks', path)
        return len(rows)

    root = a.folder
    base = read(a.base_policy)
    research = read(root/'deathtouch-source/research-policy.json')
    definitions = read(root/'deathtouch-source/keyword-candidates.json')
    names = set(definitions)
    assert len(base['verifiedNames']) == 252 and not base.get('researchOnly')
    assert research.get('researchOnly') and names and all('Deathtouch' in d['keywords'] for d in definitions.values())
    assert set(research['verifiedNames']) == set(base['verifiedNames']) | names
    assert not names & set(base['verifiedNames']) and len(research['verifiedNames']) == len(set(research['verifiedNames']))
    for key, value in base.items():
        if key not in ('verifiedNames', 'preferredPrintings', 'colorIdentities'):
            assert research[key] == value, ('Unrelated policy change', key)
    for key in ('preferredPrintings', 'colorIdentities'):
        assert all(research[key][k] == v for k, v in base[key].items()), ('Changed existing mappings', key)
        assert set(research[key])-set(base[key]) <= names
    assert all(research['preferredPrintings'][n] == d['grpId'] for n, d in definitions.items())
    comparison = read(root/'script-distribution-comparison.json')
    assert comparison['stableLegacyScriptsIdentical'] and comparison['names'] == len(names)
    total_checks = 0
    for variant, runtime in [('stable', root/'runtime'), ('legacy', root/'legacy-runtime')]:
        casts = read(root/(variant+'-cast-report.json'))
        assert casts['cards'] == len(names) and {n for r in casts['reports'] for n in r['names']} == names
        assert sum(len(r['names']) for r in casts['reports']) == len(names)
        for case in casts['reports']:
            count = checks(Path(case['evidence'])/'checks.json')
            assert count == case['checks'] == len(case['names'])*8
            total_checks += count
        combat = read(root/('combat-report.json' if variant == 'stable' else 'legacy-combat-report.json'))
        assert combat['cards'] == len(names) and {r['name'] for r in combat['cases']} == names
        assert combat['engineClassSha256'] == sha(runtime/'build/ForgeBackend/classes/ForgeLandEngine.class')
        assert combat['manifestSha256'] == sha(runtime/'native-lab/bridge-card-manifest.json')
        for case in combat['cases']:
            count = checks(Path(case['evidence'])/'checks.json')
            assert count == case['checks'] and count >= 11
            total_checks += count
        interactions = read(root/(variant+'-interaction-report.json'))
        assert {r['case'] for r in interactions['cases']} == {
            'Ambush Viper flash timing', 'Nightveil Predator hexproof ownership',
            'First strike prevents deathtouch retaliation',
            'Deathtouch blocker kills high-toughness attacker', 'Reach and deathtouch intercept a flyer'}
        for case in interactions['cases']:
            count = checks(Path(case['evidence'])/'checks.json')
            assert count == case['checks']
            total_checks += count
    assets = read(root/'native-assets/report.json')
    assert assets['cards'] == assets['passed'] == len(names) and not assets['failures']
    assert {r['name'] for r in assets['cardsChecked']} == names
    assert all(r['passed'] and r['grpId'] == definitions[r['name']]['grpId'] for r in assets['cardsChecked'])
    native_reports = [read(root/'native-casts/report.json')]
    native_reports += read(root/'native-batches-report.json')['reports']
    assert {n for r in native_reports for n in r['cards']} == names
    assert sum(len(r['cards']) for r in native_reports) == len(names)
    for report in native_reports:
        assert report['checks'] == len(report['results']) == len(report['cards'])*5
        assert all(v['passed'] for v in report['results'])
        total_checks += report['checks']
    damage = read(root/'native-damage/report.json')
    assert all(v['passed'] for v in damage['results']) and damage['checks'] >= 12
    wire = read(root/'native-damage/state.json')
    assert wire['phase'] == 'MAIN2' and wire['life'] == 22 and wire['opponentLife'] == 20 and not wire['fidelityGap']
    total_checks += damage['checks']
    matches = read(root/'normal-matches.json')
    assert len(matches) >= 2 and {v['deathtouchSeat'] for v in matches} == {1, 2}
    for match in matches:
        ipc = Path(match['evidence'])
        s = read(ipc/'state.json')
        assert s['gameOver'] and not s['fidelityGap'] and s['scenario'] == 'custom-duel'
        total_checks += checks(ipc/'checks.json')
    audit = read(root/'runtime/research/card-manifest-audit.json')
    assert audit['passed'] and audit['ordinaryAdmittedCards'] == len(research['verifiedNames'])
    regression = read(a.regression_report)
    assert regression['status'] == 'passed' and len(regression['stages']) == 25 and all(s['status'] == 'passed' for s in regression['stages'])
    assert regression['policySha256'] == sha(a.base_policy)
    source = Path(__file__).with_name('ForgeLandEngine.java')
    assert regression['sourceHashes']['ForgeBackend/ForgeLandEngine.java'] == sha(source)
    research.pop('researchOnly')
    research.setdefault('verificationFamilies', []).append(dict(
        names=list(definitions), rules='source-exact deathtouch keyword-only creatures; each casts, pays and resolves in both supported Forge distributions',
        decisions='all candidates: actual multi-block damage; zero vs positive deathtouch; flash, hexproof, first strike and reach interactions',
        assets='all pinned printings: original native models, exact effective artwork and original card/Resolve callbacks',
        sequences='two complete shuffled AI games with each controller playing the family; original damage browser Done, combat deaths and lifelink; bounded support only'))
    a.output.write_bytes((json.dumps(research, indent=2)+'\n').encode('utf8'))
    receipt = dict(utc=datetime.now(timezone.utc).isoformat(), previous=len(base['verifiedNames']), added=len(names), verified=len(research['verifiedNames']),
                   familyAssertions=total_checks, regressionAssertions=regression['recordedEngineAssertions'],
                   policy=str(a.output.resolve()), policySha256=sha(a.output), evidence=evidence,
                   scope='Bounded audited development checkpoint only; no GitHub publication, installed update, exhaustive interactions or full catalogue support.')
    receipt_path.write_bytes((json.dumps(receipt, indent=2)+'\n').encode('utf8'))
    print(json.dumps({k:v for k,v in receipt.items() if k != 'evidence'}, indent=2))


if __name__ == '__main__':
    main()
