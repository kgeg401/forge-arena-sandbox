"""Import a bounded Arena-text practice deck without silently dropping cards."""
from pathlib import Path
import argparse, hashlib, json, re
from runtime_paths import SUPPORT_POLICY
from card_support import unsupported_message

SUPPORTED = tuple(json.loads(SUPPORT_POLICY.read_text())['verifiedNames'])
CANONICAL = {name.casefold(): name for name in SUPPORTED}
BRAWL_COMMANDERS=json.loads(SUPPORT_POLICY.read_text()).get('brawlCommanders',{})
COLOR_IDENTITIES=json.loads(SUPPORT_POLICY.read_text()).get('colorIdentities',{})

def parse_brawl(text,name='Local Brawl deck'):
    sections={'Commander':{},'Deck':{}};section=None
    lookup={**CANONICAL,**{n.casefold():n for n in BRAWL_COMMANDERS}};unsupported=[]
    for number,raw in enumerate(text.splitlines(),1):
        line=raw.strip()
        if not line or line.startswith('#'):continue
        if line in sections:section=line;continue
        if section is None:raise ValueError(f'Line {number}: Brawl requires Commander and Deck sections')
        m=re.fullmatch(r'([1-9][0-9]{0,2})[xX]?\s+(.+?)(?:\s+\([A-Za-z0-9]+\)\s+[0-9]+[A-Za-z]?)?',line)
        if not m:raise ValueError(f'Line {number}: invalid Brawl card entry: {line}')
        card=lookup.get(m[2].casefold())
        if card is None:unsupported.append(m[2]);continue
        sections[section][card]=sections[section].get(card,0)+int(m[1])
    if unsupported:raise ValueError(unsupported_message(unsupported))
    commanders=sections['Commander'];main=sections['Deck']
    if len(commanders)!=1 or sum(commanders.values())!=1:raise ValueError('Brawl requires exactly one commander')
    commander=next(iter(commanders))
    if commander not in BRAWL_COMMANDERS:raise ValueError('Commander is not verified for Brawl')
    if commander in main:raise ValueError('Commander cannot also appear in the main deck')
    if sum(main.values())!=99:raise ValueError('Arena Brawl requires 99 main cards plus one commander')
    colors=set(BRAWL_COMMANDERS[commander]['colorIdentity'])
    for card,count in main.items():
        if card not in SUPPORTED:raise ValueError('Unverified Brawl main-deck card: '+card)
        if count!=1 and card not in ('Plains','Island','Swamp','Mountain','Forest'):raise ValueError('Brawl is singleton except basic lands: '+card)
        identity=COLOR_IDENTITIES.get(card,['U'] if card in ('Island','Unsummon','Essence Scatter','Quick Study') else ['W'])
        if not set(identity)<=colors:raise ValueError('Outside commander color identity: '+card)
    return dict(name=name[:80],format='arena-brawl',commander=dict(name=commander,count=1),cards=[dict(name=n,count=c) for n,c in main.items()])

def parse_deck(text, name='Custom practice deck'):
    counts = {};unsupported=[]
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#') or line == 'Deck':
            continue
        match = re.fullmatch(r'([1-9][0-9]{0,2})[xX]?\s+(.+?)(?:\s+\([A-Za-z0-9]+\)\s+[0-9]+[A-Za-z]?)?', line)
        if not match:
            raise ValueError(f'Line {number}: expected a card count and name. Only a main deck is supported: {line}')
        count, entered = int(match[1]), match[2]
        card = CANONICAL.get(entered.casefold())
        if card is None:
            unsupported.append(entered);continue
        counts[card] = counts.get(card, 0) + count
    if unsupported:raise ValueError(unsupported_message(unsupported))
    total = sum(counts.values())
    if not 40 <= total <= 250:
        raise ValueError(f'Practice decks must contain 40 to 250 cards; this list has {total}.')
    return {'name': name[:80], 'cards': [{'name': k, 'count': v} for k, v in counts.items()]}

def read_deck(path,format='practice'):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 262144:
        raise ValueError('Select a deck text file under 256 KB.')
    raw = path.read_bytes()
    deck = (parse_brawl if format=='arena-brawl' else parse_deck)(raw.decode('utf-8-sig'), path.stem)
    deck.update(source=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                printingPolicy='Pinned verified Arena art; export set and collector labels are not imported',
                formatPolicy='Arena Brawl sandbox: 99 main plus one commander, singleton and admitted color identity; no queue banlist claim' if format=='arena-brawl' else 'Sandbox main deck, 40 to 250 cards, unrestricted copy counts; no format legality claim')
    return deck

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('deck'); parser.add_argument('--opponent')
    parser.add_argument('--format',choices=('practice','arena-brawl'),default='practice')
    args = parser.parse_args()
    try:
        local = read_deck(args.deck,args.format)
        print(json.dumps({'localDeck': local, 'opponentDeck': read_deck(args.opponent,args.format) if args.opponent else local}))
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(2, str(error)+'\n')
