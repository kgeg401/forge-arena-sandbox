from engine_test_client import Engine
import json,time
from runtime_paths import ROOT
full_human_choices=json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text()).get('fullHumanChoices') is True

for case in ('resolve','cancel','concede'):
    e=Engine('defend-arrow')
    try:
        arrow=e.state['hand'][0]['forgeId'];before=json.loads(json.dumps(e.state))
        e.check('Divine Arrow unavailable without a combat target',not e.state['legalCasts'])
        for _ in range(8):
            if e.state['legalCasts']:break
            r,d=e.pass_or_decision();assert d is None,d
        e.check('instant becomes available after an attacker is declared',e.state['phase']=='COMBAT_DECLARE_ATTACKERS' and arrow in e.state['legalCasts'])
        parent=e.begin('cast_spell',arrow);progress=e.wait_json(e.ipc/'decision.json');e.state=progress['state'];d=e.state['decision'];token=d['token'];target=d['options'][0]['forgeId']
        e.check('Forge offers only the eligible attacker',d['kind']=='targets' and len(d['options'])==1 and any(c['forgeId']==target and c['attackTarget']==1 for c in e.state['battlefield']))
        # Original PlaySpellAbility moves the card to Stack while announcing
        # it, before costs. The older narrow controller announced it in Hand.
        pending_zone='stack' if full_human_choices else 'hand'
        e.check('Target choice precedes payment and retains the original pending source',any(c['forgeId']==arrow for c in e.state[pending_zone]) and all(not c['tapped'] for c in e.state['battlefield'] if c['owner']==1 and c['name']=='Plains') and not e.state['manaTotal'])
        if case=='resolve':
            r=e.send('submit_targets',decisionToken=token);e.check('empty target submission rejected',not r['accepted'])
            idle=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Yoked Ox')
            r=e.send('select_targets',decisionToken=token,assignments=[{'forgeId':idle}]);e.check('idle creature is not a valid combat target',not r['accepted'])
            r=e.send('select_targets',decisionToken=token,assignments=[{'forgeId':target}]);e.check('eligible selection accepted',r['accepted'])
            r=e.send('select_targets',decisionToken=token,assignments=[{'forgeId':target,'selected':False}]);e.check('target may be unselected',r['accepted'] and not e.state['decision']['assignments'])
            r=e.send('submit_targets',decisionToken=token);e.check('unselected target cannot be submitted',not r['accepted'])
            e.send('select_targets',decisionToken=token,assignments=[{'forgeId':target}]);r=e.send('submit_targets',decisionToken=token);assert r['accepted'],r;e.finish(parent)
            e.check('chosen target belongs to the actual stacked spell',len(e.state['stack'])==1 and e.state['stack'][0]['targetForgeIds']==[target])
            e.check('Forge pays both mana from two Plains',sum(c['tapped'] for c in e.state['battlefield'] if c['owner']==1 and c['name']=='Plains')==2 and e.state['manaTotal']==0)
            r,d=e.pass_or_decision();assert not d,d
            e.check('spell deals four noncombat damage',any(v['kind']=='damage' and v['sourceForgeId']==arrow and v['targetForgeId']==target and v['amount']==4 and not v['combat'] for v in e.state['events']))
            e.check('resolution and SBA put spell and creature in graveyards',{arrow,target}.issubset({c['forgeId'] for c in e.state['graveyard']}) and not e.state['stack'])
            e.check('the untargeted creature and player survive',any(c['forgeId']==idle for c in e.state['battlefield']) and e.state['life']==20)
        elif case=='cancel':
            r=e.send('cancel_targets',decisionToken=token);e.check('pending target choice cancels cleanly',r['accepted'] and e.state.get('decision') is None);e.finish(parent)
            e.check('canceled cast leaves card and resources available',e.state['hand'][0]['forgeId']==arrow and not e.state['stack'] and all(not c['tapped'] for c in e.state['battlefield'] if c['owner']==1 and c['name']=='Plains') and arrow in e.state['legalCasts'])
        else:
            r=e.send('concede');e.check('concession releases target-selection callback',r['accepted'] and e.state['gameOver'] and not e.state['legalCasts'])
        print(json.dumps({'case':case,'evidence':str(e.ipc),'checks':len(e.checks)}),flush=True)
    finally:e.close()
