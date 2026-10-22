from engine_test_client import Engine
import json

for case in ('kill-lion','spare-lion','concede'):
    e=Engine('attack-double-blocked')
    try:
        for _ in range(15):
            d=e.state.get('decision')
            if d and d['kind']=='assign_damage':break
            if d:
                assert d['kind']=='attackers',d
                e.send('select_attackers',decisionToken=d['token'],assignments=[{'forgeId':v['forgeId'],'targetSeat':2} for v in d['options']])
                e.send('submit_attackers',decisionToken=d['token'])
            else:e.pass_or_decision()
        d=e.state['decision'];assert d['kind']=='assign_damage',d
        e.check('real damage callback pauses before hits',d['totalDamage']==3 and len(d['options'])==2 and not e.state['events'])
        cards={c['name']:c['forgeId'] for c in e.state['battlefield']};lion=cards['Savannah Lions'];ox=cards['Yoked Ox'];swift=cards['Oreskos Swiftclaw'];fields={'decisionToken':d['token']}
        if case=='concede':
            r=e.send('concede');e.check('concession releases damage callback',r['accepted'] and e.state['gameOver'])
        else:
            if case=='kill-lion':
                for label,values in [('missing recipient',[{'forgeId':lion,'amount':3}]),('duplicate recipient',[{'forgeId':lion,'amount':1},{'forgeId':lion,'amount':2}]),('foreign recipient',[{'forgeId':swift,'amount':1},{'forgeId':ox,'amount':2}]),('negative',[{'forgeId':lion,'amount':-1},{'forgeId':ox,'amount':4}]),('over total',[{'forgeId':lion,'amount':4},{'forgeId':ox,'amount':0}]),('under total',[{'forgeId':lion,'amount':1},{'forgeId':ox,'amount':1}]),('fractional',[{'forgeId':lion,'amount':1.5},{'forgeId':ox,'amount':1.5}]),('integer overflow',[{'forgeId':lion,'amount':4294967299},{'forgeId':ox,'amount':0}])]:
                    r=e.send('submit_assign_damage',assignments=values,**fields);e.check('reject '+label,not r['accepted'] and e.state['decision']['token']==d['token'] and not e.state['events'])
                r=e.send('submit_assign_damage',decisionToken='obsolete-token',assignments=[]);e.check('stale allocation rejected',not r['accepted'])
            allocation=[{'forgeId':lion,'amount':1 if case=='kill-lion' else 0},{'forgeId':ox,'amount':2 if case=='kill-lion' else 3}]
            r=e.send('submit_assign_damage',assignments=allocation,**fields);e.check('human allocation accepted',r['accepted'] and e.state.get('decision') is None)
            for _ in range(5):
                if e.state['events']:break
                e.pass_or_decision()
            damage={v['targetForgeId']:v['amount'] for v in e.state['events'] if v['kind']=='damage' and v['sourceForgeId']==swift and v['amount']>0}
            e.check('Forge applies the submitted distribution',damage==({lion:1,ox:2} if case=='kill-lion' else {ox:3}),damage)
            e.check('attacker dies from blocker damage',any(c['forgeId']==swift for c in e.state['graveyard']))
            e.check('Lion survival follows human allocation',any(c['forgeId']==lion for c in e.state['graveyard'])==(case=='kill-lion'))
            e.check('Ox survives with correct marked damage',any(c['forgeId']==ox and c['damage']==(2 if case=='kill-lion' else 3) for c in e.state['battlefield']))
            e.check('blocked vanilla attacker deals no player damage',e.state['life']==20 and e.state['opponentLife']==20)
        print(json.dumps({'case':case,'evidence':str(e.ipc),'checks':len(e.checks)}),flush=True)
    finally:e.close()
