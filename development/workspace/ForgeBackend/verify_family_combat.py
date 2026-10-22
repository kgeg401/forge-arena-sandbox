"""New creature identities exercise Forge combat and free damage allocation."""
import json
from engine_test_client import Engine
from runtime_paths import ROOT

reports=[]
cases=[('Fusion Elemental',['Dune Beetle','Grizzly Bears'],False),
       ('Gigantosaurus',['Fire Elemental','Coral Merfolk'],False),
       ('Bastion Enforcer',['Aegis Turtle','Grizzly Bears'],True),
       ('Stone Golem',['Dune Beetle','Coral Merfolk'],True),
       ('Grizzly Bears',['Aegis Turtle','Walking Corpse'],True)]
for attacker_name,block_names,spare_first in cases:
    e=Engine('attack-double-blocked',fixtureAttacker=attacker_name,fixtureBlockers=block_names)
    try:
        source=next(c for c in e.state['battlefield'] if c['owner']==1)
        blockers=[next(c for c in e.state['battlefield'] if c['name']==name and c['owner']==2) for name in block_names]
        for _ in range(20):
            d=e.state.get('decision')
            if d and d['kind']=='assign_damage':break
            if d:
                e.check('Research source uses the actual attacker declaration',d['kind']=='attackers')
                r=e.send('select_attackers',decisionToken=d['token'],assignments=[dict(forgeId=source['forgeId'],targetSeat=2)]);e.check('Attack selected '+attacker_name,r['accepted'])
                r=e.send('submit_attackers',decisionToken=d['token']);e.check('Attack submitted '+attacker_name,r['accepted'])
            else:e.pass_or_decision()
        d=e.state['decision'];e.check('New identities reach generic multi-block damage',d['kind']=='assign_damage' and len(d['options'])==2)
        power=source['power'];first=0 if spare_first else min(power,blockers[0]['toughness']);amounts=[first,power-first]
        r=e.send('submit_assign_damage',decisionToken=d['token'],assignments=[dict(forgeId=c['forgeId'],amount=n) for c,n in zip(blockers,amounts)])
        e.check('Actual Forge accepts free-distribution damage',r['accepted'])
        for _ in range(6):
            if any(v['kind']=='damage' for v in e.state['events']):break
            e.pass_or_decision()
        for c,amount in zip(blockers,amounts):
            dead=any(v['forgeId']==c['forgeId'] for v in e.state['graveyard'])
            e.check('Blocker survival follows submitted damage '+c['name'],dead==(amount>=c['toughness']))
            if not dead:e.check('Correct marked damage '+c['name'],next(v for v in e.state['battlefield'] if v['forgeId']==c['forgeId'])['damage']==amount)
        e.check('Attacker survival follows real blocker power',any(v['forgeId']==source['forgeId'] for v in e.state['graveyard'])==(sum(c['power'] for c in blockers)>=source['toughness']))
        e.check('No player damage from a blocked plain creature',e.state['life']==20 and e.state['opponentLife']==20)
        e.check('No fidelity gap in generic combat',not e.state['fidelityGap'])
        reports.append(dict(attacker=attacker_name,blockers=block_names,checks=len(e.checks),evidence=str(e.ipc)));print(json.dumps(reports[-1]),flush=True)
    finally:e.close()
target=ROOT/'research/plain-family-checks/combat-report.json';target.write_text(json.dumps(dict(checks=sum(r['checks'] for r in reports),cases=reports),indent=2))
print(json.dumps(dict(checks=sum(r['checks'] for r in reports),report=str(target)),indent=2))
