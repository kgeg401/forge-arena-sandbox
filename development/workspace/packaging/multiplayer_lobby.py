"""Connection choices from the native client's owned menu."""
import time
from client_service import read,atomic


def validate_choice(choice):
    if not isinstance(choice,dict) or choice.get('mode') not in ('host','join'):raise ValueError('Choose Host or Join in the client')
    expected={'mode'} if choice['mode']=='host' else {'mode','invitation'}
    if set(choice)!=expected:raise ValueError('Unexpected private-room choice fields')
    if choice['mode']=='join':
        value=choice['invitation']
        if not isinstance(value,str) or not 1<=len(value)<=2048 or value!=value.strip():raise ValueError('Copy a complete private invitation before joining')


def lobby(ipc,deck,run,*,context=None):
    atomic(ipc/'network-status.json',dict(message='Host a private room or join a copied invitation.',lobbyPhase='choose',deckName=deck,**(context or {})))
    while not (ipc/'stop.request').exists():
        try:choice=read(ipc/'network-choice.json')
        except (FileNotFoundError,PermissionError):time.sleep(.1);continue
        validate_choice(choice)
        run(choice)
        return
