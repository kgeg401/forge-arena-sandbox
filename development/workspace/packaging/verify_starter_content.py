"""Exercise actual shared starter payload, safe merging, retry and once-only grants."""
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import uuid
import starter_content as starter

checks=[]
def check(label,ok):
    assert ok,label
    checks.append(label)

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf8')

def read(path):return json.loads(path.read_text(encoding='utf8'))

def main():
    payload=read(Path(__file__).with_name('starter-content.json'))
    with tempfile.TemporaryDirectory(prefix='forge-starters-') as folder:
        root=Path(folder);app=root/'app';lab=root/'lab';profile=lab/'local-profile'
        write(app/'starter-content.json',payload)
        ids=set(payload['cards'])|{key for d in payload['decks'] for p in starter.PILES for key in d[p]}
        write(lab/'deck-catalog.json',dict(cards=[dict(grpId=int(key)) for key in ids]))
        result=starter.seed_profile(app,lab);decks=read(profile/'decks.json');packs=read(profile/'packs.json')
        check('Fresh profile gets every actual saved deck',result['decksAdded']==len(payload['decks']) and len(decks['decks'])==len(payload['decks']))
        for expected,actual in zip(payload['decks'],decks['decks']):
            check('Exact printing counts and all piles: '+expected['name'],all(actual[k]==expected[k] for k in ('name','format',*starter.PILES)))
        check('Fresh collection exactly matches shared snapshot',packs['cards']==payload['cards'])
        check('Fresh starter grant records exact separately auditable quantities',packs['starterGrants']=={payload['id']:payload['cards']})
        check('No opening history or identity copied',packs['openings']==[] and packs['packs']=={} and str(uuid.UUID(packs['profileId']))==packs['profileId'])
        check('Starter deck IDs are distinct',len({d['id'] for d in decks['decks']})==len(decks['decks']))
        before={p.name:p.read_bytes() for p in profile.iterdir()}
        starter.seed_profile(app,lab)
        check('Second launch is byte-identical and grants nothing',before=={p.name:p.read_bytes() for p in profile.iterdir()})
        key=next(iter(packs['cards']));packs['cards'][key]=0;write(profile/'packs.json',packs)
        starter.seed_profile(app,lab)
        check('Once-only receipt prevents regrant after collection changes',read(profile/'packs.json')['cards'][key]==0)
        mine=copy.deepcopy(decks['decks'][0]);mine['name']=mine['name'].upper();mine['main']={key:1};mine['favorite']=True
        original_decks=dict(schema=1,revision=7,decks=[mine]);original_packs=dict(schema=1,revision=9,profileId='my-own-id',packs={'10':73},cards={key:9999},openings=[{'id':'my-original-opening'}])
        write(profile/'decks.json',original_decks);write(profile/'packs.json',original_packs)
        starter.seed_profile(app,lab);merged_decks=read(profile/'decks.json');merged_packs=read(profile/'packs.json')
        check('Same-name edited deck is preserved including favorite and exact ID',merged_decks['decks'][0]==mine and len(merged_decks['decks'])==len(payload['decks']))
        check('Higher collection counts are retained',merged_packs['cards'][key]==9999)
        check('Grant records only the missing quantities',key not in merged_packs['starterGrants'][payload['id']] and sum(merged_packs['starterGrants'][payload['id']].values())==sum(v for k,v in payload['cards'].items() if k!=key))
        check('Own identity, unopened packs and history are retained',all(merged_packs[k]==original_packs[k] for k in ('profileId','packs','openings')))
        check('Prior profile files backed up',read(profile/'decks.json.bak')==original_decks and read(profile/'packs.json.bak')==original_packs)
        good={p:p.read_bytes() for p in (profile/'decks.json',profile/'packs.json')}
        for label,change in [
            ('unknown printing',lambda x:x['decks'][0]['main'].update({'4294967295':1})),
            ('negative collection',lambda x:x['cards'].update({key:-1})),
            ('boolean count',lambda x:x['cards'].update({key:True})),
            ('duplicate deck key',lambda x:x['decks'].append(copy.deepcopy(x['decks'][0]))),
            ('oversized deck',lambda x:x['decks'][0]['main'].update({key:999,next(k for k in ids if k!=key):999})),
        ]:
            bad=copy.deepcopy(payload);change(bad);write(app/'starter-content.json',bad)
            try:starter.seed_profile(app,lab)
            except ValueError:pass
            else:raise AssertionError(label)
            check(label+' rejected without profile writes',all(p.read_bytes()==b for p,b in good.items()))
        write(app/'starter-content.json',payload)
        write(profile/'decks.json',original_decks);(profile/'packs.json').write_text('{broken')
        try:starter.seed_profile(app,lab)
        except ValueError:pass
        else:raise AssertionError('Malformed collection accepted')
        check('Malformed collection cannot partly modify decks',read(profile/'decks.json')==original_decks and (profile/'packs.json').read_text()=='{broken')
        write(profile/'packs.json',original_packs)
        real_commit=starter.commit
        def fail_second(path,state):
            if path.name=='packs.json':raise OSError('simulated second-file I/O failure')
            real_commit(path,state)
        with patch.object(starter,'commit',side_effect=fail_second):
            try:starter.seed_profile(app,lab)
            except OSError:pass
            else:raise AssertionError('I/O failure not surfaced')
        partial=(profile/'decks.json').read_bytes();starter.seed_profile(app,lab)
        check('Partial write retries without duplicate decks',(profile/'decks.json').read_bytes()==partial and len(read(profile/'decks.json')['decks'])==len(payload['decks']))
        check('Partial write retries complete collection grant',all(read(profile/'packs.json')['cards'][k]>=v for k,v in payload['cards'].items()))
        pending=profile/'unowned.json.starter-pending';pending.write_text('retain previous incomplete write')
        try:starter.commit(profile/'unowned.json',{})
        except FileExistsError:pass
        else:raise AssertionError('Existing pending file overwritten')
        check('Existing pending file is preserved',pending.read_text()=='retain previous incomplete write')
    print(json.dumps(dict(checks=len(checks),passed=checks,decks=len(payload['decks']),collectionEntries=len(payload['cards']),scope='Actual packaged payload and disposable filesystem profiles; native class acceptance is separate'),indent=2))

if __name__=='__main__':main()
