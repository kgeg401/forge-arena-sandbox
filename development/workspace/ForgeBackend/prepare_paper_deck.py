"""Prepare explicitly requested paper identities against local Forge projections.

The extended SQLite file is PRIVATE tooling input for the existing binder, never
an installed or distributed game database. Runtime additions are separate records.
"""
import argparse,copy,hashlib,json,re,sqlite3
from pathlib import Path


def native_mana_text(symbols):
    # Native sorting and icon lookup expect parenthesized hybrid/Phyrexian costs.
    return ''.join('o'+('('+v+')' if '/' in v else v) for v in symbols)


def prepare(a):
    a.output.mkdir(parents=True,exist_ok=False)
    projection=json.loads(a.projection.read_text());base=json.loads(a.manifest.read_text())
    old=json.loads(a.experimental.read_text());added=json.loads(a.additions.read_text())
    hashes=json.loads(a.scripts.read_text());audit=json.loads(a.audit.read_text())
    assert hashes.keys()<=projection['cards'].keys()
    db=sqlite3.connect(a.output/'binding-only.sqlite');source=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True)
    source.backup(db);source.close();db.row_factory=sqlite3.Row
    enums={(r['Type'],r['Loc']):r['Value'] for r in db.execute('SELECT e.Type,e.Value,l.Loc FROM Enums e JOIN Localizations_enUS l ON e.LocId=l.LocId AND l.Formatted=1')}
    def values(kind,words):return ','.join(str(enums[kind,w]) for w in words)
    def insert(table,row):
        db.execute('INSERT INTO '+table+' ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',list(row.values()))
    extension=copy.deepcopy(old.get('paperExtension',dict(schema=1,localizations={},abilities=[])))
    locs=extension['localizations'];abilities=extension['abilities']
    # An append uses its pinned parent binder, preserving every existing identity.
    for key,text in locs.items():
        row=db.execute('SELECT Loc FROM Localizations_enUS WHERE LocId=? AND Formatted=1',(int(key),)).fetchone()
        assert row and row['Loc']==text,'Parent paper binder does not match its metadata'
    for name,card in old['cards'].items():
        if card.get('paperOnly'):
            row=db.execute('SELECT TitleId,AbilityIds FROM Cards WHERE GrpId=?',(card['grpId'],)).fetchone()
            assert row and row['TitleId']==card['titleId'] and row['AbilityIds']==','.join(map(str,card['abilityIds'])),'Parent paper card differs: '+name
    loc_id=max([1000000000]+[int(v) for v in locs]);ability_id=max([2100000]+[v['id'] for v in abilities])
    grp_id=max([2000000]+[c['grpId'] for c in base['cards'].values() if c.get('paperOnly')])
    def loc(text):
        nonlocal loc_id
        loc_id+=1;assert not db.execute('SELECT 1 FROM Localizations WHERE LocId=?',(loc_id,)).fetchone()
        locs[str(loc_id)]=text;insert('Localizations',dict(LocId=loc_id))
        for formatted in (0,1):insert('Localizations_enUS',dict(LocId=loc_id,Formatted=formatted,Loc=text))
        return loc_id
    def ability(text,category=3,sub=0,base_id=None):
        nonlocal ability_id
        ability_id+=1;assert not db.execute('SELECT 1 FROM Abilities WHERE Id=?',(ability_id,)).fetchone()
        row=dict(db.execute('SELECT * FROM Abilities WHERE Id=1001').fetchone())
        row.update(Id=ability_id,BaseId=base_id or ability_id,TextId=loc(text),Category=category,SubCategory=sub,OldSchoolManaText='',HiddenAbilityIds='',EmbeddedActiveAbilityIds='',ReferencedAbilityIds='',ModalChildIds='',ModalParentIds='',HiddenByAbilityIds='',EmbeddedIntoAbilityIds='')
        insert('Abilities',row);abilities.append(dict(id=ability_id,baseId=row['BaseId'],textId=row['TextId'],category=category,subCategory=sub));return ability_id
    def link(identity,**fields):
        names={'hiddenAbilityIds':'HiddenAbilityIds','modalChildIds':'ModalChildIds','modalParentIds':'ModalParentIds'}
        row=next(a for a in abilities if a['id']==identity)
        for key,ids in fields.items():
            db.execute('UPDATE Abilities SET '+names[key]+'=? WHERE Id=?',(','.join(map(str,ids)),identity));row[key]=ids
    result=copy.deepcopy(old)
    for name,card in added['cards'].items():
        if name not in result['cards'] and name not in base['cards']:result['cards'][name]=card;base['cards'][name]=copy.deepcopy(card)
    for i,name in enumerate(sorted(audit['outsideArena']),1):
        s=projection['cards'][name];grp=grp_id+i
        assert name not in base['cards'] and not db.execute('SELECT 1 FROM Cards WHERE GrpId=?',(grp,)).fetchone()
        raw=(s.get('oracleText') or '').replace('\\n','\n');title=loc(name)
        typ=' '.join(s['supertypes']+s['coreTypes']);subtypes=' '.join(s['subtypes'])
        type_text=loc(typ+(' — '+subtypes if subtypes else ''));subtype_text=loc(subtypes)
        root=ability(raw);hidden=[]
        for v in s['abilities']+s.get('latentAbilities',[]):
            if v.get('activated'):hidden.append(ability(v['description'],1,int(v['mana'])))
        # One printed rule can have separate engine triggers (enters/damage,
        # attacks/blocks). Both resolve through the same printed ability.
        triggers=dict.fromkeys(v['TriggerDescription'] for v in s['triggers']+s.get('latentTriggers',[]) if v.get('Static')!='True' and v.get('TriggerDescription'))
        for text in triggers:hidden.append(ability(text,2))
        modes=[v for v in s['abilities'] if v.get('spell') and v.get('modes')]
        if modes:
            if len(modes)!=1:raise ValueError('Paper card needs an unambiguous modal spell parent: '+name)
            children=[ability(v['description']) for v in modes[0]['modes']]
            link(root,modalChildIds=children)
            for child in children:link(child,modalParentIds=[root])
        printed_keywords=[]
        for v in s['keywords']:
            word=v.split(':',1)[0];native=base['keywordAbilityIds'].get(word.lower())
            identity=ability(word,3,base_id=native)
            if native:printed_keywords.append(identity)
            else:hidden.append(identity)
        link(root,hiddenAbilityIds=hidden)
        symbols=re.findall(r'\{([^}]+)\}',s['manaCost']);mana=native_mana_text(symbols)
        colors=[n for bit,n in ((1,'White'),(2,'Blue'),(4,'Black'),(8,'Red'),(16,'Green')) if s['colorMask']&bit]
        identity=[n for bit,n in ((1,'White'),(2,'Blue'),(4,'Black'),(8,'Red'),(16,'Green')) if s['colorIdentityMask']&bit]
        ci=[{'White':'W','Blue':'U','Black':'B','Red':'R','Green':'G'}[n] for n in identity]
        card=dict(grpId=grp,titleId=title,types=s['coreTypes'],subtypes=s['subtypes'],supertypes=s['supertypes'],genericCost=sum(int(v) for v in symbols if v.isdecimal()),color=colors[0] if colors else 'Colorless',colors=colors,colorIdentity=ci,abilityId=root,abilityIds=[root]+printed_keywords,forgeScript='',forgeScriptSha256=hashes[name],token=False,admitted=True,experimental=True,verified=False,paperOnly=True,commanderAdmitted=name in getattr(a,'commanders',['Darien, King of Kjeldor']),abilityBindings={},targetPromptId=10)
        # Script paths come from the original source identities, not filenames
        # guessed from card titles. The caller supplies the real indexed paths.
        card['forgeScript']=a.script_paths[name]
        card['paperDefinition']=dict(typeTextId=type_text,subtypeTextId=subtype_text,manaText=mana,manaValue=sum(int(v) if v.isdecimal() else int(v!='X') for v in symbols),colorIdentity=identity,power=s.get('power'),toughness=s.get('toughness'),oracleText=raw,hiddenAbilityIds=hidden,artStatus='No native Arena art; use the original missing-art placeholder')
        row=dict(db.execute('SELECT * FROM Cards WHERE GrpId=6873').fetchone())
        row.update(GrpId=grp,ArtId=0,ArtPath='',TitleId=title,AltTitleId=0,InterchangeableTitleId=0,FlavorTextId=0,ReminderTextId=0,TypeTextId=type_text,SubtypeTextId=subtype_text,OldSchoolManaText=mana,Power=s.get('power') or '',Toughness=s.get('toughness') or '',Types=values('CardType',s['coreTypes']),Subtypes=values('SubType',s['subtypes']),Supertypes=values('SuperType',s['supertypes']),Colors=values('CardColor',colors),ColorIdentity=values('CardColor',identity),FrameColors=values('CardColor',colors),IndicatorColors='',AbilityIds=str(root),HiddenAbilityIds=','.join(map(str,hidden)),LinkedFaceGrpIds='',AbilityIdToLinkedTokenGrpId='',AbilityIdToLinkedConjurations='',IsToken=0,IsPrimaryCard=1,IsRebalanced=0,IsDigitalOnly=0,ExpansionCode='ANA',CollectorNumber=str(i),CollectorSuffix='')
        row['AbilityIds']=','.join(map(str,card['abilityIds']))
        insert('Cards',row);base['cards'][name]=copy.deepcopy(card);result['cards'][name]=card;result['blockedCards'].pop(name,None)
    db.commit();db.close()
    extension.update(schema=1,localizations=locs,abilities=abilities,source='Explicit paper-deck extension generated from the pinned local Forge runtime; these are not original Arena identities',deckSha256=audit['sha256'])
    result['paperExtension']=extension
    base['paperExtension']=result['paperExtension'];base['researchOnly']=True
    projection['provenance']=dict(forgeJarSha256=a.forge_hash,sourceScriptHashes=hashes,paperPresentationExtension=True)
    (a.output/'projection.json').write_text(json.dumps(projection,indent=2));(a.output/'base-manifest.json').write_text(json.dumps(base,indent=2));(a.output/'experimental-unbound.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(paperCards=len(audit['outsideArena']),experimentalNames=len(result['cards']),output=str(a.output))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('projection','manifest','experimental','additions','scripts','script-paths','audit','database','forge-jar','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--commander',dest='commanders',action='append',default=['Darien, King of Kjeldor'])
    a=p.parse_args();a.forge_hash=hashlib.sha256(a.forge_jar.read_bytes()).hexdigest();a.script_paths=json.loads(a.script_paths.read_text());prepare(a)
