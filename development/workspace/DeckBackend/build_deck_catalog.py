"""Index owned English primary printings for local deck storage, not rules support."""
from pathlib import Path
import hashlib, json, sqlite3, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ForgeBackend'))
from deck_import import SUPPORTED
from arena_catalog import clean_name, indexed_printings
from runtime_paths import ROOT, DB, SUPPORT_POLICY

EXPECTED = '1be0105411ad989ca60e233f1341eaaa9276e3a679c89f1ef6f07e07ede10d25'
POLICY=json.loads(SUPPORT_POLICY.read_text())
PINNED = {name:POLICY['preferredPrintings'][name] for name in SUPPORTED}
COMMANDER_PINNED={name:POLICY['preferredPrintings'][name] for name in POLICY.get('brawlCommanders',{})}

def build():
    digest = hashlib.sha256(DB.read_bytes()).hexdigest()
    if digest != EXPECTED:
        raise ValueError('Owned database changed; inspect before rebuilding deck catalog.')
    with sqlite3.connect(DB.as_uri()+'?mode=ro', uri=True) as db:
        db.row_factory=sqlite3.Row
        rows = {r['GrpId']:dict(r) for r in db.execute('''SELECT c.*,l.Loc AS EnglishName
                            FROM Cards c JOIN Localizations_enUS l ON l.LocId=c.TitleId AND l.Formatted=1 ORDER BY c.GrpId''')}
    cards = [dict(grpId=r['GrpId'],name=clean_name(r['EnglishName']),set=r['ExpansionCode'],collector=str(r['CollectorNumber'])+(r['CollectorSuffix'] or ''),sort=[r[k] for k in ('Order_LandLast','Order_CMCWithXLast','Order_ColorOrder','Order_Title')],
                  rebalanced=bool(r['IsRebalanced']),matchSupported=clean_name(r['EnglishName']) in PINNED,commanderSupported=clean_name(r['EnglishName']) in COMMANDER_PINNED,
                  colorIdentity=POLICY.get('colorIdentities',{}).get(clean_name(r['EnglishName']),[]),
                  preferred={**PINNED,**COMMANDER_PINNED}.get(clean_name(r['EnglishName']))==r['GrpId'])
             for r in indexed_printings(rows)]
    result = dict(schema=1,sourceDatabaseSha256=digest,policySha256=hashlib.sha256(SUPPORT_POLICY.read_bytes()).hexdigest(),cards=cards,
                  policy=f'Local sandbox deck storage; all catalog printings may be saved. Match admission remains {len(SUPPORTED)} verified names and pinned presentation IDs. No retail format legality claim.')
    target = ROOT/'native-lab/deck-catalog.json'
    pending=target.with_suffix('.pending');pending.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');pending.replace(target)
    print(json.dumps(dict(cards=len(cards),catalog=str(target))))

if __name__ == '__main__': build()
