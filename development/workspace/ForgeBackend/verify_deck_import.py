from deck_import import parse_deck, read_deck, SUPPORTED
from engine_test_client import Engine, ROOT
from pathlib import Path
import json, time

checks=[]
def check(label, condition):
    assert condition,label
    checks.append({'check':label,'passed':True})

deck=parse_deck('Deck\n20 Plains (M21) 262\n20 plains\n4x Unsummon (M20) 78\n16 Island')
check('Arena labels and repeated names import without losing counts',deck['cards']==[{'name':'Plains','count':40},{'name':'Unsummon','count':4},{'name':'Island','count':16}])
for label,text in {
    'unmapped card':'Deck\n59 Plains\n1 Black Lotus',
    'sideboard':'Deck\n60 Plains\nSideboard\n1 Unsummon',
    'zero count':'0 Plains\n60 Island',
    'negative count':'-1 Plains\n61 Island',
    'fractional count':'1.5 Plains\n60 Island',
    'too small':'39 Plains',
    'too large':'251 Plains',
    'merged count too large':'200 Plains\n100 plains',
}.items():
    try:parse_deck(text)
    except ValueError:check('reject '+label,True)
    else:raise AssertionError(label)

repo=Path(__file__).resolve().parents[1]
local=read_deck(repo/'decks/White-Lifegain.txt');opponent=read_deck(repo/'decks/White-Blue-Tempo.txt')
check('sample decks each contain 60 cards',all(sum(c['count'] for c in d['cards'])==60 for d in (local,opponent)))
check('source bytes are identified',all(len(d['sha256'])==64 and Path(d['source']).is_absolute() for d in (local,opponent)))
for label, cards in [('unmapped',[{'name':'Black Lotus','count':60}]),('duplicate',[{'name':'Plains','count':30},{'name':'Plains','count':30}]),('fractional',[{'name':'Plains','count':60.5}]),('small',[{'name':'Plains','count':39}])]:
    try:e=Engine('custom-duel',localDeck={'cards':cards})
    except RuntimeError:check('engine independently rejects '+label,True)
    else:e.close();raise AssertionError(label)
e=Engine('custom-duel',localDeck=local,opponentDeck=opponent,randomSeed=7274,startingPlayerPolicy='local-first')
try:
    check('engine retains both exact imported lists',e.state['localDeck']==local and e.state['opponentDeck']==opponent)
    check('actual Forge startup draws from imported local deck',len(e.state['hand'])==7 and all(c['name'] in {v['name'] for v in local['cards']} for c in e.state['hand']))
    check('both starting libraries and hands conserve deck size',len(e.state['hand'])+sum(c['owner']==1 for c in e.state['hidden'])==60 and sum(c['owner']==2 for c in e.state['hidden'])==60)
    d=e.state['decision'];r=e.send('submit_mulligan',decisionToken=d['token'],assignments=[{'keep':True}]);check('imported deck enters real play',r['accepted'] and e.state['stage']=='Play')
    e.send('concede');check('imported game can finish normally',e.state['gameOver'])
    evidence=str(e.ipc)
finally:e.close()
out=ROOT/'research'/('deck-import-check-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
out.write_text(json.dumps({'checks':checks,'engineEvidence':evidence,'allowlist':SUPPORTED},indent=2));print(json.dumps({'checks':len(checks),'report':str(out),'engine':evidence}))
