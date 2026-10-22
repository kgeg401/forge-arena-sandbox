"""Mutate disposable copies of an actual complete game's sealed evidence."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from build_card_evidence_ledger import load_matches,sha


def run(a):
    original=json.loads(a.report.read_text(encoding='utf8'))
    # Use one genuinely resolved card seen in both seats in a real game. This
    # narrows the inventory only; it does not create synthetic game outcomes.
    chosen=None
    for game in original['matches']:
        seats={name:{v['seat'] for v in game['resolved'] if v['name']==name} for name in original['requiredCards']}
        names=sorted(n for n,s in seats.items() if s=={1,2})
        if names:chosen=(game,names[0]);break
    if chosen is None:raise ValueError('Need a real single game with both-seat resolutions')
    game,name=chosen;a.output.mkdir(parents=True,exist_ok=False);checks=[]
    with tempfile.TemporaryDirectory(prefix='full-game-guards-',dir=a.output) as temporary:
        root=Path(temporary);evidence=root/'game';evidence.mkdir();report_path=root/'report.json'
        originals={n:(Path(game['evidence'])/n).read_bytes() for n in ('scenario.json','checks.json','engine-journal.jsonl')}
        small=deepcopy(original);row=deepcopy(game);row['evidence']=str(evidence)
        row['resolved']=[v for v in row['resolved'] if v['name']==name]
        counts=Counter(v['seat'] for v in row['resolved'])
        small.update(matches=[row],requiredCards=[name],resolved={name:{str(s):n for s,n in counts.items()}},missingSeatCoverage=[])
        inputs=json.loads((a.report.parent/'inputs.json').read_text(encoding='utf8'))
        (root/'inputs.json').write_text(json.dumps(inputs),encoding='utf8')

        def evaluate(label,mutate=None,valid=False):
            for filename,data in originals.items():(evidence/filename).write_bytes(data)
            data=deepcopy(small);data['matches'][0]['artifacts']={str(evidence/n):sha(evidence/n) for n in originals}
            if mutate:mutate(data)
            report_path.write_text(json.dumps(data),encoding='utf8')
            rejected=False
            try:load_matches(report_path)
            except (ValueError,KeyError,FileNotFoundError,TypeError):rejected=True
            if rejected==valid:raise AssertionError(label)
            checks.append(dict(check=label,passed=True))

        def reseal(data,filename):data['matches'][0]['artifacts'][str(evidence/filename)]=sha(evidence/filename)
        def change_json(filename,change):
            def mutate(data):
                path=evidence/filename;value=json.loads(path.read_text(encoding='utf8'));change(value)
                path.write_text(json.dumps(value),encoding='utf8');reseal(data,filename)
            return mutate
        def change_journal(change):
            def mutate(data):
                path=evidence/'engine-journal.jsonl';values=[json.loads(line) for line in path.read_text(encoding='utf8').splitlines() if line]
                change(values);path.write_text('\n'.join(json.dumps(v) for v in values)+'\n',encoding='utf8');reseal(data,'engine-journal.jsonl')
            return mutate
        def final(values):return next(v for v in reversed(values) if 'request' in v and 'response' in v)['response']['state']
        evaluate('Intact real complete game is accepted as narrow observed evidence',valid=True)
        evaluate('Match inventory cannot claim a new admission',lambda r:r.update(newAdmissions=1))
        evaluate('Incomplete requested-seat coverage is not a passed report',lambda r:r.update(missingSeatCoverage=[dict(name=name,seat=1)]))
        evaluate('A failed envelope cannot count as passed evidence',lambda r:r.update(passed=False))
        evaluate('Duplicate games cannot inflate totals',lambda r:r['matches'].append(deepcopy(r['matches'][0])))
        evaluate('Duplicate required cards are rejected',lambda r:r['requiredCards'].append(name))
        evaluate('A requested but never observed card is rejected',lambda r:r['requiredCards'].append('Unobserved test card'))
        evaluate('Wrong winner cannot be attached to a real terminal game',lambda r:r['matches'][0].update(winner=3-r['matches'][0]['winner']))
        evaluate('Wrong resolution seat cannot acquire game credit',lambda r:r['matches'][0]['resolved'][0].update(seat=3-r['matches'][0]['resolved'][0]['seat']))
        evaluate('False aggregate resolution counts are rejected',lambda r:r['resolved'][name].update({'1':999}))
        evaluate('Missing compiled rules identity is rejected',lambda r:r['identities'].pop(next(p for p in r['identities'] if Path(p).name=='ForgeLandEngine.class')))
        evaluate('Miscounted actual assertions are rejected',lambda r:r['matches'][0].update(checks=r['matches'][0]['checks']+1))
        evaluate('A failed underlying check overrides a resealed envelope',change_json('checks.json',lambda v:v[0].update(passed=False)))
        evaluate('Seeded battlefield fixtures cannot masquerade as shuffled play',change_json('scenario.json',lambda v:v.update(fixtureBattlefield=['Colossal Dreadmaw'])))
        evaluate('A different seed cannot reuse these results',change_json('scenario.json',lambda v:v.update(randomSeed=v['randomSeed']+1)))
        evaluate('An unsealed changed game file is rejected',lambda r:(evidence/'checks.json').write_text('[]',encoding='utf8'))
        evaluate('A nonterminal final state is rejected even after resealing',change_journal(lambda v:final(v).update(gameOver=False)))
        evaluate('A real fidelity gap cannot count as passing game evidence',change_journal(lambda v:final(v).update(fidelityGap='unmapped decision')))
        evaluate('Inherited local AI cannot count as strict human control',change_journal(lambda v:final(v)['researchControls'].update(strictHumanCallbacks=False)))
        def expose_hidden(values):
            state=next(v['response']['state'] for v in values if 'request' in v and 'response' in v and v['response']['state'].get('hidden'))
            state['hidden'][0]['name']='A hidden identity exposed only in an intermediate response'
        evaluate('An intermediate hidden-identity leak cannot be erased by the final state',change_journal(expose_hidden))
        def impossible_winner(data):
            change_journal(lambda values:final(values).update(winnerSeat=3))(data)
            data['matches'][0]['winner']=3
        evaluate('Even matching envelopes cannot invent a nonexistent winning seat',impossible_winner)
        def inject(values):next(v for v in values if 'request' in v and 'response' in v)['request']['op']='set_state'
        evaluate('Direct state injection is not an input-only full game',change_journal(inject))
    result=dict(checks=len(checks),results=checks,sourceReport=str(a.report),sourceReportSha256=sha(a.report),
                scope='Real full-game evidence mutation guards. Disposable copied artifacts only; no source game, policy or admission mutation.')
    (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(checks),report=str(a.output/'report.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('report','output'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
