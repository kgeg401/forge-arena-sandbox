"""Cache pinned paper-card illustrations outside the isolated game and release."""
import hashlib,json,os,urllib.parse,urllib.request
from pathlib import Path


def art_url(url):
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='cards.scryfall.io' or parsed.port not in (None,443) or parsed.username or parsed.password or not parsed.path.startswith('/art_crop/'):
        raise ValueError('Unexpected paper artwork URL')
    return url


class ArtRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        return super().redirect_request(request,fp,code,msg,headers,art_url(newurl))


def prepare_paper_art(app,lab,progress=print):
    app=Path(app);lab=Path(lab);path=app/'paper-art.json'
    if not path.is_file():return dict(expected=0,available=0)
    source=json.loads(path.read_text(encoding='utf-8-sig'))
    if source.get('schema')!=1:raise ValueError('Unknown paper artwork schema')
    experimental=json.loads((app/'ForgeBackend/experimental-admission.json').read_text(encoding='utf-8-sig'))
    inventory=dict(experimental['cards'])
    inventory.update(experimental.get('humanChoices',{}).get('presentationObjects',{}))
    expected={c['grpId']:name for name,c in inventory.items() if c.get('paperOnly')}
    rows=source['cards']
    if len(rows)!=len(expected) or {r['grpId']:r['name'] for r in rows}!=expected:raise ValueError('Paper artwork differs from admitted card identities')
    for row in rows:
        art_url(row['url'])
        if not isinstance(row['sha256'],str) or len(row['sha256'])!=64 or any(c not in '0123456789abcdef' for c in row['sha256']):raise ValueError('Invalid artwork digest')
        if type(row['bytes']) is not int or not 1<=row['bytes']<=4*1024*1024:raise ValueError('Invalid artwork size')
    cache=lab/'paper-art';cache.mkdir(exist_ok=True)
    from tester_common import no_links
    no_links(cache)
    available=0;failure=None;opener=urllib.request.build_opener(ArtRedirect)
    for row in rows:
        target=cache/(str(row['grpId'])+'.jpg');no_links(target)
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']:
            available+=1;continue
        if failure:continue
        pending=target.with_suffix('.pending');no_links(pending)
        try:
            request=urllib.request.Request(row['url'],headers={'User-Agent':'ForgeArenaSandbox/0.2 (local card-art cache)','Accept':'image/jpeg'})
            with opener.open(request,timeout=15) as response:
                content=response.read(4*1024*1024+1)
            if len(content)!=row['bytes'] or hashlib.sha256(content).hexdigest()!=row['sha256']:raise ValueError('Paper artwork checksum/size mismatch: '+row['name'])
            pending.write_bytes(content);os.replace(pending,target);available+=1
        except OSError as error:
            failure=str(error)
    ready=[r for r in rows if (cache/(str(r['grpId'])+'.jpg')).exists() and hashlib.sha256((cache/(str(r['grpId'])+'.jpg')).read_bytes()).hexdigest()==r['sha256']]
    index=cache/'index.json';pending=index.with_suffix('.pending');no_links(index);no_links(pending)
    pending.write_text(json.dumps(dict(schema=1,cards=ready,credit=source['credit']),indent=2),encoding='utf8');os.replace(pending,index)
    if available!=len(rows):progress('Paper artwork: '+str(available)+'/'+str(len(rows))+' cached; missing images use the original placeholder. '+(failure or ''))
    return dict(expected=len(rows),available=available,warning=failure)
