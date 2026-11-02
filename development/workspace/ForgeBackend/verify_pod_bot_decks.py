"""Normal shuffled pod decks through original native handlers, without zone fixtures."""
import argparse,json,os,time,traceback
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--seed',type=int,default=7274)
p.add_argument('--players',type=int,choices=(4,10),default=4)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from deck_import import read_deck
from native_engine_test_client import NativeEngine
from native_test_policy import execute

a.output.mkdir(parents=True,exist_ok=False);e=None;trace=[];report={}
try:
    source=Path(__file__).resolve().parents[1]
    names=('Isamaru','Emry','Selvala')
    bots=[read_deck(source/'decks'/('Commander-Pod-'+names[i%3]+'.txt'),'commander-40') for i in range(a.players-1)]
    assert len({d['commander']['name'] for d in bots})==3
    local=dict(name='Passive observer',format='commander-40',commander=dict(name='Isamaru, Hound of Konda',count=1),cards=[dict(name='Plains',count=99)])
    e=NativeEngine('commander-ten-pod' if a.players==10 else 'commander-pod',worker=a.worker,managed=a.managed,fixture=a.fixture,localDeck=local,opponentDeck=bots[0],opponentDecks=bots,randomSeed=a.seed,startingPlayerPolicy='local-first')
    assert len(e.state['players'])==a.players and all(v['startingLifeTotal']==40 for v in e.state['players'])
    commanders={c['owner']:c['name'] for c in e.state['command']}
    assert [commanders[i] for i in range(2,a.players+1)]==[d['commander']['name'] for d in bots]
    execute(e,trace,'submit_mulligan',decisionToken=e.state['decision']['token'],assignments=[dict(keep=True)])
    seen={seat:{} for seat in range(2,a.players+1)};land_max={seat:0 for seat in seen};creature_max=dict(land_max);commander_cast=set();attacks=set();observations=[]
    deadline=time.monotonic()+300
    for step in range(1000):
        s=e.state;assert time.monotonic()<deadline,'Native pod exceeded five-minute bound'
        assert not s.get('fidelityGap'),s.get('fidelityGap')
        for seat in seen:
            board=[c for c in s['battlefield'] if c['controller']==seat]
            land_max[seat]=max(land_max[seat],sum('Land' in c['currentTypes'] for c in board))
            creatures=[c for c in board if 'Creature' in c['currentTypes']]
            creature_max[seat]=max(creature_max[seat],len(creatures))
            for c in creatures:seen[seat][c['forgeId']]=c['name']
            if any(c['name']==commanders[seat] for c in creatures):commander_cast.add(seat)
        for event in s['events']:
            if event.get('kind')=='damage' and event.get('combat'):
                for seat,cards in seen.items():
                    if event.get('sourceForgeId') in cards:attacks.add(seat)
        if not observations or observations[-1]['turn']!=s['turn']:
            observations.append(dict(turn=s['turn'],activeSeat=s['activeSeat'],land=dict(land_max),creatures=dict(creature_max)))
        if s['gameOver'] or next(p for p in s['players'] if p['seat']==1)['lost'] or s['turn']>=1+a.players*(6 if a.players==10 else 8) and s['activeSeat']==1:break
        if s['legalLands']:execute(e,trace,'play_land',s['legalLands'][0],_attack_policy=lambda decision,state:[])
        else:execute(e,trace,'pass_priority',_attack_policy=lambda decision,state:[])
    else:raise AssertionError('Native pod exceeded action bound')
    assert all(n>=3 for n in land_max.values()),land_max
    assert all(n>=(1 if a.players==10 else 2) for n in creature_max.values()),creature_max
    declared=[event for event in s['events'] if event.get('kind')=='pod-attack-declared']
    if a.players==10:
        assert declared,'No native AI attack declarations recorded'
        assert all(event['livingPlayers']<=4 or event['targetSeat']==event['nearestLeft'] for event in declared),'Native AI attacked a non-left opponent'
    # Commander identity was checked at opening; the real AI may prefer its
    # other spells. Record that choice instead of forcing a commander-play policy.
    assert attacks,'No real bot combat damage was observed'
    report=dict(passed=True,players=a.players,nativeAttackDeclarations=len(declared),seed=a.seed,turn=s['turn'],landMax=land_max,creatureMax=creature_max,commandersCast=sorted(commander_cast),combatDamageSeats=sorted(attacks),creaturesSeen=seen,gameOver=s['gameOver'],evidence=str(e.ipc),scope='Normal shuffled full opponent lists through native handlers; passive test-only human, no manipulated bot zones/resources. Not a full-match or balance certification.')
except BaseException as error:report=dict(passed=False,error=repr(error),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
finally:
    if e:e.close()
    (a.output/'report.json').write_text(json.dumps(report,indent=2));(a.output/'trace.json').write_text(json.dumps(trace,indent=2));(a.output/'observations.json').write_text(json.dumps(locals().get('observations',[]),indent=2));print(json.dumps(report),flush=True)
raise SystemExit(0 if report.get('passed') else 1)
