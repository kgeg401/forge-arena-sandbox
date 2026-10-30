"""Assert real cycling, channel and graveyard activations across original zones.

Each bounded case supplies only initial state and player inputs. It checks the
named ability, not every printed effect or every interaction of the card.
"""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

CASES=[(n,'cycle',cost) for n,cost in [('Fetid Pools',2),('Canyon Slough',2),('Ketria Triome',3),('Savai Triome',3),("Xander's Lounge",3),('Barren Moor',1),('Tranquil Thicket',1),('Migration Path',2),('Unearth',2)]]
CASES += [('Angel of the Ruins','plains',2),('Ash Barrens','basic',1),('Lórien Revealed','island',1),('Shark Typhoon','shark0',2),('Shark Typhoon','shark2',4)]
CASES += [('Boseiju, Who Endures','destroy',1),('Sokenzan, Crucible of Defiance','spirits',3),('Otawara, Soaring City','bounce',3),('Takenuma, Abandoned Mire','mill-return',3),('Touch the Spirit Realm','blink',2),('Colossal Skyturtle','regrow',3),('Colossal Skyturtle','bounce',2),('Twinshot Sniper','damage',2),('Eiganjo, Seat of the Empire','combat-damage',2)]
CASES += [('Yotian Frontliner','unearth',1),('Molten Gatekeeper','unearth',1),('Yotian Frontliner','unearth-bounce',1),('Seasoned Pyromancer','grave-token',5),('Fanatic of Rhonas','eternalize',4)]

