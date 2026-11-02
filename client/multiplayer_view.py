"""Translate stable two-player rules seats to Arena's local-seat-one view.

Card, ability, choice and stack identities remain unchanged in both directions.
This is a projection only: it grants no additional card visibility or actions.
"""
import copy

SEATS={'seat','viewerSeat','inputSeat','owner','controller','activeSeat','prioritySeat','startingSeat','winnerSeat','targetSeat','sourceSeat','ownerSeat','protectorSeat','attackingSeat','nearestLeft','privateToSeat','fromSeat','toSeat'}
PRIVATE={'localDeck','opponentDeck','randomSeed','researchControls','researchTrace'}


def translate(value,player):
    if type(player) is not int or player not in (1,2):raise ValueError('Only two-player rooms are implemented')
    def seat(value):
        if type(value) is not int or value not in (0,1,2):raise ValueError('Unmapped player identity')
        return 3-value if player==2 and value else value
    def walk(value):
        if isinstance(value,list):return [walk(item) for item in value]
        if not isinstance(value,dict):return copy.deepcopy(value)
        result={}
        for key,item in value.items():
            if key in SEATS:result[key]=seat(item)
            elif key=='targetSeats':
                if not isinstance(item,list):raise ValueError('Invalid target player list')
                result[key]=[seat(target) for target in item]
            elif key.endswith(('Seat','Seats')):raise ValueError('Unknown player reference: '+key)
            else:result[key]=walk(item)
        return result
    return walk(value)


def project_view(view,player):
    if not isinstance(view,dict) or view.get('viewerSeat')!=player or view.get('playerCount')!=2:raise ValueError('Not this player\'s two-player view')
    if set(view)&PRIVATE:raise ValueError('Private diagnostic metadata cannot be projected')
    decision=view.get('decision')
    if decision is not None and decision.get('seat')!=player:raise ValueError('Another player owns this decision')
    result=translate(view,player)
    if isinstance(result.get('players'),list):result['players'].sort(key=lambda item:item['seat'])
    return result


def restore_action(action,player):
    # The native IPC always calls itself seat one. The coordinator authenticates
    # the remote player separately; never accept an asserted actor in its action.
    if not isinstance(action,dict) or 'seat' in action:raise ValueError('Gameplay action cannot select its actor')
    return translate(action,player)
