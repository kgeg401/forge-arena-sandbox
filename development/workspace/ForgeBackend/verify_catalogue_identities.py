"""Cross-check generated catalogue identities against read-only owned Arena rows."""
import hashlib
import json
import sqlite3
from runtime_paths import ROOT, DB
from build_card_coverage import EXPECTED

assert hashlib.sha256(DB.read_bytes()).hexdigest()==EXPECTED,'Source Arena database changed'
folder=ROOT/'research/card-coverage'
mapping=json.loads((folder/'arena-printing-mappings.json').read_text(encoding='utf8'))['printings']
deck=json.loads((ROOT/'native-lab/deck-catalog.json').read_text(encoding='utf8'))['cards']
db=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
expected={r[0] for r in db.execute('''SELECT c.GrpId FROM Cards c LEFT JOIN Cards original
    ON c.DefunctRebalancedCardGrpId=original.GrpId
    WHERE c.IsToken=0 AND (c.IsPrimaryCard=1 OR
    (c.IsRebalanced=1 AND original.IsPrimaryCard=1 AND original.IsToken=0))''')}
checks=[]
def check(label,ok):
    assert ok,label
    checks.append(label)
by_id={c['grpId']:c for c in mapping}
check('Coverage exactly matches source primary and rebalanced primary identities',set(by_id)==expected and len(mapping)==len(expected))
check('Deck storage and audit use exactly the same identities',{c['grpId'] for c in deck}==expected and len(deck)==len(expected))
check('All original primary printings are retained',{r[0] for r in db.execute('SELECT GrpId FROM Cards WHERE IsPrimaryCard=1 AND IsToken=0')}<=expected)
rebalanced={r[0] for r in db.execute('SELECT GrpId FROM Cards WHERE IsRebalanced=1')}
check('Rebalanced printings retain explicit A- identity',all(by_id[g]['name'].startswith('A-') for g in expected&rebalanced))
check('Linked secondary rebalanced faces are not standalone deck entries',not ({g for g in rebalanced if g not in expected}&set(by_id)))
check('The One Ring remains distinct from both rebalanced printings',by_id[84938]['name']=='The One Ring' and all(by_id[g]['name']=='A-The One Ring' for g in (90247,107491)))
check('Known adventure back face is excluded',82943 not in by_id and by_id[81891]['name']=='A-Monster Manual')
check('No catalogue extension silently admits rebalanced cards',all(not c['matchSupported'] for c in deck if c['grpId'] in rebalanced))
report=dict(checks=len(checks),passed=checks,printings=len(expected),rebalancedPrintings=len(expected&rebalanced),sourceDatabaseSha256=EXPECTED)
(folder/'catalogue-identity-checks.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
