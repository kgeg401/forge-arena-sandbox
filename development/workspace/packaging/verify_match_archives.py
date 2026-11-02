"""Disposable diagnostics retention/export checks; no live game paths used."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json,zipfile,os
from match_archives import archive_match,prune,export_latest,MARKER

checks=[]
def check(name,value):assert value,name;checks.append(name)
with TemporaryDirectory(prefix='forge-archives-') as temp:
    root=Path(temp);lab=root/'lab';lab.mkdir()
    profile=lab/'local-profile';profile.mkdir();(profile/'decks.json').write_text('original user decks')
    legacy=lab/'forge-ipc-evidence-20260101-000000-000000';legacy.mkdir();(legacy/'state.json').write_text('legacy evidence')
    made=[]
    for index in range(5):
        ipc=lab/'forge-ipc';ipc.mkdir();(ipc/'state.json').write_text('x'*1000);made.append(archive_match(lab,keep_all=True))
    check('Full diagnostics retains every newly archived match',all(p.is_dir() for p in made))
    active=lab/'forge-ipc';active.mkdir();(active/'state.json').write_text('active response ledger')
    result=prune(lab,max_archives=3,max_bytes=100000)
    check('Default count keeps only the three newest managed archives',result['retained']==3 and len(result['removed'])==2 and all(p.is_dir() for p in made[-3:]))
    check('Legacy evidence is never retroactively deleted',(legacy/'state.json').read_text()=='legacy evidence')
    check('Active responses and user decks are untouched',(active/'state.json').read_text()=='active response ledger' and (profile/'decks.json').read_text()=='original user decks')
    result=prune(lab,max_archives=3,max_bytes=2500)
    check('Byte cap holds independently of count',result['bytes']<=2500 and result['retained']==2)
    archive=root/'support.zip';receipt=export_latest(lab,archive)
    with zipfile.ZipFile(archive) as z:check('Export contains the exact latest closed state',z.read('state.json')==b'x'*1000)
    check('Export never includes live state or profiles',receipt['archive']==made[-1].name)
    try:export_latest(lab,archive)
    except ValueError:check('Export cannot overwrite an existing user file',True)
    else:raise AssertionError('Existing export overwritten')
    try:export_latest(lab,lab/'recursive.zip')
    except ValueError:check('Export cannot grow recursively inside game data',True)
    else:raise AssertionError('Recursive export accepted')
    result=prune(lab,max_archives=3,max_bytes=1)
    check('An oversized match cannot defeat the byte limit',result['retained']==0 and result['bytes']==0)
    for index in range(4):
        active.mkdir(exist_ok=True);(active/'state.json').write_text('default policy '+str(index));archive_match(lab)
    check('Normal archive creation enforces retention without an explicit cleanup call',len([p for p in lab.glob('forge-ipc-evidence-*') if (p/MARKER).is_file()])==3)
    bad=lab/'forge-ipc-evidence-20260102-000000-000000-deadbeef';bad.mkdir();(bad/MARKER).write_text('{"schema":99}');(bad/'keep.txt').write_text('unrecognized')
    prune(lab,max_archives=0,max_bytes=0);check('Unknown markers are preserved',(bad/'keep.txt').exists())
    # Exercise native junction protection on Windows without following its target.
    linked=lab/'forge-ipc-evidence-20260103-000000-000000-deadbeef';linked.mkdir();(linked/MARKER).write_text(json.dumps(dict(schema=1,archive=linked.name)))
    outside=root/'outside';outside.mkdir();(outside/'sentinel.txt').write_text('do not delete')
    if os.name=='nt':
        import subprocess
        subprocess.run(['powershell','-NoProfile','-Command',"New-Item -ItemType Junction -Path '"+str(linked/'junction')+"' -Target '"+str(outside)+"' | Out-Null"],check=True,capture_output=True)
        try:
            try:prune(lab,max_archives=0,max_bytes=0)
            except ValueError:check('Nested Windows junction prevents deletion',True)
            else:raise AssertionError('Linked archive accepted')
            check('Junction target remains untouched',(outside/'sentinel.txt').read_text()=='do not delete')
        finally:os.rmdir(linked/'junction')
    with patch('match_archives.prune',side_effect=OSError('locked diagnostic')) as cleanup:
        active.mkdir(exist_ok=True)
        (active/'state.json').write_text('closed but retained')
        saved=archive_match(lab)
        check('Cleanup failure does not block the next game or lose evidence',cleanup.call_count==1 and saved.is_dir() and not active.exists())
print(json.dumps(dict(checks=len(checks),passed=checks),indent=2))
