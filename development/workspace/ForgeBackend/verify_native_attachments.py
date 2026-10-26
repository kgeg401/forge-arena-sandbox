"""Independent attachment outcomes through a persistent original Arena handler.

Only initial objects are seeded. Forge casts, pays, attaches, moves and applies
state-based actions. The native worker checks both attachment graph directions
and creature characteristics after every native game-state update.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import traceback


CASES = ['aura-stats', 'stacked-auras', 'aura-host-bounce', 'aura-host-destroy', 'equipment-reattach-bounce']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(name, factory):
    e=None
    try:
        settings = {
            'aura-stats': (['Knight\'s Pledge'], ['Plains']*2),
            'stacked-auras': (["Knight's Pledge", 'Oakenform'], ['Plains']*2+['Forest']*3),
            'aura-host-bounce': (["Knight's Pledge", 'Unsummon'], ['Plains']*3+['Island']*2),
            'aura-host-destroy': (["Knight's Pledge", 'Murder'], ['Plains']*2+['Swamp']*3),
            'equipment-reattach-bounce': (['Short Sword', 'Unsummon'], ['Plains']*4+['Island']*4),
        }
        hand,lands=settings[name]
        e=factory('card-family',randomSeed=7274,fixtureHand=hand,fixtureLands=lands,
                  fixtureLibrary=['Forest','Mountain','Plains'],fixtureBattlefield=['Grizzly Bears','Savannah Lions'])
        def check(label,value):e.check(label,value)
        def find(zone,name):return next(c for c in e.state[zone] if c['name']==name)
        bears=find('battlefield','Grizzly Bears')['forgeId'];lions=find('battlefield','Savannah Lions')['forgeId']
        originals={c['name']:c['forgeId'] for c in e.state['hand']}
        def transact(op,identity=0,target=None,**fields):
            parent=e.begin(op,identity,**fields);end=time.monotonic()+20
            while time.monotonic()<end:
                if (e.ipc/'responses'/(parent+'.json')).exists():
                    check('Original native command reaches an accepted Forge boundary',e.finish(parent)['accepted']);return
                try:observed=json.loads((e.ipc/'decision.json').read_text())
                except (FileNotFoundError,PermissionError,json.JSONDecodeError):observed=None
                if observed and observed['parentRequestId']==parent:
                    e.state=observed['state'];d=e.state['decision'];token=d['token']
                    check('No hidden human decision was delegated to AI',not e.state['fidelityGap'])
                    if d['kind']=='targets':
                        check('Intended target is actually legal',target is not None and any(o.get('forgeId')==target for o in d['options']))
                        check('Native handler updates the chosen target',e.send('select_targets',assignments=[dict(forgeId=target)],decisionToken=token)['accepted'])
                        check('Native handler submits the chosen target',e.send('submit_targets',decisionToken=token)['accepted'])
                    elif d['kind']=='order_cards':
                        check('Native handler orders actual graveyard arrivals',e.send('submit_order_cards',assignments=[dict(forgeId=o['forgeId']) for o in d['options']],decisionToken=token)['accepted'])
                    elif d['kind']=='choice' and d['choice']['type']=='entities':
                        spec=d['choice'];options=spec['options']
                        check('Attachment resolution offers exactly the explicitly chosen legal host',target is not None and len(options)==1 and options[0]['forgeId']==target and spec['min']==spec['max']==1)
                        check('Actual native entity confirmation is accepted',e.send('submit_choice',assignments=[dict(choiceId=options[0]['choiceId'])],decisionToken=token)['accepted'])
                    else:raise AssertionError('Unexpected human callback '+json.dumps(d))
                time.sleep(.025)
            raise TimeoutError('Attachment operation did not complete')
        def resolve(identity,destination,target=None):
            for _ in range(12):
                if any(c['forgeId']==identity for c in e.state[destination]):return
                transact('pass_priority',target=target)
            raise AssertionError('Actual source did not resolve to '+destination)
        def cast(card,target=None,destination='battlefield'):
            source=originals[card];transact('cast_spell',source,target);resolve(source,destination,target);return source
        def stats(identity,power,toughness):
            c=next(c for c in e.state['battlefield'] if c['forgeId']==identity)
            check('Creature characteristics match independent expected effect',(c['power'],c['toughness'])==(power,toughness))
        def attached(source,target):
            c=next(c for c in e.state['battlefield'] if c['forgeId']==source)
            check('Actual Forge attachment endpoint is the chosen permanent',c.get('attachedToForgeId',0)==target)
        if name=='equipment-reattach-bounce':
            source=cast('Short Sword');attached(source,0)
            for target in (bears,lions):
                transact('activate_ability',source,target,abilityId=1268)
                for _ in range(12):
                    if not e.state['stack'] and not e.state['stackAbilities']:break
                    transact('pass_priority',target=target)
                check('Equip ability really resolved',not e.state['stack'] and not e.state['stackAbilities']);attached(source,target)
                stats(bears,3 if target==bears else 2,3 if target==bears else 2)
                stats(lions,3 if target==lions else 2,2 if target==lions else 1)
            cast('Unsummon',lions,'graveyard');attached(source,0)
            check('Returned creature is in hand',any(c['forgeId']==lions for c in e.state['hand']))
            stats(bears,2,2)
        else:
            first=cast("Knight's Pledge",bears);attached(first,bears);stats(bears,4,4)
            if name=='stacked-auras':
                second=cast('Oakenform',bears);attached(first,bears);attached(second,bears);stats(bears,7,7)
            elif name in ('aura-host-bounce','aura-host-destroy'):
                removal='Unsummon' if name=='aura-host-bounce' else 'Murder'
                cast(removal,bears,'graveyard')
                check('Unattached Aura goes to graveyard through actual state-based action',any(c['forgeId']==first for c in e.state['graveyard']))
                check('Host reaches the correct real zone',any(c['forgeId']==bears for c in e.state['hand' if removal=='Unsummon' else 'graveyard']))
                check('No stale attachment endpoint survives the zone changes',all('attachedToForgeId' not in c and 'attachedToSeat' not in c for zone in ('hand','battlefield','graveyard') for c in e.state[zone]))
        check('Attachment events retain their actual source and target',any(v['kind']=='attachment-change' and v.get('toForgeId')==bears for v in e.state['events']))
        check('No fidelity gap or unintended game outcome',not e.state['fidelityGap'] and not e.state['gameOver'])
        return dict(id=name,passed=True,checks=len(e.checks),evidence=str(e.ipc))
    except Exception as failure:
        return dict(id=name,passed=False,error=str(failure)[:2000],traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--case',choices=CASES,action='append');a=p.parse_args()
    os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy))
    from native_engine_test_client import NativeEngine
    from runtime_paths import ROOT
    preparation=json.loads((ROOT.parent/'preparation.json').read_text());source=ROOT.parent/'sources/ForgeBackend/ForgeLandEngine.java'
    if preparation['sourceSha256']!=sha(source):raise RuntimeError('Prepared source differs from current authored engine')
    a.output.mkdir(parents=True,exist_ok=False)
    hashes={str(f):sha(f) for f in a.worker.parent.glob('*.dll')}
    factory=lambda scenario,**settings:NativeEngine(scenario,worker=a.worker,managed=a.managed,fixture=a.fixture,**settings)
    rows=[]
    for case in a.case or CASES:
        row=run_case(case,factory);rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='traceback'}),flush=True)
    if any(sha(Path(path))!=digest for path,digest in hashes.items()) or sha(source)!=preparation['sourceSha256']:raise RuntimeError('Pinned test bytes changed during run')
    result=dict(passed=all(r['passed'] for r in rows),cases=rows,sourceSha256=preparation['sourceSha256'],nativeBinaries=hashes,finishedUtc=datetime.now(timezone.utc).isoformat(),scope=__doc__)
    (a.output/'report.json').write_text(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
