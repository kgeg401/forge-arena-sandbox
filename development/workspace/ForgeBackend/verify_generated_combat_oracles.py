"""Literal combat boundary examples for the independent generated oracle."""
import json
from prepare_generated_combat_batches import blocking_oracle


def run():
    # Values are explicit outcomes for one vanilla attacking 4/4, including
    # cases that distinguish first strike, simultaneous damage and two strikes.
    cases=[
        ('plain 2/2 dies and leaves two damage',2,2,[],dict(localDead=True,opponentDead=False,localDamage=4,opponentDamage=2,lifeGain=0)),
        ('one deathtouch damage kills the 4/4',1,1,['Deathtouch'],dict(localDead=True,opponentDead=True,localDamage=4,opponentDamage=1,lifeGain=0)),
        ('zero deathtouch damage is not lethal',0,5,['Deathtouch'],dict(localDead=False,opponentDead=False,localDamage=4,opponentDamage=0,lifeGain=0)),
        ('first strike kills before receiving damage',4,1,['First Strike'],dict(localDead=False,opponentDead=True,localDamage=0,opponentDamage=4,lifeGain=0)),
        ('small first striker dies in the regular step',1,1,['First Strike'],dict(localDead=True,opponentDead=False,localDamage=4,opponentDamage=1,lifeGain=0)),
        ('double striker dies simultaneously on its second hit',2,2,['Double Strike'],dict(localDead=True,opponentDead=True,localDamage=4,opponentDamage=4,lifeGain=0)),
        ('a first-hit kill prevents an extra lifelink hit',4,1,['Double Strike','Lifelink'],dict(localDead=False,opponentDead=True,localDamage=0,opponentDamage=4,lifeGain=4)),
        ('surviving double striker gains life twice',1,5,['Double Strike','Lifelink'],dict(localDead=False,opponentDead=False,localDamage=4,opponentDamage=2,lifeGain=2)),
        ('deathtouch first strike prevents retaliation',1,1,['First Strike','Deathtouch'],dict(localDead=False,opponentDead=True,localDamage=0,opponentDamage=1,lifeGain=0)),
        ('blocking trample does not redirect damage to a player',3,3,['Trample','Lifelink'],dict(localDead=True,opponentDead=False,localDamage=4,opponentDamage=3,lifeGain=3)),
        ('a zero-power blocker still receives damage',0,8,[],dict(localDead=False,opponentDead=False,localDamage=4,opponentDamage=0,lifeGain=0)),
    ]
    for label,power,toughness,keywords,expected in cases:
        actual=blocking_oracle(power,toughness,keywords)
        if actual!=expected:raise AssertionError((label,expected,actual))
    print(json.dumps(dict(checks=len(cases),passed=[c[0] for c in cases]),indent=2))


if __name__=='__main__':run()
