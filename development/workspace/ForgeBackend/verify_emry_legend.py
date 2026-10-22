"""Legend choice and both entries' triggers, using only normal match inputs."""
import json
from emry_test_client import EmryGame,EMRY

results=[]
for keep_new in (False,True):
    g=EmryGame()
    try:
        g.lands(4);first=g.ensure_hand(EMRY);g.cast(first)
        g.next_main();g.optional_land();second=g.ensure_hand(EMRY)
        library={c['forgeId'] for c in g.s['hidden'] if c['owner']==1 and c['zone']=='Library'}
        g.cast(second,False)
        for _ in range(20):
            if g.s.get('decision'):break
            g.step()
        d=g.s['decision'];expected={first['forgeId'],second['forgeId']}
        g.check('Legend rule offers the two real Emry instances',d['kind']=='legend_rule' and {o['forgeId'] for o in d['options']}==expected)
        g.reject('Legend rule rejects zero choices','submit_legend_rule',decisionToken=d['token'],assignments=[])
        g.reject('Legend rule rejects unoffered card','submit_legend_rule',decisionToken=d['token'],assignments=[{'forgeId':-1}])
        kept=second if keep_new else first;lost=first if keep_new else second
        g.answer('legend_rule',[{'forgeId':kept['forgeId']}]);g.resolve()
        g.check('Chosen Emry alone remains on battlefield',[c['forgeId'] for c in g.cards('battlefield',EMRY)]==[kept['forgeId']])
        g.check('Other legendary instance really reaches graveyard',any(c['forgeId']==lost['forgeId'] for c in g.cards('graveyard',EMRY)))
        remaining={c['forgeId'] for c in g.s['hidden'] if c['owner']==1 and c['zone']=='Library'}
        g.check('Second entry still mills4 even if new Emry is not kept',len(library-remaining)==4)
        g.check('Kept instance retains its own summoning sickness',g.one('battlefield',EMRY)['sick']==keep_new)
        r=dict(keepNew=keep_new,checks=len(g.e.checks),evidence=str(g.e.ipc));(g.e.ipc/'emry-legend-result.json').write_text(json.dumps(r,indent=2));results.append(r)
    finally:g.close()
print(json.dumps(results,indent=2))
