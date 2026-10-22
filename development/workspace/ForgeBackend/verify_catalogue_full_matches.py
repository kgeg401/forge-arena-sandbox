"""Normally shuffled input-only games, recording actual per-card resolutions.

The bot's visible choices are explicit test policies, not inherited AI answers
for the local human controller. Full games supplement independently authored
rules scenarios; winning a game does not establish every card interaction.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def damage_policy(decision):
    """Explicit test-bot input: lethal to cards in offered order, rest to player.

    Uses public decision thresholds, never the human controller's inherited AI.
    A zero-player overkill assignment is also legal, but does not exercise excess.
    """
    options=decision['options'];remaining=decision['totalDamage'];result=[]
    players=[v for v in options if v.get('targetKind')=='player']
    if len(players)>1:raise AssertionError('No test bot policy for multiple attack targets')
    for option in options:
        if option in players:continue
        lethal=option.get('lethalDamage')
        if type(lethal) is not int or lethal<0:raise AssertionError('Missing public lethal threshold')
        amount=min(remaining,lethal);remaining-=amount
        result.append(dict(forgeId=option['forgeId'],amount=amount))
    if players:result.append(dict(forgeId=players[0]['forgeId'],amount=remaining));remaining=0
    elif result:result[-1]['amount']+=remaining;remaining=0
    if remaining or not result:raise AssertionError('No complete damage recipient set')
    return result


def begin_cast(e,identity):
    """Wait for the accepted cast or its real local target decision."""
    request=e.begin('cast_spell',identity);end=time.monotonic()+8
    while time.monotonic()<end:
        if (e.ipc/'responses'/(request+'.json')).exists():
            reply=e.finish(request);assert reply['accepted'],reply;return None
        path=e.ipc/'decision.json'
        try:value=json.loads(path.read_text())
        except (FileNotFoundError,PermissionError,json.JSONDecodeError):value=None
        if value and value['parentRequestId']==request:
            e.state=value['state'];return request
        if e.process.poll() is not None:raise RuntimeError('Rules owner exited during cast')
        time.sleep(.025)
    raise TimeoutError('Cast neither returned nor exposed a human decision')


def run(a):
    os.environ['FORGE_ARENA_CONFIG']=str(a.config.resolve());os.environ['FORGE_ARENA_POLICY']=str(a.policy.resolve())
    from engine_test_client import Engine
    from runtime_paths import ROOT
    from deck_import import read_deck
    from run_background_validation import lower_resources
    lower_resources()
    if (ROOT/'native-lab/MTGA.exe').exists():raise ValueError('Independent research runtime required')
    manifest_path=ROOT/'native-lab/bridge-card-manifest.json';manifest=json.loads(manifest_path.read_text())
    if not manifest.get('researchOnly'):raise ValueError('Research policy required')
    proposals=json.loads(a.proposals.read_text(encoding='utf8'))
    specs={p['name']:p for p in proposals['proposals']};extra_inputs=[]
    for path in a.additional_proposals:
        extra=json.loads(path.read_text(encoding='utf8'));qualifier=Path(extra['qualifierSource'])
        if extra['provenance']!=proposals['provenance'] or sha(qualifier)!=extra['qualifierSha256'] or extra.get('newAdmissions')!=0:raise ValueError('Additional source family differs')
        for p in extra['proposals']:
            if p['name'] in specs:raise ValueError('Duplicate source proposal')
            specs[p['name']]=p
        extra_inputs.extend((path,qualifier))
    if not set(a.require_card)<=specs.keys():raise ValueError('Expected cards need independent source proposals')
    if proposals['provenance']['databaseSha256']!=manifest['sourceDatabaseSha256'] or proposals['provenance']['scriptsSha256']!=manifest['sourceForgeScriptsSha256']:raise ValueError('Native/source oracle provenance changed')
    for name in a.require_card:
        if manifest['cards'][name]['grpId']!=specs[name]['printing']:raise ValueError('Expected printing differs')
    preparation=json.loads((ROOT.parent/'preparation.json').read_text())
    if preparation['sourceSha256']!=sha(HERE/'ForgeLandEngine.java') or preparation['classes']!={p.name:sha(p) for p in (ROOT/'build/ForgeBackend/classes').glob('ForgeLandEngine*.class')}:raise ValueError('Prepared rules source/classes differ')
    a.output.mkdir(parents=True,exist_ok=False);archive=a.output/'source';archive.mkdir()
    inputs=[a.config,a.policy,a.proposals,*extra_inputs,a.local_deck,a.opponent_deck,manifest_path,ROOT.parent/'preparation.json',HERE/'ForgeLandEngine.java',HERE/'engine_test_client.py',HERE/'deck_import.py',HERE/'runtime_paths.py',Path(__file__),ROOT/'forge-runtime/forge.jar',ROOT/'forge-runtime/gson.jar',*sorted((ROOT/'build/ForgeBackend/classes').glob('ForgeLandEngine*.class'))]
    identities={str(p.resolve()):sha(p) for p in inputs}
    archived={}
    for index,path in enumerate(inputs):
        if path.suffix in ('.py','.java','.json','.txt'):
            copy=archive/(str(index)+'-'+path.name);shutil.copy2(path,copy);archived[str(path.resolve())]=str(copy)
    (a.output/'inputs.json').write_text(json.dumps(dict(schema=2,identities=identities,sourceCopies=archived,botPolicy='Always keep; choose local starting seat; lowest-ID discards; all legal attacks; one legal block per attacker; lethal damage to cards in offered order and remainder to the opposing player, or last card if no player; cast the first legal offer; for a single unrestricted-creature pump choose the lowest-ID legal friendly creature, otherwise the lowest-ID legal creature; unknown decisions fail.'),indent=2),encoding='utf8')
    decks=[read_deck(a.local_deck),read_deck(a.opponent_deck)];reports=[];all_resolved=defaultdict(Counter)
    locks=ROOT/'research/background-runs';locks.mkdir(parents=True,exist_ok=True)
    with (locks/'validation.lock').open('a+b') as lease:
        lease.seek(0);lease.write(b'1');lease.flush();lease.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
        for index in range(a.matches):
            if any(sha(Path(p))!=digest for p,digest in identities.items()):raise ValueError('Source/input changed; stop before next game')
            e=Engine('custom-duel',randomSeed=a.seed+index,localDeck=decks[index%2],opponentDeck=decks[1-index%2],startingPlayerPolicy='local-first')
            objects={};decisions=0;casts=0;damage_choices=[];started=time.monotonic();pending_cast=None
            def observe():
                for zone in ('hand','battlefield','graveyard','exile','command','stack'):
                    for card in e.state.get(zone,[]):objects[card['forgeId']]=card
            try:
                observe()
                for step in range(2000):
                    if time.monotonic()-started>a.game_seconds:raise TimeoutError('Bounded complete-game deadline exceeded')
                    s=e.state
                    if s['gameOver']:break
                    if s.get('fidelityGap'):raise AssertionError(s['fidelityGap'])
                    if s.get('researchControls',{}).get('strictHumanCallbacks') is not True:raise AssertionError('No strict human controller')
                    d=s.get('decision')
                    if d:
                        kind=d['kind'];fields=dict(decisionToken=d['token']);values=[]
                        if kind=='mulligan':fields['assignments']=[dict(keep=True)]
                        elif kind=='starting_player':fields['assignments']=[dict(startingSeat=1)]
                        elif kind in ('discard','mulligan_bottom'):fields['assignments']=sorted(d['options'],key=lambda v:v['forgeId'])[:d['count']]
                        elif kind=='attackers':values=[dict(forgeId=v['forgeId'],targetSeat=2) for v in d['options']]
                        elif kind=='blockers':
                            used=set()
                            for v in d['options']:
                                target=next((n for n in v['attackerIds'] if n not in used),None)
                                if target is not None:values.append(dict(forgeId=v['forgeId'],attackerIds=[target]));used.add(target)
                        elif kind=='assign_damage':
                            fields['assignments']=damage_policy(d)
                            damage_choices.append(dict(token=d['token'],total=d['totalDamage'],options=d['options'],assignments=fields['assignments']))
                        elif kind=='targets':
                            source=objects.get(d['sourceForgeId'],{});spec=specs.get(source.get('name'),{})
                            if spec.get('template') not in ('fixed-target-pump-v1','fixed-target-signed-pump-v1','fixed-creature-removal-v1','fixed-creature-damage-v1') or d.get('minTargets')!=1 or d.get('maxTargets')!=1:raise AssertionError('No explicit full-game target policy for this source')
                            legal=[v for v in d['options'] if v['forgeId'] in objects and objects[v['forgeId']].get('zone')=='Battlefield']
                            if len(legal)!=len(d['options']) or not legal:raise AssertionError('Pump target policy requires visible battlefield creatures')
                            preferred=1 if spec['template']=='fixed-target-pump-v1' else 2
                            choice=min(legal,key=lambda v:(objects[v['forgeId']]['owner']!=preferred,v['forgeId']))
                            values=[dict(forgeId=choice['forgeId'])]
                        elif kind=='order_cards':fields['assignments']=[dict(forgeId=v['forgeId']) for v in sorted(d['options'],key=lambda v:v['forgeId'])]
                        else:raise AssertionError('No explicit test bot policy for decision '+kind)
                        if values:
                            reply=e.send('select_'+kind,assignments=values,**fields);assert reply['accepted'],reply
                        reply=e.send('submit_'+kind,**fields);assert reply['accepted'],reply;decisions+=1
                        if kind=='targets' and pending_cast:
                            reply=e.finish(pending_cast);assert reply['accepted'],reply;pending_cast=None
                    elif s['legalLands']:
                        reply=e.send('play_land',s['legalLands'][0]);assert reply['accepted'],reply
                    elif s['legalCasts']:
                        pending_cast=begin_cast(e,s['legalCasts'][0]);casts+=1
                    else:e.pass_or_decision()
                    observe()
                e.check('Normally shuffled real game reaches its own terminal outcome',e.state['gameOver'])
                e.check('Actual local inputs occurred without forced outcomes',decisions>=1 and step>0)
                e.check('No unsupported callback or hidden future names',not e.state['fidelityGap'] and all('name' not in c for c in e.state['hidden']))
                e.check('Terminal state offers no gameplay',not any(e.state[k] for k in ('legalLands','legalCasts','legalMana','canPass')))
                resolved=[];fizzled=[]
                trace=e.state['researchTrace']
                for event in trace:
                    if event['kind']!='spell-resolved' or event['sourceForgeId'] not in objects:continue
                    card=objects[event['sourceForgeId']];name=card['name'];owner=card['owner']
                    if name not in a.require_card:continue
                    p=specs[name]
                    if event['hasFizzled'] is True:
                        fizzled.append(dict(name=name,seat=owner,forgeId=card['forgeId']));continue
                    e.check(name+' actually resolves successfully for seat '+str(owner),event['hasFizzled'] is False)
                    if 'oracleEffects' in p:
                        own=[r for r in trace if r.get('sourceStackForgeId')==card['forgeId']]
                        draw=sum(r['kind']=='zone-change' and r['ownerSeat']==owner and r['from']=='Library' and r['to']=='Hand' for r in own)
                        life=sum(r['after']-r['before'] for r in own if r['kind']=='life-change' and r['targetSeat']==owner and r['after']>r['before'])
                        e.check(name+' resolution draws exact native-text amount',draw==sum(r['amount'] for r in p['oracleEffects'] if r['kind']=='Draw'))
                        e.check(name+' resolution gains exact native-text life',life==sum(r['amount'] for r in p['oracleEffects'] if r['kind']=='GainLife'))
                    elif 'oracleCharacteristics' in p:e.check(name+' retains source-printed stats',all(card.get(k)==v for k,v in p['oracleCharacteristics'].items()))
                    elif p['template']=='fixed-creature-removal-v1':
                        transfers=[r for r in trace if r.get('sourceStackForgeId')==card['forgeId'] and r['kind']=='zone-change' and r.get('from')=='Battlefield' and r.get('to')==p['destination']]
                        e.check(name+' actual resolution transfers one creature to the native-text destination',len(transfers)==1)
                    elif p['template']=='fixed-creature-damage-v1':
                        hits=[r for r in e.state['events'] if r['kind']=='damage' and r['sourceForgeId']==card['forgeId']]
                        e.check(name+' actual resolution deals exact native-text noncombat damage',len(hits)==1 and hits[0]['amount']==p['damage'] and hits[0]['combat'] is False)
                    elif p['template'] not in ('fixed-target-pump-v1','fixed-target-signed-pump-v1','conditional-untargeted-draw-life-v1'):raise AssertionError('No complete-match observation policy for source template')
                    resolved.append(dict(name=name,seat=owner,forgeId=card['forgeId']));all_resolved[name][owner]+=1
                row=dict(seed=a.seed+index,evidence=str(e.ipc),checks=len(e.checks),steps=step+1,decisions=decisions,localCasts=casts,winner=e.state['winnerSeat'],reason=e.state['lossReason'],turn=e.state['turn'],resolved=resolved,fizzled=fizzled,damageChoices=damage_choices,seconds=round(time.monotonic()-started,3))
                reports.append(row);(a.output/'progress.json').write_text(json.dumps(reports,indent=2),encoding='utf8')
                print(json.dumps({**{k:v for k,v in row.items() if k not in ('resolved','damageChoices')},'damageChoices':len(damage_choices)}),flush=True)
            finally:e.close()
            for filename in ('scenario.json','checks.json','engine-journal.jsonl'):
                path=e.ipc/filename;row.setdefault('artifacts',{})[str(path)]=sha(path)
    if any(sha(Path(p))!=digest for p,digest in identities.items()):raise ValueError('Source/input changed before report seal')
    missing=[dict(name=n,seat=s) for n in a.require_card for s in (1,2) if not all_resolved[n][s]]
    result=dict(schema=2,researchOnly=True,requiredCards=a.require_card,matches=reports,resolved={n:dict(v) for n,v in all_resolved.items()},missingSeatCoverage=missing,passed=not missing,identities=identities,sourceCopies=archived,newAdmissions=0,
        scope='Complete input-only shuffled games and observed per-card resolutions. Independent targeted rules tests, native presentation and separate admission review remain required.')
    (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    if missing:raise AssertionError('Not every required card actually resolved for both seats: '+str(missing))
    print(json.dumps(dict(report=str(a.output/'report.json'),matches=len(reports),resolved=result['resolved'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','proposals','local-deck','opponent-deck','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--require-card',action='append',required=True);p.add_argument('--matches',type=int,default=4);p.add_argument('--seed',type=int,default=9022)
    p.add_argument('--game-seconds',type=int,default=180)
    p.add_argument('--additional-proposals',type=Path,action='append',default=[])
    a=p.parse_args()
    if not 1<=a.matches<=12:p.error('Match count must be 1..12')
    if not 30<=a.game_seconds<=600:p.error('Per-game bound must be 30..600 seconds')
    run(a)
