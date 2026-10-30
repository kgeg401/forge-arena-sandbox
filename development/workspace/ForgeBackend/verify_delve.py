"""Verify explicit delve payment, read-only availability and exact card outcomes."""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

CASES={
    'cruise-full':('Treasure Cruise',7,1),
    'cruise-partial':('Treasure Cruise',2,6),
    'cruise-none':('Treasure Cruise',0,8),
    'dig-full':('Dig Through Time',6,2),
    'tasigur-full':('Tasigur, the Golden Fang',5,1),
    'trespass-full':('Temporal Trespass',8,3),
}

def run(case,factory=Engine):
    name,exiles,mana=CASES[case];trace=[];choices_seen=[]
    e=factory('card-family',fixtureHand=[name],fixtureLands=['Swamp' if name.startswith('Tasigur') else 'Island']*mana,
              fixtureGraveyard=['Forest','Plains','Mountain','Swamp','Island','Grizzly Bears','Savannah Lions','Field Creeper'],
              fixtureLibrary=['Forest','Mountain','Plains','Swamp','Island','Grizzly Bears','Savannah Lions','Field Creeper','Forest','Island'])
    try:
        spell=e.state['hand'][0]['forgeId'];grave={c['forgeId'] for c in e.state['graveyard'] if c['owner']==1}
        library=[c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library'];selected=[]
        e.check('Original rules offer the spell with available delve resources',spell in e.state['legalCasts'])
        before={k:e.state[k] for k in ('hand','graveyard','exile','battlefield','manaTotal')}
        e.send('snapshot');e.send('snapshot')
        e.check('Availability refreshes never spend mana or exile cards',all(e.state[k]==v for k,v in before.items()) and e.state.get('decision') is None)
        def choice(c,state):
            if c.get('paymentKind')!='delve':return None
            choices_seen.append(c)
            e.check('Delve offers exactly the local graveyard', {o['forgeId'] for o in c['options']}==grave)
            e.check('Delve only pays the remaining generic portion',c['min']==0 and c['max']=={'Treasure Cruise':7,'Dig Through Time':6,'Tasigur, the Golden Fang':5,'Temporal Trespass':8}[name])
            if not hasattr(e,'native_call'):
                token=state['decision']['token'];first=c['options'][0]['choiceId']
                bad=[[dict(choiceId=first),dict(choiceId=first)],[dict(choiceId=-999)],[dict(choiceId=1.5)]]
                for values in bad:
                    r=e.send('submit_choice',decisionToken=token,assignments=values)
                    e.check('Invalid delve payment retains choice and all cards',not r['accepted'] and e.state['decision']['token']==token and {x['forgeId'] for x in e.state['graveyard'] if x['owner']==1}==grave and not e.state['exile'])
            selected.extend(o['forgeId'] for o in c['options'][:exiles])
            return [dict(choiceId=o['choiceId']) for o in c['options'][:exiles]]
        execute(e,trace,'cast_spell',spell,_choice_policy=choice)
        e.check('Only one actual payment choice',len(choices_seen)==1)
        e.check('Only selected graveyard cards were exiled',{c['forgeId'] for c in e.state['exile']}==set(selected))
        e.check('Unselected graveyard cards remain',{c['forgeId'] for c in e.state['graveyard'] if c['owner']==1}==grave-set(selected))
        e.check('Original mana payment spends exactly the remainder',sum(c['tapped'] for c in e.state['battlefield'] if c['owner']==1)==mana)
        for _ in range(8):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',_choice_policy=choice)
        e.check('Stack and decision complete',not e.state['stackOrder'] and e.state.get('decision') is None)
        if name=='Treasure Cruise':e.check('Cruise draws the actual three top cards',{c['forgeId'] for c in e.state['hand']}==set(library[:3]))
        elif name=='Dig Through Time':
            hand={c['forgeId'] for c in e.state['hand']};remaining=[c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library']
            e.check('Dig selects two from the top seven',len(hand)==2 and hand.issubset(set(library[:7])))
            e.check('Dig bottoms the other five without losing the untouched tail',remaining[:3]==library[7:] and set(remaining[3:])==set(library[:7])-hand)
        elif name.startswith('Tasigur'):e.check('Tasigur enters as the actual 4/5',any(c['forgeId']==spell and c['power']==4 and c['toughness']==5 for c in e.state['battlefield']))
        else:e.check('Temporal Trespass exiles itself on resolution',any(c['forgeId']==spell for c in e.state['exile']))
        e.check('No rules or presentation gap',not e.state['fidelityGap'])
        return dict(case=case,passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:return dict(case=case,passed=False,error=str(error)[:1600],evidence=str(e.ipc),trace=trace)
    finally:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append',choices=CASES)
    for name in ('native-worker','managed','fixture'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();factory=Engine
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native arguments')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    rows=[]
    for case in a.case or CASES:
        r=run(case,factory);rows.append(r);print(json.dumps({k:v for k,v in r.items() if k!='trace'}),flush=True)
        a.output.write_text(json.dumps(dict(passed=all(x['passed'] for x in rows),nativeHandlers=bool(a.native_worker),cases=rows),indent=2))
    raise SystemExit(0 if all(x['passed'] for x in rows) else 1)
