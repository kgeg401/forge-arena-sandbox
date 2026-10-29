"""Native Brawl/Commander starts, mulligans, commander casts and damage rules."""
from pathlib import Path
import argparse,os,json,time
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--damage-match',action='store_true')
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
a.output.mkdir(parents=True,exist_ok=False);results=[]
def deck(format,commander='Isamaru, Hound of Konda',cards=None):
    return dict(name='Commander mode validation',format=format,commander=dict(name=commander,count=1),cards=cards or [dict(name='Plains',count=99)],experimental=True)
def engine(format,**kwargs):
    return NativeEngine('commander-duel' if format=='commander-40' else 'brawl-duel',worker=a.worker,managed=a.managed,fixture=a.fixture,localDeck=deck(format),opponentDeck=deck(format),randomSeed=7274,startingPlayerPolicy='local-first',**kwargs)
for format,life,free in [('arena-brawl',25,1),('commander-40',40,0)]:
    e=None;trace=[]
    try:
        e=engine(format);assert e.state['life']==e.state['opponentLife']==life,e.state
        assert e.state['startingLifeTotal']==e.state['opponentStartingLifeTotal']==life
        assert e.state['format']==format and e.state['freeMulliganCount']==free
        assert len([c for c in e.state['command'] if c['owner']==1])==1
        d=e.state['decision'];assert d['kind']=='mulligan'
        execute(e,trace,'submit_mulligan',decisionToken=d['token'],assignments=[dict(keep=False)])
        assert len(e.state['hand'])==(7 if free else 6),(format,e.state['hand'])
        for _ in range(16):
            if e.state['legalLands']:break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Opening local main phase did not offer a land')
        land=e.state['legalLands'][0];execute(e,trace,'play_land',land)
        commander=next(c for c in e.state['command'] if c['owner']==1)
        assert commander['forgeId'] in e.state['legalCasts']
        execute(e,trace,'cast_spell',commander['forgeId'])
        for _ in range(12):
            if any(c['forgeId']==commander['forgeId'] for c in e.state['battlefield']):break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Commander did not enter the battlefield')
        assert not e.state['fidelityGap'],e.state['fidelityGap']
        results.append(dict(format=format,life=life,freeMulligans=free,passed=True,evidence=str(e.ipc)))
    except Exception as error:results.append(dict(format=format,passed=False,error=str(error)[-1800:],evidence=str(e.ipc) if e else ''))
    finally:
        if e:e.close()
    print(json.dumps(results[-1]),flush=True)
if a.damage_match:
    e=None;trace=[]
    try:
        format='commander-40';local=deck(format,'Derevi, Empyrial Tactician',[dict(name='Plains',count=33),dict(name='Island',count=33),dict(name='Forest',count=33)])
        e=NativeEngine('commander-duel',worker=a.worker,managed=a.managed,fixture=a.fixture,localDeck=local,opponentDeck=deck(format),randomSeed=7274,startingPlayerPolicy='local-first')
        commander_ids={c['owner']:c['forgeId'] for c in e.state['command']}
        d=e.state['decision'];execute(e,trace,'submit_mulligan',decisionToken=d['token'],assignments=[dict(keep=True)])
        deadline=time.monotonic()+420
        for i in range(1400):
            assert time.monotonic()<deadline,'Commander damage match exceeded time budget'
            assert not e.state['fidelityGap'],e.state['fidelityGap']
            if e.state['gameOver']:break
            if e.state['legalLands']:execute(e,trace,'play_land',e.state['legalLands'][0])
            elif e.state['legalCasts']:execute(e,trace,'cast_spell',e.state['legalCasts'][0])
            else:execute(e,trace,'pass_priority')
        else:raise AssertionError('Commander damage match exceeded action budget')
        assert e.state['gameOver'] and e.state['winnerSeat'] in (1,2) and e.state['lossReason']=='CommanderDamage',e.state['lossReason']
        loser=3-e.state['winnerSeat'];loser_life=e.state['life' if loser==1 else 'opponentLife']
        assert loser_life>0,loser_life
        # Forge removes a losing player's damage map when eliminating them.
        # Independently sum its authoritative combat events from that commander.
        damage=sum(d['amount'] for d in e.state['events'] if d['kind']=='damage' and d.get('combat') and d.get('targetSeat')==loser and d['sourceForgeId']==commander_ids[e.state['winnerSeat']])
        assert damage>=21,damage
        results.append(dict(case='21-commander-damage-at-positive-life',passed=True,turn=e.state['turn'],winnerSeat=e.state['winnerSeat'],loserLife=loser_life,lossReason=e.state['lossReason'],commanderCombatDamage=damage,evidence=str(e.ipc)))
    except Exception as error:results.append(dict(case='commander-damage',passed=False,error=str(error)[-1800:],evidence=str(e.ipc) if e else ''))
    finally:
        if e:(e.ipc/'commander-mode-trace.json').write_text(json.dumps(trace,indent=2));e.close()
    print(json.dumps(results[-1]),flush=True)
report=dict(passed=all(r['passed'] for r in results),results=results);(a.output/'report.json').write_text(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
