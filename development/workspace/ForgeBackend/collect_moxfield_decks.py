"""Snapshot public Moxfield popularity and deck cards without granting admission.

No sign-in, cookies, primer text, account data or game assets are needed.
Failed fetches remain explicit; another deck never silently replaces a ranked one.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

AGENT = 'ForgeArena compatibility research; public deck metadata'
BOARDS = ('mainboard', 'commanders', 'companions', 'signatureSpells', 'sideboard')

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

def extract(deck):
    cards = []
    for board in BOARDS:
        for row in deck.get('boards', {}).get(board, {}).get('cards', {}).values():
            card = row['card']; count = row['quantity']
            if not isinstance(count, int) or isinstance(count, bool) or count < 1:
                raise ValueError('Invalid card quantity')
            if not card.get('name'): raise ValueError('Missing card name')
            cards.append(dict(name=card['name'], count=count, board=board,
                              scryfallId=card.get('scryfall_id'), set=card.get('set'),
                              collectorNumber=card.get('cn')))
    if not any(c['board'] == 'mainboard' for c in cards):
        raise ValueError('Deck has no mainboard')
    return cards

def collect(output, count=50, format='commander'):
    output.mkdir(parents=True, exist_ok=False)
    query=urllib.parse.urlencode(dict(pageNumber=1,pageSize=count,sortType='views',sortDirection='Descending',fmt=format))
    source='https://api2.moxfield.com/v2/decks/search?'+query
    ranking=fetch(source)
    rows=ranking['data']
    if len(rows)!=count or len({d['publicId'] for d in rows})!=count:
        raise ValueError('Ranking is incomplete or repeats deck identities')
    views=[d['viewCount'] for d in rows]
    if views!=sorted(views,reverse=True):raise ValueError('API did not return descending views')
    report=dict(schema=1,retrievedUtc=datetime.now(timezone.utc).isoformat(),source=source,
                format=format,ranking='views-descending',requested=count,complete=False,
                boards=list(BOARDS),excludedBoards=['maybeboard','tokens','attractions','stickers','contraptions','planes','schemes'],decks=[],failures=[],newAdmissions=0)
    union=defaultdict(lambda:dict(decks=set(),boards=set(),quantities=0))
    for rank,item in enumerate(rows,1):
        meta={k:item.get(k) for k in ('publicId','publicUrl','name','viewCount','likeCount','lastUpdatedAtUtc','isLegal')}
        meta['rank']=rank
        try:
            raw=fetch('https://api2.moxfield.com/v3/decks/all/'+item['publicId'])
            if raw.get('publicId')!=item['publicId'] or raw.get('format')!=format or raw.get('visibility')!='public':
                raise ValueError('Detail identity, format or visibility differs from ranking')
            meta['cards']=extract(raw)
            meta['detailUpdatedUtc']=raw.get('lastUpdatedAtUtc')
            meta['cardListSha256']=hashlib.sha256(json.dumps(meta['cards'],sort_keys=True).encode()).hexdigest()
            for card in meta['cards']:
                entry=union[card['name']];entry['decks'].add(item['publicId']);entry['boards'].add(card['board']);entry['quantities']+=card['count']
            report['decks'].append(meta)
        except (urllib.error.URLError,ValueError,KeyError,TimeoutError) as error:
            report['failures'].append(dict(rank=rank,publicId=item['publicId'],error=str(error)))
        (output/'decks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(dict(rank=rank,downloaded=len(report['decks']),failures=len(report['failures']))),flush=True)
        time.sleep(.3)
    cards=[dict(name=name,deckCount=len(v['decks']),deckIds=sorted(v['decks']),boards=sorted(v['boards']),quantities=v['quantities']) for name,v in union.items()]
    cards.sort(key=lambda c:(-c['deckCount'],c['name'].casefold()))
    report.update(complete=len(report['decks'])==count and not report['failures'],distinctCards=len(cards),finishedUtc=datetime.now(timezone.utc).isoformat())
    (output/'decks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (output/'cards.json').write_text(json.dumps(dict(schema=1,source='decks.json',complete=report['complete'],cards=cards,newAdmissions=0),indent=2),encoding='utf-8')
    return report['complete']

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--count',type=int,default=50)
    parser.add_argument('--format',default='commander')
    args=parser.parse_args()
    if not 1<=args.count<=100:parser.error('Use 1..100 decks')
    raise SystemExit(0 if collect(args.output,args.count,args.format) else 1)
