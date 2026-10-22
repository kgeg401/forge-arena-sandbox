"""Own empty protocol scaffold. Rules state always comes from live Forge."""
def board_template():
    players=[dict(lifeTotal=20,systemSeatNumber=seat,status='PlayerStatus_InGame',maxHandSize=7,teamId=seat,
                  controllerSeatId=seat,controllerType='ControllerType_Player',startingLifeTotal=20) for seat in (1,2)]
    zones=[]
    def zone(id,kind,visibility='Public',owner=None):
        z=dict(zoneId=id,type='ZoneType_'+kind,visibility='Visibility_'+visibility,objectInstanceIds=[])
        if owner:z['ownerSeatId']=owner
        if visibility=='Private':z['viewers']=[owner]
        zones.append(z)
    zone(18,'Revealed',owner=1);zone(19,'Revealed',owner=2)
    for id,kind in enumerate(('Suppressed','Pending','Command','Stack','Battlefield','Exile','Limbo'),24):zone(id,kind)
    for seat,first in ((1,31),(2,35)):
        for offset,kind,visibility in ((0,'Hand','Private'),(1,'Library','Hidden'),(2,'Graveyard','Public'),(3,'Sideboard','Private')):zone(first+offset,kind,visibility,seat)
    state=dict(type='GameStateType_Full',gameStateId=1,pendingMessageCount=1,gameObjects=[],zones=zones,players=players,
        teams=[dict(id=seat,playerIds=[seat],status='TeamStatus_InGame') for seat in (1,2)],
        gameInfo=dict(matchID='sandbox-template',gameNumber=1,stage='GameStage_Play',type='GameType_Duel',variant='GameVariant_Normal',
                      matchState='MatchState_GameInProgress',matchWinCondition='MatchWinCondition_SingleElimination',superFormat='SuperFormat_Constructed',mulliganType='MulliganType_London'),
        turnInfo=dict(activePlayer=1,priorityPlayer=1,decisionPlayer=1,phase='Phase_Main1',turnNumber=1),update='GameStateUpdate_SendAndRecord')
    return dict(provenance=dict(kind='Authored empty protocol scaffold, not a captured game or rules result'),
                messages=[dict(type='GREMessageType_GameStateMessage',systemSeatIds=[1],msgId=1,gameStateId=1,gameStateMessage=state)])
