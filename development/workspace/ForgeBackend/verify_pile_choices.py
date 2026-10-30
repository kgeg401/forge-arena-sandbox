"""Verify genuine two-pile effects and temporary chooser-only visibility."""
import argparse
import json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute


def run(card,selection,factory=Engine):
    e=factory('card-family',fixtureHand=[card],fixtureLands=['Island']*4+['Swamp'],fixtureLibrary=['Forest','Mountain','Plains','Swamp','Island','Grizzly Bears'])
    trace=[];chosen=None;other=None
    try:
        original=[c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library'];spell=e.state['hand'][0]['forgeId']
        def choices(spec,state):
            nonlocal chosen,other
            if spec['type']!='piles':return None
            opts=spec['options'];n=4 if card=="Sauron's Ransom" else 5
            e.check('Two piles cover the exact original top cards',len(opts)==2 and sorted(i for o in opts for i in o['forgeIds'])==sorted(original[:n]))
            e.check('Correct pile faces', [o['faceDown'] for o in opts]==([True,False] if n==4 else [False,False]))
            visible={i for o in opts if not o['faceDown'] for i in o['forgeIds']};revealed={c['forgeId'] for c in spec['revealed']}
            e.check('Only face-up pile identities are disclosed',visible==revealed and all(c.get('privateToSeat')==1 and c.get('identityVisible') for c in spec['revealed']))
            e.check('Hidden pile options contain no card-name disclosure',all(set(o)=={'choiceId','label','faceDown','forgeIds'} for o in opts))
            chosen=opts[selection-1]['forgeIds'][:];other=opts[2-selection]['forgeIds'][:]
            if not hasattr(e,'native_call'):
                for values in ([],[dict(choiceId=99)],[dict(choiceId=1),dict(choiceId=2)],[dict(choiceId=1.5)]):
                    reply=e.send('submit_choice',decisionToken=state['decision']['token'],assignments=values)
                    e.check('Malformed pile selection cannot advance',not reply['accepted'] and e.state['decision']['token']==state['decision']['token'])
            return [dict(choiceId=selection)]
        execute(e,trace,'cast_spell',spell,_choice_policy=choices)
        for _ in range(8):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',_choice_policy=choices)
        e.check('Actual pile choice occurred',chosen is not None)
        e.check('Chosen pile moved to hand',{c['forgeId'] for c in e.state['hand']}==set(chosen))
        e.check('Unchosen pile moved to graveyard',{c['forgeId'] for c in e.state['graveyard'] if c['owner']==1 and c['forgeId']!=spell}==set(other))
        n=4 if card=="Sauron's Ransom" else 5
        e.check('Untouched library tail remains in order',[c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library']==original[n:])
        e.check('No pending choice, stack or rules gap',e.state.get('decision') is None and not e.state['stackOrder'] and not e.state['fidelityGap'])
        return dict(card=card,selection=selection,passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:return dict(card=card,selection=selection,passed=False,error=str(error)[:1500],evidence=str(e.ipc),trace=trace)
    finally:e.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    for name in ('native-worker','managed','fixture'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();factory=Engine
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native worker arguments')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    rows=[]
    # Fact or Fiction is intentionally excluded: it is absent from this owned
    # Arena catalogue. Test both actual choices of the admitted Arena spell.
    for card in ("Sauron's Ransom",):
        for selection in (1,2):
            r=run(card,selection,factory);rows.append(r);print(json.dumps({k:v for k,v in r.items() if k!='trace'}),flush=True)
            a.output.write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),nativeHandlers=bool(a.native_worker),cases=rows),indent=2),encoding='utf8')
    raise SystemExit(0 if all(r['passed'] for r in rows) else 1)
