"""Version-2 authored scenarios with explicit human decisions and world effects.

Selectors refer to independently specified starting objects. Expected legal
options are compared exactly; the runner never picks the first offered answer.
"""
import json
import time
import traceback
from card_batch_case import CaseFailure


def cards(state):
    return [c for zone in ('hand','battlefield','graveyard','exile','command','stack','hidden') for c in state.get(zone,[])]


def resolve(state,selector):
    if set(selector)=={'targetSeat'}:
        if selector['targetSeat'] not in (1,2):raise CaseFailure('identity','Player seat must be 1 or 2')
        return -1000000-selector['targetSeat']
    found=[c for c in cards(state) if all(c.get(k)==v for k,v in selector.items() if k!='index')]
    if 'index' in selector:
        if selector['index']<0 or selector['index']>=len(found):raise CaseFailure('identity','Selector index is outside the actual objects')
        return found[selector['index']]['forgeId']
    if len(found)!=1:raise CaseFailure('identity','Selector must identify exactly one visible object: '+json.dumps(selector))
    return found[0]['forgeId']


def execute(case,engine_factory=None):
    from engine_test_client import Engine
    e=None
    try:
        e=(engine_factory or Engine)('card-family',randomSeed=case.get('seed',7274),**case['fixture'])
        def check(category,label,value):
            e.checks.append(dict(check=label,category=category,passed=bool(value)))
            if not value:raise CaseFailure(category,label)
        check('controller','Research human callback guard is enabled',e.state.get('researchControls',{}).get('strictHumanCallbacks') is True)

        def assert_no_gap():
            check('controller','No unmapped human callback or source identity',not e.state.get('fidelityGap'))

        pending={}
        def finish_resolution(step,identity,changes):
            before=e.state
            hand={c['forgeId'] for c in before['hand']}
            library={c['forgeId'] for c in before['hidden'] if c['owner']==1 and c['zone']=='Library'}
            stack={c['forgeId'] for c in before['stack']}
            trace_start=len(before.get('researchTrace',[]))
            _,d=e.pass_or_decision()
            if d:raise CaseFailure('controller','Unexpected resolution choice: '+d['kind'])
            assert_no_gap()
            remaining={c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library'}
            drawn=library-remaining
            returned={v['forgeId'] for v in changes if v['to']=='Hand' and any(c['forgeId']==v['forgeId'] and c['owner']==1 for c in cards(before))}
            check('draw','Exact library identities and authored hand changes',len(drawn)==step['draw'] and remaining<=library and {c['forgeId'] for c in e.state['hand']}==hand|drawn|returned)
            check('life','Exact authored life change',e.state['life']-before['life']==step['life'])
            for v in changes:check('zone','Authored target reaches expected zone',any(c['forgeId']==v['forgeId'] and c['zone']==v['to'] for c in cards(e.state)))
            check('resolution','Only the expected original spell leaves the stack',{c['forgeId'] for c in e.state['stack']}==stack-{identity} and any(c['forgeId']==identity for c in e.state[step.get('zone','graveyard')]))
            trace=e.state.get('researchTrace',[])[trace_start:]
            resolved=[r for r in trace if r['kind']=='spell-resolved' and r['sourceForgeId']==identity]
            check('resolution','Actual Forge resolution reports authored fizzle status',len(resolved)==1 and resolved[0]['hasFizzled']==step.get('fizzled',False))
            if 'orderedEffects' in step:
                actual=[]
                for row in trace:
                    if row.get('sourceStackForgeId')!=identity:continue
                    if row['kind']=='zone-change' and row['ownerSeat']==1 and row['from']=='Library' and row['to']=='Hand':
                        if actual and actual[-1]['kind']=='Draw':actual[-1]['amount']+=1
                        else:actual.append(dict(kind='Draw',amount=1))
                    elif row['kind']=='life-change' and row['targetSeat']==1 and row['after']>row['before']:actual.append(dict(kind='GainLife',amount=row['after']-row['before']))
                check('resolution-order','Actual ordered draw/life events match independent source clauses',actual==step['orderedEffects'])
            check('privacy','Hidden opponent objects expose no names',all('name' not in c for c in e.state['hidden']))
            check('outcome','No unintended terminal result',not e.state['gameOver'])

        def choose(plan,d):
            assert_no_gap();token=d['token'];kind=plan['kind']
            check('controller','Actual decision has authored kind',d['kind']==kind)
            if kind=='targets':
                offered={v['forgeId'] for v in d['options']}
                expected={resolve(e.state,s) for s in plan['expectedOptions']}
                check('target','Exactly the authored targets are offered',offered==expected)
                if plan.get('probeEmpty'):
                    r=e.send('submit_targets',decisionToken=token)
                    check('target','Empty target submission is rejected',not r['accepted'] and e.state['decision']['token']==token)
                if plan.get('probeStale'):
                    r=e.send('select_targets',decisionToken='stale-token',assignments=[])
                    check('target','Stale target decision is rejected',not r['accepted'] and e.state['decision']['token']==token)
                for selector in plan.get('invalid',[]):
                    bad=resolve(e.state,selector)
                    r=e.send('select_targets',decisionToken=token,assignments=[dict(forgeId=bad)])
                    check('target','Authored invalid target is rejected',not r['accepted'] and e.state['decision']['token']==token)
                if plan.get('cancel'):
                    r=e.send('cancel_targets',decisionToken=token)
                    check('target','Human cancels before casting/payment',r['accepted'] and not e.state.get('decision'))
                    return
                values=[dict(forgeId=resolve(e.state,s)) for s in plan['choose']]
                check('target','Authored legal selection accepted',e.send('select_targets',decisionToken=token,assignments=values)['accepted'])
                check('target','Human target submission accepted',e.send('submit_targets',decisionToken=token)['accepted'])
            elif kind=='blockers':
                values=[dict(forgeId=resolve(e.state,v['blocker']),attackerIds=[resolve(e.state,a) for a in v['attackers']]) for v in plan['assignments']]
                offered={v['forgeId']:set(v['attackerIds']) for v in d['options']}
                if 'expectedOptions' in plan:
                    expected={resolve(e.state,v['blocker']):{resolve(e.state,a) for a in v['attackers']} for v in plan['expectedOptions']}
                    check('combat','Exactly the authored blocker options are offered',offered==expected)
                check('combat','Every authored block is actually legal',all(v['forgeId'] in offered and set(v['attackerIds'])<=offered[v['forgeId']] for v in values))
                check('combat','Human blocker selection accepted',e.send('select_blockers',decisionToken=token,assignments=values)['accepted'])
                check('combat','Human blocker submission accepted',e.send('submit_blockers',decisionToken=token)['accepted'])
            elif kind=='attackers':
                values=[dict(forgeId=resolve(e.state,s),targetSeat=2) for s in plan['choose']]
                if 'expectedOptions' in plan:check('combat','Exactly the authored attackers are offered',{v['forgeId'] for v in d['options']}=={resolve(e.state,s) for s in plan['expectedOptions']})
                check('combat','Human attacker selection accepted',e.send('select_attackers',decisionToken=token,assignments=values)['accepted'])
                check('combat','Human attacker submission accepted',e.send('submit_attackers',decisionToken=token)['accepted'])
            elif kind=='order_cards':
                expected={resolve(e.state,s) for s in plan['expectedOptions']}
                selected=[resolve(e.state,s) for s in plan['choose']]
                check('zone-order','Exactly the authored graveyard objects need ordering',d.get('destination')=='Graveyard' and {v['forgeId'] for v in d['options']}==expected and len(selected)==len(expected) and set(selected)==expected)
                if plan.get('probeInvalid'):
                    for label,values in [('missing',[dict(forgeId=n) for n in selected[:-1]]),('duplicate',[dict(forgeId=selected[0])]*len(selected)),('unoffered',[dict(forgeId=-99999) for _ in selected])]:
                        r=e.send('submit_order_cards',decisionToken=token,assignments=values)
                        check('zone-order','Invalid '+label+' permutation is rejected',not r['accepted'] and e.state['decision']['token']==token)
                    r=e.send('submit_order_cards',decisionToken='stale-token',assignments=[dict(forgeId=n) for n in selected])
                    check('zone-order','Stale permutation token is rejected',not r['accepted'] and e.state['decision']['token']==token)
                check('zone-order','Explicit human permutation is accepted',e.send('submit_order_cards',decisionToken=token,assignments=[dict(forgeId=n) for n in selected])['accepted'])
            elif kind=='assign_damage':
                offered={v['forgeId']:v for v in d['options']};expected={resolve(e.state,s) for s in plan['expectedOptions']}
                check('damage-allocation','Exact authored damage total and recipients',d['totalDamage']==plan['total'] and set(offered)==expected)
                for field,key in [('expectedSuggestions','assignedDamage'),('expectedLethal','lethalDamage')]:
                    if field in plan:
                        values={resolve(e.state,v['target']):v['amount'] for v in plan[field]}
                        check('damage-allocation','Source-authored '+key+' values match offered UI data',values=={n:v[key] for n,v in offered.items()})
                def entries(values):return [dict(forgeId=resolve(e.state,v['target']),amount=v['amount']) for v in values]
                for values in plan.get('reject',[]):
                    r=e.send('submit_assign_damage',decisionToken=token,assignments=entries(values))
                    check('damage-allocation','Authored illegal allocation is rejected unchanged',not r['accepted'] and e.state['decision']['token']==token)
                selected=entries(plan['allocations'])
                if plan.get('probeInvalid'):
                    for values in [selected[:-1],[selected[0]]*len(selected),[dict(forgeId=-99999,amount=0) for _ in selected]]:
                        r=e.send('submit_assign_damage',decisionToken=token,assignments=values)
                        check('damage-allocation','Missing/duplicate/foreign allocation rejected',not r['accepted'] and e.state['decision']['token']==token)
                    r=e.send('submit_assign_damage',decisionToken='stale-token',assignments=selected)
                    check('damage-allocation','Stale allocation token rejected',not r['accepted'] and e.state['decision']['token']==token)
                check('damage-allocation','Authored human allocation is accepted',e.send('submit_assign_damage',decisionToken=token,assignments=selected)['accepted'])
            else:raise CaseFailure('controller','Decision kind has no authored driver: '+kind)

        for step in case['steps']:
            op=step['op']
            if op=='assert':
                for k,v in step.get('state',{}).items():check('outcome','State '+k+' equals authored value',e.state.get(k)==v)
                for entry in step.get('objects',[]):
                    identity=resolve(e.state,entry['selector'])
                    actual=next(c for c in cards(e.state) if c['forgeId']==identity)
                    for k,v in entry['values'].items():check('outcome','Object '+k+' equals authored value',actual.get(k)==v)
                for order in step.get('zoneOrder',[]):
                    expected=[resolve(e.state,s) for s in order['objects']]
                    actual=[c['forgeId'] for c in e.state[order['zone']] if c['owner']==order['owner']]
                    check('zone-order','Exact authored public-zone object order',actual==expected)
                if 'damageEvents' in step:
                    expected=[(resolve(e.state,v['source']),resolve(e.state,v['target']),v['amount'],v.get('combat',True)) for v in step['damageEvents']]
                    sources={v[0] for v in expected}
                    actual=[(v['sourceForgeId'],v.get('targetForgeId',-1000000-v.get('targetSeat',0)),v['amount'],v['combat']) for v in e.state['events'] if v['kind']=='damage' and v['sourceForgeId'] in sources and v['amount']>0]
                    check('damage','Exact positive combat damage events and recipients',actual==expected)
                continue
            if op=='advance':
                plans=iter(step.get('decisions',[]));used=0
                for _ in range(step.get('maxPasses',48)):
                    if e.state['phase']==step['phase'] and e.state['activeSeat']==step.get('activeSeat',e.state['activeSeat']):break
                    assert_no_gap()
                    _,progress=e.pass_or_decision()
                    if progress:
                        d=e.state['decision']
                        try:plan=next(plans)
                        except StopIteration:raise CaseFailure('controller','Unexpected human decision while advancing: '+d['kind'])
                        choose(plan,d);e.finish(progress['parentRequestId']);used+=1
                check('timing','Authored phase and active player reached',e.state['phase']==step['phase'] and e.state['activeSeat']==step.get('activeSeat',e.state['activeSeat']))
                check('controller','Every authored advance decision was exercised',used==len(step.get('decisions',[])))
                continue
            if op=='resolve':
                identity=resolve(e.state,step['selector'])
                check('resolution','Selected stack object has an authored pending cast',identity in pending)
                expected,changes=pending.pop(identity);finish_resolution(expected,identity,changes)
                continue
            selector=step.get('selector',dict(name=step['card'],owner=1,zone='Hand'))
            identity=resolve(e.state,selector);before=e.state
            hand={c['forgeId'] for c in before['hand']};library={c['forgeId'] for c in before['hidden'] if c['owner']==1 and c['zone']=='Library'}
            changes=[dict(forgeId=resolve(before,v['selector']),to=v['to']) for v in step.get('zoneChanges',[])]
            if op=='deny':
                check('legality','Illegal cast absent from offers',identity not in before['legalCasts'])
                r=e.send('cast_spell',identity)
                check('legality','Illegal direct cast rejected unchanged',not r['accepted'] and all(e.state[k]==before[k] for k in ('hand','battlefield','hidden','stack','life')))
                continue
            offer=next((v for v in before['castOffers'] if v['forgeId']==identity),None)
            check('cost','Printed fixed mana cost is offered',offer is not None and sum(v['count'] for v in offer['manaCost'])==step['mana'])
            if 'targetPlan' in step:
                parent=e.begin('cast_spell',identity)
                progress=e.wait_json(e.ipc/'decision.json');e.state=progress['state'];d=e.state['decision']
                check('target','Target request belongs to this cast',progress['parentRequestId']==parent)
                check('cost','Target decision precedes payment',e.state['battlefield']==before['battlefield'] and e.state['stack']==before['stack'])
                choose(step['targetPlan'],d);r=e.finish(parent)
                if step['targetPlan'].get('cancel'):
                    check('target','Canceled cast preserves card and sources',r['accepted'] and e.state['hand']==before['hand'] and e.state['battlefield']==before['battlefield'] and e.state['stack']==before['stack'])
                    continue
            else:r=e.send('cast_spell',identity)
            assert_no_gap()
            check('casting','Input actually puts the original card on stack',r['accepted'] and any(c['forgeId']==identity for c in e.state['stack']))
            check('resolution','Effects wait for real resolution',e.state['life']==before['life'] and {c['forgeId'] for c in e.state['hand']}==hand-{identity})
            paid=sum(c['tapped'] for c in e.state['battlefield'] if c['owner']==1)-sum(c['tapped'] for c in before['battlefield'] if c['owner']==1)
            check('cost','Actual basic source payment matches printed cost',paid==step['mana'])
            if step.get('resolve',True):finish_resolution(step,identity,changes)
            else:pending[identity]=(step,changes)
        check('resolution','No authored pending spell is left untested',not pending)
        return dict(status='passed',checks=len(e.checks),evidence=str(e.ipc))
    except Exception as error:
        if e:e._case_failed=True
        gap=e.state.get('fidelityGap') if e else None
        return dict(status='failed',category=getattr(error,'category','controller' if gap else 'infrastructure'),error=str(error),fidelityGap=gap,traceback=traceback.format_exc(),checks=len(e.checks) if e else 0,evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
