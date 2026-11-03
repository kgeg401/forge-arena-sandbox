"""Read cosmetic aliases; never export profile IDs or change shared card data."""
import json,uuid
from pathlib import Path

AVATARS={'Avatar_Basic_AjaniGoldmane','Avatar_Basic_Sparky','Avatar_Basic_NPE'}

def public_identity(value):
    if not isinstance(value,dict) or set(value)!={'name','avatar'}:raise ValueError('Invalid cosmetic identity fields')
    name=value['name']
    if not isinstance(name,str) or not 1<=len(name.encode('utf-16-le'))//2<=32 or name!=name.strip() or any(ord(c)<32 or 127<=ord(c)<=159 or c in '<>' for c in name):raise ValueError('Invalid cosmetic name')
    if not isinstance(value['avatar'],str) or value['avatar'] not in AVATARS:raise ValueError('Unsupported cosmetic avatar')
    return dict(name=name,avatar=value['avatar'])

def selected_identity(lab):
    path=Path(lab)/'local-profile/identities.json'
    if not path.exists():return dict(name='Local Player',avatar='Avatar_Basic_AjaniGoldmane')
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict) or type(data.get('schema')) is not int or data['schema']!=1 or type(data.get('revision')) is not int or not 0<=data['revision']<2147483647 or not isinstance(data.get('profiles'),list) or not 1<=len(data['profiles'])<=32:raise ValueError('Invalid saved profiles; original file preserved')
    found=[];ids=set()
    for profile in data['profiles']:
        if not isinstance(profile,dict) or set(profile)!={'id','name','avatar'} or not isinstance(profile['id'],str) or str(uuid.UUID(profile['id']))!=profile['id']:raise ValueError('Invalid saved profile identity')
        value=public_identity({k:profile[k] for k in ('name','avatar')})
        if profile['id'] in ids:raise ValueError('Duplicate saved profile identity')
        ids.add(profile['id'])
        if profile['id']==data.get('activeId'):found.append(value)
    if len(found)!=1:raise ValueError('Missing selected profile')
    return found[0]
