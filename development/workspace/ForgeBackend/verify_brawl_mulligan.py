"""Real Brawl London decisions, including the free first mulligan and zero-card keep."""
from pathlib import Path
import json
from deck_import import read_deck
from engine_test_client import Engine

deck=read_deck(Path(__file__).resolve().parents[1]/'decks/Brawl-Isamaru-Foundation.txt','arena-brawl')
e=Engine('brawl-duel',localDeck=deck,opponentDeck=deck,randomSeed=113,startingPlayerPolicy='local-first')
try:
    while e.state.get('decision',{}).get('kind')=='starting_player':
        e.send('submit_starting_player',decisionToken=e.state['decision']['token'],assignments=[{'startingSeat':1}])
    for n in range(8):
        d=e.state['decision']
        e.check('Mulligan bottom count after '+str(n)+' rejections',d['count']==max(0,n-1),dict(actual=d['count']))
        e.send('submit_mulligan',decisionToken=d['token'],assignments=[{'keep':False}])
    d=e.state['decision']
    e.check('Brawl reaches a zero-card keep after its free mulligan',d['count']==7 and d['mulligans']==8)
    r=e.send('submit_mulligan',decisionToken=d['token'],assignments=[{'keep':False}])
    e.check('Cannot mulligan below zero',not r['accepted'])
    e.send('submit_mulligan',decisionToken=d['token'],assignments=[{'keep':True}]);d=e.state['decision']
    e.check('Real London bottom choice needs seven',d['kind']=='mulligan_bottom' and d['count']==7)
    e.send('submit_mulligan_bottom',decisionToken=d['token'],assignments=d['options'])
    e.check('Actual kept hand is empty',len(e.state['hand'])==0)
    print(json.dumps(dict(checks=len(e.checks),evidence=str(e.ipc)),indent=2))
finally:e.close()
