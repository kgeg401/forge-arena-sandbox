"""Exercise different costs and combat stats through the installed Forge engine."""
from engine_test_client import Engine
import json

reports = []

def resolve(e):
    for _ in range(6):
        if not e.state['stack']:
            return
        r, decision = e.pass_or_decision()
        assert not decision, 'Unexpected decision during vanilla spell resolution'
    raise AssertionError('Vanilla stack did not resolve')

e = Engine('vanilla-costs')
try:
    swift = next(c for c in e.state['hand'] if c['name'] == 'Oreskos Swiftclaw')
    ox = next(c for c in e.state['hand'] if c['name'] == 'Yoked Ox')
    e.check('one Plains cannot pay 1W', swift['forgeId'] not in e.state['legalCasts'])
    r = e.send('cast_spell', swift['forgeId'])
    e.check('unpayable Swiftclaw rejected unchanged', not r['accepted'] and not e.state['stack'] and len(e.state['battlefield']) == 1)
    e.check('second Plains play accepted', e.send('play_land', e.state['legalLands'][0])['accepted'])
    e.check('two Plains can pay 1W', swift['forgeId'] in e.state['legalCasts'])
    r = e.send('cast_spell', swift['forgeId'])
    e.check('Forge pays both mana costs', r['accepted'] and sum(c['name'] == 'Plains' and c['tapped'] for c in e.state['battlefield']) == 2)
    resolve(e)
    card = next(c for c in e.state['battlefield'] if c['forgeId'] == swift['forgeId'])
    e.check('Swiftclaw resolves as a summoning-sick 3/1', (card['power'], card['toughness'], card['sick']) == (3, 1, True))
    for _ in range(40):
        if e.state['turn'] == 3 and e.state['phase'] == 'MAIN1':
            break
        r, decision = e.pass_or_decision()
        assert not decision, 'No ready attacker should exist before next first main'
    e.check('ordinary Forge untap reaches next main', e.state['turn'] == 3 and e.state['phase'] == 'MAIN1')
    e.check('Ox one-mana cast accepted', e.send('cast_spell', ox['forgeId'])['accepted'])
    resolve(e)
    card = next(c for c in e.state['battlefield'] if c['forgeId'] == ox['forgeId'])
    e.check('Ox resolves as a 0/4', (card['power'], card['toughness']) == (0, 4))
    reports.append({'scenario': 'vanilla-costs', 'evidence': str(e.ipc), 'checks': len(e.checks)})
finally:
    e.close()

for scenario in ('attack-swift', 'defend-ox'):
    e = Engine(scenario)
    try:
        declared = False
        for _ in range(30):
            r, decision = e.pass_or_decision()
            if decision:
                dec = e.state['decision']; token = dec['token']; option = dec['options'][0]
                assignment = {'forgeId': option['forgeId']}
                if dec['kind'] == 'attackers':
                    assignment['targetSeat'] = 2
                else:
                    assignment['attackerIds'] = [option['attackerIds'][0]]
                e.check('legal declaration selection', e.send('select_' + dec['kind'], decisionToken=token, assignments=[assignment])['accepted'])
                e.check('Forge accepts declaration', e.send('submit_' + dec['kind'], decisionToken=token)['accepted'])
                declared = True
            if declared and e.state['phase'] == 'COMBAT_DAMAGE':
                break
        e.check('combat damage reached', declared and e.state['phase'] == 'COMBAT_DAMAGE')
        if scenario == 'attack-swift':
            e.check('3-power attacker deals three', e.state['opponentLife'] == 17 and sum(x['amount'] for x in e.state['events'] if x.get('targetSeat') == 2) == 3)
        else:
            ox = next(c for c in e.state['battlefield'] if c['name'] == 'Yoked Ox')
            e.check('0/4 survives two damage', ox['damage'] == 2 and ox['toughness'] == 4 and len(e.state['battlefield']) == 2 and not e.state['graveyard'])
            e.check('zero-power block deals no player damage', e.state['life'] == 20 and e.state['opponentLife'] == 20)
        reports.append({'scenario': scenario, 'evidence': str(e.ipc), 'checks': len(e.checks)})
    finally:
        e.close()
print(json.dumps(reports, indent=2))
