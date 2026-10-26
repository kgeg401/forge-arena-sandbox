"""Mill fewer than four actual cards and lose only on the later failed draw."""
import json
from deck_import import parse_deck
from emry_test_client import EmryGame,EMRY

deck=parse_deck('8 Island\n32 Emry, Lurker of the Loch\n','Emry short-library practice')
g=EmryGame(deck_override=deck)
def library():return {c['forgeId'] for c in g.s['hidden'] if c['owner']==1 and c['zone']=='Library'}
try:
    g.lands(3);survivor=None;partial=False;casts=0
    for _ in range(12):
        before=library()
        while len(before) in (4,5):
            g.next_main();before=library()
        g.check('A real library remains before mill',len(before)>0)
        emry=g.one('hand',EMRY);old_gy={c['forgeId'] for c in g.cards('graveyard')};g.cast(emry,False)
        for _ in range(30):
            d=g.s.get('decision')
            if d:
                if g.shared_observation():continue
                g.check('Only the real legend rule interrupts this entry',d['kind']=='legend_rule')
                g.answer('legend_rule',[{'forgeId':survivor['forgeId']}])
            elif not g.s['stack'] and not g.s['stackAbilities']:break
            else:g.step()
        else:raise AssertionError('Entry resolution bound exceeded')
        casts+=1;survivor=g.one('battlefield',EMRY)
        removed=before-library();gy={c['forgeId'] for c in g.cards('graveyard')}
        g.check('Mill moves exactly the available source instances',len(removed)==min(4,len(before)) and removed<=gy-old_gy)
        g.check('Mill itself does not cause draw loss',not g.s['gameOver'])
        if len(before)<4:
            partial=True;g.check('Short library is completely milled',not library());break
        g.next_main()
    g.check('Reached a genuine fewer-than-four-card entry',partial)
    for _ in range(80):
        if g.s['gameOver']:break
        g.step()
    g.check('Only the later failed draw ends the game',g.s['gameOver'] and g.s['localLost'] and g.s['lossReason']=='Milled')
    r=dict(checks=len(g.e.checks),casts=casts,evidence=str(g.e.ipc),scope='Normal 40-card shuffled practice, real draws, repeated casts/legend choices and mill; no direct library edits')
    (g.e.ipc/'emry-library-boundary-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
finally:g.close()
