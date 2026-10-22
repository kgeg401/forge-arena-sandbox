"""Regression checks for false coverage and unsafe batch definitions, without a game."""
from copy import deepcopy
import json
from pathlib import Path
from run_card_batches import validate, summarize


def run():
    suite=json.loads((Path(__file__).with_name('card_batch_suites')/'draw-life.json').read_text(encoding='utf8'))
    validate(suite)
    checks=[]
    def rejected(label, mutate):
        bad=deepcopy(suite);mutate(bad)
        try:
            validate(bad)
        except (ValueError,KeyError,TypeError):
            checks.append(label);return
        raise AssertionError(label)
    rejected('Duplicate case IDs cannot masquerade as separate tests',lambda s:s['cases'].append(deepcopy(s['cases'][0])))
    rejected('Path traversal in case IDs rejected',lambda s:s['cases'][0].update(id='../escape'))
    rejected('Outcome expectations cannot be omitted',lambda s:s['cases'][0]['steps'][0].pop('life'))
    rejected('Negative outcomes rejected',lambda s:s['cases'][0]['steps'][0].update(draw=-1))
    rejected('Fixtures cannot mutate unimplemented runtime fields',lambda s:s['cases'][0]['fixture'].update(life=100))
    rejected('Oversized initial graveyard rejected',lambda s:s['cases'][0]['fixture'].update(fixtureGraveyard=['Plains']*41))
    rejected('A case cannot claim a different card was exercised',lambda s:s['cases'][0].update(card='Revitalize',covers=['main-phase']))
    rejected('Unknown branch cannot count as coverage',lambda s:s['cases'][0].update(covers=['all-cards-supported']))
    first=suite['cases'][0]
    report=dict(cases=[dict(id=first['id'],status='passed',checks=13)])
    summarize(report,suite)
    card=report['summary']['cards'][first['card']]
    assert card['missingBranches'] and not card['headlessBranchesComplete'] and not card['admitted']
    checks.append('One passing case leaves other branches missing and grants no admission')
    report['cases'].append(dict(id=suite['cases'][1]['id'],status='failed',category='life',checks=11))
    summarize(report,suite)
    assert report['summary']['failuresByCategory']=={'life':[suite['cases'][1]['id']]} and report['summary']['cards'][first['card']]['passedBranches']==first['covers']
    checks.append('Failed conditional branches remain missing and group by failure category')
    for c in suite['cases']:
        if c['id'] not in {r['id'] for r in report['cases']}:
            report['cases'].append(dict(id=c['id'],status='passed',checks=1))
    summarize(report,suite)
    assert all(not c['admitted'] for c in report['summary']['cards'].values())
    checks.append('Even complete authored branch coverage grants no playable admission')
    print(json.dumps(dict(checks=len(checks),passed=checks),indent=2))


if __name__=='__main__':
    run()
