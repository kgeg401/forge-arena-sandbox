"""Package integrity/path checks, independent of any installed game."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path, PurePosixPath
import hashlib, json, os, re, stat, zipfile
from contextlib import contextmanager

@contextmanager
def install_lock(install):
    """Serialize launch/update actions, including across separate shortcuts."""
    import msvcrt
    path=Path(install)/'client-action.lock'
    with path.open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):lock.write(b'0');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError('Another sandbox launch or update is in progress. Try again when it finishes.')
        try:yield
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def metadata_recipe(app):
    """Invalidate derived indexes when their code or admission policy changes."""
    files=('ForgeBackend/runtime_paths.py','ForgeBackend/deck_import.py',
           'ForgeBackend/build_card_coverage.py','ForgeBackend/bridge_support.json',
           'DeckBackend/build_deck_catalog.py')
    # Older versions predate these optional helpers. Their original recipe
    # remains valid; new releases invalidate derived indexes when either changes.
    files+=tuple(name for name in ('ForgeBackend/arena_catalog.py','ForgeBackend/card_support.py','ForgeBackend/card-support-index.json') if (Path(app)/name).is_file())
    rows={name:sha(Path(app)/name) for name in files}
    return hashlib.sha256(json.dumps(rows,sort_keys=True).encode('utf8')).hexdigest()

def within(child,parent):
    child=Path(child).resolve();parent=Path(parent).resolve()
    return child==parent or parent in child.parents

def no_links(path):
    path=Path(path).absolute()
    for p in (path,*path.parents):
        if p.exists() and (p.is_symlink() or getattr(p.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Junction/symbolic-link path rejected: '+str(p))

def repository_name(value):
    if not isinstance(value,str) or value.count('/')!=1:raise ValueError('Use a GitHub owner/repository name')
    owner,repo=value.split('/')
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?',owner) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',repo) or repo in ('.','..'):raise ValueError('Invalid GitHub repository identity')
    return value

def version(value):
    m=re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([a-zA-Z0-9]+(?:[.-][a-zA-Z0-9]+)*))?',value)
    if not m:raise ValueError('Invalid package version')
    parts=tuple((0,int(p)) if p.isdecimal() else (1,p) for p in (m[4] or '').split('.'))
    return tuple(map(int,m.group(1,2,3)))+(m[4] is None,parts)

def safe_relative(name):
    if not isinstance(name,str) or '\\' in name or ':' in name or '\x00' in name:raise ValueError('Invalid package path')
    p=PurePosixPath(name)
    if p.is_absolute() or any(x in ('..','.') for x in name.split('/')) or str(p)!=name:raise ValueError('Package path escapes staging')
    # Case-insensitive NTFS, reserved device names and alternate stream aliases.
    if any(re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',s,re.I) or s.endswith((' ','.')) for s in p.parts):raise ValueError('Unsafe Windows filename')
    return Path(*p.parts)

def verify_tree(root):
    root=Path(root);manifest=json.loads((root/'release-manifest.json').read_text(encoding='utf-8-sig'))
    if manifest.get('schema')!=1 or manifest.get('profileSchema')!=1:raise ValueError('Unsupported package/profile schema')
    version(manifest['version']);entries=manifest['files'];seen=set()
    for name,digest in entries.items():
        safe_relative(name)
        if name.casefold() in seen:raise ValueError('Case-alias package paths')
        seen.add(name.casefold());p=root/safe_relative(name);no_links(p)
        if sha(p)!=digest:raise ValueError('Package checksum mismatch: '+name)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual!=set(entries)|{'release-manifest.json'}:raise ValueError('Unexpected or missing package files')
    return manifest

def extract_verified(archive,destination):
    """Extract an update to a new directory; never overwrite an installation."""
    destination=Path(destination)
    if destination.exists():raise ValueError('Update staging directory already exists')
    no_links(destination);destination.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive) as z:
            if len(z.infolist())>5000:raise ValueError('Unexpected adapter archive file count')
            seen=set();total=0
            for entry in z.infolist():
                name=entry.filename.rstrip('/') if entry.is_dir() else entry.filename
                rel=safe_relative(name)
                if name.casefold() in seen:raise ValueError('Duplicate/case-alias archive entry')
                seen.add(name.casefold());mode=entry.external_attr>>16
                if stat.S_ISLNK(mode):raise ValueError('Archive symbolic link rejected')
                total+=entry.file_size
                if total>128*1024*1024 or entry.file_size>64*1024*1024:raise ValueError('Unexpectedly large adapter update')
                target=destination/rel
                if entry.is_dir():target.mkdir(parents=True,exist_ok=True)
                else:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(entry) as source,target.open('xb') as out:
                        import shutil;shutil.copyfileobj(source,out)
        return verify_tree(destination)
    except Exception:
        # Keep failed staging for inspection. Never touch live binaries/profile.
        raise
