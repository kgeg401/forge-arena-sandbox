"""Input-driven combat checks for source-qualified deathtouch creatures.

Fixtures seed only starting cards. Forge alone advances combat, assigns AI
damage, deals damage and performs state-based actions. No expected intermediate
state is injected into the engine.
"""
import argparse
import hashlib
import json
from pathlib import Path
from engine_test_client import Engine
from runtime_paths import ROOT


def combat(e, source, split=False):
    allocations = []
    for _ in range(32):
        if e.state['phase'] == 'MAIN2':
            return allocations
        d = e.state.get('decision')
        if not d:
            e.pass_or_decision()
        elif d['kind'] == 'attackers':
            e.check('Ready source is offered as an attacker', source in {v['forgeId'] for v in d['options']})
            e.send('select_attackers', decisionToken=d['token'], assignments=[dict(forgeId=source, targetSeat=2)])
            e.check('Forge accepts attacker declaration', e.send('submit_attackers', decisionToken=d['token'])['accepted'])
        elif d['kind'] == 'assign_damage':
            e.check('Deathtouch exposes lethal damage of one', all(v['lethalDamage'] == 1 for v in d['options']))
            amounts = ([1, d['totalDamage']-1] if split else [d['totalDamage'], 0])
            values = [dict(forgeId=v['forgeId'], amount=n) for v, n in zip(d['options'], amounts)]
            e.check('Two exact recipients are exposed', len(values) == len(d['options']) == 2)
            e.check('Human allocation accepted', e.send('submit_assign_damage', decisionToken=d['token'], assignments=values)['accepted'])
            allocations = values
        else:
            raise AssertionError(d)
    raise AssertionError('Bounded combat failed to finish')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidates', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Select a new evidence file')
    manifest = ROOT/'native-lab/bridge-card-manifest.json'
    if not json.loads(manifest.read_text()).get('researchOnly'):
        raise ValueError('Use an explicit independent research runtime')
    definitions = json.loads(a.candidates.read_text())
    reports = []
    # Every candidate really deals combat damage. Flyers face reach creatures;
    # ground creatures face zero-power high-toughness blockers, isolating lethal
    # deathtouch from ordinary toughness damage and retaliation.
    for name, definition in definitions.items():
        flyers = 'Flying' in definition['keywords']
        blockers = ['Canopy Spider', 'Giant Spider'] if flyers else ['Aegis Turtle', 'Yoked Ox']
        e = Engine('attack-double-blocked', fixtureAttacker=name, fixtureBlockers=blockers)
        try:
            source = next(c for c in e.state['battlefield'] if c['owner'] == 1)
            victims = {c['forgeId']: c for c in e.state['battlefield'] if c['owner'] == 2}
            split = definition['power'] >= 2
            values = combat(e, source['forgeId'], split)
            e.check('No unsupported controller decision', not e.state['fidelityGap'])
            e.check('All blockers participate in the allocation', {v['forgeId'] for v in values} == set(victims))
            hits = {v['targetForgeId']: v['amount'] for v in e.state['events']
                    if v['kind'] == 'damage' and v['sourceForgeId'] == source['forgeId'] and v['amount'] > 0}
            expected = {v['forgeId']: v['amount'] for v in values if v['amount'] > 0}
            e.check('Forge deals exactly the submitted positive damage', hits == expected, hits)
            dead = {c['forgeId'] for c in e.state['graveyard']}
            e.check('Positive deathtouch damage kills every damaged blocker', set(expected) <= dead)
            spared = set(victims)-set(expected)
            e.check('Zero damage does not cause a deathtouch death', not spared & dead)
            e.check('No player damage leaks through a blocked attacker', e.state['opponentLife'] == 20)
            if 'Lifelink' in definition['keywords']:
                e.check('Lifelink gains actual damage, not lethal threshold', e.state['life'] == 20+definition['power'])
            if 'Vigilance' in definition['keywords']:
                live = next(c for c in e.state['battlefield']+e.state['graveyard'] if c['forgeId'] == source['forgeId'])
                e.check('Vigilance source remains untapped', not live['tapped'])
            reports.append(dict(name=name, checks=len(e.checks), evidence=str(e.ipc)))
            print(json.dumps(reports[-1]), flush=True)
        finally:
            e.close()
    result = dict(cards=len(reports), checks=sum(r['checks'] for r in reports), cases=reports,
                  manifestSha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                  engineClassSha256=hashlib.sha256((ROOT/'build/ForgeBackend/classes/ForgeLandEngine.class').read_bytes()).hexdigest(),
                  scope='Actual Forge combat for each exact source-qualified candidate; not exhaustive interactions, formats or animation parity.')
    a.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(dict(cards=result['cards'], checks=result['checks'], report=str(a.output))), flush=True)


if __name__ == '__main__':
    main()
