"""Unconnected payment choices must not crash read-only action enumeration."""
from pathlib import Path
import argparse,json
from engine_test_client import Engine

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    for name in ('native-worker','managed','fixture'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();factory=Engine;native=bool(a.native_worker)
    if native:
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**kw:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**kw)
    from runtime_paths import ROOT
    assert not (ROOT/'native-lab/MTGA.exe').exists() and json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text())['researchOnly']
    results=[]
    for source,lands,creatures in [('Chord of Calling',['Forest']*3+['Plains'],['Chatterfang, Squirrel General']),('Chord of Calling',['Forest']*3+['Plains'],[])]:
        e=factory('card-family',fixtureHand=[source,'Savannah Lions'],fixtureLands=lands,fixtureBattlefield=creatures)
        try:
            chord=next(c for c in e.state['hand'] if c['name']==source)
            assert chord['forgeId'] not in e.state['legalCasts']
            gap=next(g for g in e.state['unavailableActions'] if g['forgeId']==chord['forgeId'])
            if creatures:assert 'Convoke' in gap['reason'],gap
            else:assert 'Choosing X' in gap['reason'],gap
            assert not e.state['fidelityGap'] and e.state['canPass'] and 'decision' not in e.state
            before=[(c['forgeId'],c['tapped']) for c in e.state['battlefield']];events=e.state['events'][:]
            if not native:
                for _ in range(3):assert e.send('snapshot')['accepted']
                assert before==[(c['forgeId'],c['tapped']) for c in e.state['battlefield']] and events==e.state['events'] and e.state['manaTotal']==0
                assert not e.send('cast_spell',chord['forgeId'])['accepted'] and not e.state['fidelityGap']
            lion=next(c for c in e.state['hand'] if c['name']=='Savannah Lions')
            assert e.send('cast_spell',lion['forgeId'])['accepted'];e.pass_or_decision()
            assert any(c['forgeId']==lion['forgeId'] for c in e.state['battlefield'])
            assert not e.state['fidelityGap'] and e.process.poll() is None
            assert any(g['forgeId']==chord['forgeId'] and 'Convoke' in g['reason'] for g in e.state['unavailableActions'])
            results.append(dict(initialCreatures=len(creatures),passed=True,native=native,evidence=str(e.ipc)));print(json.dumps(results[-1]),flush=True)
        finally:e.close()
    deck=dict(name='Convoke availability regression',cards=[dict(name='Forest',count=24),dict(name='Chord of Calling',count=16),dict(name='Chatterfang, Squirrel General',count=20)])
    opponent=dict(name='Passive lands',cards=[dict(name='Plains',count=60)])
    e=factory('custom-duel',localDeck=deck,opponentDeck=opponent,startingPlayerPolicy='local-first',randomSeed=35)
    try:
        d=e.state['decision'];assert e.send('submit_mulligan',decisionToken=d['token'],assignments=[dict(keep=True)])['accepted']
        reached=False
        for _ in range(160):
            assert not e.state['fidelityGap']
            if any(c['name']=='Chatterfang, Squirrel General' and c['owner']==1 for c in e.state['battlefield']) and any(c['name']=='Chord of Calling' for c in e.state['hand']):
                assert any(g['name']=='Chord of Calling' and 'Convoke' in g['reason'] for g in e.state['unavailableActions']);reached=True;break
            d=e.state.get('decision')
            if d:
                assert d['kind']=='attackers',d
                assert e.send('submit_attackers',decisionToken=d['token'])['accepted'];continue
            if e.state['activeSeat']==1 and e.state['phase']=='MAIN1':
                if e.state['legalLands']:assert e.send('play_land',e.state['legalLands'][0])['accepted'];continue
                creature=next((c for c in e.state['hand'] if c['name']=='Chatterfang, Squirrel General' and c['forgeId'] in e.state['legalCasts']),None)
                if creature:assert e.send('cast_spell',creature['forgeId'])['accepted'];continue
            assert e.send('pass_priority')['accepted']
        assert reached and e.process.poll() is None,'Normal match did not reach the reported state'
        results.append(dict(normalMatch=True,turn=e.state['turn'],passed=True,native=native,evidence=str(e.ipc)));print(json.dumps(results[-1]),flush=True)
    finally:e.close()
    a.output.write_text(json.dumps(dict(passed=True,results=results,scope=__doc__),indent=2))

if __name__=='__main__':main()
