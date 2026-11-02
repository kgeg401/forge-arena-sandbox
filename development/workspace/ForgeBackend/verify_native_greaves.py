"""Native-handler regression for Lightning Greaves grants and attachment lifetime.

Only the initial zones are fixtures; Forge pays, targets, equips and destroys.
The persistent worker checks the native keyword IDs and attachment graph.
"""
import argparse,json,traceback
from pathlib import Path
from native_engine_test_client import NativeEngine
from native_test_policy import execute

def main(a):
    e=None;trace=[];report={};target=None;reject_shrouded=None
    def targets(d,s):
        if reject_shrouded is not None:
            e.check('Shroud excludes its wearer from our targeted spell',all(o['forgeId']!=reject_shrouded for o in d['options']),d['options'])
        return [next(o for o in d['options'] if o['forgeId']==target)]
    def act(op,id=0,**fields):execute(e,trace,op,id,_target_policy=targets,**fields)
    def settle():
        for _ in range(24):
            if not e.state['stackOrder']:return
            act('pass_priority')
        raise AssertionError('Equip/spell stack did not settle')
    def find(zone,name):return next(c for c in e.state[zone] if c['name']==name)
    def grants(c):return {g['keyword'].lower() for g in c.get('keywordGrants',[])}
    try:
        e=NativeEngine('card-family',worker=a.worker,managed=a.managed,fixture=a.fixture,randomSeed=7274,
            fixtureHand=['Lightning Greaves','Unsummon','Wrath of God'],fixtureLands=['Plains']*6+['Island']*3,
            fixtureBattlefield=["Yusri, Fortune's Flame",'Savannah Lions','Grizzly Bears'],fixtureBattlefieldReady=True,
            fixtureLibrary=['Island']*15)
        ids={c['name']:c['forgeId'] for z in ['hand','battlefield'] for c in e.state[z]}
        act('cast_spell',ids['Lightning Greaves']);settle()
        e.check('Greaves resolves unattached',not find('battlefield','Lightning Greaves').get('attachedToForgeId'))
        for wearer,previous in [("Yusri, Fortune's Flame",None),('Savannah Lions',"Yusri, Fortune's Flame")]:
            target=ids[wearer];offer=next(v for v in e.state['legalActivations'] if v['forgeId']==ids['Lightning Greaves'])
            tapped_before=[c['forgeId'] for c in e.state['battlefield'] if c['tapped']]
            act('activate_ability',ids['Lightning Greaves'],abilityId=offer['abilityId']);settle()
            e.check('Greaves attaches to the chosen wearer',find('battlefield','Lightning Greaves').get('attachedToForgeId')==target)
            e.check('Wearer receives Haste and Shroud from Greaves',grants(find('battlefield',wearer))=={'haste','shroud'})
            e.check('Zero-cost equip consumes no mana sources',[c['forgeId'] for c in e.state['battlefield'] if c['tapped']]==tapped_before)
            if previous:e.check('Moving Greaves removes both grants from its former wearer',not grants(find('battlefield',previous)))
            if previous is None:
                reject_shrouded=target;target=ids['Grizzly Bears'];act('cast_spell',ids['Unsummon']);settle();reject_shrouded=None
        target=None;act('cast_spell',ids['Wrath of God']);settle()
        e.check('Nontargeting removal still destroys the shrouded wearer',any(c['forgeId']==ids['Savannah Lions'] for c in e.state['graveyard']))
        e.check('Greaves survives detached after its wearer dies',not find('battlefield','Lightning Greaves').get('attachedToForgeId'))
        e.check('Departed wearers retain no Greaves grants',all(not grants(c) for c in e.state['graveyard']))
        e.check('No pending choice or fidelity gap remains',not e.state.get('decision') and not e.state['fidelityGap'])
        report=dict(passed=True,checks=e.checks,evidence=str(e.ipc),scope=__doc__)
    except BaseException as error:report=dict(passed=False,error=repr(error),traceback=traceback.format_exc(),evidence=str(e.ipc) if e else None)
    finally:
        if e:e.close()
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2));a.output.with_suffix('.trace.json').write_text(json.dumps(trace,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['traceback','checks','scope']}),flush=True)
    return report['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['worker','managed','fixture','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();assert not a.output.exists();raise SystemExit(0 if main(a) else 1)
