"""Input-driven verification for source-matched, fixed, untargeted draw spells.

Requires an independent research policy. It never changes card admission.
"""
import json
from engine_test_client import Engine
from runtime_paths import ROOT, SUPPORT_POLICY

NAMES = ('Concentrate', 'Divination', 'Harmonize', 'Weave Fate', 'Quick Study')
DRAW_COUNTS = (3, 2, 3, 2, 2)
policy = json.loads(SUPPORT_POLICY.read_text())
manifest = json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text())
if not policy.get('researchOnly') or not manifest.get('researchOnly'):
    raise ValueError('Use a separate research policy and runtime')
reports = []


def record(e, label):
    reports.append(dict(case=label, evidence=str(e.ipc), checks=len(e.checks)))


e = Engine('card-family', fixtureHand=list(NAMES),
           fixtureLands=['Island']*20 + ['Forest']*20)
try:
    for index, (name, count) in enumerate(zip(NAMES, DRAW_COUNTS)):
        spell = next(c for c in e.state['hand'] if c['name'] == name)
        identity = spell['forgeId']
        library = {c['forgeId'] for c in e.state['hidden']
                   if c['owner'] == 1 and c['zone'] == 'Library'}
        hand = {c['forgeId'] for c in e.state['hand']}
        sources = sum(c['tapped'] for c in e.state['battlefield'])
        definition = manifest['cards'][name]
        cost = definition['genericCost'] + sum(c['count'] for c in definition['coloredCost'])
        offer = next(o for o in e.state['castOffers'] if o['forgeId'] == identity)
        e.check(name+' keeps every printed cost symbol',
                sum(c['count'] for c in offer['manaCost']) == cost)
        response = e.send('cast_spell', identity)
        e.check(name+' casts without a target decision', response['accepted'] and
                not e.state.get('decision') and identity in [c['forgeId'] for c in e.state['stack']])
        e.check(name+' pays the full cost with actual sources',
                sum(c['tapped'] for c in e.state['battlefield'])-sources == cost)
        e.check(name+' does not draw before resolution',
                {c['forgeId'] for c in e.state['hand']} == hand-{identity})
        if index == 0:
            sorcery = next(c['forgeId'] for c in e.state['hand'] if c['name'] == 'Divination')
            instant = next(c['forgeId'] for c in e.state['hand'] if c['name'] == 'Weave Fate')
            e.check('Sorcery timing excludes another spell on the stack', sorcery not in e.state['legalCasts'])
            e.check('Instant remains available in that response window', instant in e.state['legalCasts'])
            denied = e.send('cast_spell', sorcery)
            e.check('Direct request cannot bypass sorcery timing', not denied['accepted'] and len(e.state['stack']) == 1)
        e.pass_or_decision()
        after = {c['forgeId'] for c in e.state['hand']}
        remaining = {c['forgeId'] for c in e.state['hidden']
                     if c['owner'] == 1 and c['zone'] == 'Library'}
        e.check(name+' draws exactly the source number from the real library',
                len(after-(hand-{identity})) == count and len(library-remaining) == count and
                after-(hand-{identity}) == library-remaining)
        e.check(name+' moves the original spell to graveyard',
                not e.state['stack'] and identity in [c['forgeId'] for c in e.state['graveyard']])
        e.check(name+' retains hidden opponent identity and no fidelity gap',
                all('name' not in c for c in e.state['hidden']) and not e.state['fidelityGap'])
    record(e, 'main-phase casts and response timing')
finally:
    e.close()

e = Engine('card-family', fixtureHand=['Divination', 'Weave Fate'], fixtureLands=['Island']*10)
try:
    for _ in range(12):
        if e.state['phase'] == 'COMBAT_BEGIN':
            break
        e.pass_or_decision()
    e.check('Actual phase loop reaches combat', e.state['phase'] == 'COMBAT_BEGIN')
    sorcery = next(c['forgeId'] for c in e.state['hand'] if c['name'] == 'Divination')
    instant = next(c['forgeId'] for c in e.state['hand'] if c['name'] == 'Weave Fate')
    e.check('Sorcery is unavailable outside a main phase', sorcery not in e.state['legalCasts'])
    e.check('Instant is available in combat', instant in e.state['legalCasts'])
    denied = e.send('cast_spell', sorcery)
    e.check('Direct combat request cannot bypass timing', not denied['accepted'] and not e.state['stack'])
    response = e.send('cast_spell', instant)
    e.check('Actual instant can be cast in combat', response['accepted'] and bool(e.state['stack']))
    record(e, 'combat timing')
finally:
    e.close()

out = ROOT/'research/fixed-draw-checks.json'
out.write_text(json.dumps(dict(researchOnly=True, cards=list(NAMES),
    checks=sum(r['checks'] for r in reports), reports=reports,
    scope='Seeded actual Forge casts, costs, library identities and timing; native presentation and full games are separate.'), indent=2))
print(json.dumps(dict(report=str(out), checks=sum(r['checks'] for r in reports)), indent=2))
