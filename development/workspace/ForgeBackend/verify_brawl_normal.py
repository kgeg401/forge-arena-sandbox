"""Drive a normally started 100-card Brawl game using decisions, never state injection."""
from pathlib import Path
import json,sys
from deck_import import read_deck,parse_brawl
from engine_test_client import Engine
from runtime_paths import ROOT
manifest=json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text())['cards']
mana_sources={name for name,data in manifest.items() if data.get('manaColor')}

def option(name):return sys.argv[sys.argv.index(name)+1] if name in sys.argv else None
deck=read_deck(Path(option('--deck')) if option('--deck') else Path(__file__).resolve().parents[1]/'decks/Brawl-Isamaru-Foundation.txt','arena-brawl')
if '--lands-only' in sys.argv:deck=parse_brawl('Commander\n1 Isamaru, Hound of Konda\n\nDeck\n99 Plains\n','Isamaru and99Plains - focused real-start rules probe')
opponent=read_deck(option('--opponent'),'arena-brawl') if option('--opponent') else deck
e=Engine('brawl-duel',localDeck=deck,opponentDeck=opponent,randomSeed=113,startingPlayerPolicy='local-first')
costs=[];returns=0;casts=0;decline='--decline-first-return' in sys.argv
try:
    e.check('Both normally registered players start at25',e.state['life']==25 and e.state['opponentLife']==25)
    e.check('Both real commanders start in command',len(e.state['command'])==2 and all(c['commandCasts']==0 for c in e.state['command']))
    e.check('Local library plus opening hand has99cards',len(e.state['hand'])+sum(c['owner']==1 and c['zone']=='Library' for c in e.state['hidden'])==99)
    e.check('No opponent hidden identity is exposed',all('name' not in c for c in e.state['hidden']))
    for step in range(2200):
        s=e.state
        if s['gameOver']:break
        d=s.get('decision')
        if d:
            kind=d['kind'];values=[]
            if kind=='mulligan':values=[{'keep':True}]
            elif kind=='starting_player':values=[{'startingSeat':1}]
            elif kind=='commander_return':
                if returns==0:
                    for label,invalid in [('stale decision',dict(decisionToken='stale',assignments=[{'returnToCommand':True}])),
                                          ('wrong player',dict(decisionToken=d['token'],assignments=[{'returnToCommand':True}],seat=2)),
                                          ('coerced boolean',dict(decisionToken=d['token'],assignments=[{'returnToCommand':'yes'}])),
                                          ('missing choice',dict(decisionToken=d['token'],assignments=[]))]:
                        r=e.send('submit_commander_return',**invalid)
                        e.check('Reject commander choice with '+label,not r['accepted'] and e.state['decision']['token']==d['token'])
                values=[{'returnToCommand':not(decline and returns==0)}];returns+=1
            elif kind in ('discard','mulligan_bottom'):values=d['options'][:d['count']]
            elif kind=='assign_damage':values=[{'forgeId':v['forgeId'],'amount':v['assignedDamage']} for v in d['options']]
            elif kind=='order_cards':values=[{'forgeId':v['forgeId']} for v in sorted(d['options'],key=lambda v:v['forgeId'])]
            elif kind=='attackers':
                values=[{'forgeId':v['forgeId'],'targetSeat':2} for v in d['options']]
                e.send('select_attackers',decisionToken=d['token'],assignments=values);values=[]
            elif kind=='blockers':
                used=set()
                for v in d['options']:
                    target=next((i for i in v['attackerIds'] if i not in used),None)
                    if target is not None:values.append({'forgeId':v['forgeId'],'attackerIds':[target]});used.add(target)
                e.send('select_blockers',decisionToken=d['token'],assignments=values);values=[]
            elif kind=='targets':
                enemies={c['forgeId'] for c in s['battlefield'] if c['owner']==2}
                candidate=next((v for v in d['options'] if v['forgeId'] in enemies),None)
                if candidate is None:e.send('cancel_targets',decisionToken=d['token']);continue
                e.send('select_targets',decisionToken=d['token'],assignments=[{'forgeId':candidate['forgeId']}]);values=[]
            else:raise AssertionError('Uncovered Brawl decision '+kind)
            fields={'decisionToken':d['token']}
            if kind not in ('attackers','blockers','targets'):fields['assignments']=values
            e.send('submit_'+kind,**fields)
            if kind=='commander_return':
                zone='graveyard' if decline and returns==1 else 'command'
                e.check('Commander reaches chosen '+zone,any(c['commander'] and c['owner']==1 for c in e.state[zone]))
            continue
        if s['legalLands']:e.send('play_land',s['legalLands'][0]);continue
        legal=[c for c in s['hand']+s['command'] if c['forgeId'] in s['legalCasts']]
        if legal:
            card=legal[0];before=sum(c['tapped'] for c in s['battlefield'] if c['owner']==1 and c['name'] in mana_sources)
            expected=None
            if card['commander'] and card['zone']=='Command':
                tax=2*card['commandCasts']
                if card['name']=='Isamaru, Hound of Konda':expected=1+tax
                elif card['name']=='Emry, Lurker of the Loch':
                    artifacts=sum('Artifact' in manifest.get(c['name'],{}).get('types',[]) for c in s['battlefield'] if c['controller']==1)
                    expected=1+max(0,2+tax-artifacts)
                else:raise AssertionError('Add an independent cost expectation for this commander')
            r=e.send('cast_spell',card['forgeId']);e.check('Actual legal spell cast '+str(casts),r['accepted'],r['reason']);casts+=1
            if card['commander'] and card['zone']=='Command':
                after=sum(c['tapped'] for c in e.state['battlefield'] if c['owner']==1 and c['name'] in mana_sources)
                paid=after-before;costs.append(paid)
                e.check('Actual command payment follows source cost, reduction and tax '+str(len(costs)),paid==expected,dict(paid=paid,expected=expected))
            continue
        e.pass_or_decision()
    e.check('Normally started Brawl reaches an engine result',e.state['gameOver'])
    e.check('Commander was actually cast from command',len(costs)>0)
    e.check('No unresolved fidelity gap',not e.state['fidelityGap'])
    if '--lands-only' in sys.argv:
        e.check('Repeated commander recasts exercise at least W,2W,4W',costs[:3]==[1,3,5],costs)
        totals={seat:sum(v['amount'] for v in e.state['events'] if v['kind']=='damage' and v.get('combat') and v.get('targetSeat')==seat) for seat in (1,2)}
        e.check('Brawl does not lose to21commander damage',totals[1]>=21 and totals[2]>=21 and e.state['life']>0 and e.state['opponentLife']>0 and e.state['lossReason']=='Milled',totals)
    result=dict(evidence=str(e.ipc),checks=len(e.checks),declinedFirstReturn=decline,turn=e.state['turn'],winner=e.state['winnerSeat'],life=[e.state['life'],e.state['opponentLife']],commanderCosts=costs,commanderReturnDecisions=returns,
                scope='Actual Match.startGame and inputs only. This run may not exercise every return/tax branch; no rendered-game claim.')
    (e.ipc/'brawl-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
finally:e.close()
