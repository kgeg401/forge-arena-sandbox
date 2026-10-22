from engine_test_client import Engine
import json

for scenario,orator_count in [('trigger-orator',1),('trigger-orator-double',2)]:
    e=Engine(scenario)
    try:
        for index in range(orator_count):
            card=next(c for c in e.state['hand'] if c['name']=='Impassioned Orator')
            r=e.send('cast_spell',card['forgeId']);e.check('Orator cast accepted '+str(index),r['accepted'])
            e.check('creature spell is the actual top stack item '+str(index),e.state['stackOrder']==[card['forgeId']] and not e.state['stackAbilities'])
            r,d=e.pass_or_decision();assert d is None,d
            e.check('only existing Orators trigger on arrival '+str(index),len(e.state['stackAbilities'])==index)
            if index:
                trigger=e.state['stackAbilities'][0]
                e.check('trigger has an independent stack identity',trigger['forgeId']<0 and trigger['sourceForgeId']!=card['forgeId'] and trigger['triggered'] and e.state['stackOrder']==[trigger['forgeId']])
                e.pass_or_decision()
                e.check('first Orator gains life for the second',e.state['life']==21 and not e.state['stackAbilities'])
        lion=next(c for c in e.state['hand'] if c['name']=='Savannah Lions')
        r=e.send('cast_spell',lion['forgeId']);e.check('Lion cast accepted',r['accepted'])
        e.pass_or_decision()
        abilities=e.state['stackAbilities'];order=e.state['stackOrder'][:]
        e.check('one independently identified trigger per Orator',len(abilities)==orator_count and len(set(a['sourceForgeId'] for a in abilities))==orator_count and set(order)=={a['forgeId'] for a in abilities})
        before=e.state['life']
        for index,top in enumerate(order):
            r,d=e.pass_or_decision();assert d is None,d
            e.check('trigger resolves in real Forge stack order '+str(index),e.state['life']==before+index+1 and e.state['events'][-1]['sourceStackForgeId']==top and e.state['stackOrder']==order[index+1:])
        e.check('no extra trigger or fidelity gap',e.state['life']==(21 if orator_count==1 else 23) and not e.state['stackAbilities'] and not e.state['fidelityGap'])
        print(json.dumps({'scenario':scenario,'evidence':str(e.ipc),'checks':len(e.checks)}),flush=True)
    finally:e.close()
