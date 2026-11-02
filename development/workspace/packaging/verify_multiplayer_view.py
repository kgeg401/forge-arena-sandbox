"""Projection fixtures, not rendered player-two acceptance."""
import copy,json
from multiplayer_view import project_view,restore_action,translate

checks=[]
def check(label,ok):assert ok,label;checks.append(label)
def rejects(label,call):
    try:call()
    except ValueError:checks.append(label)
    else:raise AssertionError(label)

view=dict(viewerSeat=2,playerCount=2,inputSeat=2,activeSeat=1,prioritySeat=2,startingSeat=2,winnerSeat=0,life=37,opponentLife=40,
          players=[dict(seat=1,name='Host'),dict(seat=2,name='Guest')],
          hand=[dict(forgeId=42,owner=2,controller=2,name='Island')],hidden=[dict(forgeId=43,owner=1,controller=1,zone='Hand')],
          stackAbilities=[dict(forgeId=-3,owner=2,controller=2,targetSeats=[1],targetForgeIds=[44])],
          events=[dict(targetSeat=2,amount=3,id=7)],
          decision=dict(seat=2,token='unchanged',kind='targets',options=[dict(forgeId=-1000001,targetKind='player',targetSeat=1),dict(forgeId=44,privateToSeat=2)]))
before=copy.deepcopy(view);native=project_view(view,2)
check('Guest becomes native local player without altering source',native['viewerSeat']==1 and view==before)
check('Personal life values do not swap twice',native['life']==37 and native['opponentLife']==40)
check('Turn and priority identities follow guest perspective',native['activeSeat']==2 and native['prioritySeat']==1 and native['startingSeat']==1 and native['winnerSeat']==0)
check('Known hand remains local and opposing cards remain hidden',native['hand'][0]['owner']==1 and native['hidden'][0]['owner']==2 and 'name' not in native['hidden'][0])
check('Players keep identity while presentation order starts local',native['players']==[dict(seat=1,name='Guest'),dict(seat=2,name='Host')])
check('Targets and private chooser visibility move with their player',native['decision']['options'][0]['targetSeat']==2 and native['decision']['options'][1]['privateToSeat']==1)
check('Stable card, player-target and stack IDs remain rules identities',native['hand'][0]['forgeId']==42 and native['stackAbilities'][0]['forgeId']==-3 and native['decision']['options'][0]['forgeId']==-1000001)
check('Event and stack target players use same perspective',native['events'][0]['targetSeat']==1 and native['stackAbilities'][0]['targetSeats']==[2])
action=dict(op='select_attackers',assignments=[dict(forgeId=42,targetSeat=2,targetForgeId=0)])
check('Guest native attack targets restore to actual host',restore_action(action,2)['assignments'][0]==dict(forgeId=42,targetSeat=1,targetForgeId=0))
check('Player-target identities do not get interpreted as card IDs',restore_action(dict(op='select_targets',assignments=[dict(forgeId=-1000001,selected=True)]),2)['assignments'][0]['forgeId']==-1000001)
check('Host presentation does not swap identities',translate(view,1)==view)
check('All seat translations are reversible',translate(translate(view,2),2)==view)
rejects('Cannot project a different player private view',lambda:project_view(view,1))
rejects('Cannot project unreleased deck metadata',lambda:project_view({**view,'opponentDeck':{'name':'secret'}},2))
rejects('Cannot present another player private chooser',lambda:project_view({**view,'decision':dict(seat=1)},2))
rejects('Unknown future seat fields fail closed',lambda:translate(dict(newTargetSeat=2),2))
rejects('Larger pods are not silently treated as a duel',lambda:project_view({**view,'playerCount':4},2))
rejects('Native action cannot choose its authenticated role',lambda:restore_action(dict(op='concede',seat=1),2))
print(json.dumps(dict(passed=True,checks=len(checks),results=checks,scope=__doc__),indent=2))
