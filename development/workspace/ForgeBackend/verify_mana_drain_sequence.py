"""Mana Drain counter plus delayed mana through owned native client handlers.
Checks the following main phase, exact amount, pool clearing and one-shot timing.
"""
from pathlib import Path
import argparse,os,json,time,hashlib
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
a.output.mkdir(parents=True,exist_ok=False);results=[]
cases=[('Ornithopter',0,[],True),('Grizzly Bears',2,['Forest']*2,True),('Divination',3,['Island']*3,True),('Supreme Verdict',4,['Plains']*2+['Island']*2,False)]
for name,value,lands,counterable in cases:
    e=None;trace=[]
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,
            fixtureHand=['Mana Drain'],fixtureLands=['Island']*2,fixtureLibrary=['Plains']*20,
            fixtureOpponentSpell=name,fixtureOpponentLands=lands,fixtureActiveSeat=2)
        drain=next(c for c in e.state['hand'] if c['name']=='Mana Drain');target=next(c for c in e.state['stack'] if c['name']==name)
        execute(e,trace,'cast_spell',drain['forgeId'])
        for _ in range(30):
            if not e.state['stack'] and not e.state['stackAbilities']:break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Initial spell stack did not resolve')
        counter_turn=e.state['turn']
        assert e.state['activeSeat']==2 and e.state['phase']=='MAIN1' and e.state['manaTotal']==0
        if counterable:assert any(c['forgeId']==target['forgeId'] for c in e.state['graveyard'])
        triggers=set()
        for _ in range(60):
            assert not e.state['fidelityGap'],e.state['fidelityGap']
            for ability in e.state['stackAbilities']:
                if ability['sourceForgeId']==drain['forgeId']:
                    assert ability['abilityId']==157355,ability
                    assert e.state['activeSeat']==1 and e.state['phase']=='MAIN1' and e.state['turn']>counter_turn,(e.state['turn'],e.state['phase']);triggers.add(ability['forgeId'])
            if triggers and e.state['activeSeat']==1 and e.state['phase']=='MAIN1' and not e.state['stackAbilities']:break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Delayed mana did not resolve in the next main phase')
        assert len(triggers)==1 and e.state['manaTotal']==value,(triggers,e.state['mana'])
        assert all(m['color'] in (0,32) for m in e.state['mana']),e.state['mana']
        mana_turn=e.state['turn']
        for _ in range(80):
            assert not e.state['fidelityGap'],e.state['fidelityGap']
            assert not any(b['sourceForgeId']==drain['forgeId'] for b in e.state['stackAbilities'])
            if e.state['turn']>=mana_turn+2 and e.state['activeSeat']==1 and e.state['phase']=='MAIN1':break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Could not reach the following local turn')
        assert e.state['manaTotal']==0,e.state['mana']
        result=dict(name=name,manaValue=value,counterable=counterable,passed=True,evidence=str(e.ipc))
    except Exception as error:result=dict(name=name,passed=False,error=str(error),evidence=str(e.ipc) if e else '')
    finally:
        if e:(e.ipc/'mana-drain-policy-trace.json').write_text(json.dumps(trace,indent=2));e.close()
    results.append(result);print(json.dumps(result),flush=True)
report=dict(passed=all(r['passed'] for r in results),cases=results,sourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope=__doc__)
(a.output/'report.json').write_text(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
