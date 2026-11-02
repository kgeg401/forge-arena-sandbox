"""Private disposable artwork-cache checks; no game or native image loading."""
import hashlib,json,os,shutil,tempfile
from pathlib import Path
from unittest.mock import patch
from paper_art import art_url,prepare_paper_art

root=Path(tempfile.mkdtemp(prefix='forge-paper-art-',dir=os.environ.get('FORGE_ARENA_TEST_OUTPUT')))
app=root/'app';lab=root/'lab';(app/'ForgeBackend').mkdir(parents=True);lab.mkdir()
content=b'authored download fixture; image decoding is a separate native check'
row=dict(grpId=2000010,name='Darien, King of Kjeldor',artist='Michael Phillippi',url='https://cards.scryfall.io/art_crop/front/a/b/test.jpg',sha256=hashlib.sha256(content).hexdigest(),bytes=len(content))
source=dict(schema=1,cards=[row],credit='test')
(app/'paper-art.json').write_text(json.dumps(source))
(app/'ForgeBackend/experimental-admission.json').write_text(json.dumps(dict(cards={row['name']:dict(grpId=row['grpId'],paperOnly=True)})))
cache=lab/'paper-art';cache.mkdir();(cache/'2000010.jpg').write_bytes(content)
checks=[]
def check(label,condition):
    assert condition,label
    checks.append(label)
def rejected(label,fn):
    try:fn()
    except ValueError:checks.append(label)
    else:raise AssertionError(label)
with patch('paper_art.urllib.request.build_opener') as opener:
    opener.return_value.open.side_effect=AssertionError('Cached art must work offline')
    result=prepare_paper_art(app,lab)
check('Valid cached images work without any network request',result['available']==result['expected']==1)
index=json.loads((cache/'index.json').read_text())
check('Cache retains exact identity, artist and digest',index['cards']==[row])
token=dict(row,grpId=2000084,name='token:g_0_0_hydra')
inventory=dict(cards={row['name']:dict(grpId=row['grpId'],paperOnly=True)},humanChoices=dict(presentationObjects={token['name']:dict(grpId=token['grpId'],paperOnly=True,token=True,admitted=False)}))
(app/'ForgeBackend/experimental-admission.json').write_text(json.dumps(inventory))
(app/'paper-art.json').write_text(json.dumps(dict(source,cards=[row,token])))
(cache/'2000084.jpg').write_bytes(content)
with patch('paper_art.urllib.request.build_opener') as opener:
    opener.return_value.open.side_effect=AssertionError('Cached paper token must work offline')
    result=prepare_paper_art(app,lab)
check('Explicit paper tokens are cached alongside admitted primary cards',result['available']==result['expected']==2)
(app/'ForgeBackend/experimental-admission.json').write_text(json.dumps(dict(cards={row['name']:dict(grpId=row['grpId'],paperOnly=True)})))
(app/'paper-art.json').write_text(json.dumps(source))
for url in ('http://cards.scryfall.io/art_crop/test.jpg','https://evil.example/art_crop/test.jpg','https://cards.scryfall.io/normal/test.jpg','https://user@cards.scryfall.io/art_crop/test.jpg'):
    rejected('Reject unexpected source '+url,lambda value=url:art_url(value))
bad=dict(source,cards=[dict(row,name='Wrong card')]);(app/'paper-art.json').write_text(json.dumps(bad))
rejected('Wrong named-card mapping never reaches the downloader',lambda:prepare_paper_art(app,lab))
(app/'paper-art.json').write_text(json.dumps(source));(cache/'2000010.jpg').unlink()
with patch('paper_art.urllib.request.build_opener') as opener:
    opener.return_value.open.side_effect=OSError('offline fixture')
    result=prepare_paper_art(app,lab,lambda message:None)
check('Offline first run reports missing art without blocking gameplay',result['available']==0 and result['warning']=='offline fixture')
check('Missing images are excluded from the native index',json.loads((cache/'index.json').read_text())['cards']==[])
with patch('paper_art.urllib.request.build_opener') as opener:
    opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'wrong image'
    rejected('Wrong downloaded bytes fail before cache activation',lambda:prepare_paper_art(app,lab))
check('Bad download does not become live artwork',not (cache/'2000010.jpg').exists())
print(json.dumps(dict(passed=True,checks=checks,total=len(checks),evidence=str(root)),indent=2))
