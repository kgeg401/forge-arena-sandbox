"""Pinned official prerequisite downloads, staged away from installed programs."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json,os,stat,tarfile,urllib.request,urllib.parse,uuid,zipfile
from tester_common import no_links,safe_relative,sha

HOSTS={'github.com','release-assets.githubusercontent.com','objects.githubusercontent.com','builds.dotnet.microsoft.com','dotnetcli.azureedge.net','download.visualstudio.microsoft.com'}

def approved_url(url):
    p=urllib.parse.urlparse(url)
    if p.scheme!='https' or p.hostname not in HOSTS or p.port not in (None,443) or p.username or p.password:raise ValueError('Unexpected prerequisite download host')
    return url

class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        approved_url(newurl)
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def checksum(path,algorithm='sha256'):
    h=hashlib.new(algorithm)
    with Path(path).open('rb') as f:
        while chunk:=f.read(4*1024*1024):h.update(chunk)
    return h.hexdigest()

def download(item,cache,progress=lambda text:None):
    cache=Path(cache);no_links(cache);cache.mkdir(parents=True,exist_ok=True)
    name=safe_relative(item['filename'])
    if len(name.parts)!=1:raise ValueError('Prerequisite filename must be flat')
    target=cache/name;no_links(target)
    algorithm=item.get('algorithm','sha256');digest=item['digest']
    if target.exists():
        if checksum(target,algorithm)==digest:return target
        target.rename(cache/(name.name+'.rejected-'+uuid.uuid4().hex))
    pending=cache/(name.name+'.'+uuid.uuid4().hex+'.pending')
    maximum=item.get('maximumBytes',512*1024*1024)
    progress('Downloading '+item['label']+'…')
    request=urllib.request.Request(approved_url(item['url']),headers={'User-Agent':'ForgeArenaSandbox-Setup'})
    opener=urllib.request.build_opener(OfficialRedirect)
    with opener.open(request,timeout=45) as source,pending.open('xb') as out:
        size=0
        while chunk:=source.read(4*1024*1024):
            size+=len(chunk)
            if size>maximum:raise ValueError('Prerequisite download exceeded its size limit')
            out.write(chunk);progress('Downloading '+item['label']+': '+str(size//1024//1024)+' MB')
    if checksum(pending,algorithm)!=digest:raise ValueError('Prerequisite checksum mismatch. Nothing was installed: '+item['label'])
    pending.rename(target);return target

def extract(archive,destination,kind):
    """No archive links, traversal, overwrite or unbounded expansion."""
    destination=Path(destination);no_links(destination)
    if destination.exists():raise ValueError('Prerequisite extraction folder already exists: '+str(destination))
    destination.mkdir(parents=True);seen=set();total=0
    def entry(name,size,is_dir=False,is_link=False):
        nonlocal total
        while name.startswith('./'):name=name[2:]
        if is_dir:name=name.rstrip('/')
        if not name and is_dir:return None
        rel=safe_relative(name)
        if name.casefold() in seen:raise ValueError('Duplicate/case-alias prerequisite path')
        seen.add(name.casefold());total+=size
        if len(seen)>100000 or total>4*1024**3 or size>512*1024**2 or is_link:raise ValueError('Unsafe prerequisite archive entry or size')
        target=destination/rel
        if is_dir:target.mkdir(parents=True,exist_ok=True)
        else:target.parent.mkdir(parents=True,exist_ok=True)
        return target
    import shutil
    if kind=='zip':
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                target=entry(info.filename,info.file_size,info.is_dir(),stat.S_ISLNK(info.external_attr>>16))
                if target is not None and not info.is_dir():
                    with z.open(info) as src,target.open('xb') as out:shutil.copyfileobj(src,out)
    elif kind=='tar.bz2':
        with tarfile.open(archive,'r:bz2') as tar:
            for info in tar:
                if not info.isfile() and not info.isdir():raise ValueError('Prerequisite archive special/link entry rejected')
                target=entry(info.name,info.size,info.isdir())
                if target is not None and info.isfile():
                    with tar.extractfile(info) as src,target.open('xb') as out:shutil.copyfileobj(src,out)
    else:raise ValueError('Unknown prerequisite archive type')

def prepare(item,workspace,progress=lambda text:None):
    workspace=Path(workspace);archive=download(item,workspace/'downloads',progress)
    extracted=workspace/(item['id']+'-'+item['digest'][:12]);receipt=extracted/'prerequisite-receipt.json'
    if extracted.exists():
        if not receipt.exists():
            # Preserve interrupted work; finish a fresh extraction alongside it.
            extracted=workspace/(item['id']+'-'+item['digest'][:12]+'-'+uuid.uuid4().hex[:8]);receipt=extracted/'prerequisite-receipt.json'
            progress('Preparing '+item['label']+' after interrupted setup…');extract(archive,extracted,item['archive']);receipt.write_text(json.dumps(dict(digest=item['digest'],source=item['url']),indent=2))
        elif json.loads(receipt.read_text())['digest']!=item['digest']:raise ValueError('Prerequisite extraction receipt changed; preserved for inspection')
    else:
        progress('Preparing '+item['label']+'…');extract(archive,extracted,item['archive'])
        receipt.write_text(json.dumps(dict(digest=item['digest'],source=item['url']),indent=2))
    root=extracted/safe_relative(item['root']) if item.get('root') else extracted
    for rel,digest in item.get('files',{}).items():
        p=root/safe_relative(rel);no_links(p)
        if not p.is_file() or sha(p)!=digest:raise ValueError('Prepared prerequisite differs from tested build: '+rel)
    return root

def forge_variants(requirements):
    return requirements.get('forgeVariants') or [dict(id='legacy-snapshot',jar=requirements['forgeJar'],files=requirements['forgeFiles'])]

def match_forge(base,requirements,runtime=False):
    base=Path(base)
    for variant in forge_variants(requirements):
        if all((base/('forge.jar' if runtime and rel==variant['jar'] else rel)).is_file() and sha(base/('forge.jar' if runtime and rel==variant['jar'] else rel))==digest for rel,digest in variant['files'].items()):return variant
    raise ValueError('Unsupported or changed Forge build. Use automatic setup to download the tested release.')
