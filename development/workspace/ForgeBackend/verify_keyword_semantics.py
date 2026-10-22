"""Real engine decisions and outcomes for eleven bounded keyword families."""
import hashlib
import json
from pathlib import Path
from engine_test_client import Engine
from runtime_paths import ROOT

manifest_path = ROOT/'native-lab/bridge-card-manifest.json'
if not json.loads(manifest_path.read_text()).get('researchOnly'):
    raise ValueError('Use an independent research runtime')
reports = []


def record(e, name):
    reports.append(dict(case=name, checks=len(e.checks), evidence=str(e.ipc)))
    print(json.dumps(reports[-1]), flush=True)


def finish_combat(e, source):
    for _ in range(32):
        if e.state['phase'] == 'MAIN2':
            return
        d = e.state.get('decision')
        if not d:
            e.pass_or_decision()
        elif d['kind'] == 'attackers':
            options = {v['forgeId'] for v in d['options']}
            assignments = [dict(forgeId=source['forgeId'],targetSeat=2)] if source['forgeId'] in options else []
            r = e.send('select_attackers',decisionToken=d['token'],assignments=assignments)
            e.check('Source attacker selection accepted',r['accepted'])
            r = e.send('submit_attackers',decisionToken=d['token'])
            e.check('Actual attacker declaration accepted',r['accepted'])
            if source['name'] == 'Alpine Watchdog':
                e.check('Vigilance leaves the declared attacker untapped',
                        not next(c for c in e.state['battlefield'] if c['forgeId']==source['forgeId'])['tapped'])
            if source['name'] == 'Moat Piranhas':
                e.check('Ready defender is absent from actual attacker options',source['forgeId'] not in options)
        elif d['kind'] == 'assign_damage':
            assignments = [dict(forgeId=v['forgeId'],amount=d['totalDamage'] if index==0 else 0)
                           for index,v in enumerate(d['options'])]
            r = e.send('submit_assign_damage',decisionToken=d['token'],assignments=assignments)
            e.check('Actual free damage allocation accepted',r['accepted'])
        else:
            raise AssertionError(d)
    raise AssertionError('Bounded combat did not complete')


cases = [
    ('flying over ground','Azure Drake',['Grizzly Bears','Yoked Ox']),
    ('reach blocks flying','Azure Drake',['Canopy Spider','Yoked Ox']),
    ('first strike before retaliation','Youthful Knight',['Savannah Lions','Yoked Ox']),
    ('two double strike damage steps','Fencing Ace',['Yoked Ox','Aegis Turtle']),
    ('vigilance attack','Alpine Watchdog',['Yoked Ox','Aegis Turtle']),
    ('lifelink from blocked damage','Child of Night',['Yoked Ox','Aegis Turtle']),
    ('defender cannot attack','Moat Piranhas',['Yoked Ox','Aegis Turtle']),
]
for label, name, blockers in cases:
    e = Engine('attack-double-blocked',fixtureAttacker=name,fixtureBlockers=blockers)
    try:
        source = next(c for c in e.state['battlefield'] if c['owner']==1)
        defender = next(c for c in e.state['battlefield'] if c['owner']==2 and c['name']==blockers[0])
        finish_combat(e,source)
        hits = [v for v in e.state['events'] if v['kind']=='damage' and v['sourceForgeId']==source['forgeId']]
        if label == 'flying over ground':
            e.check('Ground creatures cannot intercept the flyer',e.state['opponentLife']==18 and len(hits)==1 and hits[0]['targetSeat']==2)
        elif label == 'reach blocks flying':
            e.check('Reach blocks without a ground blocker joining',e.state['opponentLife']==20 and len(hits)==1 and hits[0]['targetForgeId']==defender['forgeId'])
            e.check('Reach and flyer exchange actual damage',next(c for c in e.state['battlefield'] if c['forgeId']==source['forgeId'])['damage']==1 and next(c for c in e.state['battlefield'] if c['forgeId']==defender['forgeId'])['damage']==2)
        elif label == 'first strike before retaliation':
            e.check('First strike kills the blocker in its earlier step',any(c['forgeId']==defender['forgeId'] for c in e.state['graveyard']) and any(v['phase']=='COMBAT_FIRST_STRIKE_DAMAGE' for v in hits))
            e.check('Dead blocker cannot retaliate',any(c['forgeId']==source['forgeId'] and c['damage']==0 for c in e.state['battlefield']))
        elif label == 'two double strike damage steps':
            e.check('Double strike deals damage in both distinct steps',{v['phase'] for v in hits}=={'COMBAT_FIRST_STRIKE_DAMAGE','COMBAT_DAMAGE'} and sum(v['amount'] for v in hits)==2)
        elif label == 'lifelink from blocked damage':
            e.check('Lifelink gains life from actual creature damage',e.state['life']==22 and any(v['kind']=='life-gain' and v['amount']==2 for v in e.state['events']))
        elif label == 'defender cannot attack':
            e.check('Defender produces no combat damage',not hits and e.state['opponentLife']==20)
        e.check('No unhandled combat decision',not e.state['fidelityGap'])
        record(e,label)
    finally:
        e.close()

e = Engine('card-family',fixtureHand=['Brazen Scourge','Grizzly Bears','Moat Piranhas'],
           fixtureLands=['Mountain']*10+['Forest']*10+['Island']*10)
