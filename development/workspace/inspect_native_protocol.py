"""Extract small protocol examples from the existing local observer recording."""
import json
from pathlib import Path
p=Path(r'D:\GAMES\CodexAssets\ArenaObserver\sessions\20261017-122858-822080\events.jsonl')
out={}
for line in p.open(encoding='utf-8'):
    e=json.loads(line); payload=e.get('payload',{})
    for message in payload.get('greToClientEvent',{}).get('greToClientMessages',[]):
        state=message.get('gameStateMessage',{})
        for c in state.get('gameObjects',[]):
            if c.get('visibility')=='Visibility_Hidden' and 'hidden' not in out:out['hidden']=c
        info=state.get('gameInfo',{})
        if info.get('stage')=='GameStage_GameOver' and 'gameOver' not in out:out['gameOver']=message
        for a in state.get('annotations',[]):
            if any(k.get('key')=='category' and any(v in ['Draw','Discard'] for v in k.get('valueString',[])) for k in a.get('details',[])):
                out.setdefault('zoneCategories',[])
                if len(out['zoneCategories'])<3:out['zoneCategories'].append(a)
target=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\research\combat-protocol\hidden-and-terminal.json')
target.write_text(json.dumps(out,indent=2));print(target);print(json.dumps(out,indent=2)[:16000])
