"""Strict declarative schema-2 decisions and initial fixture validation."""
def selector(s):
    if not isinstance(s,dict) or not s:raise ValueError('Explicit object selector required')
    if set(s)=={'targetSeat'}:
        if type(s['targetSeat']) is not int or s['targetSeat'] not in (1,2):raise ValueError('Invalid target seat')
        return
    if set(s)-{'name','owner','controller','zone','index'} or not {'name','owner','zone'}<=set(s):raise ValueError('Use a named object, seat and zone')
    if not isinstance(s['name'],str) or not s['name'] or type(s['owner']) is not int or s['owner'] not in (1,2) or s['zone'] not in ('Hand','Battlefield','Graveyard','Stack','Exile','Command'):raise ValueError('Invalid object selector')
    if 'controller' in s and (type(s['controller']) is not int or s['controller'] not in (1,2)):raise ValueError('Invalid object controller')
    if 'index' in s and (type(s['index']) is not int or s['index']<0):raise ValueError('Invalid object ordinal')

def decision(d):
    kind=d.get('kind')
    if kind=='targets':
        if not {'kind','expectedOptions'}<=set(d) or set(d)-{'kind','expectedOptions','invalid','choose','cancel','probeEmpty','probeStale'}:raise ValueError('Target plan needs exact expected legal options')
        for field in ('expectedOptions','invalid','choose'):
            if field in d:
                if not isinstance(d[field],list):raise ValueError('Target lists required')
                for s in d[field]:selector(s)
        for field in ('cancel','probeEmpty','probeStale'):
            if field in d and type(d[field]) is not bool:raise ValueError('Boolean target control required')
        if bool(d.get('cancel'))==('choose' in d):raise ValueError('Choose targets or cancel, exclusively')
    elif kind=='attackers':
        if not {'kind','choose'}<=set(d) or set(d)-{'kind','choose','expectedOptions'}:raise ValueError('Explicit attacker selection required')
        for s in d['choose']:selector(s)
        for s in d.get('expectedOptions',[]):selector(s)
    elif kind=='blockers':
        if not {'kind','assignments'}<=set(d) or set(d)-{'kind','assignments','expectedOptions'}:raise ValueError('Explicit blockers required')
        for b in d['assignments']+d.get('expectedOptions',[]):
            if set(b)!={'blocker','attackers'}:raise ValueError('Blocker and attacker selectors required')
            selector(b['blocker'])
            for s in b['attackers']:selector(s)
    elif kind=='order_cards':
        if not {'kind','expectedOptions','choose'}<=set(d) or set(d)-{'kind','expectedOptions','choose','probeInvalid'}:raise ValueError('An explicit full permutation is required')
        for field in ('expectedOptions','choose'):
            if not isinstance(d[field],list) or len(d[field])<2:raise ValueError('Ordering needs at least two named objects')
            for s in d[field]:selector(s)
        if 'probeInvalid' in d and type(d['probeInvalid']) is not bool:raise ValueError('Boolean invalid-order probe required')
    elif kind=='assign_damage':
        if not {'kind','total','expectedOptions','allocations'}<=set(d) or set(d)-{'kind','total','expectedOptions','allocations','expectedSuggestions','expectedLethal','reject','probeInvalid'}:raise ValueError('Independent complete damage allocation required')
        if type(d['total']) is not int or d['total']<0 or not isinstance(d['expectedOptions'],list) or not d['expectedOptions']:raise ValueError('Explicit total and recipients required')
        for s in d['expectedOptions']:selector(s)
        for field in ('allocations','expectedSuggestions','expectedLethal'):
            if field not in d:continue
            if not isinstance(d[field],list):raise ValueError('Explicit allocation list required')
            for value in d[field]:
                if set(value)!={'target','amount'} or type(value['amount']) is not int or value['amount']<0:raise ValueError('Nonnegative integer damage values required')
                selector(value['target'])
        if sum(v['amount'] for v in d['allocations'])!=d['total']:raise ValueError('Authored valid allocation must spend the exact total')
        if 'probeInvalid' in d and type(d['probeInvalid']) is not bool:raise ValueError('Boolean invalid-allocation probe required')
        if len(d.get('reject',[]))>20:raise ValueError('Too many invalid allocation probes')
        for values in d.get('reject',[]):
            for value in values:
                if set(value)!={'target','amount'}:raise ValueError('Explicit rejected allocation payload required')
                selector(value['target'])
    else:raise ValueError('No driver for decision '+str(kind))


def exercises(c):
    if any(s.get('op') in ('cast','deny') and s.get('card')==c['card'] for s in c['steps']):return True
    if c['card'] not in c['fixture'].get('fixtureBattlefield',[]):return False
    for step in c['steps']:
        if step.get('op')!='advance':continue
        for d in step.get('decisions',[]):
            if d.get('kind')=='attackers':choices=d.get('choose',[])+d.get('expectedOptions',[])
            elif d.get('kind')=='blockers':choices=[v['blocker'] for v in d.get('assignments',[])]+[v['blocker'] for v in d.get('expectedOptions',[])]
            else:continue
            if any(s.get('name')==c['card'] and s.get('owner')==1 and s.get('zone')=='Battlefield' for s in choices):return True
    return False

