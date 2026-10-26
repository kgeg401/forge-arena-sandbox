"""Exercise each exact deck card through native play/cast/resolution handlers.
Planeswalkers also exercise one available loyalty ability. This is a smoke test,
not validation of every effect branch or interaction in the deck.
"""
from pathlib import Path
import argparse,os,json,time,concurrent.futures
p=argparse.ArgumentParser(description=__doc__)
for key in ('config','worker','managed','fixture','deck','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--jobs',type=int,default=3);p.add_argument('--card',action='append')
a=p.parse_args();os.environ['FORGE_ARENA_CONFIG']=str(a.config)
from native_engine_test_client import NativeEngine
from native_test_policy import execute
root=Path(json.loads(a.config.read_text())['privateRoot']);manifest=json.loads((root/'native-lab/bridge-card-manifest.json').read_text())
names=[]
for line in a.deck.read_text().splitlines():
    line=line.strip()
    if not line or line.startswith('#') or line in ('Commander','Deck'):continue
    count,name=line.split(' ',1)
    if name not in names:names.append(name)
if a.card:names=[n for n in names if n in a.card]
a.output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
counters={'Mana Drain','Counterspell',"Dovin's Veto",'Swan Song','Wash Away','No More Lies'}

def run(name):
    e=None;trace=[]
    try:
        card=manifest['cards'][name];land='Land' in card['types'];counter=name in counters
        options=dict(fixtureHand=[name],fixtureLands=[] if land else ['Plains','Island','Swamp','Mountain','Forest']*6,
          fixtureBattlefield=[] if land else ['Grizzly Bears','Ornithopter'],fixtureOpponentBattlefield=['Grizzly Bears','Ornithopter'],
          fixtureOpponentHand=['Grizzly Bears'],fixtureLibrary=['Plains','Island','Grizzly Bears','Jace, Cunning Castaway','Arcane Signet','Demonic Tutor','Counterspell']*10)
        if counter:options.update(fixtureOpponentSpell='Divination',fixtureOpponentLands=['Island']*3)
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,**options)
        def resolve():
            for _ in range(50):
                if e.state['gameOver'] or not e.state['stack'] and not e.state['stackAbilities']:return
                execute(e,trace,'pass_priority')
            raise AssertionError('Resolution budget exceeded')
        target=next(c for c in e.state['hand'] if c['name']==name)
        assert target['forgeId'] in e.state['legalLands' if land else 'legalCasts'],('No legal native action',name,e.state.get('unavailableActions'))
        execute(e,trace,'play_land' if land else 'cast_spell',target['forgeId']);resolve()
        assert not e.state['fidelityGap'] and not e.state.get('decision')
        assert any(c['name']==name and c['owner']==1 for zone in ['battlefield','graveyard','exile','command'] for c in e.state[zone]),('Card did not resolve to a supported zone',name)
        activated=None
        if 'Planeswalker' in card['types'] and not e.state['gameOver']:
            offers=[x for x in e.state['legalActivations'] if x['forgeId']==target['forgeId']]
            assert offers,('No usable loyalty ability after cast',name)
            activated=offers[0]['abilityId'];execute(e,trace,'activate_ability',target['forgeId'],abilityId=activated);resolve()
        result=dict(name=name,passed=True,kind='land-play' if land else 'spell-resolution',loyaltyAbility=activated,evidence=str(e.ipc))
    except Exception as error:result=dict(name=name,passed=False,error=str(error)[-2200:],evidence=str(e.ipc) if e else '')
    finally:
        if e:(e.ipc/'smoke-policy-trace.json').write_text(json.dumps(trace,indent=2));e.close()
    (a.output/(str(names.index(name))+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True);return result

with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(3,a.jobs))) as pool:results=list(pool.map(run,names))
report=dict(passed=bool(results) and all(r['passed'] for r in results),cards=len(results),results=results,elapsed=time.monotonic()-started,scope=__doc__)
(a.output/'report.json').write_text(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