try:
    ids = {}
    for name in ('Brazen Scourge','Grizzly Bears','Moat Piranhas'):
        identity = next(c['forgeId'] for c in e.state['hand'] if c['name']==name)
        ids[name] = identity
        e.check('Cast fresh '+name,e.send('cast_spell',identity)['accepted'])
        e.pass_or_decision()
    for _ in range(12):
        if e.state.get('decision'):
            break
        e.pass_or_decision()
    d = e.state['decision']
    e.check('Only the fresh haste creature can attack',d['kind']=='attackers' and
            {v['forgeId'] for v in d['options']}=={ids['Brazen Scourge']})
    record(e,'haste and fresh summoning sickness')
finally:
    e.close()

e = Engine('card-family',fixtureHand=['Hired Blade','Grizzly Bears'],fixtureLands=['Swamp']*10+['Forest']*10)
try:
    for _ in range(12):
        if e.state['phase']=='COMBAT_BEGIN':
            break
        e.pass_or_decision()
    e.check('Real phase loop enters combat',e.state['phase']=='COMBAT_BEGIN')
    flash = next(c['forgeId'] for c in e.state['hand'] if c['name']=='Hired Blade')
    normal = next(c['forgeId'] for c in e.state['hand'] if c['name']=='Grizzly Bears')
    e.check('Flash and ordinary creature timing differ',flash in e.state['legalCasts'] and normal not in e.state['legalCasts'])
    e.check('Direct request cannot bypass ordinary timing',not e.send('cast_spell',normal)['accepted'])
    e.check('Flash actually casts in combat',e.send('cast_spell',flash)['accepted'])
    e.pass_or_decision()
    e.check('Flash resolves with ordinary summoning sickness',any(c['forgeId']==flash and c['sick'] for c in e.state['battlefield']))
    record(e,'flash timing')
finally:
    e.close()

e = Engine('card-family',fixtureHand=['Gladecover Scout','Unsummon'],fixtureLands=['Island','Island','Forest'],
           fixtureOpponentBattlefield=['Gladecover Scout'])
try:
    friendly = next(c['forgeId'] for c in e.state['hand'] if c['name']=='Gladecover Scout')
    enemy = next(c['forgeId'] for c in e.state['battlefield'] if c['owner']==2)
    e.check('Friendly hexproof creature actually casts',e.send('cast_spell',friendly)['accepted'])
    e.pass_or_decision()
    spell = next(c['forgeId'] for c in e.state['hand'] if c['name']=='Unsummon')
    parent = e.begin('cast_spell',spell)
    e.state = e.wait_json(e.ipc/'decision.json')['state']
    d = e.state['decision']
    e.check('Hexproof excludes only the opponent-owned target',{v['forgeId'] for v in d['options']}=={friendly})
    e.check('Direct hexproof violation is rejected',not e.send('select_targets',decisionToken=d['token'],assignments=[dict(forgeId=enemy)])['accepted'])
    e.send('select_targets',decisionToken=d['token'],assignments=[dict(forgeId=friendly)])
    e.send('submit_targets',decisionToken=d['token'])
    e.finish(parent)
    e.pass_or_decision()
    e.check('Own hexproof creature can be legally targeted and returned',any(c['forgeId']==friendly for c in e.state['hand']) and any(c['forgeId']==enemy for c in e.state['battlefield']))
    record(e,'hexproof ownership and targets')
finally:
    e.close()

e = Engine('defend',fixtureAttacker='Alley Strangler',fixtureBlockers=['Grizzly Bears','Yoked Ox'])
try:
    for _ in range(16):
        if (e.state.get('decision') or {}).get('kind')=='blockers':
            break
        e.pass_or_decision()
    d = e.state['decision']
    e.check('Menace exposes the two individually eligible blockers',d['kind']=='blockers' and len(d['options'])==2)
    first = d['options'][0]
    e.send('select_blockers',decisionToken=d['token'],assignments=[dict(forgeId=first['forgeId'],attackerIds=first['attackerIds'])])
    e.check('One blocker cannot satisfy menace',not e.send('submit_blockers',decisionToken=d['token'])['accepted'])
    assignments = [dict(forgeId=v['forgeId'],attackerIds=v['attackerIds']) for v in d['options']]
    e.send('select_blockers',decisionToken=d['token'],assignments=assignments)
    e.check('Two blockers satisfy actual Forge validation',e.send('submit_blockers',decisionToken=d['token'])['accepted'])
    e.check('No unknown decision after correcting illegal declaration',not e.state['fidelityGap'])
    record(e,'menace collective blocking')
finally:
    e.close()

out = ROOT.parent/'semantics-report.json'
out.write_text(json.dumps(dict(checks=sum(r['checks'] for r in reports),cases=reports,
    engineClassSha256=hashlib.sha256((ROOT/'build/ForgeBackend/classes/ForgeLandEngine.class').read_bytes()).hexdigest(),
    manifestSha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    scope='Bounded representative input-driven keyword decisions/outcomes; not exhaustive interactions or native animation parity.'),indent=2))
print(json.dumps(dict(report=str(out),checks=sum(r['checks'] for r in reports)),indent=2))
