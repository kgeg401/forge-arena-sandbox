"""Original automatic replacement chooser with a preserved manual override.

Forge's pinned automatic ranking is tested here, not Arena's server heuristic.
The player's real color choice and resulting token quantities remain asserted.
"""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

def run(mode,factory):
    tokens=mode=='tokens';name='Prosperous Innkeeper' if tokens else 'Coldsteel Heart'
    e=factory('card-family',fixtureHand=[name],fixtureLands=['Forest']*2 if tokens else ['Island']*2,fixtureBattlefield=['Chatterfang, Squirrel General','Peregrin Took'] if tokens else [],autoChooseReplacementEffects=mode!='manual')
    trace=[]
    try:
        if mode=='toggle':
            e.check('Preference can change inside the same game',e.send('snapshot',autoChooseReplacementEffects=False)['accepted'])
            e.check('Nonboolean preference is rejected',not e.send('snapshot',autoChooseReplacementEffects='true')['accepted'])
        def choose(spec,state):
            if spec['type']=='colors':return [dict(choiceId=next(o['choiceId'] for o in spec['options'] if o['color'].lower()=='blue'))]
            if spec['type']=='options':
                e.check('Manual replacement contains both original descriptions',len(spec['options'])==2 and all(o.get('description') for o in spec['options']))
                return [dict(choiceId=spec['options'][-1]['choiceId'])]
            raise AssertionError('Unexpected choice: '+spec['type'])
        execute(e,trace,'cast_spell',e.state['hand'][0]['forgeId'],_choice_policy=choose)
        for _ in range(12):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',_choice_policy=choose)
        seen=[row['type'] for row in trace if row.get('kind')=='choice']
        audit=e.state['researchControls']['auditedAutomaticDecisions']
        if tokens:
            selected=[v.removeprefix('auto-replacement:') for v in audit if v.startswith('auto-replacement:')]
            e.check('Automatic replacement records the actual original source',len(selected)==1 and selected[0] in ('Chatterfang, Squirrel General','Peregrin Took'))
            expected=2 if selected[0]=='Peregrin Took' else 1
            counts={n:sum(c['name']==n for c in e.state['battlefield']) for n in ('Treasure Token','Food Token','Squirrel Token')}
            e.check('Actual replacement order determines exact token outcome',counts=={'Treasure Token':1,'Food Token':1,'Squirrel Token':expected})
            e.check('Automatic ordering never requires a replacement button',not seen)
        else:
            heart=next(c for c in e.state['battlefield'] if c['name']==name)
            e.check('Original entered-tapped and chosen-color effects both apply',heart['tapped'] and [c.lower() for c in heart['chosenColors']]==['blue'])
            e.check('Automatic ordering preserves only the real color decision' if mode=='auto' else 'Manual override preserves ordering then real color decision',seen==(['colors'] if mode=='auto' else ['options','colors']))
            e.check('Automatic choice is auditable and absent in manual mode',('auto-replacement:Coldsteel Heart' in audit)==(mode=='auto'))
        e.check('No unresolved choice or native gap',not e.state.get('decision') and not e.state['fidelityGap'])
        return dict(case=mode,card=name,passed=True,checks=len(e.checks),trace=trace,evidence=str(e.ipc))
    finally:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('worker','managed','fixture','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    from native_engine_test_client import NativeEngine
    factory=lambda *args,**kw:NativeEngine(*args,worker=a.worker,managed=a.managed,fixture=a.fixture,**kw)
    rows=[]
    for mode in ('auto','manual','tokens','toggle'):
        row=run(mode,Engine if mode=='toggle' else factory);rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='trace'}),flush=True)
        a.output.write_text(json.dumps(dict(passed=True,cases=rows,scope=__doc__),indent=2),encoding='utf8')
