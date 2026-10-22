"""Cross-keyword deathtouch decisions through real Forge controllers."""
import json
from engine_test_client import Engine
from runtime_paths import ROOT

reports = []


def record(e, name):
    e.check('No unhandled controller decision', not e.state['fidelityGap'])
    reports.append(dict(case=name, checks=len(e.checks), evidence=str(e.ipc)))
    print(json.dumps(reports[-1]), flush=True)


e = Engine('card-family', fixtureHand=['Ambush Viper', 'Grizzly Bears'], fixtureLands=['Forest']*4)
try:
    for _ in range(12):
        if e.state['phase'] == 'COMBAT_BEGIN':
            break
        e.pass_or_decision()
    flash = next(c['forgeId'] for c in e.state['hand'] if c['name'] == 'Ambush Viper')
    ordinary = next(c['forgeId'] for c in e.state['hand'] if c['name'] == 'Grizzly Bears')
    e.check('Actual combat phase reached', e.state['phase'] == 'COMBAT_BEGIN')
    e.check('Ambush Viper can flash in while ordinary creature cannot', flash in e.state['legalCasts'] and ordinary not in e.state['legalCasts'])
    e.check('Direct request cannot bypass ordinary timing', not e.send('cast_spell', ordinary)['accepted'])
    e.check('Flash deathtouch creature casts during combat', e.send('cast_spell', flash)['accepted'])
    e.pass_or_decision()
    e.check('Flash creature resolves with summoning sickness', any(c['forgeId'] == flash and c['sick'] for c in e.state['battlefield']))
    record(e, 'Ambush Viper flash timing')
finally:
    e.close()

e = Engine('card-family', fixtureHand=['Nightveil Predator', 'Unsummon'],
           fixtureLands=['Island']*3+['Swamp']*2, fixtureOpponentBattlefield=['Nightveil Predator'])
try:
    friendly = next(c['forgeId'] for c in e.state['hand'] if c['name'] == 'Nightveil Predator')
    enemy = next(c['forgeId'] for c in e.state['battlefield'] if c['owner'] == 2)
    e.check('Multicolored hexproof/deathtouch creature casts', e.send('cast_spell', friendly)['accepted'])
    e.pass_or_decision()
    spell = next(c['forgeId'] for c in e.state['hand'] if c['name'] == 'Unsummon')
    parent = e.begin('cast_spell', spell)
    e.state = e.wait_json(e.ipc/'decision.json')['state']
    d = e.state['decision']
    e.check('Enemy Predator excluded while own Predator offered', {v['forgeId'] for v in d['options']} == {friendly})
    e.check('Direct enemy hexproof target rejected', not e.send('select_targets', decisionToken=d['token'], assignments=[dict(forgeId=enemy)])['accepted'])
    e.send('select_targets', decisionToken=d['token'], assignments=[dict(forgeId=friendly)])
    e.send('submit_targets', decisionToken=d['token'])
    e.finish(parent)
    e.pass_or_decision()
    e.check('Own Predator returned and enemy Predator untouched', any(c['forgeId'] == friendly for c in e.state['hand']) and any(c['forgeId'] == enemy for c in e.state['battlefield']))
    record(e, 'Nightveil Predator hexproof ownership')
finally:
    e.close()

# First strike kills the deathtouch blocker before it can retaliate. This checks
# phase ordering and state-based actions rather than assuming every block kills.
e = Engine('attack-double-blocked', fixtureAttacker='Youthful Knight', fixtureBlockers=['Typhoid Rats', 'Yoked Ox'])
try:
    knight = next(c['forgeId'] for c in e.state['battlefield'] if c['owner'] == 1)
    rat = next(c['forgeId'] for c in e.state['battlefield'] if c['name'] == 'Typhoid Rats')
    for _ in range(32):
        if e.state['phase'] == 'MAIN2':
            break
        d = e.state.get('decision')
        if not d:
            e.pass_or_decision()
        elif d['kind'] == 'attackers':
            e.send('select_attackers', decisionToken=d['token'], assignments=[dict(forgeId=knight, targetSeat=2)])
            e.send('submit_attackers', decisionToken=d['token'])
        elif d['kind'] == 'assign_damage':
            values = [dict(forgeId=v['forgeId'], amount=1) for v in d['options']]
            e.check('Split first strike damage accepted', e.send('submit_assign_damage', decisionToken=d['token'], assignments=values)['accepted'])
        else:
            raise AssertionError(d)
    e.check('First strike sequence completes', e.state['phase'] == 'MAIN2')
    e.check('Rats die before ordinary combat damage', any(c['forgeId'] == rat for c in e.state['graveyard']))
    e.check('Dead deathtouch blocker cannot damage or kill Knight', any(c['forgeId'] == knight and c['damage'] == 0 for c in e.state['battlefield']) and not any(v['kind'] == 'damage' and v['sourceForgeId'] == rat and v['amount'] > 0 for v in e.state['events']))
    e.check('Knight damage occurs in first strike step', {v['phase'] for v in e.state['events'] if v['kind'] == 'damage' and v['sourceForgeId'] == knight} == {'COMBAT_FIRST_STRIKE_DAMAGE'})
    record(e, 'First strike prevents deathtouch retaliation')
finally:
    e.close()

for label, attacker, blockers, chosen in [
    ('Deathtouch blocker kills high-toughness attacker', 'Ancient Brontodon', ['Typhoid Rats', 'Yoked Ox'], 'Typhoid Rats'),
    ('Reach and deathtouch intercept a flyer', 'Azure Drake', ['Thornweald Archer', 'Yoked Ox'], 'Thornweald Archer'),
]:
    e = Engine('defend', fixtureAttacker=attacker, fixtureBlockers=blockers)
    try:
        source = next(c['forgeId'] for c in e.state['battlefield'] if c['owner'] == 2)
        blocker = next(c['forgeId'] for c in e.state['battlefield'] if c['name'] == chosen)
        for _ in range(24):
            if e.state['phase'] == 'MAIN2':
                break
            d = e.state.get('decision')
            if not d:
                e.pass_or_decision()
            elif d['kind'] == 'blockers':
                e.check('Required blocker offered by actual legality rules', blocker in {v['forgeId'] for v in d['options']})
                e.send('select_blockers', decisionToken=d['token'], assignments=[dict(forgeId=blocker, attackerIds=[source])])
                e.check('Actual blocker declaration accepted', e.send('submit_blockers', decisionToken=d['token'])['accepted'])
            else:
                raise AssertionError(d)
        e.check('Opponent turn combat finishes', e.state['phase'] == 'MAIN2')
        e.check('Deathtouch blocker kills actual attacker', any(c['forgeId'] == source for c in e.state['graveyard']))
        e.check('Attacker damage remains on blocker and not player', e.state['life'] == 20 and any(v['kind'] == 'damage' and v['sourceForgeId'] == source and v.get('targetForgeId') == blocker for v in e.state['events']))
        record(e, label)
    finally:
        e.close()

out = ROOT.parent/'interaction-report.json'
out.write_text(json.dumps(dict(cases=reports, checks=sum(v['checks'] for v in reports),
    scope='Input-driven cross-keyword checks; fixture starts only, no injected outcomes.'), indent=2))
print(json.dumps(dict(checks=sum(v['checks'] for v in reports), report=str(out))), flush=True)
