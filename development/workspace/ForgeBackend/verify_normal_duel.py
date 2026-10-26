"""Complete a genuinely started game; inputs only, no intermediate-state feed."""
from engine_test_client import Engine
import json,sys

scenario=sys.argv[2] if len(sys.argv)>2 else 'opening-duel'
settings={'randomSeed':int(sys.argv[1]) if len(sys.argv)>1 else 7274}
if scenario=='custom-duel':
    from deck_import import read_deck
    from pathlib import Path
    repo=Path(__file__).resolve().parents[1]
    settings.update(localDeck=read_deck(Path(sys.argv[3]) if len(sys.argv)>3 else repo/'decks/White-Lifegain.txt'),opponentDeck=read_deck(Path(sys.argv[4]) if len(sys.argv)>4 else repo/'decks/White-Blue-Tempo.txt'))
e=Engine(scenario,**settings)
try:
    declarations=0;seen=set();casts=0;start_names=[c['name'] for c in e.state['hand']]
    for step in range(1800):
        s=e.state
        if s['gameOver']:break
        d=s.get('decision')
        if d:
            kind=d['kind'];fields={'decisionToken':d['token']};assignments=[]
            if kind=='mulligan':
                if not start_names:start_names=[c['name'] for c in s['hand']]
                land_count=sum('Land' in c.get('currentTypes',[]) or c['name'] in ('Plains','Island','Swamp','Mountain','Forest','Seat of the Synod') for c in s['hand'])
                fields['assignments']=[{'keep':2<=land_count<=5 or s['mulligans']>=2}]
            elif kind=='starting_player':fields['assignments']=[{'startingSeat':1}]
            elif kind=='assign_damage':
                fields['assignments']=[{'forgeId':v['forgeId'],'amount':v['assignedDamage']} for v in d['options']]
            elif kind=='order_cards':fields['assignments']=[{'forgeId':v['forgeId']} for v in sorted(d['options'],key=lambda v:v['forgeId'])]
            elif kind=='discard':fields['assignments']=d['options'][:d['count']]
            elif kind=='mulligan_bottom':
                hand={c['forgeId']:c for c in s['hand']}
                bottom=sorted(d['options'],key=lambda o:'Land' in hand[o['forgeId']].get('currentTypes',[]) or hand[o['forgeId']]['name'] in ('Plains','Island','Swamp','Mountain','Forest','Seat of the Synod'))
                fields['assignments']=bottom[:d['count']]
            elif kind=='attackers':assignments=[{'forgeId':v['forgeId'],'targetSeat':2} for v in d['options']]
            elif kind=='blockers':
                used=set()
                for v in d['options']:
                    target=next((i for i in v['attackerIds'] if i not in used),None)
                    if target is not None:assignments.append({'forgeId':v['forgeId'],'attackerIds':[target]});used.add(target)
            elif kind=='targets':
                enemies={c['forgeId'] for c in s['battlefield'] if c['owner']==2}
                target=next((v for v in d['options'] if v['forgeId'] in enemies),d['options'][0])
                assignments=[{'forgeId':target['forgeId']}]
            else:raise AssertionError(d)
            if assignments:
                r=e.send('select_'+kind,assignments=assignments,**fields);assert r['accepted'],r
            r=e.send('submit_'+kind,**fields);assert r['accepted'],r;declarations+=1
        elif s['legalLands']:
            r=e.send('play_land',s['legalLands'][0]);assert r['accepted'],r
        elif s['legalCasts']:
            r=e.send('cast_spell',s['legalCasts'][0]);assert r['accepted'],r;casts+=1
        else:
            r,d=e.pass_or_decision()
        for c in e.state['battlefield']+e.state['graveyard']+e.state['stack']:
            if c['owner']==2:seen.add(c['name'])
        if step%100==0:print(step,e.state['turn'],e.state['phase'],e.state['life'],e.state['opponentLife'],flush=True)
    e.check('complete normal game reaches an engine outcome',e.state['gameOver'])
    e.check('real phase loop handles repeated human decisions',declarations>=3,declarations)
    e.check('local controller abilities are executed inside the phase loop',casts>=1,casts)
    e.check('normal game uses the actual Forge opponent',len(seen)>=2,seen)
    e.check('hidden zones omit future identities',all('name' not in c for c in e.state['hidden']))
    e.check('terminal state has no legal gameplay',not any(e.state[k] for k in ('legalLands','legalCasts','legalMana','canPass')))
    history=[json.loads(line) for line in (e.ipc/'engine-journal.jsonl').read_text().splitlines()]
    e.check('completed startup and gameplay evidence is preserved',any(x.get('event')=='decision-open' for x in history) and sum('request' in x for x in history)>100)
    print(json.dumps({'evidence':str(e.ipc),'seed':e.state['randomSeed'],'openingHand':start_names,'checks':len(e.checks),'turn':e.state['turn'],'winner':e.state['winnerSeat'],'reason':e.state['lossReason'],'life':[e.state['life'],e.state['opponentLife']]},indent=2))
finally:e.close()
