"""Negative launch checks against a private pinned spec; no client is launched."""
from pathlib import Path
import argparse,copy,importlib.util,json,tempfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
loader=importlib.util.spec_from_file_location('local_preview',Path(__file__).with_name('launch_local_preview.py'))
m=importlib.util.module_from_spec(loader);loader.loader.exec_module(m)
original=m.read(a.spec);before=m.processes();checks=[]
cases=[('Incomplete release',lambda s:s['files'].pop('app/ForgeBackend/bridge_support.json'),'Incomplete preview release'),
       ('Changed bridge',lambda s:s['files'].__setitem__('NativeHost.dll','0'*64),'Preview release file changed'),
       ('Changed owned build',lambda s:s['nativeRequirements'].__setitem__('MTGA.exe','0'*64),'Pinned Arena preview build changed'),
       ('Release path escape',lambda s:s['files'].__setitem__('../outside-release.bin','0'*64),'Preview release file changed')]
with tempfile.TemporaryDirectory(dir=a.output) as scratch:
 for label,alter,expected in cases:
  spec=copy.deepcopy(original);alter(spec);path=Path(scratch)/(label.replace(' ','-')+'.json');path.write_text(json.dumps(spec))
  try:m.launch(path)
  except ValueError as error:assert expected in str(error),(label,str(error));checks.append(label+' rejected before launch')
  else:raise AssertionError(label+' unexpectedly launched')
after=m.processes()
identities=lambda items:sorted((p['ProcessId'],p.get('ExecutablePath')) for p in items)
assert identities(before)==identities(after),'A native or rules process changed during preflight rejection checks'
checks.append('Existing native/rules processes preserved')
report=dict(passed=True,checks=checks,scope='Real private files and process inventory; rejection checks only. Cold launch and rendered gameplay require separate acceptance.')
(a.output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
