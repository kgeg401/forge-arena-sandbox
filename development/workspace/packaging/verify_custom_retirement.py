"""Retire only invented printings; retain real cards and user-edited decks."""
import copy,json,tempfile
from pathlib import Path
import starter_content as s
checks=[]
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
def read(p):return json.loads(p.read_text())
with tempfile.TemporaryDirectory(prefix='forge-retirement-') as scratch:
 root=Path(scratch);app=root/'app';lab=root/'lab';profile=lab/'local-profile'
 custom=dict(id='retired-deck',name='Supplied custom deck',format='arena-brawl',main={'1':98,'2000085':1},sideboard={},commander={'2':1},companion={})
 real={**copy.deepcopy(custom),'id':'keep','name':'Real deck','main':{'1':99}}
 content=dict(schema=1,id='retire-v1',decks=[],cards={},retiredCards=['2000085'],retiredStarterDeckSignatures={custom['id']:s.deck_signature(custom)})
 write(app/'starter-content.json',content);write(lab/'deck-catalog.json',dict(cards=[dict(grpId=1),dict(grpId=2)]))
 decks=dict(schema=1,revision=1,decks=[custom,real]);packs=dict(schema=1,profileId='own-identity',revision=1,packs={'own':3},openings=[{'own':'history'}],cards={'1':123,'2':1,'2000085':1},starterGrants={'old':{'1':10,'2000085':1}})
 write(profile/'decks.json',decks);write(profile/'packs.json',packs)
 result=s.seed_profile(app,lab);actual=read(profile/'decks.json');owned=read(profile/'packs.json')
 assert actual['decks']==[real] and result['retiredDecks']==1;checks.append('Only the untouched supplied custom deck is removed')
 assert owned['cards']=={'1':123,'2':1} and owned['starterGrants']['old']=={'1':10};checks.append('Only the invented printing and its grant are removed')
 assert all(owned[k]==packs[k] for k in ('profileId','packs','openings'));checks.append('Identity, unopened packs and history are preserved')
 before={p.name:p.read_bytes() for p in profile.iterdir()};s.seed_profile(app,lab);assert before=={p.name:p.read_bytes() for p in profile.iterdir()};checks.append('Retry is byte-identical')
 edited=copy.deepcopy(custom);edited['main']['1']=97;edited['favorite']=True;write(profile/'decks.json',dict(schema=1,revision=1,decks=[edited,real]))
 result=s.seed_profile(app,lab);expected=copy.deepcopy(edited);expected['main'].pop('2000085');assert read(profile/'decks.json')['decks']==[expected,real] and result['editedDecksCleaned']==1;checks.append('Edited decks keep all real cards and custom settings')
 bad=copy.deepcopy(content);bad['retiredCards']=['1'];write(app/'starter-content.json',bad);before={p.name:p.read_bytes() for p in profile.iterdir()}
 try:s.seed_profile(app,lab)
 except ValueError:pass
 else:raise AssertionError('Retired a real catalogue identity')
 assert before=={p.name:p.read_bytes() for p in profile.iterdir()};checks.append('A real catalogue identity cannot be retired by this migration')
print(json.dumps(dict(passed=True,checks=checks)))
