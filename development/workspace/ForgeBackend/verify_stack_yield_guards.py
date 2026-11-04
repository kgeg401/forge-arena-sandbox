"""Malformed/foreign requests cannot suppress real human offers or advance rules."""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
e=Engine('card-family',fixtureHand=['Secure the Wastes','Opt'],fixtureLands=['Plains']*5+['Island'],fixtureBattlefield=['Impassioned Orator']*4,fixtureOpponentPolicy='passive',autoOrderTriggers=True)
checks=[]
def check(label,value):checks.append(dict(check=label,passed=bool(value)));assert value,label
try:
    def choose(c,s):
        if c['type']=='number':return [dict(number=4)]
    execute(e,[],'cast_spell',e.state['hand'][0]['forgeId'],_choice_policy=choose);execute(e,[],'pass_priority')
    check('Actual paid spell generates sixteen triggers',len(e.state['stackOrder'])==16)
    opt=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Opt')
    for fields in [dict(deferActionOffers='all'),dict(automaticRulesStep=False,deferActionOffers='all'),dict(automaticRulesStep='true',deferActionOffers='all'),dict(automaticRulesStep={},deferActionOffers='all'),dict(automaticRulesStep=True,deferActionOffers=1),dict(automaticRulesStep=True,deferActionOffers='unknown')]:
        reply=e.send('pass_priority',**fields)
        check('Only the exact automatic yield policy defers offers: '+str(fields),reply['accepted'] and not e.state.get('actionOffersDeferred') and opt in e.state['legalCasts'])
    for fields in [dict(seat=2),dict(session='foreign')]:
        before=e.state['life'];reply=e.send('pass_priority',automaticRulesStep=True,deferActionOffers='all',**fields)
        check('A rejected request changes neither life nor action offers: '+str(fields),not reply['accepted'] and e.state['life']==before and not e.state.get('actionOffersDeferred') and opt in e.state['legalCasts'])
    reply=e.send('pass_priority',automaticRulesStep=True,deferActionOffers='all')
    check('Explicit accepted local yield defers only forecasts',reply['accepted'] and e.state.get('actionOffersDeferred') and e.state['canPass'] and not e.state['legalCasts'])
    before=(e.state['life'],e.state['stackOrder']);reply=e.send('snapshot',automaticRulesStep=True,deferActionOffers='all')
    check('A snapshot restores offers without resolving another trigger',reply['accepted'] and not e.state.get('actionOffersDeferred') and opt in e.state['legalCasts'] and before==(e.state['life'],e.state['stackOrder']))
    report=dict(passed=True,checks=checks,evidence=str(e.ipc),scope=__doc__)
finally:e.close()
(a.output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(passed=True,checks=len(checks),evidence=str(e.ipc))))