def run(name,kind,cost,factory=Engine):
    grave_mode=kind.startswith('unearth') or kind in ('grave-token','eternalize')
    settings=dict(fixtureHand=[] if grave_mode else [name],fixtureLands=[v for v in ('Plains','Island','Swamp','Mountain','Forest') for _ in range(3)],
        fixtureBattlefield=['Grizzly Bears','Magda, Brazen Outlaw'],fixtureBattlefieldReady=True,
        fixtureOpponentBattlefield=['Field Creeper'],fixtureGraveyard=([name] if grave_mode else [])+['Savannah Lions'],
        fixtureLibrary=['Forest','Island','Plains','Grizzly Bears','Forest','Island','Plains','Grizzly Bears'])
    if kind=='unearth-bounce':settings['fixtureHand']=['Unsummon']
    e=factory('card-family',**settings);trace=[]
    try:
        source=next(c['forgeId'] for c in e.state['graveyard' if grave_mode else 'hand'] if c['name']==name)
        bear=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears')
        enemy=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Field Creeper')
        lion=next(c['forgeId'] for c in e.state['graveyard'] if c['name']=='Savannah Lions')
        library=[c['forgeId'] for c in e.state['hidden'] if c['owner']==1 and c['zone']=='Library']
        search_target=library[2 if kind=='plains' else 1 if kind=='island' else 0]
        def offers():return [v for v in e.state['legalActivations'] if v['forgeId']==source]
        def choose(c,state):
            if c['type']=='number':return [dict(number=2 if kind=='shark2' else c['min'])]
            if c['type']=='confirm':return [dict(accept=not c.get('prompt','').startswith('Cancel Search?'))]
            if kind in ('plains','island','basic','mill-return'):
                wanted=lion if kind=='mill-return' else search_target
                match=[o for o in c['options'] if o.get('forgeId')==wanted]
                if match:return [dict(choiceId=match[0]['choiceId'])]
            return None
        def targets(spec,state):
            wanted=bear if kind in ('blink','combat-damage','unearth') else lion if kind=='regrow' else source if kind=='unearth-bounce' else enemy
            return [next(o for o in spec['options'] if o['forgeId']==wanted)]
        args=dict(_choice_policy=choose,_target_policy=targets)
        if kind=='combat-damage':
            e.check('Eiganjo is unavailable without an attacking or blocking target',not offers())
            for _ in range(20):
                if offers():break
                execute(e,trace,'pass_priority',_attack_policy=lambda spec,state:[dict(forgeId=bear,targetSeat=2)],**args)
            e.check('Eiganjo becomes available only after declaring an actual attacker',bool(offers()) and next(c for c in e.state['battlefield'] if c['forgeId']==bear)['attackTarget']==2)
        available=offers();e.check('Original zone exposes the requested ability',bool(available))
        if name=='Colossal Skyturtle':
            # Binding descriptions, not list order, distinguish both channels.
            from runtime_paths import ROOT
            entry=json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text())['cards'][name]
            identity=next(v for text,v in entry['abilityBindings']['descriptions'].items() if text.startswith('Channel') and ('from your graveyard' in text)==(kind=='regrow'))
            chosen=next(o for o in available if o['abilityId']==identity)
        else:chosen=available[0]
        execute(e,trace,'activate_ability',source,abilityId=chosen['abilityId'],**args)
        for _ in range(16):
            if not e.state['stackOrder']:break
            execute(e,trace,'pass_priority',**args)
        e.check('Actual mana cost including legendary reduction is paid',len([c for c in e.state['battlefield'] if 'Land' in c['currentTypes'] and c['owner']==1 and c['tapped']])==cost)
        if not grave_mode:e.check('Cycling or channel discards the actual source',any(c['forgeId']==source for c in e.state['graveyard']))
        if kind=='cycle' or kind.startswith('shark'):
            e.check('Cycling draws exactly the original top card',set(c['forgeId'] for c in e.state['hand'])=={library[0]})
            if kind.startswith('shark'):
                sharks=[c for c in e.state['battlefield'] if c.get('token') and 'Shark' in c['currentSubtypes']]
                e.check('Cycling X produces the correct live Shark or the zero-toughness token dies',not sharks if kind=='shark0' else len(sharks)==1 and sharks[0]['power']==2 and sharks[0]['toughness']==2 and 'Flying' in sharks[0]['rulesKeywords'])
        elif kind in ('plains','island','basic'):e.check('Typecycling puts only the selected matching land in hand',{c['forgeId'] for c in e.state['hand']}=={search_target})
        elif kind in ('destroy','damage','combat-damage'):e.check('The selected permanent actually dies',any(c['forgeId']==(bear if kind=='combat-damage' else enemy) for c in e.state['graveyard']))
        elif kind=='bounce':e.check('The selected opponent creature returns to its owner',any(c['forgeId']==enemy and c['owner']==2 and c['zone']=='Hand' for c in e.state['hidden']))
        elif kind=='regrow':e.check('Selected graveyard card reaches hand',any(c['forgeId']==lion for c in e.state['hand']))
        elif kind=='mill-return':
            e.check('Exactly the original top three cards were milled',set(library[:3])<={c['forgeId'] for c in e.state['graveyard']})
            e.check('Selected creature returns from graveyard',any(c['forgeId']==lion for c in e.state['hand']))
        elif kind=='spirits':
            tokens=[c for c in e.state['battlefield'] if c.get('token') and 'Spirit' in c['currentSubtypes']]
            e.check('Channel creates two 1/1 haste Spirits',len(tokens)==2 and all(c['power']==c['toughness']==1 and 'Haste' in c['rulesKeywords'] for c in tokens))
            e.check('Both temporary haste grants retain the actual channel source',all(any(g['keyword']=='Haste' and g['sourceForgeId']==source for g in c['keywordGrants']) for c in tokens))
        elif kind=='blink':e.check('Channel exiles the selected creature until the end step',any(c['forgeId']==bear for c in e.state['exile']))
        elif kind.startswith('unearth'):
            returned=next(c for c in e.state['battlefield'] if c['forgeId']==source)
            e.check('Unearth returns the original creature with haste','Haste' in returned['rulesKeywords'])
            if kind=='unearth-bounce':
                bounce=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Unsummon')
                execute(e,trace,'cast_spell',bounce,**args)
                for _ in range(8):
                    if not e.state['stackOrder']:break
                    execute(e,trace,'pass_priority',**args)
                e.check('Unearth replaces return to hand with exile',any(c['forgeId']==source for c in e.state['exile']) and not any(c['forgeId']==source for c in e.state['hand']))
        elif kind in ('grave-token','eternalize'):
            e.check('Actual source is exiled as the graveyard activation cost',any(c['forgeId']==source for c in e.state['exile']))
            tokens=[c for c in e.state['battlefield'] if c.get('token')]
            e.check('Expected graveyard ability tokens enter',len(tokens)==2 and all(c['power']==c['toughness']==1 and 'Elemental' in c['currentSubtypes'] for c in tokens) if kind=='grave-token' else len(tokens)==1 and tokens[0]['name']==name and tokens[0]['power']==tokens[0]['toughness']==4 and 'Zombie' in tokens[0]['currentSubtypes'] and tokens[0]['colorMask']==4)
        if kind in ('blink','unearth','spirits'):
            for _ in range(48):
                if e.state['turn']>1 and e.state['phase']=='MAIN1':break
                execute(e,trace,'pass_priority',**args)
            e.check('Game continues past the real end step',e.state['turn']>1)
            if kind=='blink':e.check('Delayed trigger returns the same creature',any(c['forgeId']==bear for c in e.state['battlefield']) and not any(c['forgeId']==bear for c in e.state['exile']))
            elif kind=='unearth':e.check('Unearth exiles the creature at the end step',any(c['forgeId']==source for c in e.state['exile']))
            else:e.check('Temporary Spirit haste expires',all('Haste' not in c['rulesKeywords'] for c in e.state['battlefield'] if c.get('token') and 'Spirit' in c['currentSubtypes']))
        e.check('No pending stack, hidden decision or fidelity gap',not e.state['stackOrder'] and not e.state.get('decision') and not e.state['fidelityGap'])
        return dict(card=name,kind=kind,passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:
        msg=error.args[0] if isinstance(error,AssertionError) and error.args else error
        if isinstance(msg,tuple):msg=msg[0]
        return dict(card=name,kind=kind,passed=False,error=type(error).__name__+': '+str(msg)[:1400],evidence=str(e.ipc),trace=trace)
    finally:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--shard-index',type=int,default=0);p.add_argument('--shard-count',type=int,default=1)
    for key in ('native-worker','managed','fixture'):p.add_argument('--'+key,type=Path)
    a=p.parse_args();factory=Engine
    if not 0<=a.shard_index<a.shard_count<=4:p.error('Invalid shard')
    if any((a.native_worker,a.managed,a.fixture)):
        if not all((a.native_worker,a.managed,a.fixture)):p.error('Supply all native paths')
        from native_engine_test_client import NativeEngine
        factory=lambda *args,**settings:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**settings)
    rows=[]
    for case in CASES[a.shard_index::a.shard_count]:
        r=run(*case,factory);rows.append(r);print(json.dumps({k:v for k,v in r.items() if k!='trace'}),flush=True)
        a.output.write_text(json.dumps(dict(passed=all(v['passed'] for v in rows),nativeHandlers=bool(a.native_worker),cases=rows),indent=2))
    raise SystemExit(0 if rows and all(v['passed'] for v in rows) else 1)
