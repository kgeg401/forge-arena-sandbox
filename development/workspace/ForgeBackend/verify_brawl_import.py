"""Brawl deck boundary checks; no game or account is opened."""
from pathlib import Path
import json
from deck_import import parse_brawl,parse_deck

text=(Path(__file__).resolve().parents[1]/'decks/Brawl-Isamaru-Foundation.txt').read_text();checks=[]
def check(name,ok):
    if not ok:raise AssertionError(name)
    checks.append(name)
def rejects(name,content):
    try:parse_brawl(content)
    except ValueError:check(name,True)
    else:raise AssertionError('Accepted invalid Brawl list: '+name)
deck=parse_brawl(text)
check('99main plus one source-admitted commander',sum(c['count'] for c in deck['cards'])==99 and deck['commander']['count']==1)
check('Brawl uses an explicit separate format',deck['format']=='arena-brawl')
for name,content in [
    ('Missing commander',text.split('Deck\n',1)[1]),
    ('Two commander copies',text.replace('1 Isamaru','2 Isamaru')),
    ('Unknown commander',text.replace('Isamaru, Hound of Konda','Krenko, Mob Boss')),
    ('98main cards',text.replace('93 Plains','92 Plains')),
    ('100main cards',text.replace('93 Plains','94 Plains')),
    ('Repeated nonbasic card',text.replace('93 Plains','92 Plains').replace('1 Yoked Ox','2 Yoked Ox')),
    ('Duplicate commander in main',text.replace('1 Yoked Ox','1 Isamaru, Hound of Konda')),
    ('Off-color basic land',text.replace('93 Plains','93 Island')),
    ('Off-color instant',text.replace('1 Divine Arrow','1 Unsummon')),
    ('Unverified main card',text.replace('1 Yoked Ox','1 Unverified Test Artifact')),
    ('Unrecognized section',text+'\nSideboard\n1 Plains'),
    ('Zero count',text.replace('1 Yoked Ox','0 Yoked Ox')),
    ('Fractional count',text.replace('1 Yoked Ox','1.5 Yoked Ox')),
]:rejects(name,content)
try:parse_deck(text)
except ValueError:check('Practice importer does not silently flatten a commander deck',True)
else:raise AssertionError('Practice importer flattened Brawl')
emry=(Path(__file__).resolve().parents[1]/'decks/Brawl-Emry-Foundation.txt').read_text()
blue=parse_brawl(emry)
check('Emry accepts a legal-size blue and colorless foundation',blue['commander']['name']=='Emry, Lurker of the Loch' and sum(c['count'] for c in blue['cards'])==99)
check('A blue commander admits colorless Ornithopter and blue-activated Spellbomb',{'Ornithopter','Aether Spellbomb'}<={c['name'] for c in blue['cards']})
seat=parse_brawl(emry.replace('96 Island','95 Island')+'\n1 Seat of the Synod\n')
check('Artifact land is admitted as a blue singleton',any(c['name']=='Seat of the Synod' for c in seat['cards']))
crypt=parse_brawl(emry.replace('96 Island','95 Island')+"\n1 Tormod's Crypt\n")
check('Colorless Crypt fits Emry identity',any(c['name']=="Tormod's Crypt" for c in crypt['cards']))
rejects('Emry rejects white basics',emry.replace('96 Island','96 Plains'))
rejects('Emry rejects a white spell',emry.replace('1 Unsummon','1 Savannah Lions'))
rejects('Emry still rejects repeated artifact nonbasics',emry.replace('96 Island','95 Island').replace('1 Ornithopter','2 Ornithopter'))
rejects('White commander cannot use colorless Spellbomb with blue activation',text.replace('1 Yoked Ox','1 Aether Spellbomb'))
rejects('White commander cannot use blue artifact land',text.replace('1 Yoked Ox','1 Seat of the Synod'))
print(json.dumps(dict(checks=len(checks),passed=checks),indent=2))
