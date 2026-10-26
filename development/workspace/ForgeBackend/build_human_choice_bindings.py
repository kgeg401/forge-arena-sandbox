"""Build private native presentation bindings from pinned local Forge/Arena data.
Bindings identify original UI records; they do not certify gameplay support.
No private projection or generated game data belongs in a public release.
"""
from pathlib import Path
import argparse,hashlib,json,sqlite3,re,html,unicodedata,collections,copy
p=argparse.ArgumentParser(description=__doc__)
for k in ('database','projection','manifest','output','report'):p.add_argument('--'+k,type=Path,required=True)
args=p.parse_args()
projection=json.loads(args.projection.read_text(encoding='utf-8-sig'));manifest=json.loads(args.manifest.read_text(encoding='utf-8-sig'))
# Older platform-default readers can misdecode the Saga em dash. Canonicalize
# only that exact byte-decoding artifact before retaining source descriptions.
def canonical_projection(value):
    if isinstance(value,str):return value.replace('\u00e2\u20ac\u201d','\u2014')
    if isinstance(value,list):return [canonical_projection(v) for v in value]
    if isinstance(value,dict):return {k:canonical_projection(v) for k,v in value.items()}
    return value
projection=canonical_projection(projection)
provenance=projection.get('provenance',{})
if not provenance.get('forgeJarSha256') or not provenance.get('sourceScriptHashes'):raise ValueError('Projection must carry pinned executable and source-script hashes')
for name,digest in provenance['sourceScriptHashes'].items():
    if manifest['cards'][name].get('forgeScriptSha256')!=digest:raise ValueError('Projection and admission manifest source drift: '+name)
db=sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
face_enums={(r['Type'],r['Value']):r['Loc'] for r in db.execute('SELECT e.Type,e.Value,l.Loc FROM Enums e JOIN Localizations_enUS l ON e.LocId=l.LocId AND l.Formatted=1')}
def face_values(kind,text):return [face_enums[kind,int(x)] for x in filter(None,text.split(','))]
for name,source in projection['cards'].items():
    if not source.get('facePresentation'):continue
    parent=manifest['cards'][source['parentName']];row=dict(db.execute('SELECT * FROM Cards WHERE GrpId=?',(parent['grpId'],)).fetchone());linked=[]
    for id in re.findall(r'\d+',row['LinkedFaceGrpIds']):
        linked.extend(dict(r) for r in db.execute('SELECT c.*,l.Loc AS EnglishName FROM Cards c JOIN Localizations_enUS l ON c.TitleId=l.LocId AND l.Formatted=1 WHERE c.GrpId=? AND l.Loc=?',(int(id),name)))
    if len(linked)!=1:raise ValueError('Face has no uniquely linked original Arena identity: '+name)
    row=linked[0];ids=[int(v.split(':')[0]) for v in filter(None,row['AbilityIds'].split(','))];colors=face_values('CardColor',row['Colors'])
    manifest['cards'][name]=dict(grpId=row['GrpId'],titleId=row['TitleId'],types=face_values('CardType',row['Types']),subtypes=face_values('SubType',row['Subtypes']),supertypes=face_values('SuperType',row['Supertypes']),color=next((c for c in colors if c in ('White','Blue','Black','Red','Green')),'Colorless'),colors=colors,colorIdentity=parent.get('colorIdentity',[]),genericCost=0,abilityId=ids[0] if ids else 0,abilityIds=ids,token=False,admitted=False,facePresentation=True,parentName=source['parentName'],forgeScript=parent['forgeScript'],forgeScriptSha256=parent['forgeScriptSha256'],bindingBasis='Original native LinkedFaceGrpIds and exact pinned Forge backside state')
for source in projection['cards'].values():
    source['abilities']+= [a for a in source.get('latentAbilities',[]) if a.get('description') and a['description'] not in {x['description'] for x in source['abilities']}]
    source['triggers']+=source.get('latentTriggers',[])
