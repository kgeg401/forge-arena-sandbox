"""Join the owned Arena catalogue to installed Forge scripts; emit private evidence.

A script name match is a mapping candidate, never a gameplay-support assertion.
Only explicit bridge support entries become runtime presentation mappings.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib, html, json, re, sqlite3, unicodedata, zipfile
from runtime_paths import ROOT, DB, FORGE_SCRIPTS

EXPECTED='1be0105411ad989ca60e233f1341eaaa9276e3a679c89f1ef6f07e07ede10d25'
FORGE=FORGE_SCRIPTS
POLICY=Path(__file__).with_name('bridge_support.json')

def clean_name(name):return html.unescape(re.sub(r'<[^>]+>','',name)).strip()
def norm(name):
    # Arena uses /// for aftermath split titles; Forge uses //. This changes
    # candidate identity only and never relaxes gameplay admission.
    value=unicodedata.normalize('NFKC',clean_name(name)).replace('’',"'").replace('−','-').casefold().strip()
    return re.sub(r'\s*/{2,3}\s*',' // ',value)

def build():
    digest=hashlib.sha256(DB.read_bytes()).hexdigest()
    if digest!=EXPECTED:raise ValueError('Owned Arena database changed; inspect before mapping cards.')
    policy=json.loads(POLICY.read_text()); db=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    verified=set(policy['verifiedNames']);candidates=set(policy['candidateNames'])
    if verified&candidates or len(verified)!=len(policy['verifiedNames']) or len(candidates)!=len(policy['candidateNames']):raise ValueError('Duplicate or overlapping admission/candidate names')
    if set(policy['preferredPrintings'])!=verified|candidates:raise ValueError('Runtime printings must be explicitly verified or candidates')
    enums={(r['Type'],r['Value']):r['Loc'] for r in db.execute('SELECT e.Type,e.Value,l.Loc FROM Enums e JOIN Localizations_enUS l ON l.LocId=e.LocId AND l.Formatted=1')}
    def enum_values(kind,text):return [enums[(kind,int(v))] for v in filter(None,text.split(','))]
    scripts=defaultdict(list);definitions={}
    with zipfile.ZipFile(FORGE) as archive:
        for path in archive.namelist():
            if not path.endswith('.txt'):continue
            raw=archive.read(path);text=raw.decode('utf-8-sig');names=re.findall(r'^Name:(.+)$',text,re.M)
            if not names:continue
            names=[n.strip() for n in names]; definitions[path]=dict(sha256=hashlib.sha256(raw).hexdigest(),text=text,names=names)
            for name in names:scripts[norm(name)].append(path)
            if len(names)>1:scripts[norm(' // '.join(names))].append(path)
    all_rows={r['GrpId']:dict(r) for r in db.execute('SELECT c.*,l.Loc AS EnglishName FROM Cards c JOIN Localizations_enUS l ON l.LocId=c.TitleId AND l.Formatted=1')}
    for row in all_rows.values():row['SourceEnglishName']=row['EnglishName'];row['EnglishName']=clean_name(row['EnglishName'])
    printings=[r for r in all_rows.values() if r['IsPrimaryCard']==1 and r['IsToken']==0]
    groups=defaultdict(list)
    for r in printings:groups[r['EnglishName']].append(r)
    entries=[]
    for name,rows in sorted(groups.items()):
        matches=sorted(set(scripts.get(norm(name),[])));definition=definitions[matches[0]] if len(matches)==1 else None
        features=[]
        if definition:
            for prefix,feature in [('T:','trigger'),('A:','activated-or-spell'),('S:','static'),('R:','replacement'),('K:','keyword')]:
                if re.search('^'+re.escape(prefix),definition['text'],re.M):features.append(feature)
            for pattern,feature in [(r'\bToken\b','tokens'),(r'\bChangeZone\b','zone-change'),(r'\bCounter\b','counters'),(r'\bChoose','choice'),(r'\bValidTgts\$','targeting'),(r'ALTERNATE','multiple-faces')]:
                if re.search(pattern,definition['text']):features.append(feature)
        entries.append(dict(name=name,arenaGrpIds=sorted(r['GrpId'] for r in rows),forgeScripts=matches,
            mapping='unique-script-candidate' if len(matches)==1 else 'ambiguous-script-candidate' if matches else 'no-script-name-match',
            bridge='verified-existing-slice' if name in policy['verifiedNames'] else 'implementation-candidate' if name in policy['candidateNames'] else 'not-admitted',features=features,
            forgeScriptSha256=definition['sha256'] if definition else None))
    runtime={}
    for name,grp in policy['preferredPrintings'].items():
        r=all_rows[grp]
        if r['EnglishName']!=name:raise ValueError(('Pinned identity mismatch',name,grp))
        match=next(e for e in entries if e['name']==name)
        if match['mapping']!='unique-script-candidate':raise ValueError(('Admitted card needs unique Forge script',name))
        fields={k:v for line in definitions[match['forgeScripts'][0]]['text'].split('ALTERNATE')[0].splitlines() if ':' in line for k,v in [line.split(':',1)]}
        forge_types=fields['Types'].split(); arena_subtypes=enum_values('SubType',r['Subtypes'])
        core=enum_values('CardType',r['Types']);super_types=enum_values('SuperType',r['Supertypes'])
        if 'Creature' in core and fields.get('PT')!=r['Power']+'/'+r['Toughness']:raise ValueError(('Printed stats mismatch',name))
        if not all(t in forge_types for t in core+super_types+arena_subtypes):raise ValueError(('Types differ',name,core,super_types,arena_subtypes,forge_types))
        costs=fields.get('ManaCost','').split();generic=sum(int(x) for x in costs if x.isdecimal());symbols=[x for x in costs if x in ('W','U','B','R','G')]
        if 'Land' not in core and (len(symbols)>1 or any(x not in ('W','U','B','R','G') and not x.isdecimal() for x in costs)):raise ValueError(('Current cost UI cannot admit this cost',name))
        color={'1':'White','2':'Blue','4':'Black','8':'Red','16':'Green','':'Colorless'}.get(r['Colors'])
        if color is None:raise ValueError(('Current mapping supports only source monocolor/colorless cards',name))
        ability_ids=[int(x.split(':')[0]) for x in filter(None,r['AbilityIds'].split(','))]
        runtime[name]=dict(grpId=grp,titleId=r['TitleId'],types=core,subtypes=arena_subtypes,supertypes=super_types,genericCost=generic,color=color,abilityId={**policy.get('nativeBasicManaAbilityIds',{}),**policy.get('nativeManaAbilityIds',{})}.get(name,ability_ids[0] if ability_ids else 0),
            abilityIds=ability_ids,forgeScript=match['forgeScripts'][0],forgeScriptSha256=match['forgeScriptSha256'],token=False,admitted=name in verified,candidate=name in candidates)
        identity=policy.get('colorIdentities',{}).get(name,symbols or (['U'] if name=='Island' else ['W'] if name=='Plains' else []))
        runtime[name]['colorIdentity']=identity
        if name in policy.get('nativeManaColors',{}):runtime[name]['manaColor']=policy['nativeManaColors'][name]
        runtime[name]['coloredCost']=[dict(color={'W':'White','U':'Blue','B':'Black','R':'Red','G':'Green'}[x],count=symbols.count(x)) for x in dict.fromkeys(symbols)]
        bindings=policy.get('abilityBindings',{}).get(name,{})
        bound=[bindings['trigger']] if 'trigger' in bindings else []
        bound+=list(bindings.get('activated',{}).values())
        if any(v not in ability_ids for v in bound):raise ValueError(('Ability binding is absent from source printing',name))
        runtime[name]['abilityBindings']=bindings
    for token in policy['tokens']:
        r=all_rows[token['arenaGrpId']];source=all_rows[policy['preferredPrintings'][token['sourceName']]]
        links=dict(p.split(':') for p in source['AbilityIdToLinkedTokenGrpId'].split(',') if p)
        if links.get(str(token['sourceAbilityId']))!=str(token['arenaGrpId']) or not r['IsToken']:raise ValueError('Token source link does not match owned data')
        path=FORGE.parent.parent/'tokenscripts'/(token['forgeScript']+'.txt')
        raw=path.read_bytes();fields=dict(line.split(':',1) for line in raw.decode().splitlines() if ':' in line)
        if fields['Name']!=token['forgeName'] or fields.get('PT')!=r['Power']+'/'+r['Toughness']:raise ValueError('Token script mismatch')
        if token['forgeName'] in runtime:raise ValueError('Token name collides with a primary card')
        runtime[token['forgeName']]=dict(grpId=r['GrpId'],titleId=r['TitleId'],types=enum_values('CardType',r['Types']),subtypes=enum_values('SubType',r['Subtypes']),supertypes=[],genericCost=0,color=fields['Colors'].title(),abilityId=0,abilityIds=[],token=True,admitted=False,candidate=False,forgeScript=token['forgeScript'],forgeScriptSha256=hashlib.sha256(raw).hexdigest())
    root=ROOT/'research/card-coverage';root.mkdir(parents=True,exist_ok=True)
    by_name={e['name']:e for e in entries};full_mappings=[]
    for r in printings:
        entry=by_name[r['EnglishName']]
        full_mappings.append(dict(grpId=r['GrpId'],name=r['EnglishName'],titleId=r['TitleId'],artId=r['ArtId'],set=r['ExpansionCode'],collector=str(r['CollectorNumber'])+(r['CollectorSuffix'] or ''),
            types=enum_values('CardType',r['Types']),subtypes=enum_values('SubType',r['Subtypes']),supertypes=enum_values('SuperType',r['Supertypes']),manaText=r['OldSchoolManaText'],colors=r['Colors'],power=r['Power'],toughness=r['Toughness'],
            abilityIds=[int(v.split(':')[0]) for v in filter(None,r['AbilityIds'].split(','))],linkedTokenMap=r['AbilityIdToLinkedTokenGrpId'],
            digitalOnly=bool(r['IsDigitalOnly']),rebalanced=bool(r['IsRebalanced']),rebalancedGrpId=r['RebalancedCardGrpId'],defunctRebalancedGrpId=r['DefunctRebalancedCardGrpId'],
            linkedFaces=r['LinkedFaceGrpIds'],linkedConjurations=r['AbilityIdToLinkedConjurations'],draftContent=bool(r['DraftContent']),
            forgeScripts=entry['forgeScripts'],mapping=entry['mapping'],bridge=entry['bridge']))
    (root/'arena-printing-mappings.json').write_text(json.dumps(dict(sourceDatabaseSha256=digest,printings=full_mappings),ensure_ascii=False),encoding='utf-8')
    report=dict(utc=datetime.now(timezone.utc).isoformat(),sourceDatabaseSha256=digest,sourceForgeScriptsSha256=hashlib.sha256(FORGE.read_bytes()).hexdigest(),policySha256=hashlib.sha256(POLICY.read_bytes()).hexdigest(),arenaPrintings=len(printings),arenaNames=len(groups),forgeScriptFiles=len(definitions),mappingCounts=dict(Counter(e['mapping'] for e in entries)),featureCounts=dict(Counter(f for e in entries for f in e['features'])),verifiedNames=policy['verifiedNames'],candidateNames=policy['candidateNames'],scope='Source/name coverage only. A match is not engine compatibility, native rendering, asset availability or gameplay verification.')
    (root/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');(root/'arena-forge-coverage.json').write_text(json.dumps(dict(summary=report,cards=entries),ensure_ascii=False),encoding='utf-8')
    probe={path:dict(script=path,sha256=definitions[path]['sha256'],names=definitions[path]['names'])
           for e in entries if len(e['forgeScripts'])==1 for path in e['forgeScripts']}
    (root/'forge-compile-input.json').write_text(json.dumps(dict(schema=1,sourceForgeScriptsSha256=report['sourceForgeScriptsSha256'],scripts=list(probe.values())),ensure_ascii=False),encoding='utf-8')
    for name,commander in policy.get('brawlCommanders',{}).items():
        if name not in runtime or 'Legendary' not in runtime[name]['supertypes'] or 'Creature' not in runtime[name]['types']:raise ValueError('Brawl commander must have an explicit source-checked legendary creature mapping')
        if commander['colorIdentity']!=runtime[name]['colorIdentity']:raise ValueError('Commander identity differs from the source-checked policy')
        runtime[name]['commanderAdmitted']=True
        runtime[name]['colorIdentity']=commander['colorIdentity']
    target=ROOT/'native-lab/bridge-card-manifest.json';pending=target.with_suffix('.pending')
    pending.write_text(json.dumps(dict(schema=1,admissionSchema=1,sourceDatabaseSha256=digest,policySha256=report['policySha256'],sourceForgeScriptsSha256=report['sourceForgeScriptsSha256'],cards=runtime),indent=2))
    pending.replace(target)
    print(json.dumps(report,indent=2))

if __name__=='__main__':build()
