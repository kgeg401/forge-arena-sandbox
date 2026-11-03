"""Select an explicitly fingerprinted Arena build; never waive a mismatch."""
from pathlib import Path
import json
from tester_common import sha, no_links, safe_relative

def select_arena(requirements,root):
    variants=requirements.get('arenaVariants')
    if variants is None:return requirements
    if not isinstance(variants,list) or not variants:raise ValueError('Missing supported Arena builds')
    root=Path(root);cache={}
    def matches(name,digest):
        path=root/safe_relative(name);no_links(path)
        if name not in cache:cache[name]=sha(path) if path.is_file() else None
        return cache[name]==digest
    for variant in variants:
        files=variant.get('arenaFiles',{})
        if not isinstance(files,dict) or 'MTGA_Data/Managed/Core.dll' not in files:raise ValueError('Invalid Arena build fingerprint')
        if not matches('MTGA_Data/Managed/Core.dll',files['MTGA_Data/Managed/Core.dll']):continue
        if all(matches(name,digest) for name,digest in files.items()):
            return {**requirements,**variant,'arenaVariant':variant['id']}
    builds=', '.join(v.get('arenaBuild',v.get('id','unknown')) for v in variants)
    raise ValueError('Arena files do not match a tested build ('+builds+'). Finish Arena updates and use a supported installation; existing sandbox data was preserved.')

def validated_family(lab):
    for parent in (Path(__file__).parent,Path(__file__).parent.parent):
        file=parent/'ForgeBackend/arena-builds.json'
        if file.is_file():break
    else:raise ValueError('Missing pinned Arena compatibility profiles')
    source=json.loads(file.read_text(encoding='utf8'))
    if source.get('schema')!=1 or not isinstance(source.get('family'),str):raise ValueError('Invalid Arena compatibility profiles')
    selected=select_arena({'arenaVariants':source['builds']},lab)
    return source['family'],selected