def normalized(text,name):
    text=html.unescape(re.sub(r'<[^>]+>',' ',text or '')).replace(name,'CARDNAME')
    # New Forge prefixes Saga descriptions with the chapter; Arena stores the
    # same effect text under the chapter's separate original ability identity.
    text=re.sub(r'^[IVX]+(?:\s*,\s*[IVX]+)*\s*(?:[\u2014\u2013-]|\u00e2\u20ac\u201d)\s*','',text)
    text=re.sub(r'\{([o0-9WUBRGCTQSEXP/]+)\}',lambda m:m[1].replace('o',''),text)
    # Parenthetical reminder prose is display text, not a separate rule identity.
    text=re.sub(r'\([^()]*\)','',text)
    text=text.replace('enters the battlefield','enters').replace("exile all cards from target player's graveyard", "exile target player's graveyard")
    text=text.replace('NICKNAME','CARDNAME')
    text=re.sub(r'\bthis (?:artifact|creature|enchantment|token)\b','CARDNAME',text,flags=re.I)
    text=re.sub(r'\s+([.,;:])',r'\1',text)
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text)).strip().rstrip('.').lower()
def ability_rows(card):
    pending=list(card['abilityIds']);seen=set();rows=[]
    while pending:
        id=pending.pop(0)
        if id in seen:continue
        seen.add(id)
        for raw in db.execute('SELECT a.*,l.Loc AS EnglishText FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId AND l.Formatted=1 WHERE a.Id=?',(id,)):
            row=dict(raw);row['PrintedRoot']=id in card['abilityIds'];rows.append(row)
            for field in ('EmbeddedActiveAbilityIds','HiddenAbilityIds','ReferencedAbilityIds','ModalChildIds'):
                pending.extend(int(x) for x in re.findall(r'\d+',str(row[field] or '')))
    return rows
def descriptions(text,name):
    values={normalized(text,name)}
    if ':' in text:values.add(normalized(text.split(':',1)[1],name))
    return values
