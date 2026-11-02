"""Owner-thread pod spectating: dead-seat actions stay rejected; bots remain real."""
import argparse,json,os,time
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from engine_test_client import Engine

deck=dict(name='Spectator boundary test',format='commander-40',commander=dict(name='Isamaru, Hound of Konda',count=1),cards=[dict(name='Plains',count=99)],experimental=True)
e=None;checks=[]
def check(name,value):
    checks.append(dict(check=name,passed=bool(value)));assert value,name
try:
    e=Engine('commander-ten-pod',localDeck=deck,opponentDecks=[deck]*9,randomSeed=7274,startingPlayerPolicy='local-first')
    check('Initial concede is accepted',e.send('concede')['accepted'])
    check('Elimination pauses with nine actual survivors',e.state['localLost'] and not e.state['gameOver'] and len([s for s in e.state['players'] if not s['lost']])==9 and not e.state['canPass'])
    check('No automatic spectator advance before consent',not e.send('pass_priority')['accepted'])
    check('Opening-hand concession cannot enter unsafe native startup',not e.send('spectate')['accepted'])
    e.close();e=None
    e=Engine('commander-ten-pod',localDeck=deck,opponentDecks=[deck]*9,randomSeed=7274,startingPlayerPolicy='local-first')
    d=e.state['decision'];kept=e.finish(e.begin('submit_mulligan',decisionToken=d['token'],assignments=[dict(keep=True)]),seconds=45)
    check('Real opening hand kept',kept['accepted'])
    for _ in range(30):
        if e.state['stage']=='Play':break
        check('Enter real play',e.send('pass_priority')['accepted'])
    check('Actual Play stage before elimination',e.state['stage']=='Play')
    check('In-play concede accepted',e.send('concede')['accepted'] and e.state['localLost'])
    check('Foreign seat cannot resume',not e.send('spectate',seat=2)['accepted'])
    check('Stale session cannot resume',not e.send('spectate',session='stale')['accepted'])
    # All nine real AI mulligans can run before the first priority boundary.
    resumed=e.finish(e.begin('spectate'),seconds=45)
    check('Explicit spectate starts real bot progression',resumed['accepted'] and e.state['spectating'] and e.state['canPass'])
    check('Dead seat cannot cast',not e.send('cast_spell',123456)['accepted'])
    check('Duplicate resume does not reset the match',not e.send('spectate')['accepted'])
    first=e.state['turn'];seen=set();deadline=time.monotonic()+90
    for _ in range(240):
        check('Bounded native owner-thread advance',time.monotonic()<deadline and e.send('pass_priority')['accepted'])
        seen.add(e.state['activeSeat'])
        if e.state['turn']>=first+2:break
    check('Multiple bot turns advanced',e.state['turn']>=first+2 and len(seen)>=2)
    check('Human has no legal gameplay offers',not e.state['legalLands'] and not e.state['legalCasts'] and not e.state['legalActivations'])
    check('No invented game winner',not e.state['gameOver'] and e.state['winnerSeat']==0)
    result=dict(passed=True,checks=checks,turn=e.state['turn'],observedSeats=sorted(seen),evidence=str(e.ipc))
finally:
    if e:e.close()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(locals().get('result',dict(passed=False,checks=checks)),indent=2))
print(json.dumps(result))
