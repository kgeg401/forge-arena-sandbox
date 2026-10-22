"""Index owned English primary printings for local deck storage, not rules support."""
from pathlib import Path
import hashlib, json, sqlite3, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ForgeBackend'))
from deck_import import SUPPORTED
from build_card_coverage import clean_name
from runtime_paths import ROOT, DB

EXPECTED = '1be0105411ad989ca60e233f1341eaaa9276e3a679c89f1ef6f07e07ede10d25'
POLICY=json.loads((Path(__file__).resolve().parents[1]/'ForgeBackend/bridge_support.json').read_text())
PINNED = {name:POLICY['preferredPrintings'][name] for name in SUPPORTED}

def build():
    digest = hashlib.sha256(DB.read_bytes()).hexdigest()
    if digest != EXPECTED:
        raise ValueError('Owned database changed; inspect before rebuilding deck catalog.')
    with sqlite3.connect(DB.as_uri()+'?mode=ro', uri=True) as db:
        rows = db.execute('''SELECT c.GrpId,l.Loc,c.ExpansionCode,c.CollectorNumber,c.CollectorSuffix,
                            c.Order_LandLast,c.Order_CMCWithXLast,c.Order_ColorOrder,c.Order_Title
                            FROM Cards c JOIN Localizations_enUS l ON l.LocId=c.TitleId AND l.Formatted=1
                            WHERE c.IsPrimaryCard=1 AND c.IsToken=0 ORDER BY c.GrpId''').fetchall()
    cards = [dict(grpId=g,name=clean_name(n),set=s,collector=str(i)+(x or ''),sort=[a,b,c,d],
                  matchSupported=clean_name(n) in PINNED,preferred=PINNED.get(clean_name(n))==g)
             for g,n,s,i,x,a,b,c,d in rows]
    result = dict(schema=1,sourceDatabaseSha256=digest,policySha256=hashlib.sha256((Path(__file__).resolve().parents[1]/'ForgeBackend/bridge_support.json').read_bytes()).hexdigest(),cards=cards,
                  policy=f'Local sandbox deck storage; all catalog printings may be saved. Match admission remains {len(SUPPORTED)} verified names and pinned presentation IDs. No retail format legality claim.')
    target = ROOT/'native-lab/deck-catalog.json'
    pending=target.with_suffix('.pending');pending.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');pending.replace(target)
    print(json.dumps(dict(cards=len(cards),catalog=str(target))))

if __name__ == '__main__': build()