def validate(suite):
    if suite.get('schema')!=2 or not suite.get('cards') or not suite.get('cases'):raise ValueError('Nonempty schema-2 suite required')
    ids=set();bounds={'fixtureHand':8,'fixtureLands':100,'fixtureBattlefield':8,'fixtureOpponentBattlefield':8,'fixtureGraveyard':40,'fixtureOpponentGraveyard':40}
    for name,branches in suite['cards'].items():
        if not isinstance(name,str) or not name or not isinstance(branches,list) or not branches or len(branches)!=len(set(branches)) or any(not isinstance(b,str) or not b for b in branches):raise ValueError('Explicit card coverage branches required')
    for c in suite['cases']:
        key=c['id']
        if not isinstance(key,str) or not key or len(key)>100 or any(v not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for v in key) or key in ids:raise ValueError('Distinct path-safe case IDs required')
        ids.add(key)
        if c['card'] not in suite['cards'] or not c['covers'] or not set(c['covers'])<=set(suite['cards'][c['card']]):raise ValueError('Unknown coverage attribution')
        f=c['fixture']
        if not {'fixtureHand','fixtureLands'}<=set(f) or set(f)-set(bounds)-{'fixtureActiveSeat','fixtureOpponentPolicy','fixtureBattlefieldReady'}:raise ValueError('Unsupported starting fixture')
        if 'fixtureBattlefieldReady' in f and (type(f['fixtureBattlefieldReady']) is not bool or not f.get('fixtureBattlefield')):raise ValueError('Ready fixture needs initial battlefield objects and a boolean')
        for k,limit in bounds.items():
            if k in f and (not isinstance(f[k],list) or len(f[k])>limit or any(not isinstance(n,str) or not n for n in f[k])):raise ValueError('Fixture exceeds research bounds')
        if 'fixtureActiveSeat' in f and (type(f['fixtureActiveSeat']) is not int or f['fixtureActiveSeat'] not in (1,2)):raise ValueError('Starting seat must be 1 or 2')
        if f.get('fixtureOpponentPolicy','passive') not in ('passive','attack-all','block-all'):raise ValueError('Unknown research opponent policy')
        if not c['steps'] or len(c['steps'])>128 or not exercises(c):raise ValueError('Each bounded case must exercise its declared card through casting or explicit combat decisions')
        for s in c['steps']:
            op=s.get('op')
            if op=='assert':
                if set(s)-{'op','state','objects','zoneOrder','damageEvents'} or not (s.get('state') or s.get('objects') or s.get('zoneOrder') or s.get('damageEvents')):raise ValueError('Explicit state assertions required')
                for o in s.get('objects',[]):
                    if set(o)!={'selector','values'} or not o['values']:raise ValueError('Explicit object assertions required')
                    selector(o['selector'])
                for order in s.get('zoneOrder',[]):
                    if set(order)!={'zone','owner','objects'} or order['zone'] not in ('graveyard','exile','command') or type(order['owner']) is not int or order['owner'] not in (1,2) or not isinstance(order['objects'],list):raise ValueError('Explicit public-zone order assertion required')
                    for item in order['objects']:selector(item)
                for event in s.get('damageEvents',[]):
                    if not {'source','target','amount'}<=set(event) or set(event)-{'source','target','amount','combat'} or type(event['amount']) is not int or event['amount']<=0 or type(event.get('combat',True)) is not bool:raise ValueError('Explicit positive damage-event oracle required')
                    selector(event['source']);selector(event['target'])
            elif op=='advance':
                if set(s)-{'op','phase','activeSeat','decisions','maxPasses'} or s.get('phase') not in ('MAIN1','COMBAT_BEGIN','COMBAT_DECLARE_ATTACKERS','COMBAT_DECLARE_BLOCKERS','COMBAT_END','MAIN2','END_OF_TURN'):raise ValueError('Unsupported phase advance')
                if 'activeSeat' in s and (type(s['activeSeat']) is not int or s['activeSeat'] not in (1,2)):raise ValueError('Invalid active seat')
                if type(s.get('maxPasses',48)) is not int or not 1<=s.get('maxPasses',48)<=96:raise ValueError('Advance bound required')
                for d in s.get('decisions',[]):decision(d)
            elif op=='deny':
                if not {'op','card'}<=set(s) or set(s)-{'op','card','selector'}:raise ValueError('Invalid denial case')
                if 'selector' in s:selector(s['selector'])
            elif op=='cast':
                if not {'op','card','mana','draw','life'}<=set(s) or set(s)-{'op','card','mana','draw','life','zone','selector','zoneChanges','targetPlan','resolve','orderedEffects','fizzled'}:raise ValueError('Every cast needs an independent expected outcome')
                if any(type(s[k]) is not int or s[k]<0 for k in ('mana','draw')) or type(s['life']) is not int:raise ValueError('Integer spell outcomes required')
                for key in ('resolve','fizzled'):
                    if key in s and type(s[key]) is not bool:raise ValueError('Boolean stack/resolution control required')
                if 'orderedEffects' in s:
                    if not isinstance(s['orderedEffects'],list):raise ValueError('Explicit ordered effect list required')
                    for effect in s['orderedEffects']:
                        if set(effect)!={'kind','amount'} or effect['kind'] not in ('Draw','GainLife') or type(effect['amount']) is not int or not 1<=effect['amount']<=20:raise ValueError('Unknown ordered effect oracle')
                if s.get('zone','graveyard') not in ('graveyard','battlefield'):raise ValueError('Unknown spell destination')
                if 'selector' in s:selector(s['selector'])
                if 'targetPlan' in s:decision(s['targetPlan'])
                for z in s.get('zoneChanges',[]):
                    if set(z)!={'selector','to'} or z['to'] not in ('Hand','Battlefield','Graveyard','Exile','Library'):raise ValueError('Explicit zone transition required')
                    selector(z['selector'])
            elif op=='resolve':
                if set(s)!={'op','selector'}:raise ValueError('Resolve an explicitly selected pending spell')
                selector(s['selector'])
                if s['selector']['zone']!='Stack' or s['selector']['owner']!=1:raise ValueError('Pending local stack spell required')
            else:raise ValueError('No driver for '+str(op))
    return suite
