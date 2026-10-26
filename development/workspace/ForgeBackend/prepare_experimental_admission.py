"""Map explicitly requested deck cards for unverified local play, not promotion."""
from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json,re,sqlite3,zipfile
from arena_catalog import clean_name,indexed_printings
from build_card_coverage import norm,modal_binding,mode_text
from runtime_paths import DB,FORGE_SCRIPTS,SUPPORT_POLICY


def prepare(decks_path,output):
    if output.exists():raise ValueError('Preserve previous experimental inventories; select a fresh output')
    decks=json.loads(decks_path.read_text(encoding='utf-8-sig'))
    policy=json.loads(SUPPORT_POLICY.read_text())
    verified=set(policy['verifiedNames']);needed={d['commander'] for d in decks.values()}|{c['name'] for d in decks.values() for c in d['cards']}
    commanders={d['commander'] for d in decks.values()}
    db=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    enums={(r['Type'],r['Value']):r['Loc'] for r in db.execute('SELECT e.Type,e.Value,l.Loc FROM Enums e JOIN Localizations_enUS l ON l.LocId=e.LocId AND l.Formatted=1')}
    def enum_values(kind,text):return [enums[kind,int(v)] for v in filter(None,text.split(','))]
    rows={r['GrpId']:dict(r) for r in db.execute('SELECT c.*,l.Loc AS EnglishName FROM Cards c JOIN Localizations_enUS l ON l.LocId=c.TitleId AND l.Formatted=1')}
    groups=defaultdict(list)
    for row in indexed_printings(rows):
        if not row['IsRebalanced']:groups[clean_name(row['EnglishName'])].append(row)
    scripts=defaultdict(list);source={}
    with zipfile.ZipFile(FORGE_SCRIPTS) as archive:
        for path in archive.namelist():
            if not path.endswith('.txt'):continue
            raw=archive.read(path);text=raw.decode('utf-8-sig');names=re.findall(r'^Name:(.+)$',text,re.M)
            if not names:continue
            source[path]=(text,hashlib.sha256(raw).hexdigest())
            for name in names:scripts[norm(name.strip())].append(path)
    cards={};blocked={}
    for name in sorted(needed-verified):
        options=groups.get(name,[]);matches=sorted(set(scripts.get(norm(name),[])))
        if not options:blocked[name]='No installed Arena primary printing/presentation; rules-only Forge availability is insufficient';continue
        if len(matches)!=1:blocked[name]='Requires exactly one pinned Forge script identity';continue
        row=min(options,key=lambda r:r['GrpId']);text,digest=source[matches[0]]
        identity=[{'1':'W','2':'U','3':'B','4':'R','5':'G'}[v] for v in filter(None,row['ColorIdentity'].split(',')) if v in ('1','2','3','4','5')]
        core=enum_values('CardType',row['Types']);supers=enum_values('SuperType',row['Supertypes']);subtypes=enum_values('SubType',row['Subtypes'])
        if name in commanders and ('Legendary' not in supers or not {'Creature','Planeswalker'} & set(core)):blocked[name]='Brawl commander requires a mapped legendary creature or planeswalker';continue
        ability_ids=[int(v.split(':')[0]) for v in filter(None,row['AbilityIds'].split(','))]
        colors=[v for v in enum_values('CardColor',row['Colors']) if v in ('White','Blue','Black','Red','Green')]
        # The native card database owns printed X/hybrid costs. This numeric
        # field is legacy presentation metadata, never payment permission.
        native_cost=row['OldSchoolManaText'] or ''
        card=dict(grpId=row['GrpId'],titleId=row['TitleId'],types=core,subtypes=subtypes,supertypes=supers,genericCost=sum(map(int,re.findall(r'o([0-9]+)',native_cost))),
                  printedManaText=native_cost,color=colors[0] if colors else 'Colorless',colors=colors,colorIdentity=identity,
                  abilityId=ability_ids[0] if ability_ids else 0,abilityIds=ability_ids,forgeScript=matches[0],forgeScriptSha256=digest,
                  token=False,admitted=True,candidate=False,experimental=True,verified=False,abilityBindings={},
                  coloredCost=[dict(color=color,count=native_cost.count('o'+letter)) for letter,color in [('W','White'),('U','Blue'),('B','Black'),('R','Red'),('G','Green')] if 'o'+letter in native_cost])
        if name in commanders:card['commanderAdmitted']=True
        binding=modal_binding(db,name,row,text)
        if binding:card['modalBinding']=binding
        # Bind only exact source descriptions; ambiguous or unmatched abilities
        # remain actual runtime gaps, not guessed IDs or hidden AI decisions.
        descriptions={}
        for ability in ability_ids:
            texts=list(db.execute('SELECT l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId AND l.Formatted=1 WHERE a.Id=?',(ability,)))
            if len(texts)==1:descriptions.setdefault(mode_text(texts[0][0],name),[]).append(ability)
        activated={}
        for line in text.splitlines():
            if not line.startswith('A:AB$'):continue
            fields={k.strip():v.strip() for part in line[2:].split('|') if '$' in part for k,v in [part.split('$',1)]}
            api=fields.get('AB');description=mode_text(fields.get('SpellDescription',''),name)
            ids=descriptions.get(description,[])
            if api and len(ids)==1:
                if api in activated:activated[api]=None
                else:activated[api]=ids[0]
        activated={k:v for k,v in activated.items() if v is not None}
        if activated:card['abilityBindings']['activated']=activated
        if name=='Bojuka Bog':
            # Source-validated named binding: Forge says "all cards from";
            # Arena's current oracle text says "target player's graveyard".
            # Pin both descriptions instead of fuzzy-matching other triggers.
            expected="When CARDNAME enters, exile all cards from target player's graveyard."
            native="When CARDNAME enters, exile target player's graveyard."
            trigger_lines=[line for line in text.splitlines() if line.startswith('T:')]
            matches=[ability for ability in ability_ids if [r[0] for r in db.execute('SELECT l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId AND l.Formatted=1 WHERE a.Id=?',(ability,))]==[native]]
            prompt=[r[0] for r in db.execute('SELECT l.Loc FROM Prompts p JOIN Localizations_enUS l ON p.LocId=l.LocId AND l.Formatted=1 WHERE p.Id=1019')]
            if len(trigger_lines)!=1 or not trigger_lines[0].endswith('TriggerDescription$ '+expected) or len(matches)!=1 or prompt!=['Target a player.']:
                raise ValueError('Bojuka Bog source trigger or native prompt changed')
            card['abilityBindings']['trigger']=matches[0]
            card['targetPromptId']=1019
            if 'A:AB$ Mana | Cost$ T | Produced$ B | SpellDescription$ Add {B}.' not in text.splitlines() or 1003 not in ability_ids:
                raise ValueError('Bojuka Bog fixed black mana source changed')
            card['manaColor']='Black'
            card['abilityId']=1003
        cards[name]=card
    result=dict(schema=1,enabled=True,status='User-authorized experimental admission; no gameplay verification or promotion claim',
                sourceDatabaseSha256=hashlib.sha256(DB.read_bytes()).hexdigest(),sourceForgeScriptsSha256=hashlib.sha256(FORGE_SCRIPTS.read_bytes()).hexdigest(),
                policySha256=hashlib.sha256(SUPPORT_POLICY.read_bytes()).hexdigest(),requestedDecksSha256=hashlib.sha256(decks_path.read_bytes()).hexdigest(),cards=cards,blockedCards=blocked)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(experimental=len(cards),verifiedUnchanged=len(verified),commanders=[n for n,c in cards.items() if c.get('commanderAdmitted')],blocked=blocked,output=str(output)),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--decks',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();prepare(a.decks,a.output)
