"""Specific initial conditions for popular Arena cards that generic casts miss.

The independent assertions below measure these named scenarios only. No case
grants blanket support or substitutes seeded final states for real resolution.
"""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

CASES=[
 ('dispel','Dispel','counter'),('snare','Spell Snare','counter'),('scolding','Stern Scolding','counter'),('serenade','Strix Serenade','counter'),
 ('pull-plain',"Long River's Pull",'counter'),('pull-gift',"Long River's Pull",'counter'),
 ('swat','Deflecting Swat','redirect'),('lightning','Redirect Lightning','redirect'),('favor-redirect','Return the Favor','redirect'),
 ('flare','Flare of Duplication','copy'),('reversal',"Narset's Reversal",'copy'),('favor-copy','Return the Favor','copy'),('commandeer','Commandeer','control'),
 ('mycospawn-plain','Sowing Mycospawn','ramp'),('mycospawn-kicked','Sowing Mycospawn','ramp'),
 ('recycling-plain','Peerless Recycling','recycle'),('recycling-gift','Peerless Recycling','recycle'),
 ('despark','Despark','exile'),('stolen','Stolen by the Fae','bounce-token'),
 ('wail-exile','Warping Wail','exile'),('wail-counter','Warping Wail','counter'),('wail-token','Warping Wail','token'),
 ('hermit','Malevolent Hermit','creature'),('wanderer','Mausoleum Wanderer','creature'),
]

