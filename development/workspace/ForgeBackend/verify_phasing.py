"""Real phasing keeps physical permanents, native identities, counters and attachments."""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

def updates(e):
    return [json.loads(v)['value'] for v in (e.native_folder/'native-model.jsonl').read_text().splitlines() if json.loads(v)['kind']=='native-update']

def run(a,bulk):
    e=None;trace=[];key='tokens-counters-equipment' if bulk else 'plain-permanents'
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,
            randomSeed=7274,fixtureHand=(["Raise the Alarm"] if bulk else [])+["Teferi's Protection"],
            fixtureLands=['Plains']*(5 if bulk else 3),fixtureBattlefield=['Grizzly Bears']+(['Lightning Greaves'] if bulk else []),
            fixtureCounters=[dict(seat=1,cardName='Grizzly Bears',occurrence=0,type='P1P1',count=2)] if bulk else [],
            fixtureBattlefieldReady=True,fixtureLibrary=['Plains']*20)
        bear=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears')
        def settle():
            for _ in range(20):
                if not e.state['stackOrder']:return
                execute(e,trace,'pass_priority')
            raise AssertionError('Actual phasing setup stack did not settle')
        if bulk:
            alarm=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Raise the Alarm');execute(e,trace,'cast_spell',alarm);settle()
            greaves=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Lightning Greaves')
            offer=next(v for v in e.state['legalActivations'] if v['forgeId']==greaves)
            execute(e,trace,'activate_ability',greaves,abilityId=offer['abilityId'],_target_policy=lambda d,s:[v for v in d['options'] if v['forgeId']==bear]);settle()
            e.check('Two actual tokens exist and original equipment is attached',sum(c.get('token',False) for c in e.state['battlefield'])==2 and next(c for c in e.state['battlefield'] if c['forgeId']==greaves)['attachedToForgeId']==bear)
        physical={c['forgeId'] for c in e.state['battlefield']};native_before=updates(e)[-1]
        identities={c['id'] for c in native_before['cards'] if c['zone']=='Battlefield'}
        counter_before={c['id']:c['counters'] for c in native_before['cards'] if c['id'] in identities}
        spell=next(c['forgeId'] for c in e.state['hand'] if c['name']=="Teferi's Protection");execute(e,trace,'cast_spell',spell);settle();phased=e.state
        e.check('Phasing preserves every actual physical battlefield identity',{c['forgeId'] for c in phased['battlefield']}==physical and all(c['phasedOut'] for c in phased['battlefield']))
        row=updates(e)[-1];native_out={c['id'] for c in row['cards'] if c['phasedOut']}
        e.check('Original native phased realm retains every same identity',native_out==identities and all(c['zone']=='PhasedOut' for c in row['cards'] if c['id'] in identities))
        e.check('Phased-out permanents provide no actions or mana',not phased['legalMana'] and not phased['legalActivations'] and not phased['legalCasts'])
        e.check('Counter values remain on the phased native entities',{c['id']:c['counters'] for c in row['cards'] if c['id'] in identities}==counter_before)
        for _ in range(80):
            if e.state['turn']>=3 and e.state['activeSeat']==1 and all(not c['phasedOut'] for c in e.state['battlefield']):break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Permanents did not return through the actual next untap')
        e.check('Actual next-turn return preserves physical identities and token count',{c['forgeId'] for c in e.state['battlefield']}==physical and sum(c.get('token',False) for c in e.state['battlefield'])==(2 if bulk else 0))
        after=updates(e)[-1]
        e.check('Original native entities return to battlefield without replacement',{c['id'] for c in after['cards'] if c['zone']=='Battlefield'}==identities and not any(c['phasedOut'] for c in after['cards'] if c['id'] in identities))
        rows=updates(e);events=[v for r in rows for v in r['phaseEvents']]
        e.check('Every permanent has one original phase-out and one phase-in event',len(events)==2*len(identities) and {v['id'] for v in events if v['to']=='PhasedOut'}==identities and {v['id'] for v in events if v['from']=='PhasedOut'}==identities)
        e.check('No phased permanent is falsely deleted by the native parser',not any(set(r['deletedCards'])&identities for r in rows))
        e.check('Counter values survive the actual return',{c['id']:c['counters'] for c in after['cards'] if c['id'] in identities}==counter_before)
        if bulk:
            e.check('The actual attachment and printed/granted abilities survive phasing',next(c for c in e.state['battlefield'] if c['forgeId']==greaves)['attachedToForgeId']==bear and {'Haste','Shroud'}<=set(next(c for c in e.state['battlefield'] if c['forgeId']==bear)['rulesKeywords']))
        e.check('No unsupported callback or unfinished stack remains',not e.state['fidelityGap'] and not e.state['stackOrder'])
        result=dict(passed=True,case=key,checks=e.checks,phasedState=phased,finalState=e.state,nativeIds=sorted(identities),phaseEvents=events,evidence=str(e.ipc))
    except Exception as error:result=dict(passed=False,case=key,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
    (a.output/(key+'.json')).write_text(json.dumps(result,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps({k:result.get(k) for k in ('case','passed','error','evidence')}),flush=True);return result['passed']

def targeted(a):
    e=None;trace=[];key='targeted-attachment'
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,
            fixtureHand=['Slip Out the Back'],fixtureLands=['Island']*3,
            fixtureBattlefield=['Grizzly Bears','Swiftfoot Boots'],fixtureBattlefieldReady=True,fixtureLibrary=['Island']*20)
        bear=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Grizzly Bears');boots=next(c['forgeId'] for c in e.state['battlefield'] if c['name']=='Swiftfoot Boots')
        physical={c['forgeId'] for c in e.state['battlefield']}
        def settle():
            for _ in range(20):
                if not e.state['stackOrder']:return
                execute(e,trace,'pass_priority')
            raise AssertionError('Actual targeted phasing stack did not settle')
        offer=next(v for v in e.state['legalActivations'] if v['forgeId']==boots)
        pick=lambda d,s:[v for v in d['options'] if v['forgeId']==bear]
        execute(e,trace,'activate_ability',boots,abilityId=offer['abilityId'],_target_policy=pick);settle()
        spell=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Slip Out the Back')
        execute(e,trace,'cast_spell',spell,_target_policy=pick);settle();out=e.state
        e.check('Targeted spell phases only its creature and indirectly attached original equipment',{c['forgeId'] for c in out['battlefield'] if c['phasedOut']}=={bear,boots} and {c['forgeId'] for c in out['battlefield']}==physical)
        e.check('Unphased real lands remain available as mana',bool(out['legalMana']) and all(not c['phasedOut'] for c in out['battlefield'] if c['name']=='Island'))
        native=updates(e)[-1];ids={1000+bear,1000+boots}
        e.check('Original native model phases only those same two identities',{c['id'] for c in native['cards'] if c['phasedOut']}==ids)
        for _ in range(80):
            if e.state['turn']>=3 and e.state['activeSeat']==1 and all(not c['phasedOut'] for c in e.state['battlefield']):break
            execute(e,trace,'pass_priority')
        else:raise AssertionError('Targeted and indirectly phased equipment did not return at actual untap')
        creature=next(c for c in e.state['battlefield'] if c['forgeId']==bear);equipment=next(c for c in e.state['battlefield'] if c['forgeId']==boots)
        e.check('The actual counter, attachment, haste and hexproof return together',creature['power']==3 and creature['toughness']==3 and equipment['attachedToForgeId']==bear and {'Haste','Hexproof'}<=set(creature['rulesKeywords']))
        rows=updates(e);events=[v for r in rows for v in r['phaseEvents']]
        e.check('No unrelated card receives a phase event or phased identity deletion',len(events)==4 and {v['id'] for v in events}==ids and not any(set(r['deletedCards'])&ids for r in rows))
        e.check('Actual final physical membership and completed rules remain intact',{c['forgeId'] for c in e.state['battlefield']}==physical and not e.state['fidelityGap'] and not e.state['stackOrder'])
        result=dict(passed=True,case=key,checks=e.checks,phasedState=out,finalState=e.state,phaseEvents=events,evidence=str(e.ipc))
    except Exception as error:result=dict(passed=False,case=key,error=repr(error),traceback=traceback.format_exc(),checks=e.checks if e else [],evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
    (a.output/(key+'.json')).write_text(json.dumps(result,indent=2));(a.output/(key+'-trace.json')).write_text(json.dumps(trace,indent=2));print(json.dumps({k:result.get(k) for k in ('case','passed','error','evidence')}),flush=True);return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('worker','managed','fixture','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--case',action='append',choices=['plain-permanents','tokens-counters-equipment','targeted-attachment'])
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);selected=set(a.case or ['plain-permanents','tokens-counters-equipment','targeted-attachment']);results=[]
    if 'plain-permanents' in selected:results.append(run(a,False))
    if 'tokens-counters-equipment' in selected:results.append(run(a,True))
    if 'targeted-attachment' in selected:results.append(targeted(a))
    raise SystemExit(0 if all(results) else 1)
