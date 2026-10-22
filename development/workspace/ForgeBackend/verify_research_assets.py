"""Check original native model identities and effective art against owned data."""
import hashlib
import json
from pathlib import Path
import time

base=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox')
folder=base/'research/broad-card-support';lab=base/'native-lab'
request=json.loads((folder/'all-card-assets-request.json').read_text())
path=lab/'card-assets-report.json';end=time.monotonic()+120
while time.monotonic()<end:
    if path.exists():
        report=json.loads(path.read_text())
        if report['requestId']==request['requestId']:break
    time.sleep(.2)
else:raise TimeoutError('Native asset probe did not finish; original request and logs retained')
source=json.loads((base/'research/packaging/forge-stable-2.0.15/isolated-tests/research/card-coverage/arena-printing-mappings.json').read_text(encoding='utf8'))
printings={r['grpId']:r for r in source['printings']};checks=[]
def check(label,ok):
    assert ok,label
    checks.append(dict(check=label,passed=True))
check('Every requested printing appears exactly once',{r['grpId'] for r in report['cards']}==set(request['grpIds']) and len(report['cards'])==len(request['grpIds']))
for row in report['cards']:
    check('Original native model identity '+row['name'],not row.get('error') and row['modelGrpId']==row['grpId'])
    check('Original artwork available '+row['name'],row['artReady'])
    expected=str(printings[row['grpId']]['artId']).zfill(6)+'_AIF'
    check('Effective rendered texture matches exact source art '+row['name'],any(t['property']=='_MainTex' and t['name']==expected for t in row['textures']))
result=dict(checks=len(checks),cards=len(report['cards']),passed=checks,nativeReport=report,
            nativeHostSha256=hashlib.sha256((lab/'BepInEx/plugins/ForgeArenaSandbox/NativeHost.dll').read_bytes()).hexdigest(),
            scope='Per-printing native model/art availability plus exact source art-ID match; complete manual gameplay and visual-parity checks are separate.')
(folder/'native-art-90.json').write_text(json.dumps(result,indent=2))
print(json.dumps(dict(checks=len(checks),cards=len(report['cards']),report=str(folder/'native-art-90.json')),indent=2))
