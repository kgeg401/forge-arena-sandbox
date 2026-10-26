"""Adversarial native-driver inputs, recovery and exactly-once gameplay checks."""
import argparse
import copy
import json
import os
from pathlib import Path
import uuid


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy))
    from native_engine_test_client import NativeEngine
    a.output.mkdir(parents=True,exist_ok=False)
    e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,fixtureHand=['Opt'],fixtureLands=['Island'],fixtureLibrary=['Forest','Mountain','Plains'])
    try:
        def check(label,value):e.check(label,value)
        def state():return copy.deepcopy(e.state)
        before=state();cast=next(c['forgeId'] for c in before['hand'] if c['name']=='Opt')
        for label,fields in [('foreign worker',dict(worker='foreign')),('foreign session',dict(session='foreign')),('stale state',dict(nativeStateId=0)),('stale request',dict(nativeMessageId=0)),('wrong seat',dict(seat=2))]:
            reply=e.native_call('cast_spell',cast,**fields);check(label+' rejected before native handler',not reply['accepted']);check(label+' leaves actual rules state unchanged',e.state==before)
        for fields in (dict(forgeId=str(cast)),dict(forgeId=float(cast)),dict(nativeStateId=str(e.native_status['nativeStateId'])),dict(nativeMessageId=float(e.native_status['nativeMessageId']))):
            reply=e.native_call('cast_spell',**fields);check('Native integer coercion is rejected before consuming the handler',not reply['accepted']);check('Rejected coercion preserves the actual rules state',e.state==before)
        invalid=e.native_call('cast_spell',next(c['forgeId'] for c in before['battlefield']));check('Unoffered native action is rejected without consuming the handler',not invalid['accepted'] and e.state==before)
        check('Valid native cast works after rejected input',e.send('cast_spell',cast)['accepted'])
        response,decision=e.pass_or_decision();check('Native scry interaction appears in the same session',decision is not None and e.native_status['interaction']=='GroupRequest')
        d=e.state['decision'];token=d['token'];option=d['choice']['options'][0]['choiceId'];before=state();ordinal=e.native_status['updateOrdinal']
        for values in [[],[dict(choiceId=option,group='top')]*2,[dict(choiceId=option+999,group='top')],[dict(choiceId=option,group='unknown')],[dict(choiceId=option,group='top',extra=True)]]:
            reply=e.native_call('submit_choice',decisionToken=token,assignments=values);check('Malformed native partition is rejected before submitting',not reply['accepted']);check('Malformed partition preserves the active native handler',e.state==before and e.native_status['updateOrdinal']==ordinal)
        values=[dict(choiceId=option,group='top')]
        reply=e.native_call('submit_choice',decisionToken=token,assignments=values);check('Native handler recovers and submits the valid choice',reply['accepted'])
        actual=e.finish(reply['forgeRequestId']);check('Recovered choice really draws one card',actual['accepted'] and [c['name'] for c in e.state['hand']]==['Forest'])
        before=state();ordinal=e.native_status['updateOrdinal']
        lines=[json.loads(line) for line in (e.native_folder/'native-model.jsonl').read_text().splitlines()]
        original=next(row['value']['request'] for row in lines if row['kind']=='command-submitted' and row['value']['id']==reply['id'])
        def resend(request):
            path=e.native_folder/'requests'/(request['id']+'.json');temporary=path.with_suffix('.pending');temporary.write_text(json.dumps(request));temporary.replace(path)
            return e.native_wait(e.native_folder/'responses'/path.name)
        # Remove only the specific old reply so waiting cannot read its stale copy.
        response_path=e.native_folder/'responses'/(reply['id']+'.json');response_path.unlink();again=resend(original)
        check('Exact accepted replay returns its original receipt',again==reply)
        check('Accepted replay cannot draw twice or advance the native model',e.state==before and e.native_status['updateOrdinal']==ordinal)
        response_path.unlink();conflict=copy.deepcopy(original);conflict['assignments'][0]['group']='bottom';bad=resend(conflict)
        check('Conflicting accepted request identity is rejected',not bad['accepted'] and 'reused' in bad['reason'])
        from engine_test_client import Engine
        actual=Engine.finish(e,Engine.begin(e,'snapshot'))
        check('Conflicting replay preserves actual rules state',actual['accepted'] and e.state==before)
        submitted=[json.loads(line) for line in (e.ipc/'engine-journal.jsonl').read_text().splitlines()]
        check('Replays create no second rules submission',sum(row.get('request',{}).get('op')=='submit_choice' and row.get('request',{}).get('decisionToken')==token for row in submitted)==1)
        check('Native session remains usable after conflicting replay',e.send('pass_priority')['accepted'])
        result=dict(passed=True,checks=e.checks,evidence=str(e.ipc),scope='Persistent local native input, recovery and request replay. No rendered acceptance or card admission.')
        (a.output/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(passed=True,checks=len(e.checks),evidence=str(e.ipc))))
    finally:e.close()


if __name__=='__main__':main()
