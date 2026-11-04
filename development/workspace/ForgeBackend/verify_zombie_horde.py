"""Bounded Horde games through the original Arena parser and input handlers.

Only starting decks and seed are supplied. The small-pool cases are labelled
mechanic fixtures; the ordinary 500-card loss case has no Horde pool override.
"""
import argparse
import json
import os
from pathlib import Path
import time
import traceback


def run(case, args):
    from native_engine_test_client import NativeEngine
    from native_test_policy import execute
    engine = None
    trace = []
    try:
        settings = dict(randomSeed=7274)
        if case in ('ordinary-win','ordinary-playthrough'):
            deck = [('Plains', 16), ('Impassioned Orator', 12), ('Hare Apparent', 12)]
        elif case == 'ordinary-loss':
            deck = [('Forest', 40)]
        elif case == 'mill-before-wave':
            deck = [('Mountain', 16), ('Lightning Bolt', 24)]
            settings['hordeFixturePool'] = ['Walking Corpse'] * 3
        elif case == 'empty-library-survivor':
            deck = [('Mountain', 16), ('Lightning Bolt', 24)]
            settings['hordeFixturePool'] = ['Walking Corpse']
        elif case == 'combat-mill':
            deck = [('Plains', 16), ('Savannah Lions', 24)]
            settings['hordeFixturePool'] = ['Walking Corpse'] * 12
        elif case in ('counter-wave', 'counter-physical-token'):
            deck = [('Island', 16), ('Counterspell', 24)]
            settings['hordeFixturePool'] = ['Walking Corpse' if case == 'counter-wave' else 'token:b_2_2_zombie']
        elif case == 'bounce-recast':
            deck = [('Island', 16), ('Unsummon', 24)]
            settings['hordeFixturePool'] = ['Walking Corpse']
        else:
            raise ValueError(case)
        settings['localDeck'] = dict(name='Bounded Horde ' + case,
                                     cards=[dict(name=n, count=c) for n, c in deck])
        engine = NativeEngine('zombie-horde', worker=args.worker,
                              managed=args.managed, fixture=args.fixture, **settings)
        def blocks(spec, state):
            if case not in ('ordinary-win','ordinary-playthrough'):
                return []
            used = set()
            result = []
            for option in spec['options']:
                attacker = next((i for i in option['attackerIds'] if i not in used), None)
                if attacker is not None:
                    used.add(attacker)
                    result.append(dict(forgeId=option['forgeId'], attackerIds=[attacker]))
            return result
        def attacks(spec, state):
            if case not in ('ordinary-win','ordinary-playthrough') or state['horde']['wave'] == 0:
                return [dict(forgeId=o['forgeId'], targetSeat=2) for o in spec['options']]
            # Preserve defenders rather than suicidally tapping the entire team.
            cards={c['forgeId']:c for c in state['battlefield']}
            reserve=sum(c['controller']==2 and 'Creature' in c['currentTypes'] for c in state['battlefield']) + 3
            candidates=sorted(spec['options'],key=lambda o:(cards[o['forgeId']]['name']=='Impassioned Orator', -cards[o['forgeId']]['power']))
            return [dict(forgeId=o['forgeId'], targetSeat=2) for o in candidates[:max(0,len(candidates)-reserve)]]
        def act(*positional, **keywords):
            return execute(engine, trace, *positional, _block_policy=blocks, _attack_policy=attacks, **keywords)
        rows = []
        observed_empty_alive = False
        seen_graveyard = set()
        seen_local_creatures = set()
        deadline = time.monotonic() + (300 if case=='ordinary-playthrough' else 180)
        for step in range(1400 if case=='ordinary-playthrough' else 500):
            s = engine.state
            seen_local_creatures.update(c['forgeId'] for z in ('hand','battlefield','graveyard','exile','stack') for c in s[z] if c['owner']==1 and 'Creature' in c['currentTypes'])
            seen_graveyard.update(c['forgeId'] for c in s['graveyard'] if c['owner'] == 2)
            rows.append({k: s.get(k) for k in ('turn', 'activeSeat', 'phase', 'life',
                                              'opponentLife', 'horde', 'gameOver')})
            assert not s['fidelityGap'], s['fidelityGap']
            if s['gameOver']:
                break
            assert time.monotonic() < deadline, 'Bounded Horde case timed out'
            if (s['horde']['remainingCards'] == 0 and
                    any(c['controller'] == 2 for c in s['battlefield'])):
                observed_empty_alive = True
                engine.check('Empty library alone is not a survivor win', not s['gameOver'])
            d = s.get('decision')
            if d:
                # execute also handles nested decisions through original handlers.
                if d['kind'] == 'mulligan':
                    act('submit_mulligan', decisionToken=d['token'], assignments=[dict(keep=True)])
                elif d['kind'] in ('discard', 'mulligan_bottom'):
                    act('submit_' + d['kind'], decisionToken=d['token'],
                            assignments=[dict(forgeId=o['forgeId']) for o in d['options'][:d['count']]])
                else:
                    raise AssertionError('Unexpected free-standing decision ' + str(d))
            elif s['legalLands']:
                act('play_land', s['legalLands'][0])
            elif s['legalCasts'] and case != 'ordinary-loss' and (
                    case not in ('empty-library-survivor', 'bounce-recast') or any(c['controller'] == 2 for c in s['battlefield'])):
                def target(spec, state):
                    if case == 'mill-before-wave':
                        return [next(o for o in spec['options'] if o.get('targetSeat') == 2)]
                    enemies = {c['forgeId'] for c in state['stack' if case.startswith('counter-') else 'battlefield'] if c['controller'] == 2}
                    return [next(o for o in spec['options'] if o['forgeId'] in enemies)]
                candidates=s['legalCasts']
                if case in ('ordinary-win','ordinary-playthrough'):
                    names={c['forgeId']:c['name'] for c in s['hand']}
                    candidates=sorted(candidates,key=lambda i:0 if names.get(i)=='Impassioned Orator' else 1)
                act('cast_spell', candidates[0], _target_policy=target)
            else:
                act('pass_priority')
            if case == 'combat-mill' and any(e['kind'] == 'horde-damage-mill' for e in engine.state['events']):
                break
            if case == 'bounce-recast' and sum(e['kind'] == 'horde-free-cast' for e in engine.state['events']) >= 2:
                break
        else:
            raise AssertionError('Horde action bound exceeded')
        s = engine.state
        events = s['events']
        engine.check('Horde initialized from real deck', s['horde']['initialized'])
        if case == 'ordinary-playthrough':
            engine.check('Unmodified 500-card Horde pool',s['horde']['initialCards']==500)
            engine.check('Actual non-pass-only game reaches a rules-owned outcome',s['gameOver'] and s['winnerSeat'] in (1,2))
            engine.check('Survivor cast real creatures before terminal player cleanup',any(v['kind']=='zone-change' and v['ownerSeat']==1 and v['forgeId'] in seen_local_creatures and v['from']=='Hand' and v['to']=='Stack' for v in s['researchTrace']))
            engine.check('Real blocker choices used',any(t['kind']=='blocker-assignments' and t['assignments'] for t in trace))
        elif case == 'ordinary-win':
            engine.check('Unmodified 500-card Horde pool', s['horde']['initialCards'] == 500)
            engine.check('Full ordinary Horde game records survivor victory', s['gameOver'] and s['winnerSeat'] == 1)
            engine.check('Real blocker choices used', any(t['kind'] == 'blocker-assignments' and t['assignments'] for t in trace))
        elif case == 'ordinary-loss':
            engine.check('Normal pool has exactly 500 cards', s['horde']['initialCards'] == 500)
            engine.check('Three preparation turns precede first wave',
                         next(e for e in events if e['kind'] == 'horde-wave')['turn'] == 4)
            engine.check('Horde actually wins against pass-only survivor', s['gameOver'] and s['winnerSeat'] == 2)
            engine.check('Forced Horde attacks dealt real combat damage',
                         any(e['kind'] == 'damage' and e['targetSeat'] == 1 and e['combat'] for e in events))
        elif case == 'bounce-recast':
            casts = [e for e in events if e['kind'] == 'horde-free-cast']
            engine.check('Bounced physical Horde card is cast again next wave',
                         len(casts) >= 2 and casts[0]['sourceForgeId'] == casts[1]['sourceForgeId']
                         and casts[1]['wave'] > casts[0]['wave'])
            engine.check('Pending bounced card does not cause premature victory', not s['gameOver'])
        elif case == 'combat-mill':
            damage = [e for e in events if e['kind'] == 'horde-damage-mill']
            engine.check('Human combat damage actually mills', bool(damage))
            engine.check('Mill count follows actual damage and remaining library',
                         all(len(e['milled']) == min(e['damage'], e['before']) and
                             e['remaining'] == e['before'] - len(e['milled']) for e in damage))
        else:
            engine.check('Clear Horde records actual survivor victory', s['gameOver'] and s['winnerSeat'] == 1)
            engine.check('No remaining Horde creatures at victory',
                         not any(c['controller'] == 2 for c in s['battlefield']))
            if case == 'empty-library-survivor':
                engine.check('Real creature kept empty-library Horde alive', observed_empty_alive)
            elif case.startswith('counter-'):
                cast_ids = {e['sourceForgeId'] for e in events if e['kind'] == 'horde-free-cast'}
                transitions = s['researchTrace']
                engine.check('Countered original Horde spell moves stack to graveyard',
                             any(e['kind'] == 'zone-change' and e['forgeId'] in cast_ids and
                                 e['from'] == 'Stack' and e['to'] == 'Graveyard' for e in transitions))
                engine.check('Countered Horde spell never enters battlefield',
                             not any(e['kind'] == 'zone-change' and e['forgeId'] in cast_ids and
                                     e['to'] == 'Battlefield' for e in transitions))
            else:
                damage = [e for e in events if e['kind'] == 'horde-damage-mill']
                engine.check('Damage causes real library-to-graveyard mill', bool(damage))
                milled = {i for e in damage for i in e['milled']}
                engine.check('Milled original IDs are in actual graveyard',
                             milled.issubset(seen_graveyard) or
                             milled.issubset({e['forgeId'] for e in s['researchTrace']
                                             if e['kind'] == 'zone-change' and e['ownerSeat'] == 2
                                             and e['from'] == 'Library' and e['to'] == 'Graveyard'}))
        return dict(case=case, passed=True, checks=engine.checks, final=s,
                    trace=trace, rows=rows, evidence=str(engine.ipc),
                    scope='Normal opening, native-handler inputs, real Forge effects; ' +
                    ('ordinary 500-card game' if case in ('ordinary-loss', 'ordinary-win','ordinary-playthrough') else 'initial small-pool mechanic fixture'))
    except Exception as error:
        return dict(case=case, passed=False, error=repr(error), traceback=traceback.format_exc(),
                    evidence=str(engine.ipc) if engine else None, trace=trace)
    finally:
        if engine:
            engine.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--worker', required=True, type=Path)
    p.add_argument('--managed', required=True, type=Path)
    p.add_argument('--fixture', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--cases', nargs='+', default=['ordinary-loss', 'mill-before-wave', 'empty-library-survivor', 'combat-mill'])
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    results = []
    for case in args.cases:
        result = run(case, args)
        (args.out / (case + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
        results.append({k: result[k] for k in ('case', 'passed', 'evidence')})
        print(json.dumps({**results[-1], 'error': (result.get('error') or '')[:200]}), flush=True)
    (args.out / 'report.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    raise SystemExit(0 if all(r['passed'] for r in results) else 1)


if __name__ == '__main__':
    main()
