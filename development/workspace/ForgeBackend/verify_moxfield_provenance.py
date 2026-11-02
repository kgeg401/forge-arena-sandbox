"""Deck-count provenance checks without game assets or network access."""
import json,tempfile
from pathlib import Path
from audit_moxfield_pool import ranked_deck_count

checks=[]
with tempfile.TemporaryDirectory(prefix='moxfield-count-') as folder:
    p=Path(folder)/'cards.json';ranking=p.with_name('decks.json')
    for count in (20,50):
        ranking.write_text(json.dumps(dict(requested=count,complete=True,decks=[{}]*count)))
        assert ranked_deck_count(p,{})==count
        assert ranked_deck_count(p,dict(rankedDecks=count))==count
        checks.append('Correct count from old and explicit capture: '+str(count))
    for label,source,capture in [
        ('mismatched counts',dict(rankedDecks=20),dict(requested=50,complete=True,decks=[{}]*50)),
        ('incomplete ranking',{},dict(requested=20,complete=False,decks=[{}]*19)),
        ('boolean count',dict(rankedDecks=True),dict(requested=True,complete=True,decks=[{}])),
    ]:
        ranking.write_text(json.dumps(capture))
        try:ranked_deck_count(p,source)
        except ValueError:checks.append('Rejects '+label)
        else:raise AssertionError('Accepted '+label)
print(json.dumps(dict(passed=True,checks=checks),indent=2))
