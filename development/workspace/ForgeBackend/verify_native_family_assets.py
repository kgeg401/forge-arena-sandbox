"""Bounded original-native model/art checks for a candidate source family.

Uses the existing isolated lab probe. Sends each request once, retains every
response, and reports failures explicitly. Does not grant card admission.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import uuid

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--candidates',type=Path,required=True)
p.add_argument('--mappings',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
args = p.parse_args()
if args.output.exists():
    raise ValueError('Select a new output folder')
args.output.mkdir(parents=True)
lab = Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab')
candidates = json.loads(args.candidates.read_text())
source = {r['grpId']:r for r in json.loads(args.mappings.read_text(encoding='utf8'))['printings']}
manifest = json.loads((lab/'bridge-card-manifest.json').read_text())
if not manifest.get('researchOnly'):
    raise ValueError('Active original-native lab must use an explicit research manifest')
for name, definition in candidates.items():
    if manifest['cards'][name]['grpId'] != definition['grpId']:
        raise ValueError('Native manifest differs from candidate source')
reports = []
names = list(candidates)
for offset in range(0,len(names),120):
    group = names[offset:offset+120]
    request = dict(requestId=uuid.uuid4().hex,grpIds=[candidates[n]['grpId'] for n in group])
    request_path = lab/'card-assets.request.json'
    if request_path.exists():
        raise ValueError('Another native asset request is pending; do not overwrite it')
    (args.output/(str(offset)+'-request.json')).write_text(json.dumps(request,indent=2))
    temporary = request_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(request))
    temporary.rename(request_path)
    end = time.monotonic()+150
    while time.monotonic()<end:
        try:
            report = json.loads((lab/'card-assets-report.json').read_text())
            if report.get('requestId')==request['requestId']:
                break
        except (FileNotFoundError,PermissionError,json.JSONDecodeError):
            pass
        time.sleep(.2)
    else:
        raise TimeoutError('Native asset probe did not finish; original request retained, not resent')
    (args.output/(str(offset)+'-native.json')).write_text(json.dumps(report,indent=2))
    if len(report['cards'])!=len(group) or {r['grpId'] for r in report['cards']}!=set(request['grpIds']):
        raise ValueError('Native probe did not return exactly the requested identities')
    for row in report['cards']:
        expected = str(source[row['grpId']]['artId']).zfill(6)+'_AIF'
        passed = not row.get('error') and row.get('modelGrpId')==row['grpId'] and row.get('artReady') and any(t['name']==expected for t in row.get('textures',[]))
        reports.append(dict(name=row['name'],grpId=row['grpId'],passed=bool(passed),expectedArt=expected))
    print(json.dumps(dict(batch=len(group),passed=sum(r['passed'] for r in reports),checked=len(reports))),flush=True)
result = dict(cards=len(reports),passed=sum(r['passed'] for r in reports),failures=[r for r in reports if not r['passed']],cardsChecked=reports,
    manifestSha256=hashlib.sha256((lab/'bridge-card-manifest.json').read_bytes()).hexdigest(),
    nativeHostSha256=hashlib.sha256((lab/'BepInEx/plugins/ForgeArenaSandbox/NativeHost.dll').read_bytes()).hexdigest(),
    scope='Original model and exact effective source art texture. Separate from gameplay/animation verification and admission.')
(args.output/'report.json').write_text(json.dumps(result,indent=2))
print(json.dumps(dict(cards=result['cards'],passed=result['passed'],failed=len(result['failures']),report=str(args.output/'report.json')),indent=2))
raise SystemExit(0 if not result['failures'] else 1)
