"""Stable shortcut entry point; application code stays versioned."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,re,subprocess,hashlib

def verify_before_execution(app,expected_version):
    """Check bytes using only the standard library before importing an update."""
    manifest=json.loads((app/'release-manifest.json').read_text(encoding='utf-8-sig'))
    if manifest.get('schema')!=1 or manifest.get('profileSchema')!=1 or manifest.get('version')!=expected_version:raise ValueError('Installed release identity differs')
    for name,digest in manifest['files'].items():
        parts=name.split('/')
        if not parts or any(p in ('','.','..') for p in parts) or '\\' in name or ':' in name:raise ValueError('Unsafe installed path')
        path=app.joinpath(*parts)
        for parent in (path,*path.parents):
            if parent.is_symlink() or (parent.exists() and getattr(parent.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Linked installed path')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Installed file changed: '+name)
    actual={p.relative_to(app).as_posix() for p in app.rglob('*') if p.is_file()}
    if actual!=set(manifest['files'])|{'release-manifest.json'}:raise ValueError('Unexpected installed files')

def main():
    root=Path(__file__).resolve().parent
    config=json.loads((root/'sandbox-install.json').read_text())
    active=json.loads((root/'active-version.json').read_text())
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?',active['version']):raise ValueError('Invalid installed version')
    if (root/'installation-incomplete.txt').exists():raise ValueError('Finish installation first')
    app=root/'versions'/active['version'];verify_before_execution(app,active['version'])
    entry=app/'client_entry.py'
    return subprocess.call([config['python'],'-B',str(entry),'--install-root',str(root),*sys.argv[1:]])

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError) as e:
        print('Sandbox launcher stopped: '+str(e))
        if sys.stdin.isatty():input('Press Enter to close...')
        raise SystemExit(1)
