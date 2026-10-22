from engine_test_client import Engine
import json

for case in ('idle','wrong-color','resolve','cancel','concede'):
    scenario='counter-ready-idle' if case=='idle' else 'counter-ready-white' if case=='wrong-color' else 'counter-ready'
    e=Engine(scenario)
    try:
        spell=e.state['hand'][0]['forgeId']
        if case in ('idle','wrong-color'):
            e.check('counter unavailable without a creature spell or blue source',not e.state['legalCasts'])
            r=e.send('cast_spell',spell);e.check('unavailable counter request is rejected',not r['accepted'])
        else:
            target=e.state['stack'][0]['forgeId']
            e.check('fixture actually pays for its prepared creature spell',any(c['owner']==2 and c['name']=='Plains' and c['tapped'] for c in e.state['battlefield']))
            e.check('counter is offered against the actual creature spell',spell in e.state['legalCasts'])
            parent=e.begin('cast_spell',spell);p=e.wait_json(e.ipc/'decision.json');e.state=p['state'];d=e.state['decision'];fields={'decisionToken':d['token']}
            e.check('offered target is an independent real stack entry',len(d['options'])==1 and d['options'][0]['forgeId']==target and d['options'][0]['targetKind']=='spell' and d['options'][0]['stackInstanceId']>0)
            if case=='resolve':
                permanent=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Yoked Ox')
                r=e.send('select_targets',assignments=[{'forgeId':permanent}],**fields);e.check('a battlefield creature is not a creature spell',not r['accepted'])
                r=e.send('submit_targets',**fields);e.check('target is required before paying',not r['accepted'] and all(not c['tapped'] for c in e.state['battlefield'] if c['owner']==1))
                e.send('select_targets',assignments=[{'forgeId':target}],**fields);e.send('submit_targets',**fields);e.finish(parent)
                e.check('counter is above its target in real stack order',e.state['stackOrder']==[spell,target] and next(c for c in e.state['stack'] if c['forgeId']==spell)['targetForgeIds']==[target])
                e.check('Forge pays both generic and blue mana',all(c['tapped'] for c in e.state['battlefield'] if c['owner']==1) and e.state['manaTotal']==0)
                e.pass_or_decision()
                e.check('creature is countered before entering battlefield',not e.state['stack'] and {spell,target}.issubset({c['forgeId'] for c in e.state['graveyard']}) and not any(c['forgeId']==target for c in e.state['battlefield']))
                e.check('actual counter effect names its source and target',len(e.state['events'])==1 and e.state['events'][0]['kind']=='countered' and e.state['events'][0]['sourceForgeId']==spell and e.state['events'][0]['targetForgeId']==target)
                e.check('counter causes no damage or life change',e.state['life']==20 and e.state['opponentLife']==20)
            elif case=='cancel':
                e.send('cancel_targets',**fields);e.finish(parent)
                e.check('cancel keeps counter, mana and opposing stack intact',e.state['hand'][0]['forgeId']==spell and e.state['stackOrder']==[target] and all(not c['tapped'] for c in e.state['battlefield'] if c['owner']==1))
                e.pass_or_decision();e.check('uncountered creature resolves normally',any(c['forgeId']==target for c in e.state['battlefield']) and not e.state['stack'])
            else:
                e.send('concede');e.check('concession releases spell-target callback',e.state['gameOver'])
        print(json.dumps({'case':case,'evidence':str(e.ipc),'checks':len(e.checks)}),flush=True)
    finally:e.close()
