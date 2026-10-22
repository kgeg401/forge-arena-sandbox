"""Regression boundaries for Arena identities, complete deck reports and admission."""
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from arena_catalog import clean_name, indexed_printings
from card_support import explain, inspect_deck, load_index
from deck_import import parse_deck

checks = []


def check(label, condition):
    assert condition, label
    checks.append(label)


check('Ordinary rich text preserves names', clean_name('Fable of the <nobr>Mirror-Breaker</nobr>') == 'Fable of the Mirror-Breaker')
check('Rebalanced sprite is an identity prefix', clean_name('<sprite="SpriteSheet_MiscIcons" name="arena_a">The One Ring') == 'A-The One Ring')
check('Entities retain exact card punctuation', clean_name('Urza&#39;s Saga') == "Urza's Saga")
base = dict(IsPrimaryCard=0, IsToken=0, IsRebalanced=0, DefunctRebalancedCardGrpId=0)
rows = {1:dict(base, GrpId=1, IsPrimaryCard=1), 2:dict(base, GrpId=2),
        3:dict(base, GrpId=3, IsRebalanced=1, DefunctRebalancedCardGrpId=1),
        4:dict(base, GrpId=4, IsRebalanced=1, DefunctRebalancedCardGrpId=2),
        5:dict(base, GrpId=5, IsPrimaryCard=1, IsToken=1),
        6:dict(base, GrpId=6, IsRebalanced=1, DefunctRebalancedCardGrpId=999)}
check('Back faces, tokens and orphaned rebalances cannot become deck entries', [r['GrpId'] for r in indexed_printings(rows)] == [1, 3])

with tempfile.TemporaryDirectory(prefix='arena-support-check-') as temp:
    policy = Path(temp)/'policy.json'
    scripts=Path(temp)/'scripts.zip';scripts.write_bytes(b'script identity fixture')
    jar=Path(temp)/'forge.jar';jar.write_bytes(b'engine identity fixture')
    policy.write_text(json.dumps(dict(verifiedNames=['Plains'], brawlCommanders={'Isamaru, Hound of Konda':{}})))
    index = dict(schema=1, provenance=dict(policySha256=hashlib.sha256(policy.read_bytes()).hexdigest(),sourceForgeScriptsSha256=hashlib.sha256(scripts.read_bytes()).hexdigest(),forgeJarSha256=hashlib.sha256(jar.read_bytes()).hexdigest()), issues={'bridge.choices':'Human choice adapter missing.'}, cards=[
        dict(name='The One Ring',status='blocked',construction='constructed-not-playtested',blockers=['bridge.choices'],arenaGrpIds=[1]),
        dict(name='A-The One Ring',status='blocked',construction='constructed-not-playtested',blockers=['bridge.choices'],arenaGrpIds=[2]),
        dict(name='Isamaru, Hound of Konda',status='blocked',construction='constructed-not-playtested',blockers=['bridge.choices'],arenaGrpIds=[3]),
        dict(name='Appeal /// Authority',status='blocked',construction='constructed-not-playtested',blockers=['bridge.choices'],arenaGrpIds=[4])])
    paper = explain('The One Ring', index, policy)
    digital = explain('A-The One Ring', index, policy)
    check('Paper and rebalanced cards never share a rules identity', paper['arenaGrpIds'] != digital['arenaGrpIds'])
    check('Construction never implies admission', not paper['matchAdmitted'])
    index['cards'][0]['status']='verified-bounded-slice'
    check('Forged report status cannot grant admission', not explain('The One Ring', index, policy)['matchAdmitted'])
    check('Forged report status cannot display verified support', explain('The One Ring', index, policy)['status']!='verified-bounded-slice')
    check('Explicit policy retains bounded admission', explain('Plains', index, policy)['matchAdmitted'])
    check('Commander-only cards stay blocked in the main deck', not explain('Isamaru, Hound of Konda', index, policy)['matchAdmitted'])
    check('Verified commander is allowed in commander context', explain('Isamaru, Hound of Konda', index, policy, 'Commander')['matchAdmitted'])
    check('Aftermath notation maps diagnostics without changing admission', explain('Appeal // Authority', index, policy)['name']=='Appeal /// Authority')
    report = inspect_deck('Deck\n20 Plains (M21) 262\n1 The One Ring\n1 A-The One Ring\n1 Unknown Card\nSideboard\n1 Unknown Card\n', index, policy)
    check('All unsupported names are reported together', set(report['unsupportedNames'])=={'The One Ring','A-The One Ring','Unknown Card'})
    check('All copies and sections are retained', report['totalCopies']==24 and report['unsupportedCopies']==4 and report['cards'][-1]['section']=='Sideboard')
    check('Known catalogue gaps differ from unknown names', report['cards'][1]['status']!='not-indexed' and report['cards'][3]['status']=='not-indexed')
    check('Malformed counts cannot disappear silently', inspect_deck('0 Plains\n-1 Island\n1.5 Plains',index,policy)['admissionBlocked'])
    check('Rebalanced identity is not silently rewritten', report['cards'][2]['name']=='A-The One Ring')
    path = Path(temp)/'index.json';path.write_text(json.dumps(index))
    check('Matching policy and exact engine/script identities load', load_index(path,policy,scripts,jar)['schema']==1)
    jar.write_bytes(b'other engine version')
    try:load_index(path,policy,scripts,jar)
    except ValueError:check('Other Forge engine versions cannot reuse constructor findings',True)
    else:raise AssertionError('Wrong engine diagnostics accepted')
    jar.write_bytes(b'engine identity fixture')
    policy.write_text(json.dumps(dict(verifiedNames=['Island'])))
    try:load_index(path,policy,scripts,jar)
    except ValueError:check('Stale policy diagnostics are rejected',True)
    else:raise AssertionError('Stale report accepted')
    check('A stale report cannot authorize removed cards', not explain('Plains',index,policy)['matchAdmitted'])

with patch('card_support.load_index',return_value=None):
    try:parse_deck('Deck\n38 Plains\n1 Black Lotus\n1 Unknown Card')
    except ValueError as error:check('Production importer aggregates every unverified name', 'Black Lotus' in str(error) and 'Unknown Card' in str(error))
    else:raise AssertionError('Unknown cards imported')
check('Verified practice deck still imports', sum(c['count'] for c in parse_deck('24 Plains\n16 Savannah Lions')['cards'])==40)
print(json.dumps(dict(checks=len(checks),passed=checks),indent=2))
