"""Join the owned Arena catalogue to installed Forge scripts; emit private evidence.

A script name match is a mapping candidate, never a gameplay-support assertion.
Only explicit bridge support entries become runtime presentation mappings.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib, html, json, re, sqlite3, unicodedata, zipfile
from runtime_paths import ROOT, DB, FORGE_SCRIPTS, SUPPORT_POLICY
from arena_catalog import clean_name, indexed_printings

EXPECTED='1be0105411ad989ca60e233f1341eaaa9276e3a679c89f1ef6f07e07ede10d25'
FORGE=FORGE_SCRIPTS
POLICY=SUPPORT_POLICY

def norm(name):
    # Arena uses /// for aftermath split titles; Forge uses //. This changes
    # candidate identity only and never relaxes gameplay admission.
    value=unicodedata.normalize('NFKC',clean_name(name)).replace('’',"'").replace('−','-').casefold().strip()
    return re.sub(r'\s*/{2,3}\s*',' // ',value)

def checked_target_prompt(db,name,binding):
    if set(binding)!={'promptId','expectedText'} or type(binding['promptId']) is not int or binding['promptId']<=0:
        raise ValueError(('Invalid explicit target prompt binding',name))
    rows=list(db.execute('SELECT l.Loc FROM Prompts p JOIN Localizations_enUS l ON p.LocId=l.LocId WHERE p.Id=? AND l.Formatted=1',(binding['promptId'],)))
    normalized=[html.unescape(re.sub('<[^>]+>','',row[0])).strip() for row in rows]
    if normalized!=[binding['expectedText']]:raise ValueError(('Owned target prompt text differs',name))
    return binding['promptId']


def mode_text(value,name):
    """Exact text identity after markup/spacing only; never fuzzy matching."""
    value=html.unescape(re.sub(r'<[^>]*>','',value or '')).replace('CARDNAME',name)
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',value)).strip()


def modal_binding(db,name,native_card,forge_text):
    roots=[line for line in forge_text.splitlines() if re.match(r'A:(?:SP|AB)\$ Charm\b',line)]
    if len(roots)!=1:return None
    fields=dict(part.strip().split('$',1) for part in roots[0].split('|') if '$' in part)
    choices=fields.get('Choices','').strip().split(',')
    descriptions=[]
    for choice in choices:
        matches=re.findall(r'^SVar:'+re.escape(choice)+r':(.+)$',forge_text,re.M)
        if len(matches)!=1:return None
        parts={k.strip():v.strip() for part in matches[0].split('|') if '$' in part for k,v in [part.split('$',1)]}
        if not parts.get('SpellDescription'):return None
        descriptions.append(mode_text(parts['SpellDescription'],name))
    if len(set(descriptions))!=len(descriptions):return None
    candidates=[]
    for raw in filter(None,native_card['AbilityIds'].split(',')):
        root=int(raw.split(':')[0]);row=db.execute('SELECT ModalChildIds FROM Abilities WHERE Id=?',(root,)).fetchone()
        if not row or not row[0]:continue
        ids=[int(v) for v in row[0].split(',') if v]
        if len(ids)!=len(descriptions):continue
        native={}
        for identity in ids:
            rows=list(db.execute('SELECT l.Loc FROM Abilities a JOIN Localizations_enUS l ON l.LocId=a.TextId AND l.Formatted=1 WHERE a.Id=?',(identity,)))
            if len(rows)!=1:break
            text=mode_text(rows[0][0],name)
            if text in native:break
            native[text]=identity
        if len(native)==len(descriptions) and set(native)==set(descriptions):
            candidates.append(dict(parentAbilityId=root,choices=[dict(forgeDescription=text,nativeAbilityId=native[text]) for text in descriptions],basis='Exact owned modal child text and Forge description after markup/whitespace normalization'))
    return candidates[0] if len(candidates)==1 else None


def build():
    digest=hashlib.sha256(DB.read_bytes()).hexdigest()
    if digest!=EXPECTED:raise ValueError('Owned Arena database changed; inspect before mapping cards.')
    policy=json.loads(POLICY.read_text()); db=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    verified=set(policy['verifiedNames']);candidates=set(policy['candidateNames'])
    if verified&candidates or len(verified)!=len(policy['verifiedNames']) or len(candidates)!=len(policy['candidateNames']):raise ValueError('Duplicate or overlapping admission/candidate names')
    if set(policy['preferredPrintings'])!=verified|candidates:raise ValueError('Runtime printings must be explicitly verified or candidates')
    if not set(policy.get('targetPromptBindings',{}))<=verified|candidates:raise ValueError('Target prompt bindings must belong to explicit runtime cards')
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
    printings=indexed_printings(all_rows)
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
        if 'Land' not in core and any(x not in ('W','U','B','R','G','C') and not x.isdecimal() for x in costs):raise ValueError(('Unimplemented hybrid, snow or variable printed cost',name))
        if 'Land' not in core:
            native_text=r['OldSchoolManaText'] or ''
            native_tokens=re.findall(r'o([0-9]+|[WUBRGC])',native_text)
            if ''.join('o'+v for v in native_tokens)!=native_text:raise ValueError(('Unimplemented native printed mana notation',name,native_text))
            def cost_identity(parts):return (sum(int(v) for v in parts if v.isdecimal()),Counter(v for v in parts if not v.isdecimal()))
            if cost_identity(native_tokens)!=cost_identity(costs):raise ValueError(('Printed Arena/Forge mana costs differ',name,native_text,costs))
        # Arena database colors are CardColor enum ordinals (Black=3,
        # Red=4, Green=5); Forge runtime colors are a separate bit mask.
        colors=[v for v in enum_values('CardColor',r['Colors']) if v in ('White','Blue','Black','Red','Green')]
        color=colors[0] if colors else 'Colorless'
        ability_ids=[int(x.split(':')[0]) for x in filter(None,r['AbilityIds'].split(','))]
        runtime[name]=dict(grpId=grp,titleId=r['TitleId'],types=core,subtypes=arena_subtypes,supertypes=super_types,genericCost=generic,color=color,colors=colors,abilityId={**policy.get('nativeBasicManaAbilityIds',{}),**policy.get('nativeManaAbilityIds',{})}.get(name,ability_ids[0] if ability_ids else 0),
            abilityIds=ability_ids,forgeScript=match['forgeScripts'][0],forgeScriptSha256=match['forgeScriptSha256'],token=False,admitted=name in verified,candidate=name in candidates)
        binding=modal_binding(db,name,r,definitions[match['forgeScripts'][0]]['text'])
        if binding:runtime[name]['modalBinding']=binding
        generic=policy.get('genericChoiceBindings',{}).get(name)
        if generic is not None:
            if set(generic)!={'promptId','expectedText','labels'} or not isinstance(generic['labels'],list) or not generic['labels'] or any(not isinstance(label,str) for label in generic['labels']):raise ValueError(('Invalid explicit generic choice binding',name))
            prompt=checked_target_prompt(db,name,{k:generic[k] for k in ('promptId','expectedText')})
            text=definitions[match['forgeScripts'][0]]['text'];roots=re.findall(r'^A:(?:SP|AB)\$ GenericChoice\b(.+)$',text,re.M)
            if len(roots)!=1:raise ValueError(('Generic choice needs a single explicit source root',name))
            params={k.strip():v.strip() for part in roots[0].split('|') if '$' in part for k,v in [part.split('$',1)]};labels=[]
            for choice in params.get('Choices','').split(','):
                options=re.findall(r'^SVar:'+re.escape(choice)+r':(.+)$',text,re.M)
                if len(options)!=1:raise ValueError(('Generic choice source option is ambiguous',name,choice))
                fields={k.strip():v.strip() for part in options[0].split('|') if '$' in part for k,v in [part.split('$',1)]};labels.append(mode_text(fields.get('SpellDescription',''),name))
            if labels!=generic['labels'] or len(set(labels))!=len(labels):raise ValueError(('Native choice labels differ from the exact source descriptions',name))
            native_texts=[mode_text(t[0],name) for raw in r['AbilityIds'].split(',') if raw for t in db.execute('SELECT l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId AND l.Formatted=1 WHERE a.Id=?',(int(raw.split(':')[0]),))]
            if not any(t.startswith(generic['expectedText']) for t in native_texts) or any(re.search(r'(?<![A-Za-z0-9])'+re.escape(label)+r'(?![A-Za-z0-9])',generic['expectedText'],re.I) is None for label in labels):raise ValueError(('Owned source does not independently bind the choice instruction and labels',name))
            runtime[name]['genericChoiceBinding']=dict(promptId=prompt,labels=labels,basis='Exact source option descriptions and owned native instruction/option words; original dynamic prompt-parameter workflow; English option labels, rendered acceptance pending')
        basic_identity={'Plains':'W','Island':'U','Swamp':'B','Mountain':'R','Forest':'G'}
        identity=policy.get('colorIdentities',{}).get(name,list(dict.fromkeys(symbols)) or [basic_identity[t] for t in arena_subtypes if t in basic_identity])
        runtime[name]['colorIdentity']=identity
        if name in policy.get('nativeManaColors',{}):runtime[name]['manaColor']=policy['nativeManaColors'][name]
        runtime[name]['coloredCost']=[dict(color={'W':'White','U':'Blue','B':'Black','R':'Red','G':'Green'}[x],count=symbols.count(x)) for x in dict.fromkeys(symbols)]
        bindings=policy.get('abilityBindings',{}).get(name,{})
        bound=[bindings['trigger']] if 'trigger' in bindings else []
        bound+=list(bindings.get('activated',{}).values())
        if any(v not in ability_ids for v in bound):raise ValueError(('Ability binding is absent from source printing',name))
        runtime[name]['abilityBindings']=bindings
        prompt_binding=policy.get('targetPromptBindings',{}).get(name)
        if prompt_binding is not None:
            runtime[name]['targetPromptId']=checked_target_prompt(db,name,prompt_binding)
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
    report=dict(utc=datetime.now(timezone.utc).isoformat(),sourceDatabaseSha256=digest,sourceForgeScriptsSha256=hashlib.sha256(FORGE.read_bytes()).hexdigest(),policySha256=hashlib.sha256(POLICY.read_bytes()).hexdigest(),arenaPrintings=len(printings),arenaNames=len(groups),primaryPrintings=sum(bool(r['IsPrimaryCard']) for r in printings),rebalancedPrintings=sum(bool(r['IsRebalanced']) for r in printings),forgeScriptFiles=len(definitions),mappingCounts=dict(Counter(e['mapping'] for e in entries)),featureCounts=dict(Counter(f for e in entries for f in e['features'])),verifiedNames=policy['verifiedNames'],candidateNames=policy['candidateNames'],scope='Installed primary and source-linked rebalanced metadata only; not release, format legality or ownership. A match is not engine compatibility, native rendering, asset availability or gameplay verification.')
    (root/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');(root/'arena-forge-coverage.json').write_text(json.dumps(dict(summary=report,cards=entries),ensure_ascii=False),encoding='utf-8')
    probe={path:dict(script=path,sha256=definitions[path]['sha256'],names=definitions[path]['names'])
           for e in entries if len(e['forgeScripts'])==1 for path in e['forgeScripts']}
    (root/'forge-compile-input.json').write_text(json.dumps(dict(schema=1,sourceForgeScriptsSha256=report['sourceForgeScriptsSha256'],scripts=list(probe.values())),ensure_ascii=False),encoding='utf-8')
    for name,commander in policy.get('brawlCommanders',{}).items():
        if name not in runtime or 'Legendary' not in runtime[name]['supertypes'] or not {'Creature','Planeswalker'} & set(runtime[name]['types']):raise ValueError('Brawl commander must have an explicit source-checked legendary creature or planeswalker mapping')
        if commander['colorIdentity']!=runtime[name]['colorIdentity']:raise ValueError('Commander identity differs from the source-checked policy')
        runtime[name]['commanderAdmitted']=True
        runtime[name]['colorIdentity']=commander['colorIdentity']
    keyword_ids={}
    type_ids={}
    for kind in ['CardType','SubType','SuperType']:
        values={}
        for row in db.execute('SELECT e.Value,l.Loc FROM Enums e JOIN Localizations_enUS l ON e.LocId=l.LocId AND l.Formatted=1 WHERE e.Type=?',(kind,)):
            name=row['Loc'].lower()
            if name in values and values[name]!=row['Value']:raise ValueError(('Ambiguous owned type enum label',kind,name))
            values[name]=row['Value']
        type_ids[kind]=values
    for keyword in ['Flying','Trample','Hexproof','Haste','Lifelink','Deathtouch','Vigilance','Indestructible','Reach','First strike','Double strike','Defender','Menace','Protection from white','Protection from blue','Protection from black','Protection from red','Protection from green']:
        matches=list(db.execute('SELECT a.Id FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId AND l.Formatted=1 WHERE a.Category=3 AND l.Loc=?',(keyword,)))
        if len(matches)!=1:raise ValueError(('Owned native keyword identity is not unique',keyword))
        keyword_ids[keyword.lower()]=matches[0]['Id']
    target=ROOT/'native-lab/bridge-card-manifest.json';pending=target.with_suffix('.pending')
    from experimental_cards import merge_manifest
    manifest=merge_manifest(dict(schema=1,admissionSchema=1,researchOnly=bool(policy.get('researchOnly')),sourceDatabaseSha256=digest,policySha256=report['policySha256'],sourceForgeScriptsSha256=report['sourceForgeScriptsSha256'],keywordAbilityIds=keyword_ids,typeEnumIds=type_ids,cards=runtime))
    pending.write_text(json.dumps(manifest,indent=2))
    pending.replace(target)
    print(json.dumps(report,indent=2))

if __name__=='__main__':build()
