"""Real Forge regression for the reported Bojuka Bog triggered-target crash.

An independent research runtime is required. Optional native-worker arguments
exercise the original Arena target handler without opening a rendered client.
"""
from pathlib import Path
import argparse,json,time
from engine_test_client import Engine

def wait_choice(engine,parent):
    end=time.monotonic()+12
    while time.monotonic()<end:
        if engine.process.poll() is not None:raise RuntimeError((engine.ipc/'engine.log').read_text()[-3500:])
        try:message=json.loads((engine.ipc/'decision.json').read_text())
        except (OSError,ValueError):time.sleep(.025);continue
        if message['parentRequestId']==parent:
            engine.state=message['state'];return message['state']['decision']
        time.sleep(.025)
    raise TimeoutError('No triggered target choice')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    for name in ('native-worker','managed','fixture'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();native=bool(a.native_worker)
    if any((a.native_worker,a.managed,a.fixture)) and not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native worker arguments')
    from runtime_paths import ROOT
    if (ROOT/'native-lab/MTGA.exe').exists() or json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text()).get('researchOnly') is not True:raise ValueError('Select an independent research runtime')
    factory=Engine
    if native:
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**kwargs:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**kwargs)
    results=[]
    for target,empty in [(1,False),(2,False),(2,True)]:
        e=factory('card-family',fixtureHand=['Bojuka Bog','Savannah Lions'],fixtureLands=['Plains'],fixtureGraveyard=['Savannah Lions'],fixtureOpponentGraveyard=[] if empty else ['Yoked Ox'])
        try:
            bog=next(c for c in e.state['hand'] if c['name']=='Bojuka Bog')
            parent=e.begin('play_land',bog['forgeId']);choice=wait_choice(e,parent);token=choice['token']
            assert choice['kind']=='targets' and choice['sourceAbilityId']==90052 and choice['canCancel'] is False,choice
            assert {o['targetSeat'] for o in choice['options']}=={1,2}
            if not native:
                assert not e.send('cancel_targets',decisionToken=token)['accepted']
                assert not e.send('select_targets',decisionToken=token,assignments=[dict(forgeId=999999)])['accepted']
            assert e.send('select_targets',decisionToken=token,assignments=[dict(forgeId=-1000000-target,selected=True)])['accepted']
            assert e.send('submit_targets',decisionToken=token)['accepted'];e.finish(parent)
            assert not e.state['fidelityGap'],e.state['fidelityGap']
            assert len(e.state['stackAbilities'])==1,e.state['stackAbilities']
            e.pass_or_decision()
            names=lambda zone,seat:sorted(c['name'] for c in e.state.get(zone,[]) if c['owner']==seat)
            assert names('graveyard',target)==[]
            assert names('graveyard',3-target)==(['Yoked Ox'] if target==1 else ['Savannah Lions'])
            assert names('exile',target)==(['Savannah Lions'] if target==1 else [] if empty else ['Yoked Ox'])
            assert next(c for c in e.state['battlefield'] if c['forgeId']==bog['forgeId'])['tapped']
            lion=next(c for c in e.state['hand'] if c['name']=='Savannah Lions')
            assert e.send('cast_spell',lion['forgeId'])['accepted'];e.pass_or_decision()
            assert any(c['forgeId']==lion['forgeId'] for c in e.state['battlefield'])
            assert e.process.poll() is None and not e.state['fidelityGap']
            results.append(dict(target=target,empty=empty,passed=True,nativeHandlers=native,evidence=str(e.ipc)))
            print(json.dumps(results[-1]),flush=True)
        finally:e.close()
    e=factory('card-family',fixtureHand=['Savannah Lions'],fixtureLands=['Bojuka Bog'])
    try:
        bog=next(c for c in e.state['battlefield'] if c['name']=='Bojuka Bog')
        assert e.send('activate_mana',bog['forgeId'])['accepted']
        assert e.state['manaTotal']==1 and any(m['color']==4 for m in e.state['mana']),e.state['mana']
        results.append(dict(fixedBlackMana=True,passed=True,nativeHandlers=native,evidence=str(e.ipc)))
    finally:e.close()
    # A normal owner-thread game is essential: the reported crash escaped
    # Match.startGame, whereas fixture requests can catch errors themselves.
    local=dict(name='Trigger regression',cards=[dict(name='Bojuka Bog',count=60)])
    opponent=dict(name='Passive land regression',cards=[dict(name='Plains',count=60)])
    e=factory('custom-duel',localDeck=local,opponentDeck=opponent,startingPlayerPolicy='local-first',randomSeed=35)
    try:
        choice=e.state['decision'];assert choice['kind']=='mulligan'
        assert e.send('submit_mulligan',decisionToken=choice['token'],assignments=[dict(keep=True)])['accepted']
        for _ in range(12):
            if e.state['phase']=='MAIN1' and e.state['activeSeat']==1:break
            assert e.send('pass_priority')['accepted']
        assert e.state['phase']=='MAIN1' and e.state['activeSeat']==1
        bog=next(c for c in e.state['hand'] if c['name']=='Bojuka Bog')
        parent=e.begin('play_land',bog['forgeId']);choice=wait_choice(e,parent)
        assert choice['kind']=='targets' and choice['sourceAbilityId']==90052
        assert e.send('select_targets',decisionToken=choice['token'],assignments=[dict(forgeId=-1000002,selected=True)])['accepted']
        assert e.send('submit_targets',decisionToken=choice['token'])['accepted']
        assert len(e.state['stackAbilities'])==1 and not e.state['fidelityGap']
        assert e.send('pass_priority')['accepted']
        assert not e.state['stackAbilities'] and e.process.poll() is None and not e.state['fidelityGap']
        results.append(dict(normalMatchLoop=True,passed=True,nativeHandlers=native,evidence=str(e.ipc)))
    finally:e.close()
    a.output.write_text(json.dumps(dict(passed=True,results=results,scope=__doc__),indent=2))

if __name__=='__main__':main()
