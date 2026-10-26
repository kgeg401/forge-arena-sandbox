"""Prove private profile preparation and reject escaped overrides before Forge loads them."""
import argparse
import json
from pathlib import Path
import subprocess
from headless_resources import run_owned


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('runtime','java','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);checks=[];rows=[]
    cp=';'.join(str(p) for p in [a.runtime/'build/ForgeBackend/classes',a.runtime/'forge-runtime/forge.jar',a.runtime/'forge-runtime/gson.jar'])
    for name in ('positive','escaped-user','escaped-cache','missing-user','non-research'):
        folder=(a.output/name).resolve();assets=folder/'runtime/forge-runtime';assets.mkdir(parents=True)
        lab=assets.parent/'native-lab';lab.mkdir();(lab/'bridge-card-manifest.json').write_text(json.dumps(dict(researchOnly=name!='non-research')))
        outside=folder/'outside-profile';user=outside if name=='escaped-user' else assets/'user';cache=outside if name=='escaped-cache' else assets/'cache'
        props=('' if name=='missing-user' else 'userDir='+str(user).replace('\\','/')+'\n')+'cacheDir='+str(cache).replace('\\','/')+'\n'
        (assets/'forge.profile.properties').write_text(props)
        with (folder/'stdout.log').open('w',encoding='utf8') as stdout,(folder/'stderr.log').open('w',encoding='utf8') as stderr:
            result=run_owned([str(a.java),'-Xmx256m','-XX:ActiveProcessorCount=2','-cp',cp,'PrepareResearchProfile',str(assets)],timeout=15,stdout=stdout,stderr=stderr)
        if name=='positive':
            receipt=json.loads((folder/'stdout.log').read_text());ok=result.returncode==0 and receipt['prepared'] and bool(receipt['directories']) and all(Path(path).is_relative_to(assets) and Path(path).is_dir() for path in receipt['directories'])
        else:ok=result.returncode!=0 and not outside.exists() and not (assets/'user').exists() and not (assets/'cache').exists()
        checks.append(dict(check=name+' validates boundaries before creating profile directories',passed=ok));rows.append(dict(id=name,exitCode=result.returncode,evidence=str(folder)))
    report=dict(passed=all(c['passed'] for c in checks),checks=checks,cases=rows,scope=__doc__)
    (a.output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
