"""Merge packaged starter decks/collection before the native profile owner starts."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
from tester_common import no_links

PILES=('main','sideboard','commander','companion')

def deck_signature(deck):
    value={k:deck.get(k) for k in ('name','format',*PILES)}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def counts(value,known,limit):
    if not isinstance(value,dict):raise ValueError('Invalid starter card counts')
    for key,count in value.items():
        if not isinstance(key,str) or not key.isdecimal() or str(int(key))!=key or key not in known or type(count) is not int or not 1<=count<=limit:
            raise ValueError('Invalid or unavailable starter card: '+str(key))

def load_content(app,lab):
    content=read(Path(app)/'starter-content.json')
    if content.get('schema')!=1 or not isinstance(content.get('id'),str) or not content['id'] or not isinstance(content.get('decks'),list):
        raise ValueError('Invalid starter content')
    known={str(c['grpId']) for c in read(Path(lab)/'deck-catalog.json')['cards']}
    retired=content.get('retiredCards',[])
    if not isinstance(retired,list) or any(not isinstance(k,str) or not k.isdecimal() or str(int(k))!=k or not 2000000<=int(k)<2100000 or k in known for k in retired):
        raise ValueError('Invalid retired custom card identities')
    signatures=content.get('retiredStarterDeckSignatures',{})
    if not isinstance(signatures,dict) or any(not isinstance(k,str) or not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v) for k,v in signatures.items()):
        raise ValueError('Invalid retired starter deck signatures')
    counts(content.get('cards'),known,100000)
    keys=set();names=set()
    for deck in content['decks']:
        if not isinstance(deck,dict):raise ValueError('Invalid starter deck')
        key=deck.get('key');name=deck.get('name')
        if not isinstance(key,str) or not key or key in keys or not isinstance(name,str) or not 1<=len(name.strip())<=80 or name.casefold() in names or deck.get('format') not in ('practice','arena-brawl'):
            raise ValueError('Invalid starter deck')
        keys.add(key);names.add(name.casefold())
        for pile in PILES:counts(deck.get(pile),known,999)
        total=sum(sum(deck[p].values()) for p in PILES)
        if not 1<=total<=1000:raise ValueError('Invalid starter deck size')
    return content

def commit(path,state):
    no_links(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.starter-pending')
    no_links(temporary)
    created=False
    try:
        with temporary.open('x',encoding='utf8') as stream:
            created=True
            json.dump(state,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        if path.exists():
            backup=path.with_name(path.name+'.bak');no_links(backup);shutil.copy2(path,backup)
        os.replace(temporary,path)
    finally:
        if created:temporary.unlink(missing_ok=True)

def seed_profile(app,lab):
    app=Path(app);lab=Path(lab);profile=lab/'local-profile';no_links(profile)
    content=load_content(app,lab)
    decks_path=profile/'decks.json';packs_path=profile/'packs.json'
    for path in (decks_path,packs_path):no_links(path)
    decks=read(decks_path) if decks_path.exists() else dict(schema=1,revision=0,decks=[])
    packs=read(packs_path) if packs_path.exists() else dict(schema=1,profileId=str(uuid.uuid4()),revision=0,packs={},cards={},openings=[])
    # Validate both profiles before writing either; malformed user data is preserved.
    if decks.get('schema')!=1 or not isinstance(decks.get('decks'),list) or any(not isinstance(d,dict) or not isinstance(d.get('name'),str) for d in decks['decks']):
        raise ValueError('Invalid saved deck library; original preserved')
    if packs.get('schema')!=1 or not isinstance(packs.get('packs'),dict) or not isinstance(packs.get('cards'),dict) or not isinstance(packs.get('openings'),list) or not isinstance(packs.get('starterGrants',{}),dict):
        raise ValueError('Invalid saved collection; original preserved')
    for state in (decks,packs):
        if type(state.get('revision')) is not int or not 0<=state['revision']<2147483647 or not isinstance(state.get('starterContent',[]),list) or any(not isinstance(x,str) for x in state.get('starterContent',[])):
            raise ValueError('Invalid saved profile receipt; original preserved')
    if any(type(v) is not int or v<0 for v in packs['cards'].values()):raise ValueError('Invalid saved collection count; original preserved')
    retired=set(content.get('retiredCards',[]));signatures=content.get('retiredStarterDeckSignatures',{})
    retired_decks=0;removed_copies=0;edited_decks=0;retained=[]
    for deck in decks['decks']:
        # Only an untouched supplied custom deck is retired wholesale.
        # User edits retain every real card and lose only the retired printing.
        if signatures.get(deck.get('id'))==deck_signature(deck):retired_decks+=1;continue
        changed=False
        for pile in PILES:
            if not isinstance(deck.get(pile),dict):raise ValueError('Invalid saved deck piles; original preserved')
            for card in retired:
                if card in deck[pile]:deck[pile].pop(card);changed=True
        if changed:edited_decks+=1
        retained.append(deck)
    decks['decks']=retained
    for card in retired:removed_copies+=packs['cards'].pop(card,0)
    retired_grants=False
    for grant in packs.get('starterGrants',{}).values():
        if not isinstance(grant,dict):raise ValueError('Invalid saved starter grant; original preserved')
        for card in retired:
            if card in grant:grant.pop(card);retired_grants=True
    if retired_decks or edited_decks:decks['revision']+=1
    if removed_copies or retired_grants:packs['revision']+=1
    added=0;granted=0
    if content['id'] not in decks.get('starterContent',[]):
        names={d['name'].casefold() for d in decks['decks']};ids={d.get('id') for d in decks['decks']}
        for entry in content['decks']:
            if entry['name'].casefold() in names:continue
            deck={k:copy.deepcopy(entry[k]) for k in ('name','format',*PILES)}
            deck['id']=str(uuid.uuid5(uuid.NAMESPACE_URL,'forge-arena/starter/'+entry['key']))
            if deck['id'] in ids:raise ValueError('Starter deck ID conflicts with saved data')
            decks['decks'].append(deck);names.add(deck['name'].casefold());ids.add(deck['id']);added+=1
        decks.setdefault('starterContent',[]).append(content['id']);decks['revision']+=1
    if content['id'] not in packs.get('starterContent',[]):
        delta={}
        for key,count in content['cards'].items():
            before=packs['cards'].get(key,0);packs['cards'][key]=max(before,count)
            if count>before:delta[key]=count-before;granted+=count-before
        packs.setdefault('starterGrants',{})[content['id']]=delta
        packs.setdefault('starterContent',[]).append(content['id']);packs['revision']+=1
    # Each receipt commits with its data, so a partial I/O failure can be retried safely.
    if not decks_path.exists() or read(decks_path)!=decks:commit(decks_path,decks)
    if not packs_path.exists() or read(packs_path)!=packs:commit(packs_path,packs)
    return dict(decksAdded=added,collectionCopiesAdded=granted,starter=content['id'],retiredDecks=retired_decks,retiredCopies=removed_copies,editedDecksCleaned=edited_decks)
