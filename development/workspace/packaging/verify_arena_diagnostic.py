"""Exercise the read-only Windows checker against disposable file fingerprints."""
from pathlib import Path
import hashlib,json,subprocess,tempfile

checks=[]
with tempfile.TemporaryDirectory(prefix='arena-diagnostic-') as temp:
    root=Path(temp);game=root/'game';game.mkdir()
    for name,value in [('MTGA.exe',b'exe'),('Core.dll',b'core')]:
        (game/name).write_bytes(value)
    profiles=root/'profiles.json'
    profiles.write_text(json.dumps({'builds':[{'arenaBuild':'fixture','arenaFiles':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in game.iterdir()}}]}),encoding='utf8')
    def run(folder):
        report=root/'report.json'
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(Path(__file__).with_name('Check-Arena-Files.ps1')),'-Arena',str(folder),'-Profiles',str(profiles),'-Report',str(report),'-NoDialog'],check=True,capture_output=True,timeout=30)
        return json.loads(report.read_text(encoding='utf-8-sig'))
    assert run(game)['accepted'];checks.append('Exact files accepted')
    (game/'Core.dll').write_bytes(b'changed')
    result=run(game)
    assert not result['accepted'] and [d['path'] for d in result['comparisons'][0]['differences']]==['Core.dll']
    assert (game/'Core.dll').read_bytes()==b'changed';checks.append('Changed file identified without changing it')
    result=run(root/'missing')
    assert not result['accepted'] and not result['executableFound'];checks.append('Wrong folder identified')
    (game/'MTGA.exe').unlink()
    result=run(game)
    assert not result['accepted'] and not result['executableFound'];checks.append('Incomplete installation identified')
print(json.dumps({'passed':True,'checks':checks},indent=2))