missing=[];modal_missing=[];counts=collections.Counter();tokens_linked=collections.defaultdict(list);original=copy.deepcopy(manifest)
for name,source in projection['cards'].items():
    card=manifest['cards'][name];rows=ability_rows(card);bindings=card.setdefault('abilityBindings',{});activated={};bindings['activated']=activated;trigger_map={};description_map={};mana_map={}
    for ability in source['abilities']:
        if not ability['activated']:continue
        native=[r for r in rows if r['Category']==1 and bool(r['SubCategory']==1)==ability['mana']]
        desc=ability['description']
        body=ability['params'].get('SpellDescription') or desc
        wanted={normalized(body,name),normalized(desc,name)}
        full=[r for r in native if normalized(ability['description'],name)==normalized(r['EnglishText'],name)]
        matches=full if len(full)==1 else [r for r in native if wanted & descriptions(r['EnglishText'],name)]
        basis='exact text'
        printed=[r for r in native if r['PrintedRoot']]
        same_role=[a for a in source['abilities'] if a['activated'] and a['mana']==ability['mana']]
        if not matches and ability.get('sourceSVar'):
            global_matches=[]
            for raw in db.execute('SELECT a.*,l.Loc AS EnglishText FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId AND l.Formatted=1 WHERE a.Category=1'):
                row=dict(raw)
                if bool(row['SubCategory']==1)!=ability['mana']:continue
                if ability['params'].get('Planeswalker')=='True' and str(row['LoyaltyCost'])!=ability['costs']:continue
                if normalized(row['EnglishText'],name) not in wanted:continue
                global_matches.append(row)
            full_global=[r for r in global_matches if normalized(r['EnglishText'],name)==normalized(ability['description'],name)]
            if len(full_global)==1:global_matches=full_global
            if len(global_matches)==1:matches=global_matches;basis='source SVar and unique original native effect text plus loyalty cost when applicable'
        if not matches and len(printed)==1 and len(same_role)==1:matches=printed;basis='sole printed ability of this role in both pinned card definitions'
        if not matches and ability['mana'] and not native and card.get('manaColor') and len(same_role)==1:
            description_map[desc]=card['abilityId'];mana_map[desc]=card['abilityId'];counts['verified implicit mana']+=1;continue
        if len(matches)==1:
            r=matches[0];description_map[desc]=r['Id'];counts['activated '+basis]+=1
            if ability['mana']:mana_map[desc]=r['Id']
        else:missing.append(dict(name=name,kind='mana' if ability['mana'] else 'activated',description=desc,api=ability['api'],matches=[r['Id'] for r in matches],native=[dict(id=r['Id'],text=r['EnglishText']) for r in native]))
    for trigger in source['triggers']:
        if trigger.get('Static')=='True':counts['nonstack internal triggers']+=1;continue
        desc=trigger.get('TriggerDescription','');native=[r for r in rows if r['Category']==2]
        chapter=re.sub(r'^(?:I|II|III|IV|V)\s*[—-]\s*','',desc) if trigger.get('Chapter') else desc
        matches=[r for r in native if normalized(chapter,name)==normalized(r['EnglishText'],name)]
        if not matches and re.search(r'UntapUpTo\$\s*True\b',trigger.get('executeRule','')):
            matches=[r for r in native if normalized(chapter,name)==normalized(r['EnglishText'],name).replace('untap up to ','untap ')]
            if len(matches)==1:counts['native up-to wording checked against source UntapUpTo rule']+=1
        if not matches and desc.startswith('Evoke '):matches=[r for r in rows if r['PrintedRoot'] and r['EnglishText'].startswith('Evoke')]
        printed=[r for r in native if r['PrintedRoot']]
        visible_descriptions={t.get('TriggerDescription','') for t in source['triggers'] if t.get('Static')!='True' and not t.get('sourceSVar')}
        if not matches and len(visible_descriptions)==1 and not trigger.get('sourceSVar'):
            if len(printed)==1:matches=printed
            elif len(native)==1:matches=native
        if len(matches)==1:trigger_map[desc]=matches[0]['Id'];counts['trigger exact']+=1
        else:missing.append(dict(name=name,kind='trigger',description=desc,matches=[r['Id'] for r in matches],native=[dict(id=r['Id'],text=r['EnglishText']) for r in native]))
    bindings['descriptions']=description_map;bindings['triggerDescriptions']=trigger_map;bindings['manaDescriptions']=mana_map
    apis=collections.defaultdict(list)
    for a in source['abilities']:
        desc=a['description']
        if a['activated'] and not a['mana'] and desc in description_map:apis[a['api']].append(description_map[desc])
    for api,ids in apis.items():
        if len(set(ids))==1:activated[api]=ids[0]
    bindings.pop('trigger',None)
    if len(set(trigger_map.values()))==1:bindings['trigger']=next(iter(trigger_map.values()))
    card['targetPromptId']=10
    if name=='Bojuka Bog':card['targetPromptId']=1019
    c=dict(db.execute('SELECT * FROM Cards WHERE GrpId=?',(card['grpId'],)).fetchone())
    for pair in filter(None,c['AbilityIdToLinkedTokenGrpId'].split(',')):
        raw=pair.split(':');
        if len(raw)==2:tokens_linked[int(raw[1])].append(dict(name=name,abilityId=int(raw[0])))
    # All printed abilities remain available for the native card and its tooltip.
    card['nativeAbilityTexts']={str(r['Id']):r['EnglishText'] for r in rows}
    keyword_map={}
    for keyword in source.get('keywords',[]):
        base=keyword.split(':',1)[0]
        matches=[r for r in rows if r['PrintedRoot'] and normalized(r['EnglishText'],name)==normalized(base,name)]
        if len(matches)==1:keyword_map[re.sub(r'[^A-Z0-9]','',base.upper())]=matches[0]['Id']
    bindings['keywords']=keyword_map
    for ability in source['abilities']:
        if ability.get('api')!='Charm':continue
        parents=[r for r in rows if r['PrintedRoot'] and r['ModalChildIds']]
        candidates=[]
        for parent in parents:
            ids={int(x) for x in re.findall(r'\d+',parent['ModalChildIds'])};children=[r for r in rows if r['Id'] in ids];mapped=[]
            for mode in ability.get('modes',[]):
                matched=[r for r in children if normalized(r['EnglishText'],name)==normalized(mode['description'],name)]
                if len(matched)==1:mapped.append(dict(forgeDescription=re.sub(r'\s+',' ',unicodedata.normalize('NFKC',mode['description'])).strip(),nativeAbilityId=matched[0]['Id']))
            if len(mapped)==len(ability.get('modes',[])) and mapped:candidates.append(dict(parentAbilityId=parent['Id'],choices=mapped))
        if len(candidates)==1:card['modalBinding']=candidates[0];counts['modal cards bound']+=1
        else:modal_missing.append(dict(name=name,source=ability.get('modes'),native=[dict(id=r['Id'],text=r['EnglishText'],children=r['ModalChildIds']) for r in parents]))

