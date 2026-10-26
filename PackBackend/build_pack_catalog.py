"""Build a private collectible-card catalog from the owned, pinned Arena database.

This is custom sandbox collation: five commons, two uncommons, and one
rare/mythic (one in eight when a mythic pool exists). It is NOT retail odds.
"""
from pathlib import Path
import hashlib, json, sqlite3, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ForgeBackend'))
from runtime_paths import ROOT,DB
EXPECTED='1be0105411ad989ca60e233f1341eaaa9276e3a679c89f1ef6f07e07ede10d25'

def build():
    digest=hashlib.sha256(DB.read_bytes()).hexdigest()
    if digest != EXPECTED: raise ValueError('Owned card database identity changed; inspect before rebuilding.')
    # This private data file is emitted by the isolated native adapter from the
    # installed enum. No extracted enum source or card assets are distributed.
    mapping_path=ROOT/'native-lab/pack-collation-map.json'
    mapping_bytes=mapping_path.read_bytes();mapping=json.loads(mapping_bytes)
    assembly_digest=mapping.get('sourceAssemblySha256')
    if mapping.get('schema')!=1 or assembly_digest!='42f2fb5f062ccc6098182a902d411746070759a404e875b6e0aac44d3b7ccc6e':raise ValueError('Installed collation source identity changed; inspect before rebuilding.')
    mappings=mapping['mappings']
    if not isinstance(mappings,dict) or not mappings or any(not isinstance(k,str) or type(v)is not int or not 60000<v<200000 for k,v in mappings.items()):raise ValueError('Invalid installed collation mapping')
    connection=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
    catalog=[]
    for code,collation in mappings.items():
        rows=connection.execute('SELECT GrpId,Rarity FROM Cards WHERE ExpansionCode=? AND IsPrimaryCard=1 AND IsToken=0 AND IsRebalanced=0 AND DraftContent=1 AND Rarity BETWEEN 2 AND 5 ORDER BY GrpId',(code,)).fetchall()
        pools={str(r):[g for g,rarity in rows if rarity==r] for r in range(2,6)}
        if len(pools['2'])<5 or len(pools['3'])<2 or not pools['4']: continue
        catalog.append({'set':code,'collationId':collation,'initialPacks':100,'pools':pools})
    if not any(x['set']=='WOE' for x in catalog): raise ValueError('Required native test set is missing')
    connection.close()
    result={'schema':1,'sourceDatabaseSha256':digest,'sourceCollationAssemblySha256':assembly_digest,'collationEvidenceSha256':hashlib.sha256(mapping_bytes).hexdigest(),'policy':'Custom sandbox: 5 common + 2 uncommon + 1 rare/mythic; mythic 1/8 when available; distinct printings within each pack; no wildcard/bonus-sheet/duplicate protection. Not retail collation.','sets':catalog}
    destination=ROOT/'native-lab/pack-catalog.json'
    pending=destination.with_suffix('.pending');pending.write_text(json.dumps(result,indent=2),encoding='utf-8');pending.replace(destination)
    print(json.dumps({'sets':len(catalog),'printings':sum(len(v) for s in catalog for v in s['pools'].values()),'catalog':str(destination)}))

if __name__=='__main__': build()
