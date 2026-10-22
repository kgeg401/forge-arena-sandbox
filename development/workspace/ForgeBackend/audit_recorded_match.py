"""Compare a real session's Forge journal with the installed Arena parser replay.

This audits recorded evidence, not rendered animation fidelity. Run ParserProbe on
the matching native-wire file first. Originals remain unchanged.
"""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('journal', type=Path)
parser.add_argument('parser_report', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
entries = [json.loads(line) for line in args.journal.read_text().splitlines() if line.strip()]
states = [e['response']['state'] for e in entries if e.get('response', {}).get('accepted') and 'state' in e['response']]
native = json.loads(args.parser_report.read_text())
final = states[-1]
checks = []

def check(name, condition):
    checks.append({'name': name, 'passed': bool(condition)})

def changes(values):
    result = []
    for value in values:
        if not result or value != result[-1]:
            result.append(value)
    return result

check('one Forge session', len({s['session'] for s in states}) == 1)
check('no reported Forge fidelity gap', all(not s.get('fidelityGap') for s in states))
check('Forge reached terminal result', final['gameOver'] and final['winnerSeat'] in (1, 2))
check('exact final life totals', native['states'][-1]['life'] == [final['life'], final['opponentLife']])
engine_life = changes([[20, 20]] + [[s['life'], s['opponentLife']] for s in states])
native_life = changes([s['life'] for s in native['states']])
check('every life change agrees in order', engine_life == native_life)
events = {e['id']: e for s in states for e in s['events'] if e['kind'] == 'damage'}
damage = sum(e['amount'] for e in events.values())
check('all damage agrees', damage == native['damageTotal'])
for seat in (1, 2):
    engine_hits = sorted(e['amount'] for e in events.values() if e.get('targetSeat') == seat)
    native_hits = sorted(e['amount'] for e in native['events'] if e['kind'] == 'damage' and e['target'] == seat)
    check(f'every player {seat} hit agrees', engine_hits == native_hits)
check('one native match result', len(native['results']) == 1 and native['results'][0]['scope'] == 'Match')
expected_loser = 'LocalPlayer' if final['winnerSeat'] == 2 else 'Opponent'
check('winner agrees', len(native['results']) == 1 and native['results'][0]['loser'] == expected_loser)
check('native game-over stage', native['states'][-1]['stage'] == 'GameOver')
check('hidden cards carry no names', all('name' not in c for s in states for c in s['hidden']))
report = {'scope': 'Recorded Forge versus installed Arena parser; rendered outcome verified separately',
          'session': final['session'], 'scenario': final['scenario'], 'turn': final['turn'],
          'damage': damage, 'lifeChanges': engine_life, 'checks': checks,
          'passed': all(c['passed'] for c in checks)}
args.output.write_text(json.dumps(report, indent=2))
print(json.dumps(report))
raise SystemExit(0 if report['passed'] else 1)
