"""Named conditional activation outcomes through independent Forge inputs.

Only initial objects are seeded. Costs, targets, copies and expiration execute
normally. Passing these scenarios is not exhaustive card or combo coverage.
"""
import argparse,json
from pathlib import Path
from engine_test_client import Engine
from native_test_policy import execute

CASES=['wirewood','fair-active','fair-inactive','nightmare','nightmare-expensive','nightmare-decline','woodland','gardens-zero','gardens-two','gardens-unpayable','citadel']


def run(kind,factory):
    settings=dict(fixtureHand=[],fixtureLands=['Forest']*4+['Swamp']*2,fixtureBattlefieldReady=True,fixtureLibrary=['Arcane Signet','Plains','Forest','Island','Mountain','Swamp']*3)
    names={'wirewood':'Wirewood Symbiote','fair-active':"Inventors' Fair",'fair-inactive':"Inventors' Fair",'nightmare':'Chthonian Nightmare','woodland':'Shifting Woodland','gardens-zero':'The Mycosynth Gardens','gardens-two':'The Mycosynth Gardens','citadel':"Bolas's Citadel"}
    name=names['nightmare' if kind.startswith('nightmare') else 'gardens-two' if kind=='gardens-unpayable' else kind]
    if kind=='wirewood':settings.update(fixtureBattlefield=[name,'Llanowar Elves','Elvish Mystic'])
    elif kind.startswith('fair-'):settings.update(fixtureBattlefield=[name]+['Ornithopter']*(3 if kind=='fair-active' else 2))
    elif kind.startswith('nightmare'):settings.update(fixtureHand=[name],fixtureBattlefield=['Llanowar Elves'],fixtureGraveyard=['Solemn Simulacrum' if kind=='nightmare-expensive' else 'Grizzly Bears'])
    elif kind=='woodland':settings.update(fixtureBattlefield=[name],fixtureGraveyard=['Forest','Grizzly Bears','Ornithopter','Divination'])
    elif kind.startswith('gardens-'):settings.update(fixtureBattlefield=[name,'Ornithopter' if kind=='gardens-zero' else 'Arcane Signet'])
    elif kind=='citadel':settings.update(fixtureBattlefield=[name]+['Ornithopter']*7,fixtureHand=['Ornithopter']*2)
    if kind=='gardens-unpayable':settings['fixtureLands']=[]
    e=factory('card-family',**settings);trace=[];wanted=None
    try:
        def find(zone,n):return next(c for c in e.state[zone] if c['name']==n and c.get('owner')==1)
        def choice(spec,state):
            if spec['type']=='confirm':return [dict(accept=not(kind=='nightmare-decline' and spec.get('context')=='energy-payment'))]
            if spec['type']=='number':return [dict(number=0 if kind=='gardens-zero' else 2)]
            if kind=='wirewood' and spec['type'] in ('cards-effect','entities'):
                return [dict(choiceId=next(o['choiceId'] for o in spec['options'] if o.get('forgeId')==find('battlefield','Elvish Mystic')['forgeId']))]
            if kind=='citadel' and spec['type'] in ('cards-effect','sacrifice'):
                return [dict(choiceId=o['choiceId']) for o in spec['options']]
            if kind=='fair-active' and spec['type']=='cards-zone':
                return [dict(choiceId=next(o['choiceId'] for o in spec['options'] if o['label']=='Arcane Signet'))]
            return None
        def target(spec,state):return [next(o for o in spec['options'] if o['forgeId']==wanted)]
        def act(op,card=0,**fields):return execute(e,trace,op,card,_choice_policy=choice,_target_policy=target,**fields)
        def resolve():
            for _ in range(20):
                if not e.state['stackOrder']:return
                act('pass_priority')
            raise AssertionError('Resolution exceeded20 steps')
        if kind.startswith('nightmare'):
            act('cast_spell',find('hand',name)['forgeId']);resolve()
            e.check('Actual enter trigger gives three energy',any(c['type']=='ENERGY' and c['count']==3 for c in e.state['players'][0]['counters']))
        if kind=='citadel':
            for _ in range(2):
                act('cast_spell',find('hand','Ornithopter')['forgeId']);resolve()
        source=find('battlefield',name)['forgeId']
        def offers():return [a for a in e.state['legalActivations'] if a['forgeId']==source]
        if kind in ('fair-inactive','nightmare-expensive','gardens-unpayable'):
            e.check('Ability unavailable when its actual resource requirement cannot be met',not offers())
            if kind=='nightmare-expensive':
                e.check('Availability probe retains all energy and permanents',any(c['type']=='ENERGY' and c['count']==3 for c in e.state['players'][0]['counters']) and find('battlefield','Llanowar Elves') and find('battlefield',name) and find('graveyard','Solemn Simulacrum'))
            elif kind=='gardens-unpayable':
                e.check('Availability probe leaves both artifacts and land untapped',not find('battlefield',name)['tapped'] and not find('battlefield','Arcane Signet')['tapped'])
        else:
            if kind=='wirewood':
                elf=find('battlefield','Llanowar Elves');wanted=elf['forgeId']
                mana=next(a for a in e.state['legalManaOffers'] if a['forgeId']==wanted)
                act('activate_mana',wanted,abilityId=mana['abilityId'])
                e.check('Actual mana activation taps target elf',find('battlefield','Llanowar Elves')['tapped'])
            elif kind=='woodland' or kind.startswith('nightmare'):wanted=find('graveyard','Grizzly Bears')['forgeId']
            elif kind.startswith('gardens-'):wanted=find('battlefield','Ornithopter' if kind=='gardens-zero' else 'Arcane Signet')['forgeId']
            available=offers();e.check('Original conditional ability is available',len(available)==1)
            before_taps=sum(c['tapped'] for c in e.state['battlefield'] if c['owner']==1 and 'Land' in c['currentTypes'])
            try:act('activate_ability',source,abilityId=available[0]['abilityId'])
            except RuntimeError as error:
                if kind!='nightmare-decline' or 'canceled' not in str(error).lower():raise
            resolve()
            if kind=='wirewood':
                e.check('Chosen second elf returned as the actual cost',any(c['name']=='Elvish Mystic' for c in e.state['hand']))
                e.check('Target elf untapped',not find('battlefield','Llanowar Elves')['tapped'])
                e.check('Once-per-turn activation now unavailable',not offers())
            elif kind=='fair-active':
                e.check('Tutor sacrifices its actual source',any(c['forgeId']==source for c in e.state['graveyard']))
                e.check('Exactly selected artifact goes to hand',[c['name'] for c in e.state['hand']]==['Arcane Signet'])
                e.check('Four real lands pay the cost',sum(c['tapped'] for c in e.state['battlefield'] if c['owner']==1 and 'Land' in c['currentTypes'])-before_taps==4)
            elif kind=='nightmare-decline':
                e.check('Energy decline was a real player choice',any(row.get('prompt','').startswith('Pay 2 energy') and row.get('selected')==[dict(accept=False)] for row in trace))
                e.check('Decline preserves all three energy',any(c['type']=='ENERGY' and c['count']==3 for c in e.state['players'][0]['counters']))
                e.check('Decline preserves creature source and graveyard target',find('battlefield','Llanowar Elves') and find('battlefield',name) and find('graveyard','Grizzly Bears'))
                e.check('Canceled activation can be offered again',len(offers())==1 and not e.state['stackOrder'])
            elif kind=='nightmare':
                e.check('Two energy paid from three',any(c['type']=='ENERGY' and c['count']==1 for c in e.state['players'][0]['counters']))
                e.check('Creature sacrificed and enchantment returned',any(c['name']=='Llanowar Elves' for c in e.state['graveyard']) and any(c['forgeId']==source for c in e.state['hand']))
                e.check('Selected creature returned from graveyard',any(c['forgeId']==wanted and c['power']==c['toughness']==2 for c in e.state['battlefield']))
            elif kind=='woodland':
                current=next(c for c in e.state['battlefield'] if c['forgeId']==source)
                e.check('Land copies selected creature while retaining instance',current['name']=='Grizzly Bears' and current['power']==current['toughness']==2 and 'Creature' in current['currentTypes'] and 'Land' not in current['currentTypes'])
                for _ in range(48):
                    if e.state['turn']>1:break
                    act('pass_priority')
                current=next(c for c in e.state['battlefield'] if c['forgeId']==source)
                e.check('Original land returns at actual end of turn',current['name']==name and 'Land' in current['currentTypes'] and 'Creature' not in current['currentTypes'])
            elif kind.startswith('gardens-'):
                current=next(c for c in e.state['battlefield'] if c['forgeId']==source)
                e.check('Exact artifact identity copied',current['name']==('Ornithopter' if kind=='gardens-zero' else 'Arcane Signet') and 'Artifact' in current['currentTypes'] and 'Land' not in current['currentTypes'])
                e.check('Copy retains paid tap cost',current['tapped'])
                e.check('X mana cost actually paid',sum(c['tapped'] for c in e.state['battlefield'] if c['owner']==1 and 'Land' in c['currentTypes'])-before_taps==(0 if kind=='gardens-zero' else 2))
            else:
                e.check('All ten nonland permanents sacrificed',sum(c['name']=='Ornithopter' for c in e.state['graveyard'])==9 and any(c['forgeId']==source for c in e.state['graveyard']))
                e.check('Opponent loses exactly ten life and local player none',e.state['opponentLife']==10 and e.state['life']==20)
        e.check('No fidelity gap or pending decision',not e.state['fidelityGap'] and not e.state.get('decision'))
        if kind in ('nightmare','nightmare-decline'):
            updates=[r['value'] for line in (e.native_folder/'native-model.jsonl').read_text(encoding='utf-8-sig').splitlines() for r in [json.loads(line)] if r['kind']=='native-update']
            e.check('Native energy question uses original two-energy prompt',any(r.get('promptId')==1150 for r in updates))
            if kind=='nightmare':e.check('Native return payment names actual source',any(r.get('promptId')==3641 and r['promptParameters'][0]['name']=='CardId' and r['promptParameters'][0]['number']>4 for r in updates))
        return dict(case=kind,card=name,passed=True,checks=len(e.checks),evidence=str(e.ipc),trace=trace)
    except Exception as error:
        message=error.args[0] if isinstance(error,AssertionError) and error.args else error
        if isinstance(message,tuple):message=message[0]
        return dict(case=kind,card=name,passed=False,error=type(error).__name__+': '+str(message)[:1600],evidence=str(e.ipc),trace=trace)
    finally:e.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append')
    for key in ('native-worker','managed','fixture'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    from native_engine_test_client import NativeEngine
    factory=lambda *args,**kw:NativeEngine(*args,worker=a.native_worker,managed=a.managed,fixture=a.fixture,**kw)
    rows=[]
    for case in a.case or CASES:
        if case not in CASES:p.error('Unknown case '+case)
        result=run(case,factory);rows.append(result);print(json.dumps({k:v for k,v in result.items() if k!='trace'}),flush=True)
        a.output.write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),cases=rows,scope=__doc__),indent=2),encoding='utf8')
    raise SystemExit(0 if all(r['passed'] for r in rows) else 1)