# Complete a role only when exact matches leave one source and one native slot.
# This covers split Forge subabilities represented by one printed native rule.
for name,source in projection['cards'].items():
    card=manifest['cards'][name];rows=ability_rows(card);binding=card['abilityBindings']
    trigger_descriptions={t.get('TriggerDescription','') for t in source['triggers'] if t.get('Static')!='True'}
    remaining_descriptions=trigger_descriptions-binding['triggerDescriptions'].keys();used=set(binding['triggerDescriptions'].values())
    native_triggers=[r for r in rows if r['Category']==2];unbound_native=[r for r in native_triggers if r['Id'] not in used]
    if len(remaining_descriptions)==len(unbound_native)==1 and len(trigger_descriptions)==len(native_triggers):
        desc=next(iter(remaining_descriptions));binding['triggerDescriptions'][desc]=unbound_native[0]['Id']
        missing=[m for m in missing if not(m['name']==name and m['kind']=='trigger' and m['description']==desc)];counts['one remaining native/source trigger slot']+=1
    for mana in (False,True):
        all_source=[a for a in source['abilities'] if a['activated'] and a['mana']==mana]
        native=[r for r in rows if r['PrintedRoot'] and r['Category']==1 and bool(r['SubCategory']==1)==mana]
        unbound=[a for a in all_source if a['description'] not in binding['descriptions']]
        used={binding['descriptions'].get(a['description']) for a in all_source}
        remaining=[r for r in native if r['Id'] not in used]
        if len(unbound)==len(remaining)==1 and len(all_source)==len(native):
            a=unbound[0];desc=a['description'];id=remaining[0]['Id'];binding['descriptions'][desc]=id
            if mana:binding['manaDescriptions'][desc]=id
            else:binding['activated'][a['api']]=id
            missing=[r for r in missing if not (r['name']==name and r['description']==desc and r['kind']==('mana' if mana else 'activated'))]
            counts['one remaining native/source slot']+=1

for name,source in projection['cards'].items():
    binding=manifest['cards'][name]['abilityBindings'];aliases=collections.defaultdict(list)
    for a in source['abilities']:
        if a['activated'] and a['description'] in binding['descriptions']:
            aliases[a['params'].get('SpellDescription') or a['description']].append(binding['descriptions'][a['description']])
    for alias,ids in aliases.items():
        if len(set(ids))==1:binding['descriptions'][alias]=ids[0]

