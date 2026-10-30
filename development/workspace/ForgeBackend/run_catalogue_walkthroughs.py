"""Bounded input-driven cast/land walkthroughs, not effect verification.

Use isolated research runtimes for parallel shards. Each case receives a fresh
game and classloader; the warm database is retired on failure. The explicit
test-only choice policy never runs in the player client. A successful
walkthrough does not grant admission or prove the card's complete rules.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(a):
    os.environ['FORGE_ARENA_CONFIG']=str(a.config.resolve())
    from runtime_paths import ROOT
    from warm_game_worker import WarmPool, atomic
    from native_test_policy import execute
    manifest_path=ROOT/'native-lab/bridge-card-manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    if manifest.get('researchOnly') is not True or (ROOT/'native-lab/MTGA.exe').exists():raise ValueError('Use a private headless research runtime')
    preparation=json.loads((ROOT.parent/'preparation.json').read_text())
    if sha(manifest_path)!=preparation['generatedManifestSha256']:raise ValueError('Manifest changed after preparation')
    for name,digest in preparation['classes'].items():
        if sha(ROOT/'build/ForgeBackend/classes'/name)!=digest:raise ValueError('Compiled engine changed')
    pool_input=json.loads(a.pool.read_text(encoding='utf8'))
    if pool_input.get('arenaOnly') is not True:raise ValueError('Arena-only audited pool required')
    chosen={}
    for c in pool_input['cards']:
        if c['status']=='identity-candidate':chosen.setdefault(c['nativeName'],c)
    # Preserve popular-first order as captured by the collector. Stable modulo
    # partitions cover every identity exactly once when all shards finish.
    cards=list(chosen)[a.shard_index::a.shard_count]
    if a.limit:cards=cards[:a.limit]
    a.output.mkdir(parents=True,exist_ok=False)
    projection=json.loads(a.projection.read_text(encoding='utf8'))['cards']
    if a.activations:cards=[name for name in cards if any(v.get('activated') and not v.get('mana') for v in projection.get(name,{}).get('abilities',[]))]
    report=dict(schema=1,status='running',shardIndex=a.shard_index,shardCount=a.shard_count,
                planned=len(cards),startedUtc=datetime.now(timezone.utc).isoformat(),
                inputs={str(p.resolve()):sha(p) for p in [a.pool,a.projection,a.config,manifest_path,Path(__file__),Path(__file__).with_name('native_test_policy.py')]},
                scope=__doc__,activationWalkthrough=a.activations,newAdmissions=0,effectVerifiedCards=0,cases=[])
    def save():
        report['counts']=dict(Counter(c['status'] for c in report['cases']))
        atomic(a.output/'report.json',report)
    save()
    with WarmPool(a.output/'workers',maximum=50) as workers:
        for name in cards:
            started=time.monotonic();row=dict(card=name,status='pending');e=None;timer=None;expired=threading.Event();trace=[]
            try:
                entry=manifest['cards'].get(name)
                if not entry or not entry.get('admitted'):raise ValueError('Research identity is not mapped: '+name)
                # Non-Arena cards are never synthesized into the fixture.
                state=dict(fixtureHand=[name,'Savannah Lions','Grizzly Bears','Forest'],
                           fixtureLands=[n for n in ['Plains','Island','Swamp','Mountain','Forest'] for _ in range(6)],
                           fixtureBattlefield=['Grizzly Bears','Field Creeper'],fixtureBattlefieldReady=True,
                           fixtureOpponentBattlefield=['Grizzly Bears','Field Creeper'],
                           fixtureGraveyard=['Savannah Lions','Opt'],fixtureOpponentGraveyard=['Savannah Lions','Opt'],
                           fixtureLibrary=['Forest','Grizzly Bears','Island','Savannah Lions']*10,randomSeed=7274)
                source=projection.get(name,{})
                if any(x.get('api')=='Counter' and x.get('spell') for x in source.get('abilities',[])):
                    state.update(fixtureOpponentSpell='Divination',fixtureOpponentLands=['Island']*3)
                current=workers.ensure_worker()
                def abort():expired.set();current.poison()
                timer=threading.Timer(a.timeout,abort);timer.daemon=True;timer.start()
                e=workers.engine_existing(current,'card-family',**state)
                if e.state['fidelityGap']:raise RuntimeError(e.state['fidelityGap'])
                card=next(c for c in e.state['hand'] if c['name']==name)
                op='play_land' if 'Land' in entry['types'] else 'cast_spell'
                legal='legalLands' if op=='play_land' else 'legalCasts'
                if card['forgeId'] not in e.state[legal]:
                    row.update(status='needs-specific-fixture',reason='Forge did not offer this card in the generic fixture; this is not a card failure')
                else:
                    execute(e,trace,op,card['forgeId'])
                    for _ in range(16):
                        if not e.state.get('stackOrder') or e.state.get('gameOver'):break
                        execute(e,trace,'pass_priority')
                    else:raise RuntimeError('Stack exceeded sixteen resolution steps; needs a dedicated bounded interaction case')
                    if e.state['fidelityGap']:raise RuntimeError(e.state['fidelityGap'])
                    if e.process.poll() is not None:raise RuntimeError('Rules process exited')
                    if a.activations:
                        def offers():return [v for v in e.state.get('legalActivations',[]) if v['forgeId']==card['forgeId']]
                        # A just-cast tap ability must reach its real next turn;
                        # do not clear sickness or inject intermediate resources.
                        for _ in range(40):
                            if offers() or e.state.get('gameOver') or e.state['turn']>=3 and e.state['phase']=='MAIN1':break
                            execute(e,trace,'pass_priority')
                        available=offers()
                        if not available:
                            row.update(status='needs-specific-fixture',reason='No nonmana ability was offered before the next own main phase; not a card failure')
                        else:
                            chosen=available[0];row.update(abilityId=chosen['abilityId'],offeredAbilityIds=[v['abilityId'] for v in available],activationCoverage='First currently offered ability only; other abilities, modes and interactions remain unverified')
                            execute(e,trace,'activate_ability',card['forgeId'],abilityId=chosen['abilityId'])
                            for _ in range(16):
                                if not e.state.get('stackOrder') or e.state.get('gameOver'):break
                                execute(e,trace,'pass_priority')
                            else:raise RuntimeError('Activated stack exceeded sixteen resolution steps')
                            if e.state['fidelityGap']:raise RuntimeError(e.state['fidelityGap'])
                            row['status']='activation-walkthrough-completed'
                    else:row['status']='walkthrough-completed'
                    row.update(cardId=card['forgeId'],life=e.state['life'],
                               cardZones=[zone for zone in ['hand','battlefield','graveyard','exile','stack','command'] if any(c['forgeId']==card['forgeId'] for c in e.state.get(zone,[]))],
                               pendingStack=len(e.state.get('stackOrder',[])),gameOver=e.state.get('gameOver',False))
            except Exception as error:
                row.update(status='timeout' if expired.is_set() else 'needs-investigation',error=str(error)[-1600:])
                if e:e._case_failed=True
            finally:
                if timer:timer.cancel();timer.join()
                if e:
                    row['evidence']=str(e.ipc)
                    try:e.close()
                    except Exception as error:row.update(status='needs-investigation',cleanupError=str(error)[-500:])
                row.update(seconds=round(time.monotonic()-started,3),decisions=trace)
                report['cases'].append(row);save()
                print(json.dumps({k:v for k,v in row.items() if k not in ('decisions','error','cleanupError')}),flush=True)
    report.update(status='complete',finishedUtc=datetime.now(timezone.utc).isoformat());save()
    print(json.dumps(dict(status='complete',counts=report['counts'],newAdmissions=0,effectVerifiedCards=0)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','pool','projection','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--shard-index',type=int,default=0);p.add_argument('--shard-count',type=int,default=1)
    p.add_argument('--limit',type=int,default=0);p.add_argument('--timeout',type=int,default=60)
    p.add_argument('--activations',action='store_true',help='After a normal cast, exercise the first legally offered nonmana activation, waiting through a real turn if needed. Not exhaustive ability verification.')
    a=p.parse_args()
    if not 0<=a.shard_index<a.shard_count<=4 or not 10<=a.timeout<=120 or a.limit<0:p.error('Invalid shard, timeout or limit')
    run(a)
