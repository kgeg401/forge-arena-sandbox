"""Cross-check all admitted mappings against the owned, pinned source data."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re, sqlite3, zipfile
from collections import Counter
from deck_import import SUPPORTED
from runtime_paths import ROOT, DB, FORGE_SCRIPTS, SUPPORT_POLICY

REPO=Path(__file__).resolve().parents[1]
PRIVATE=ROOT
DATABASE=DB
EXPECTED='1be0105411ad989ca60e233f1341eaaa9276e3a679c89f1ef6f07e07ede10d25'
digest=hashlib.sha256(DATABASE.read_bytes()).hexdigest()
assert digest==EXPECTED, 'Arena card database changed; recover mappings before evaluating them.'
policy=json.loads(SUPPORT_POLICY.read_text())
manifest=json.loads((PRIVATE/'native-lab/bridge-card-manifest.json').read_text())
assert manifest['sourceDatabaseSha256']==digest
native_cards=manifest['cards']
assert manifest.get('admissionSchema')==1
assert {name for name,c in native_cards.items() if c.get('admitted')}==set(policy['verifiedNames']), 'Candidates or tokens entered normal match admission'
assert set(SUPPORTED)==set(policy['verifiedNames']) and set(SUPPORTED)<=set(native_cards), 'Admission policy differs from generated native manifest'
SOURCE_NAMES=tuple(dict.fromkeys(tuple(SUPPORTED)+tuple(policy.get('brawlCommanders',{}))))
assert {name for name,c in native_cards.items() if c.get('commanderAdmitted')}==set(policy.get('brawlCommanders',{})), 'Brawl commander admission differs from explicit policy'
mappings={name:(c['grpId'],c['titleId'],json.dumps(c['subtypes']),c['genericCost'],'true' if 'Instant' in c['types'] else 'false',c['abilityId']) for name,c in native_cards.items() if name in SOURCE_NAMES}
blue={name for name,c in native_cards.items() if c['color']=='Blue'}
db=sqlite3.connect(DATABASE.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
archive=zipfile.ZipFile(FORGE_SCRIPTS)
cards=[]
for name in SOURCE_NAMES:
    grp,title,subtypes,generic,instant,ability=mappings[name]
    row=db.execute('SELECT GrpId,TitleId,AbilityIds,OldSchoolManaText,Colors,Types,Subtypes,Power,Toughness FROM Cards WHERE GrpId=?',(int(grp),)).fetchone()
    assert row and row['TitleId']==int(title), ('Wrong native identity',name)
    filename=native_cards[name]['forgeScript']
    raw=archive.read(filename);definition=dict(line.split(':',1) for line in raw.decode().splitlines() if ':' in line)
    assert hashlib.sha256(raw).hexdigest()==native_cards[name]['forgeScriptSha256'], ('Source script changed',name)
    types=definition['Types'].split();land='Land' in types
    assert (instant=='true')==('Instant' in types), ('Wrong native card type',name)
    assert land or 'Instant' in types or 'Sorcery' in types or 'Creature' in types or 'Artifact' in types, ('Unsupported presentation type',name)
    tokens=[] if definition.get('ManaCost')=='no cost' else definition.get('ManaCost','').split()
    forge_generic=sum(int(t) for t in tokens if t.isdecimal())
    arena_generic=sum(int(t) for t in re.findall(r'o([0-9]+)',row['OldSchoolManaText']))
    assert int(generic)==forge_generic==arena_generic, ('Generic cost mismatch',name)
    expected_subtypes=types[types.index('Land')+1:] if land else types[types.index('Creature')+1:] if 'Creature' in types else []
    assert Counter(re.findall(r'"([^"]+)"',subtypes))==Counter(expected_subtypes), ('Subtype mismatch',name)
    arena_subtypes=[]
    for value in filter(None,row['Subtypes'].split(',')):
        localized=db.execute("SELECT l.Loc FROM Enums e JOIN Localizations_enUS l ON l.LocId=e.LocId WHERE e.Type='SubType' AND e.Value=? AND l.Formatted=1",(int(value),)).fetchone()
        assert localized, ('Unknown installed subtype enum',name,value)
        arena_subtypes.append(localized[0])
    assert Counter(expected_subtypes)==Counter(arena_subtypes), ('Forge and pinned Arena subtype difference requires review',name,expected_subtypes,arena_subtypes)
    if 'Creature' in types:
        assert definition['PT'].split('/')==[row['Power'],row['Toughness']], ('Printed power/toughness mismatch',name)
    if not land:
        symbols=[t for t in tokens if not t.isdecimal()]
        assert all(symbol in ('W','U','B','R','G','C') for symbol in symbols), ('Unsupported colored cost',name)
        native_tokens=re.findall(r'o([0-9]+|[WUBRGC])',row['OldSchoolManaText'])
        assert ''.join('o'+v for v in native_tokens)==row['OldSchoolManaText'], ('Native cost notation',name)
        assert Counter(symbols)==Counter(v for v in native_tokens if not v.isdecimal()), ('Complete colored cost mismatch',name)
        # Source enum ordinals differ from Forge masks, especially B/R/G.
        color_enums={'1':'White','2':'Blue','3':'Black','4':'Red','5':'Green'}
        colors=[color_enums[v] for v in row['Colors'].split(',') if v in color_enums]
        assert native_cards[name]['colors']==colors and native_cards[name]['color']==(colors[0] if colors else 'Colorless'), ('Native source color mismatch',name)
        symbol_colors={'White':'W','Blue':'U','Black':'B','Red':'R','Green':'G'}
        assert {symbol_colors[c['color']]:c['count'] for c in native_cards[name]['coloredCost']}==dict(Counter(symbols)), ('Native colored cost counts',name)
        if int(ability):assert int(ability) in [int(v.split(':')[0]) for v in row['AbilityIds'].split(',')], ('Wrong native ability printing',name)
    else:
        expected_mana={**policy['nativeBasicManaAbilityIds'],**policy.get('nativeManaAbilityIds',{})}[name]
        assert 'Land' in native_cards[name]['types'] and not tokens and int(ability)==expected_mana, ('Source-bound land mana mapping mismatch',name)
    assert native_cards[name]['abilityIds']==[int(v.split(':')[0]) for v in filter(None,row['AbilityIds'].split(','))], ('Complete native ability identities',name)
    cards.append({'name':name,'grpId':int(grp),'titleId':int(title),'abilityId':int(ability),'genericCost':int(generic),'sourceDefinition':filename,'sourceDefinitionSha256':hashlib.sha256(raw).hexdigest(),'checks':'identity, presentation type, subtypes, creature base stats, cost, color and ability passed'})
report={'utc':datetime.now(timezone.utc).isoformat(),'database':str(DATABASE),'databaseSha256':digest,'allowlistsAgree':True,'cards':cards,'ordinaryAdmittedCards':len(SUPPORTED),'brawlCommanderMappings':len(policy.get('brawlCommanders',{})),'passed':True,'scope':str(len(SOURCE_NAMES))+' source mappings, with ordinary and commander-only admission counted separately; not animation, arbitrary-card or full rules parity. Basic mana IDs retain prior source-validated mapping.'}
output=PRIVATE/'research/card-manifest-audit.json';output.write_text(json.dumps(report,indent=2))
print(json.dumps({'cards':len(cards),'passed':True,'report':str(output)}))