emblem_missing=[]
for name,source in projection['cards'].items():
    for emblem in source.get('emblems',[]):
        parent=manifest['cards'][name];bindings=parent['abilityBindings'];root_id=bindings['descriptions'].get(emblem['sourceAbilityDescription'])
        if root_id is None:emblem_missing.append(dict(name=name,reason='No source-bound creating ability'));continue
        root=next((r for r in ability_rows(parent) if r['Id']==root_id),None)
        ids={int(x) for x in re.findall(r'\d+',root['HiddenAbilityIds'] or '')} if root else set();native=[r for r in ability_rows(parent) if r['Id'] in ids]
        trigger_map={};selected=[]
        for trigger in emblem['triggers']:
            if trigger.get('Static')=='True':continue
            desc=trigger.get('TriggerDescription','');matches=[r for r in native if r['Category']==2 and normalized(r['EnglishText'],name)==normalized(desc,name)]
            role=[r for r in native if r['Category']==2]
            if not matches and len(role)==len(emblem['triggers'])==1:matches=role
            if len(matches)!=1:emblem_missing.append(dict(name=name,description=desc,reason='Emblem trigger not uniquely bound'));continue
            trigger_map[desc]=matches[0]['Id'];selected.append(matches[0]['Id'])
        statics=emblem['statics'];native_statics=[r for r in native if r['Category']==3]
        if len(statics)!=len(native_statics):emblem_missing.append(dict(name=name,reason='Emblem static ability count differs from original native child graph'))
        else:selected.extend(r['Id'] for r in native_statics)
        if not selected:emblem_missing.append(dict(name=name,reason='No emblem rules bound'));continue
        manifest['cards']['emblem:'+name]=dict(grpId=2,titleId=parent['titleId'],types=[],subtypes=[],supertypes=[],colors=[],color='Colorless',colorIdentity=[],genericCost=0,abilityId=selected[0],abilityIds=sorted(set(selected)),token=False,admitted=False,emblemPresentation=True,parentName=name,sourceEmblemName=emblem['name'],sourceCreatingAbilityId=root_id,targetPromptId=10,abilityBindings=dict(triggerDescriptions=trigger_map),bindingBasis='Original Forge emblem creator, original native hidden ability graph and GRE WellKnownCatalogId.Emblem=2')
        counts['emblem mapped']+=1

# Resolve tokens against actual source-card links first. Source tokens share
# names across printed variants; color, body, subtype and printed keywords must
# match rather than selecting by name alone.
enums={(r['Type'],r['Value']):r['Loc'] for r in db.execute('SELECT e.Type,e.Value,l.Loc FROM Enums e JOIN Localizations_enUS l ON e.LocId=l.LocId AND l.Formatted=1')}
def values(kind,text):return [enums[kind,int(x)] for x in filter(None,text.split(','))]
tokens=[dict(r) for r in db.execute('SELECT c.*,l.Loc AS EnglishName FROM Cards c JOIN Localizations_enUS l ON c.TitleId=l.LocId AND l.Formatted=1 WHERE c.IsToken=1')]
unbound_tokens=[]
for script,source in projection['tokens'].items():
    if source.get('missing'):unbound_tokens.append(dict(script=script,reason='Missing pinned Forge token'));continue
    name=source['name'].removesuffix(' Token')
    candidates=[]
    for row in tokens:
        if set(values('CardType',row['Types']))!=set(source['coreTypes']) or set(values('SubType',row['Subtypes']))!=set(source['subtypes']):continue
        mask=sum({'White':1,'Blue':2,'Black':4,'Red':8,'Green':16,'Colorless':0}.get(c,0) for c in values('CardColor',row['Colors'] or row['FrameColors']))
        body=lambda value:'' if value is None else str(value)
        if mask!=source['colorMask'] or body(row['Power'])!=body(source.get('power')) or body(row['Toughness'])!=body(source.get('toughness')):continue
        ids=[int(v.split(':')[0]) for v in filter(None,row['AbilityIds'].split(','))]
        texts=[r[0] for id in ids for r in db.execute('SELECT l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId AND l.Formatted=1 WHERE a.Id=?',(id,))]
        keywords={normalized(k,name) for k in source['keywords']}
        if not keywords.issubset({normalized(t,name) for t in texts}):continue
        candidates.append(row)
    linked=[r for r in candidates if r['GrpId'] in tokens_linked]
    if source.get('parentTokenScript') and 'token:'+source['parentTokenScript'] in manifest['cards']:
        parent=manifest['cards']['token:'+source['parentTokenScript']];raw=db.execute('SELECT LinkedFaceGrpIds FROM Cards WHERE GrpId=?',(parent['grpId'],)).fetchone()[0];face_ids={int(x) for x in re.findall(r'\d+',raw)}
        linked=[r for r in candidates if r['GrpId'] in face_ids]
    candidates=linked or candidates
    if not candidates:unbound_tokens.append(dict(script=script,source=source));continue
    row=min(candidates,key=lambda r:r['GrpId']);ids=[int(v.split(':')[0]) for v in filter(None,row['AbilityIds'].split(','))]
    manifest['cards']['token:'+script]=dict(grpId=row['GrpId'],titleId=row['TitleId'],types=values('CardType',row['Types']),subtypes=values('SubType',row['Subtypes']),supertypes=values('SuperType',row['Supertypes']),color={0:'Colorless',1:'White',2:'Blue',4:'Black',8:'Red',16:'Green'}.get(source['colorMask'],'Colorless'),colors=values('CardColor',row['Colors'] or row['FrameColors']),colorIdentity=[],genericCost=0,abilityId=ids[0] if ids else 0,abilityIds=ids,token=True,admitted=False,forgeTokenScript=script,nativeLinks=tokens_linked.get(row['GrpId'],[]),bindingBasis='Original native source links and exact token body, color, types, subtypes and printed keywords',equivalentNativeCandidates=sorted(r['GrpId'] for r in candidates))
    counts['token bound']+=1
