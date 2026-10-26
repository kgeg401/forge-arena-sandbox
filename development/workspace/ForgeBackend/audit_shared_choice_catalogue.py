"""Measure static catalogue reach of shared interfaces, never gameplay admission.

Uses the owned, pinned database and complete catalogue produced by the mapping
builder. Presence of an API in a script is a test-planning signal only. A card
can require several other missing interfaces or differ from its Arena rules.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zipfile
from build_card_coverage import modal_binding, EXPECTED
from runtime_paths import ROOT, DB, FORGE_SCRIPTS


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Use a fresh report path')
    if sha(DB)!=EXPECTED:raise ValueError('Owned database changed; rebuild and review catalogue first')
    source=ROOT/'research/card-coverage/arena-forge-coverage.json';coverage=json.loads(source.read_text(encoding='utf8'))
    if coverage['summary']['sourceDatabaseSha256']!=EXPECTED or coverage['summary']['sourceForgeScriptsSha256']!=sha(FORGE_SCRIPTS):raise ValueError('Coverage and installed sources differ')
    mappings=ROOT/'research/card-coverage/arena-printing-mappings.json';printings=json.loads(mappings.read_text(encoding='utf8'))['printings']
    representatives={}
    for row in sorted(printings,key=lambda r:r['grpId']):representatives.setdefault(row['name'],row['grpId'])
    db=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    families={'Scry':'scry','Surveil':'surveil','Charm':'modes','Dig':'look-select-order','DigUntil':'reveal-until','ChooseNumber':'number','GenericChoice':'generic-ability-choice','Discard':'discard','ChangeZone':'zone-change-or-search','Sacrifice':'sacrifice','PutCounter':'put-counters','RemoveCounter':'remove-counters','ChooseColor':'colors','ChooseType':'type-choice-still-unmapped','Protection':'color-protection','ProtectionAll':'color-protection','Pump':'temporary-characteristics','PumpAll':'temporary-characteristics','Animate':'type-and-ability-overwrite','AnimateAll':'type-and-ability-overwrite'}
    rows=[];counts=Counter();modal=[];unmatched=[]
    with zipfile.ZipFile(FORGE_SCRIPTS) as archive:
        for card in coverage['cards']:
            name=card['name'];paths=card['forgeScripts']
            if len(paths)!=1:unmatched.append(dict(name=name,mapping=card['mapping']));continue
            text=archive.read(paths[0]).decode('utf-8-sig')
            apis=sorted(set(re.findall(r'\b(?:SP|AB|DB)\$\s*([A-Za-z0-9_]+)',text)))
            found={families[api] for api in apis if api in families}
            if re.search(r'^K:Enchant:|^K:Equip:',text,re.M):found.add('attachments')
            if re.search(r'\b(?:KW|AddKeyword|RemoveKeywords?)\$',text):found.add('keyword-mutation')
            if re.search(r'\bRemoveAllAbilities\$',text):found.add('ability-removal')
            if re.search(r'\b(?:AddType|RemoveCardTypes|RemoveCreatureTypes)\$',text):found.add('type-mutation')
            found=sorted(found);counts.update(found)
            native=db.execute('SELECT * FROM Cards WHERE GrpId=?',(representatives[name],)).fetchone()
            binding=modal_binding(db,name,native,text)
            if binding:modal.append(dict(name=name,grpId=native['GrpId'],parentAbilityId=binding['parentAbilityId'],modeCount=len(binding['choices'])))
            if found:rows.append(dict(name=name,apis=apis,families=found,script=paths[0],forgeScriptSha256=hashlib.sha256(text.encode('utf8')).hexdigest(),exactNativeModalBinding=bool(binding)))
    result=dict(schema=1,utc=datetime.now(timezone.utc).isoformat(),scope='Static complete catalogue test-planning audit only; no gameplay, native rendering, release admission, rules parity or exhaustive callback reachability claim.',
        arenaNames=coverage['summary']['arenaNames'],uniquelyMappedNames=coverage['summary']['mappingCounts'].get('unique-script-candidate',0),namesMentioningTheseInterfaces=len(rows),familyNameCounts=dict(counts),
        exactNativeModalBindingNames=len(modal),modalBindings=modal,cards=rows,unmatched=unmatched,sourceDatabaseSha256=EXPECTED,sourceForgeScriptsSha256=sha(FORGE_SCRIPTS),sourceCoverageSha256=sha(source),sourcePrintingMappingsSha256=sha(mappings))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cards','modalBindings','unmatched')}))


if __name__=='__main__':main()
