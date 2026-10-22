"""Installed Forge startup, London choices and turn-loop integration checks."""
from engine_test_client import Engine
import json

reports=[]
for case in ('keep','double-mulligan','concede-mulligan','concede-bottom'):
    e=Engine('opening-duel',startingPlayerPolicy='local-first')
    try:
        s=e.state
        e.check('real startup exposes a seven-card mulligan decision',s['stage']=='Mulligan' and s['phase']=='PREGAME' and s['turn']==0 and len(s['hand'])==7 and s['decision']['kind']=='mulligan')
        e.check('startup has no gameplay offers',not any(s[k] for k in ('legalLands','legalCasts','legalMana')) and not s['canPass'])
        e.check('two full practice decks are present',len(s['hidden'])+len(s['hand'])==120 and len([c for c in s['hidden'] if c['owner']==2 and c['zone']=='Hand'])==7)
        if case=='concede-mulligan':
            r=e.send('concede');e.check('concession releases the real startup callback',r['accepted'] and e.state['gameOver'] and e.state['winnerSeat']==2)
        else:
            if case!='keep':
                redraws=2 if case=='double-mulligan' else 1
                for n in range(redraws):
                    d=e.state['decision'];old_token=d['token']
                    r=e.send('submit_mulligan',decisionToken=old_token,assignments=[{'keep':False}])
                    e.check('redraw '+str(n+1)+' offers seven before the keep choice',r['accepted'] and e.state['decision']['kind']=='mulligan' and len(e.state['hand'])==7 and e.state['mulligans']==n+1)
                d=e.state['decision']
                bad=e.send('submit_mulligan',decisionToken=old_token,assignments=[{'keep':True}])
                e.check('old redraw token cannot keep the new hand',not bad['accepted'] and e.state['decision']['token']==d['token'])
            d=e.state['decision'];r=e.send('submit_mulligan',decisionToken=d['token'],assignments=[{'keep':True}]);e.check('keep accepted by real Forge callback',r['accepted'])
            if case=='concede-bottom':
                e.check('kept mulligan requires the bottom-card choice',e.state['decision']['kind']=='mulligan_bottom')
                r=e.send('concede');e.check('concession releases bottom-card callback',r['accepted'] and e.state['gameOver'])
            else:
                if case=='double-mulligan':
                    d=e.state['decision'];token=d['token'];chosen=d['options'][:d['count']]
                    e.check('two mulligans require exactly two cards to bottom',d['kind']=='mulligan_bottom' and d['count']==2 and len(e.state['hand'])==7)
                    for label,values in [('too few',chosen[:1]),('duplicate',[chosen[0],chosen[0]]),('unoffered',[{'forgeId':999999},chosen[0]])]:
                        r=e.send('submit_mulligan_bottom',decisionToken=token,assignments=values)
                        e.check('reject '+label+' without changing the hand',not r['accepted'] and len(e.state['hand'])==7 and e.state['decision']['token']==token)
                    r=e.send('submit_mulligan_bottom',decisionToken=token,assignments=chosen);e.check('Forge bottoms exactly the selected cards',r['accepted'] and len(e.state['hand'])==5 and all(any(c['forgeId']==v['forgeId'] and c['zone']=='Library' for c in e.state['hidden']) for v in chosen))
                expected=7 if case=='keep' else 5
                e.check('normal first upkeep retains the kept hand',e.state['stage']=='Play' and e.state['turn']==1 and e.state['phase']=='UPKEEP' and len(e.state['hand'])==expected and not e.state['battlefield'])
                r=e.send('pass_priority');e.check('normal draw step skips the starting player draw',r['accepted'] and e.state['phase']=='MAIN1' and len(e.state['hand'])==expected)
                if e.state['legalLands']:
                    land=e.state['legalLands'][0];r=e.send('play_land',land)
                    e.check('normal priority loop executes a land ability',r['accepted'] and e.state['landsPlayed']==1 and any(c['forgeId']==land for c in e.state['battlefield']))
                r=e.send('concede');e.check('normal loop settles concession with no offers',r['accepted'] and e.state['gameOver'] and not any(e.state[k] for k in ('legalLands','legalCasts','legalMana')))
        e.check('hidden records omit card identities',all('name' not in c for c in e.state['hidden']))
        reports.append({'case':case,'evidence':str(e.ipc),'checks':len(e.checks)})
        print(json.dumps(reports[-1]),flush=True)
    finally:e.close()
print(json.dumps(reports,indent=2))