for script,source in projection['tokens'].items():
    key='token:'+script
    if key not in manifest['cards']:continue
    card=manifest['cards'][key];rows=ability_rows(card);desc_map={};api_map={}
    for a in source['abilities']:
        if not a['activated']:continue
        native=[r for r in rows if r['Category']==1 and bool(r['SubCategory']==1)==a['mana']]
        wanted={normalized(a['description'],source['name']),normalized(a['params'].get('SpellDescription',''),source['name'])}
        matches=[r for r in native if wanted & descriptions(r['EnglishText'],source['name'])]
        role=[b for b in source['abilities'] if b['activated'] and b['mana']==a['mana']]
        if not matches and len(native)==len(role)==1:matches=native
        if len(matches)!=1:unbound_tokens.append(dict(script=script,ability=a['description'],reason='Token ability has no unique native binding'));continue
        desc_map[a['description']]=matches[0]['Id'];desc_map[a['params'].get('SpellDescription') or a['description']]=matches[0]['Id'];api_map[a['api']]=matches[0]['Id']
    trigger_map={};keyword_map={}
    for keyword in source.get('keywords',[]):
        base=keyword.split(':',1)[0];matches=[r for r in rows if r['PrintedRoot'] and normalized(r['EnglishText'],source['name'])==normalized(base,source['name'])]
        if len(matches)==1:keyword_map[re.sub(r'[^A-Z0-9]','',base.upper())]=matches[0]['Id']
    for trigger in source.get('triggers',[]):
        desc=trigger.get('TriggerDescription','');matches=[r for r in rows if r['Category']==2 and normalized(r['EnglishText'],source['name'])==normalized(desc,source['name'])]
        if 'Decayed' in source.get('keywords',[]) and trigger.get('Mode')=='Attacks' and trigger.get('Secondary')=='True' and desc=='When a creature with decayed attacks, sacrifice it at end of combat.':
            # Pinned CardFactoryUtil creates this secondary attack trigger and
            # the separate Phase/EndCombat sacrifice. Native Decayed's hidden
            # ability is the latter, not a second printed token rule.
            roots=[r for r in rows if r['PrintedRoot'] and r['EnglishText']=='Decayed']
            delayed=[r for r in rows if not r['PrintedRoot'] and r['Category']==2 and r['EnglishText']=='Sacrifice it at end of combat.']
            if len(roots)==len(delayed)==1:
                trigger_map[desc]=roots[0]['Id'];trigger_map['At end of combat, sacrifice CARDNAME.']=delayed[0]['Id'];counts['token decayed attack and delayed sacrifice']+=1;continue
        if len(matches)==1:trigger_map[desc]=matches[0]['Id'];counts['token trigger exact']+=1
        else:unbound_tokens.append(dict(script=script,trigger=desc,reason='Token trigger has no unique native binding'))
    card['abilityBindings']=dict(descriptions=desc_map,activated=api_map,triggerDescriptions=trigger_map,keywords=keyword_map)
