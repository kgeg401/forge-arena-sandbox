"""Create a private, independent Arena lab copy. No links to mutable game files."""
import json
import shutil
from pathlib import Path

source = Path(r'D:\GAMES\MTGA')
root = Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox')
lab = root / 'native-lab'
if lab.exists():
    raise SystemExit('Lab already exists; inspect it instead of overwriting it.')
lab.mkdir()
for entry in source.iterdir():
    if entry.name in {'MTGALauncher', 'version'}:
        continue
    destination = lab / entry.name
    if entry.is_dir():
        shutil.copytree(entry, destination, ignore=shutil.ignore_patterns('Logs', '*.log'))
    else:
        shutil.copy2(entry, destination)
loader = root / 'tools' / 'BepInEx-5.4.23.5'
shutil.copytree(loader, lab, dirs_exist_ok=True)
(lab / 'sandbox-lab.json').write_text(json.dumps({'localOnly': True, 'requireAppContainer': True,
                                               'source': str(source), 'independentCopies': True}, indent=2))
print(lab)
