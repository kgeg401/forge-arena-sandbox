from engine_test_client import Engine
import json

for scenario in ('blue-wrong-color','blue-bounce'):
    e=Engine(scenario)
    try:
        spell=e.state['hand'][0]['forgeId']
        if scenario=='blue-wrong-color':
            e.check('white sources cannot pay Unsummon',not e.state['legalCasts'])
            r=e.send('cast_spell',spell);e.check('wrong-color direct request is rejected',not r['accepted'] and not e.state['stack'])
        else:
            island=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Island')
            e.send('activate_mana',island)
            e.check('Island produces actual blue mana',len(e.state['mana'])==1 and e.state['mana'][0]['color']==2 and e.state['mana'][0]['sourceForgeId']==island)
            e.check('blue mana permits Unsummon',spell in e.state['legalCasts'])
            target=next(c['forgeId'] for c in e.state['battlefield'] if c['owner']==2)
            parent=e.begin('cast_spell',spell);p=e.wait_json(e.ipc/'decision.json');e.state=p['state'];d=e.state['decision'];fields={'decisionToken':d['token']}
            e.check('both creatures but no lands are offered',len(d['options'])==2 and {v['forgeId'] for v in d['options']}=={c['forgeId'] for c in e.state['battlefield'] if c['name'] in ('Savannah Lions','Yoked Ox')})
            land=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Plains')
            r=e.send('select_targets',assignments=[{'forgeId':land}],**fields);e.check('land target is rejected',not r['accepted'])
            e.send('select_targets',assignments=[{'forgeId':target}],**fields);e.send('submit_targets',**fields);e.finish(parent)
            e.check('blue mana is spent on actual stacked spell',e.state['manaTotal']==0 and e.state['stack'][0]['targetForgeIds']==[target])
            e.pass_or_decision()
            e.check('opponent creature returns to its hidden hand',any(c['forgeId']==target and c['owner']==2 and c['zone']=='Hand' and 'name' not in c for c in e.state['hidden']) and not any(c['forgeId']==target for c in e.state['battlefield']))
            e.check('return is not damage or a death',not e.state['events'] and all(c['forgeId']!=target for c in e.state['graveyard']))
            e.check('spell resolves to graveyard with no lingering stack',any(c['forgeId']==spell for c in e.state['graveyard']) and not e.state['stack'])
            second=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Unsummon')
            friendly=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Savannah Lions')
            parent=e.begin('cast_spell',second);p=e.wait_json(e.ipc/'decision.json');e.state=p['state'];d=e.state['decision'];fields={'decisionToken':d['token']}
            e.send('select_targets',assignments=[{'forgeId':friendly}],**fields);e.send('submit_targets',**fields);e.finish(parent);e.pass_or_decision()
            e.check('friendly creature returns to visible local hand',any(c['forgeId']==friendly and c['name']=='Savannah Lions' for c in e.state['hand']) and not any(c['forgeId']==friendly for c in e.state['battlefield']))
            r=e.send('cast_spell',friendly);e.check('returned creature can be recast with white mana',r['accepted'] and e.state['stack'][0]['forgeId']==friendly)
            e.pass_or_decision();lion=next(c for c in e.state['battlefield'] if c['forgeId']==friendly)
            e.check('recast creature is a fresh sick permanent',lion['sick'] and lion['damage']==0)
        print(json.dumps({'scenario':scenario,'evidence':str(e.ipc),'checks':len(e.checks)}),flush=True)
    finally:e.close()