manifest['cardNameIds']={r['Name']:r['TitleId'] for r in db.execute('SELECT l.Loc AS Name,MIN(c.TitleId) AS TitleId FROM Cards c JOIN Localizations_enUS l ON c.TitleId=l.LocId AND l.Formatted=1 WHERE c.IsToken=0 GROUP BY l.Loc')}
for kind in ('CardType','SubType','SuperType'):
    target=manifest['typeEnumIds'].setdefault(kind,{})
    for row in db.execute('SELECT e.Value,l.Loc FROM Enums e JOIN Localizations_enUS l ON e.LocId=l.LocId AND l.Formatted=1 WHERE e.Type=?',(kind,)):
        name=row['Loc'].lower();value=row['Value']
        if name in target and target[name]!=value:raise ValueError('Conflicting native type enum '+name)
        target[name]=value
for color in ('white','blue','black','red','green'):
    text='Hexproof from '+color
    ids=[r[0] for r in db.execute('SELECT a.Id FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId AND l.Formatted=1 WHERE a.Category=3 AND l.Loc=?',(text,))]
    if len(ids)!=1:raise ValueError('Ambiguous original keyword '+text)
    manifest['keywordAbilityIds']['hexproof:'+color]=ids[0]
if 'Underworld Breach' in projection['cards']:
    # Its owned static ability explicitly references this generic keyword;
    # individual escape costs are supplied by the original Forge keyword.
    roots=ability_rows(manifest['cards']['Underworld Breach'])
    escapes=[r for r in roots if r['Category']==8 and r['EnglishText']=='Escape']
    if len(escapes)!=1:raise ValueError('Underworld Breach has no unique linked native Escape identity')
    manifest['keywordAbilityIds']['escape']=escapes[0]['Id']
if 'Narset Transcendent' in projection['cards']:
    # Narset's owned native ability graph links the same generic Rebound rule
    # used by a spell after Forge grants that keyword. No per-spell guess.
    rebounds=[r for r in ability_rows(manifest['cards']['Narset Transcendent']) if r['Category']==3 and r['EnglishText']=='Rebound']
    if len(rebounds)!=1:raise ValueError('Narset has no unique linked native Rebound identity')
    rebound=rebounds[0]['Id'];manifest['keywordAbilityIds']['rebound']=rebound
    delayed=[r for r in ability_rows(manifest['cards']['Narset Transcendent']) if r['Category']==2 and 'upkeep' in r['EnglishText'].lower() and 'without paying' in r['EnglishText'].lower()]
    if len(delayed)!=1:raise ValueError('Rebound has no unique linked native delayed trigger')
    for card in manifest['cards'].values():
        card.setdefault('abilityBindings',{}).setdefault('keywords',{})['REBOUND']=rebound
        card['abilityBindings']['reboundDelayedTrigger']=delayed[0]['Id']
manifest['humanChoiceBindingProvenance']=dict(projectionSha256=hashlib.sha256(args.projection.read_bytes()).hexdigest(),databaseSha256=hashlib.sha256(args.database.read_bytes()).hexdigest(),source=provenance,gameplayVerified=False)
args.report.write_text(json.dumps(dict(counts=counts,missing=missing,unboundTokens=unbound_tokens,missingModes=modal_missing,missingEmblems=emblem_missing),indent=2))
print(json.dumps(dict(counts=counts,missing=len(missing),unboundTokens=len(unbound_tokens),missingModes=len(modal_missing),missingEmblems=len(emblem_missing))))

if missing or unbound_tokens or modal_missing or emblem_missing:raise SystemExit(1)
pending=args.output.with_suffix(args.output.suffix+'.pending')
pending.write_text(json.dumps(manifest,indent=2));pending.replace(args.output)
