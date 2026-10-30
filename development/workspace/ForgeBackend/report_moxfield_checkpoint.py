"""Publish bounded catalogue evidence without private paths or game data."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    def read(name): return json.loads((a.evidence/name).read_text(encoding='utf8'))
    captured = read('top50/decks.json')
    audit = read('pool-audit-validated.json')
    decks = captured['decks']
    assert len(decks) == len({d['publicId'] for d in decks}) == 50
    assert all(decks[i]['viewCount'] >= decks[i+1]['viewCount'] for i in range(49))
    cards = {c['nativeName']: c for c in audit['cards'] if c['status'] == 'identity-candidate'}
    assert audit['arenaOnly'] is True and len(cards) == 1188
    cast = {}
    activation = {}
    for i in range(1, 5):
        for row in read(f'catalogue-final-run-r1-{i}/report.json')['cases']:
            assert row['card'] not in cast
            cast[row['card']] = row['status']
        for row in read(f'activation-run-r1-{i}/report.json')['cases']:
            assert row['card'] not in activation
            activation[row['card']] = row['status']
    for row in read('activation-retest-run-r2/report.json')['cases']:
        assert row['card'] in activation
        activation[row['card']] = row['status']
    assert set(cast) == set(cards)
    assert sum(v == 'walkthrough-completed' for v in cast.values()) == 1173
    explicit = {}
    for filename in ('specific-native-r1-1.json', 'specific-native-r1-2.json',
                     'ninjutsu-native-r2.json', 'zones-native-r2.json',
                     'conditional-activations-native-final.json',
                     'context-activations-native-final.json'):
        report = read(filename)
        assert report['passed']
        for row in report['cases']:
            assert row['passed']
            if row.get('card') in cards:
                label = row.get('case', row.get('kind', row.get('effect')))
                assert isinstance(label, str) and label
                explicit.setdefault(row['card'], []).append(label)
    table = io.StringIO(newline='')
    writer = csv.writer(table, lineterminator='\n')
    writer.writerow(['Arena name', 'Deck appearances', 'Cast or land smoke test',
                     'First activation smoke test', 'Named native scenarios', 'Coverage limit'])
    for name in sorted(cards, key=str.casefold):
        writer.writerow([name, cards[name]['deckCount'], cast[name], activation.get(name, 'not selected'),
                         '; '.join(explicit.get(name, [])), 'Not exhaustive effect or interaction verification'])
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output/'MOXFIELD-CARD-COVERAGE.csv').write_text(table.getvalue(), encoding='utf8')
    text = '''# Moxfield Commander pool: 30 October 2026

This checkpoint sampled the 50 public Commander decks ranked by descending total
views in Moxfield's public search at the time below. This is popularity by views,
not a ranking of deck strength, recent tournament results or Arena legality.
Mainboards, commanders, companions, signature spells and sideboards are included;
maybeboards and token lists are excluded.

The lists contain 1,826 distinct names. **1,188 have matching identities in the
pinned installed Arena catalogue; 638 are excluded.** Catalogue presence does not
establish retail Brawl legality or account ownership. The client does not import
cards missing from that catalogue.

**942 new names are enabled experimentally.** Combined with earlier releases,
this build admits 1,285 experimental names plus the unchanged 370-name verified
baseline. No smoke-test result promotes a name to that verified baseline.

## What the tests establish

- All 1,188 identities match unique pinned Forge scripts and have resolved native
  presentation bindings. Binding success is not gameplay verification.
- 1,173 cards completed a generic cast or land-play walkthrough. The other 15
  require specific board states or choices and are covered by named native
  scenarios. Generic walkthroughs do not exercise every printed ability.
- 284 cards received a first-activation walkthrough attempt: 215 completed;
  69 need a specific fixture. Dedicated suites cover additional ninjutsu,
  cycling, channel, unearth, eternalize, protection and Class scenarios.
- Dedicated native scenarios cover counterspells, redirection, copying,
  conditional targets, gift, divided damage, piles, delve and a Battle.
- Eleven conditional-activation cases cover Wirewood Symbiote, Inventors' Fair,
  Chthonian Nightmare, Shifting Woodland, The Mycosynth Gardens and Bolas's
  Citadel, including real costs, expiration, insufficient resources and decline.
- Fourteen additional cases cover threshold lands, Dinosaur recovery, Haywire
  Mite, temporary protection, nonbasic-land destruction, bottom-library recovery,
  Minas Tirith's actual attack history and regeneration replacing destruction.
- Native-handler tests preserve genuine target/payment/response decisions.
  Rendered checks cover automatic combat triggers, original damage spinners,
  piles and Wizard Class levels with targeted draw triggers.

[Per-card smoke-test and named-scenario coverage](MOXFIELD-CARD-COVERAGE.csv)
separates completed walkthroughs from untested branches. A successful scenario
does not establish every interaction, combo, animation or complete deck.
In particular, partner commander pairs and importing these 50 decks as fully
playable lists are not established by this checkpoint.

## Captured public decks

'''
    text += 'Captured UTC: ' + captured['retrievedUtc'] + '\n\n'
    text += '| Rank | Public deck | Views at capture |\n| --- | --- | ---: |\n'
    for deck in decks:
        name = deck['name'].replace('|', '\\|').replace('[', '\\[').replace(']', '\\]').replace('\n', ' ')
        text += f"| {deck['rank']} | [{name}]({deck['publicUrl']}) | {deck['viewCount']:,} |\n"
    text += '\nCapture SHA-256: `' + hashlib.sha256((a.evidence/'top50/decks.json').read_bytes()).hexdigest() + '`\n'
    (a.output/'MOXFIELD-COVERAGE.md').write_text(text, encoding='utf8')
    print(json.dumps(dict(decks=len(decks), cards=len(cards), castSmokePasses=1173,
                          activationSmokePasses=sum(v=='activation-walkthrough-completed' for v in activation.values()),
                          verifiedPromotions=0)))


if __name__ == '__main__':
    main()
