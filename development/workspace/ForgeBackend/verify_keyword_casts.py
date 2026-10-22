"""Cast every source-qualified keyword creature through the real Forge engine.

This gate does not verify keyword semantics, native rendering or production
admission. Those gates have separate reports.
"""
import argparse
import json
from engine_test_client import Engine
from runtime_paths import ROOT, SUPPORT_POLICY

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--candidates', type=__import__('pathlib').Path, required=True)
args = p.parse_args()
candidates = json.loads(args.candidates.read_text())
manifest = json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text())
if not manifest.get('researchOnly') or not json.loads(SUPPORT_POLICY.read_text()).get('researchOnly'):
    raise ValueError('Use a separate research-only policy and runtime')
reports = []
names = list(candidates)
for start in range(0, len(names), 6):
    group = names[start:start+6]
    e = Engine('card-family', fixtureHand=group,
               fixtureLands=[name for name in ('Plains','Island','Swamp','Mountain','Forest') for _ in range(20)])
    try:
        for name in group:
            source = candidates[name]
            definition = manifest['cards'][name]
            card = next(c for c in e.state['hand'] if c['name'] == name)
            identity = card['forgeId']
            e.check(name+' exact source stats', (card['power'],card['toughness']) == (source['power'],source['toughness']))
            mask = sum({'White':1,'Blue':2,'Black':4,'Red':8,'Green':16}[c] for c in definition['colors'])
            e.check(name+' exact source colors', card['colorMask'] == mask)
            e.check(name+' complete source ability identities', definition['abilityIds'] == source['abilityIds'])
            offer = next(o for o in e.state['castOffers'] if o['forgeId'] == identity)
            expected = {c['color']:c['count'] for c in definition['coloredCost']}
            if definition['genericCost']:
                expected['Generic'] = definition['genericCost']
            e.check(name+' actual printed cost', {c['color']:c['count'] for c in offer['manaCost']} == expected)
            before = sum(c['tapped'] for c in e.state['battlefield'])
            response = e.send('cast_spell', identity)
            e.check(name+' actual cast', response['accepted'] and identity in [c['forgeId'] for c in e.state['stack']])
            e.check(name+' actual cost payment', sum(c['tapped'] for c in e.state['battlefield'])-before == sum(expected.values()))
            e.pass_or_decision()
            resolved = next(c for c in e.state['battlefield'] if c['forgeId'] == identity)
            e.check(name+' actual resolution', not e.state['stack'] and (resolved['power'],resolved['toughness']) == (source['power'],source['toughness']))
            e.check(name+' no unknown stack behavior', not e.state['fidelityGap'])
        reports.append(dict(names=group, checks=len(e.checks), evidence=str(e.ipc)))
        print(json.dumps(reports[-1]), flush=True)
    finally:
        e.close()
out = args.candidates.parent/'cast-report.json'
out.write_text(json.dumps(dict(cards=len(names), checks=sum(r['checks'] for r in reports), reports=reports,
    scope='Seeded real Forge casts/costs/resolution only; keyword semantics and native presentation are separate.'), indent=2))
print(json.dumps(dict(cards=len(names), checks=sum(r['checks'] for r in reports), report=str(out)), indent=2))
