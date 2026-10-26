"""Unsupported additional payments must fail before any payment or movement."""
import argparse
import copy
import json
import os
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','policy','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();os.environ.update(FORGE_ARENA_CONFIG=str(a.config),FORGE_ARENA_POLICY=str(a.policy))
    from engine_test_client import Engine
    a.output.mkdir(parents=True,exist_ok=False)
    e=Engine('card-family',randomSeed=7274,fixtureHand=["Altar's Reap",'Divination','Forest'],fixtureLands=['Swamp']*2+['Island']*3,fixtureBattlefield=['Grizzly Bears'])
    try:
        before=copy.deepcopy(e.state);identity=next(c['forgeId'] for c in before['hand'] if c['name']=="Altar's Reap")
        e.check('Forge considers the source payable before the bridge payment guard',identity in e.state['legalCasts'])
        reply=e.send('cast_spell',identity)
        e.check('Unsupported sacrifice payment produces an explicit refusal before payment',not reply['accepted'] and 'Unmapped human payment choice: CostSacrifice' in e.state['fidelityGap'])
        keys=('hand','battlefield','stack','graveyard','hidden','mana','manaTotal','life','opponentLife')
        e.check('Refused extra payment changes no resources, objects or zones',all(e.state[k]==before[k] for k in keys))
        blocked_state=copy.deepcopy(e.state)
        for op,target in [('pass_priority',0),('cast_spell',next(c['forgeId'] for c in before['hand'] if c['name']=='Divination')),('activate_mana',before['battlefield'][0]['forgeId']),('play_land',next(c['forgeId'] for c in before['hand'] if c['name']=='Forest'))]:
            reply=e.send(op,target);e.check('Unresolved payment gap blocks further gameplay: '+op,not reply['accepted'] and e.state==blocked_state)
        e.check('Snapshot remains available to inspect the exact unresolved state',e.send('snapshot')['accepted'] and e.state==blocked_state)
        e.check('Concession remains available without choosing the unsupported payment',e.send('concede')['accepted'] and e.state['gameOver'])
        result=dict(passed=True,checks=e.checks,evidence=str(e.ipc),scope=__doc__)
        (a.output/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(passed=True,checks=len(e.checks),evidence=str(e.ipc))))
    finally:e.close()


if __name__=='__main__':main()