def run(case,factory=Engine):
    key,name,kind=case;trace=[]
    settings=dict(fixtureHand=[name],fixtureLands=[n for n in ['Plains','Island','Swamp','Mountain','Forest'] for _ in range(3)],
                  fixtureBattlefield=['Grizzly Bears','Sol Ring'],fixtureOpponentBattlefield=['Field Creeper','Forest'],
                  fixtureGraveyard=['Forest','Savannah Lions','Opt'],fixtureLibrary=['Forest','Plains','Island','Mountain','Grizzly Bears','Field Creeper']*3)
    enemy=None
    if kind in ('counter','copy','control','redirect'):
        enemy='Lightning Bolt' if key=='dispel' or kind=='redirect' else 'Divination' if kind in ('copy','control') or key in ('pull-gift','wail-counter') else 'Grizzly Bears'
        settings.update(fixtureOpponentSpell=enemy,fixtureOpponentLands=['Island']*3+['Mountain']+['Forest']*2)
        if enemy=='Lightning Bolt':settings['fixtureOpponentTargets']=[dict(seat=1,cardName='Grizzly Bears',occurrence=0)]
    if key=='despark':settings['fixtureOpponentBattlefield']=['Inferno Titan','Field Creeper']
    e=factory('card-family',**settings)
    try:
        spell=next(c['forgeId'] for c in e.state['hand'] if c['name']==name)
        old_enemy_hand={c['forgeId'] for c in e.state['hidden'] if c['owner']==2 and c['zone']=='Hand'}
        library=[c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library']
        battle={(c['name'],c['controller']):c['forgeId'] for c in e.state['battlefield']}
        grave={c['name']:c['forgeId'] for c in e.state['graveyard'] if c['owner']==1}
        stack=next((c['forgeId'] for c in e.state['stack'] if c['name']==enemy),None)
        e.check('Specific rules fixture makes this action available',spell in e.state['legalCasts'])
        def choices(c,state):
            typ=c['type'];prompt=c.get('prompt','').lower()
            if typ=='number':return [dict(number=2 if key=='stolen' else c['min'])]
            if typ=='confirm':return [dict(accept=not prompt.startswith('cancel search') and (kind=='redirect' or c.get('context')=='life-payment'))]
            if typ=='options':
                if 'additional costs' in prompt:
                    return [dict(choiceId=o['choiceId']) for o in c['options']] if key.endswith(('-gift','-kicked')) else []
                if 'choose how to cast' in prompt:return [dict(choiceId=c['options'][0]['choiceId'])]
            if typ=='modes':
                if key.startswith('wail-'):
                    phrase={'wail-exile':'Exile target','wail-counter':'Counter target','wail-token':'Create a'}[key]
                    mode=next(o['choiceId'] for o in c['options'] if phrase in o['label'])
                else:mode=2 if key=='favor-redirect' else 1
                return [dict(choiceId=mode)]
            if typ=='cards-zone' and kind=='ramp':return [dict(choiceId=next(o['choiceId'] for o in c['options'] if o['label']=='Forest'))]
            return None
        def targets(spec,state):
            opts=spec['options'];ids={o['forgeId'] for o in opts}
            if stack in ids:return [next(o for o in opts if o['forgeId']==stack)]
            if kind=='redirect' or key in ('stolen','wail-exile'):wanted=[battle['Field Creeper',2]]
            elif key=='despark':wanted=[battle['Inferno Titan',2]]
            elif kind=='ramp':wanted=[battle['Forest',2]]
            elif kind=='recycle':wanted=[grave['Forest'],grave['Savannah Lions']][:2 if key.endswith('gift') else 1]
            else:raise AssertionError('Unexpected target request '+str(spec))
            e.check('Only legal intended targets are offered',set(wanted).issubset(ids))
            return [next(o for o in opts if o['forgeId']==i) for i in wanted]
        args=dict(_choice_policy=choices,_target_policy=targets)
        execute(e,trace,'cast_spell',spell,**args)
        for _ in range(16):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',**args)
        else:raise AssertionError('Bounded stack did not finish')
        e.check('No pending stack or unsupported choice',not e.state['stackOrder'] and not e.state.get('decision') and not e.state['fidelityGap'])
        enemy_hand={c['forgeId'] for c in e.state['hidden'] if c['owner']==2 and c['zone']=='Hand'}
        if kind=='counter':
            e.check('Exact opposing spell was countered into its owner graveyard',any(c['forgeId']==stack and c['owner']==2 for c in e.state['graveyard']))
            e.check('No effects of the countered spell occurred',not any(c['forgeId']==stack for c in e.state['battlefield']) and all(c['damage']==0 for c in e.state['battlefield']))
            if key=='serenade':e.check('Serenade gives the opposing controller the flying 2/2 Bird',len([c for c in e.state['battlefield'] if c.get('token') and c['controller']==2 and c['power']==2 and c['toughness']==2 and 'Bird' in c['currentSubtypes'] and 'Flying' in c['rulesKeywords']])==1)
            if name=="Long River's Pull":e.check('Only promised gift draws an opposing card',len(enemy_hand-old_enemy_hand)==(1 if key.endswith('gift') else 0))
        elif kind=='redirect':
            e.check('Original intended target survives undamaged',any(c['forgeId']==battle['Grizzly Bears',1] and c['damage']==0 for c in e.state['battlefield']))
            e.check('Redirected Lightning Bolt kills the selected opposing creature',any(c['forgeId']==battle['Field Creeper',2] for c in e.state['graveyard']))
        elif kind in ('copy','control'):
            e.check('Local player draws the exact two cards from the copied or stolen Divination',{c['forgeId'] for c in e.state['hand']}==set(library[:2]))
            if key=='reversal':e.check('Reversal returns the original spell to its owner hand',stack in enemy_hand)
            else:e.check('Original Divination resolves to the owner graveyard',any(c['forgeId']==stack and c['owner']==2 for c in e.state['graveyard']))
            e.check('Only the original opposing spell draws for the opponent',len(enemy_hand-old_enemy_hand)==(2 if kind=='copy' and key!='reversal' else 1 if key=='reversal' else 0))
        elif kind=='ramp':
            e.check('Sowing Mycospawn enters as 3/3',any(c['forgeId']==spell and c['power']==3 and c['toughness']==3 for c in e.state['battlefield']))
            e.check('Cast trigger puts an actual library land onto battlefield',any(c['forgeId'] in library and c['name']=='Forest' and c['controller']==1 for c in e.state['battlefield']))
            e.check('Only kicker exiles the opposing land',any(c['forgeId']==battle['Forest',2] for c in e.state['exile'])==key.endswith('kicked'))
        elif kind=='recycle':
            wanted={grave['Forest'],grave['Savannah Lions']} if key.endswith('gift') else {grave['Forest']}
            e.check('Exact selected permanent cards return to hand',{c['forgeId'] for c in e.state['hand']}==wanted)
            e.check('Unselected instant remains in graveyard',any(c['forgeId']==grave['Opt'] for c in e.state['graveyard']))
            e.check('Gift draws exactly one card only if promised',len(enemy_hand-old_enemy_hand)==int(key.endswith('gift')))
        elif kind=='exile':
            target=battle['Inferno Titan' if key=='despark' else 'Field Creeper',2]
            e.check('Exact legal permanent exiled',any(c['forgeId']==target for c in e.state['exile']))
        elif kind=='bounce-token':
            e.check('Mana value X creature returned to its owner hand',battle['Field Creeper',2] in enemy_hand)
            e.check('Exactly X blue flying 1/1 Faeries created',len([c for c in e.state['battlefield'] if c.get('token') and c['controller']==1 and c['power']==1 and c['toughness']==1 and c['colorMask']==2 and 'Faerie' in c['currentSubtypes'] and 'Flying' in c['rulesKeywords']])==2)
        elif kind=='token':e.check('Third mode creates one colorless 1/1 Scion',len([c for c in e.state['battlefield'] if c.get('token') and c['controller']==1 and c['power']==1 and c['toughness']==1 and c['colorMask']==0 and 'Scion' in c['currentSubtypes']])==1)
        else:e.check('Creature spell enters battlefield',any(c['forgeId']==spell for c in e.state['battlefield']))
        return dict(case=key,card=name,passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:
        message=error.args[0] if isinstance(error,AssertionError) and error.args else error
        if isinstance(message,tuple):message=message[0]
        return dict(case=key,card=name,passed=False,error=str(message)[:1800],evidence=str(e.ipc),trace=trace)
    finally:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append');p.add_argument('--shard-index',type=int,default=0);p.add_argument('--shard-count',type=int,default=1)
    for name in ('native-worker','managed','fixture'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();factory=Engine
    if not 0<=a.shard_index<a.shard_count<=4:p.error('Invalid shard')
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native arguments')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    cases=[c for c in CASES if not a.case or c[0] in a.case][a.shard_index::a.shard_count];rows=[]
    for c in cases:
        r=run(c,factory);rows.append(r);print(json.dumps({k:v for k,v in r.items() if k!='trace'}),flush=True)
        a.output.write_text(json.dumps(dict(passed=all(x['passed'] for x in rows),nativeHandlers=bool(a.native_worker),cases=rows),indent=2))
    raise SystemExit(0 if rows and all(x['passed'] for x in rows) else 1)
