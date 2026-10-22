"""Read-only installed-game observations, including transient automatic passes.

This is observation of a delivered build, not an independent rules replay.
Rules expectations still come from the separate native-text proposal delta.
"""
import json
from pathlib import Path


def observed_pumps(ipc, specs):
    native_stats=[];mapping={}
    for line in (Path(ipc)/'native-wire.jsonl').read_text(encoding='utf8').splitlines():
        row=json.loads(line)
        if row['direction']!='incoming':continue
        state=row['message'].get('gameStateMessage',{})
        for annotation in state.get('annotations',[]):
            if 'AnnotationType_ObjectIdChanged' in annotation.get('type',[]):
                fields={d['key']:d for d in annotation['details']};old=fields['orig_id']['valueInt32'][0];new=fields['new_id']['valueInt32'][0]
                mapping[new]=mapping.get(old,old-1000 if 1000<old<10000 else None)
        for card in state.get('gameObjects',[]):
            identity=card['instanceId']
            if 1000<identity<10000:mapping[identity]=identity-1000
            if card.get('zoneId')==28 and 'power' in card and 'toughness' in card:
                native_stats.append(dict(forgeId=mapping.get(identity),power=card['power'].get('value',0),toughness=card['toughness'].get('value',0),nativeState=state.get('gameStateId',0)))
    pending={};confirmed=[]
    for index,line in enumerate((Path(ipc)/'engine-journal.jsonl').read_text(encoding='utf8').splitlines()):
        row=json.loads(line);state=row.get('response',{}).get('state')
        if state is None:continue
        actors={c['forgeId']:c for c in state['battlefield']};stacked={c['forgeId'] for c in state['stack']};grave={c['forgeId'] for c in state['graveyard']}
        for spell in state['stack']:
            name=spell['name'];targets=spell.get('targetForgeIds',[])
            if name not in specs or specs[name]['template']!='fixed-target-pump-v1' or spell['forgeId'] in pending or len(targets)!=1 or targets[0] not in actors:continue
            target=actors[targets[0]];delta=specs[name]['oracleDelta']
            pending[spell['forgeId']]=dict(name=name,forgeId=spell['forgeId'],owner=spell['owner'],target=targets[0],power=target['power']+delta['power'],toughness=target['toughness']+delta['toughness'],stackJournalLine=index+1,minNativeState=row.get('request',{}).get('nativeStateId',0))
        for identity,proof in pending.items():
            if proof.get('recorded') or identity in stacked or identity not in grave:continue
            actor=actors.get(proof['target'])
            if actor is None or (actor['power'],actor['toughness'])!=(proof['power'],proof['toughness']):continue
            matches=[v for v in native_stats if v['forgeId']==proof['target'] and (v['power'],v['toughness'])==(proof['power'],proof['toughness']) and v['nativeState']>=proof['minNativeState']]
            if matches:
                proof['recorded']=True;confirmed.append({**{k:v for k,v in proof.items() if k!='recorded'},'resolvedJournalLine':index+1,'nativeStatState':matches[0]['nativeState']})
    return confirmed


def observed_burns(ipc,specs):
    """A real direct-damage event plus its original native damage annotation."""
    ipc=Path(ipc);known={};states=[];mapping={};annotations=[]
    for line in (ipc/'engine-journal.jsonl').read_text(encoding='utf8').splitlines():
        state=json.loads(line).get('response',{}).get('state')
        if state is None:continue
        states.append(state)
        for zone in ('hand','battlefield','graveyard','exile','stack'):
            for card in state.get(zone,[]):known[card['forgeId']]=card
    for line in (ipc/'native-wire.jsonl').read_text(encoding='utf8').splitlines():
        row=json.loads(line)
        if row['direction']!='incoming':continue
        state=row['message'].get('gameStateMessage',{})
        for annotation in state.get('annotations',[]):
            if 'AnnotationType_ObjectIdChanged' in annotation.get('type',[]):
                fields={d['key']:d for d in annotation['details']};old=fields['orig_id']['valueInt32'][0];new=fields['new_id']['valueInt32'][0]
                mapping[new]=mapping.get(old,old-1000 if 1000<old<10000 else None)
            if 'AnnotationType_DamageDealt' in annotation.get('type',[]):annotations.append(annotation)
        for card in state.get('gameObjects',[]):
            if 1000<card['instanceId']<10000:mapping[card['instanceId']]=card['instanceId']-1000
    confirmed=[]
    for event in states[-1]['events'] if states else []:
        source=known.get(event.get('sourceForgeId'),{});spec=specs.get(source.get('name'),{})
        if event['kind']!='damage' or spec.get('template')!='fixed-creature-damage-v1' or event.get('combat') is not False or event.get('amount')!=spec['damage']:continue
        native=[a for a in annotations if mapping.get(a.get('affectorId'))==source['forgeId'] and any(mapping.get(i)==event.get('targetForgeId') for i in a.get('affectedIds',[])) and any(d['key']=='damage' and d.get('valueInt32')==[spec['damage']] for d in a.get('details',[]))]
        if native:confirmed.append(dict(name=source['name'],owner=source['owner'],forgeId=source['forgeId'],target=event['targetForgeId'],amount=event['amount'],eventId=event['id']))
    return confirmed
