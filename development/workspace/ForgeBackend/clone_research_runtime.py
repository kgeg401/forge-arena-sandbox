"""Fresh research build/profile with shared, pinned read-only Forge resources.

Keeps previous compiled builds/evidence intact; no playable or retail process
is modified. Only resources are shared; classes, IPC, user and cache are fresh.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def clone(a):
    config=json.loads(a.source_config.read_text(encoding='utf-8-sig'))
    source=Path(config['privateRoot']).resolve()
    manifest=json.loads((source/'native-lab/bridge-card-manifest.json').read_text(encoding='utf8'))
    policy=json.loads(a.source_policy.read_text(encoding='utf-8-sig'))
    if manifest.get('researchOnly') is not True or policy.get('researchOnly') is not True or (source/'native-lab/MTGA.exe').exists():
        raise ValueError('Select an independent research source')
    if sha(a.source_policy)!=manifest['policySha256']:raise ValueError('Research policy and source manifest differ')
    out=a.output.resolve()
    forbidden=[source,Path(config['arenaInstall']).resolve(),Path(config['forgeInstall']).resolve()]
    if out.exists() or any(out==p or p in out.parents for p in forbidden):raise ValueError('Fresh output must be outside source and game installs')
    version=subprocess.run([str(a.javac),'-version'],capture_output=True,text=True,check=True).stdout.strip()
    if not version.startswith('javac 17.'):raise ValueError('Use the pinned Java 17 compiler')
    rt=out/'runtime/forge-runtime';rt.mkdir(parents=True)
    resources=(source/'forge-runtime/res').resolve()
    if os.name=='nt':
        encoded=[base64.b64encode(str(p).encode()).decode() for p in (rt/'res',resources)]
        command="$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded[0]+"'));$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded[1]+"'));New-Item -ItemType Junction -Path $p -Target $t -ErrorAction Stop | Out-Null"
        subprocess.run(['powershell.exe','-NoProfile','-Command',command],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        (rt/'res').symlink_to(resources,target_is_directory=True)
    for n in ('forge.jar','gson.jar'):shutil.copy2(source/'forge-runtime'/n,rt/n)
    (rt/'forge.profile.properties').write_text('userDir='+str(rt/'user').replace('\\','/')+'\ncacheDir='+str(rt/'cache').replace('\\','/')+'\n',encoding='utf8')
    root=rt.parent;(root/'native-lab').mkdir();(root/'research').mkdir()
    shutil.copy2(source/'native-lab/bridge-card-manifest.json',root/'native-lab/bridge-card-manifest.json')
    qualified=getattr(a,'qualified_policy',None)
    effective=qualified or a.source_policy
    if json.loads(effective.read_text(encoding='utf-8-sig')).get('researchOnly') is not True:raise ValueError('Qualified policy must remain research-only')
    shutil.copy2(effective,out/'research-policy.json')
    config.update(privateRoot=str(root),forgeResourcesRoot=str(rt))
    (out/'runtime-config.json').write_text(json.dumps(config,indent=2),encoding='utf8')
    if sha(effective)!=manifest['policySha256']:
        env={**os.environ,'FORGE_ARENA_CONFIG':str(out/'runtime-config.json'),'FORGE_ARENA_POLICY':str(out/'research-policy.json'),'PYTHONIOENCODING':'utf-8'}
        with (out/'mapping.log').open('w',encoding='utf8') as log:
            subprocess.run([os.sys.executable,'-X','utf8','-B',str(HERE/'build_card_coverage.py')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    classes=root/'build/ForgeBackend/classes';classes.mkdir(parents=True)
    cp=os.pathsep.join(map(str,[rt/'forge.jar',rt/'gson.jar']))
    with (out/'compile.log').open('w',encoding='utf8') as log:
        p=subprocess.run([str(a.javac),'-J-Xmx512m','-J-XX:ActiveProcessorCount=2','-cp',cp,'-d',str(classes),str(HERE/'ForgeLandEngine.java'),str(HERE/'ResearchGameWorker.java'),str(HERE/'VerifyResearchCallbackSurface.java')],stdout=log,stderr=subprocess.STDOUT,timeout=90)
    if p.returncode:raise RuntimeError((out/'compile.log').read_text(encoding='utf8'))
    audit=HERE/'callback_audits/forge-2.0.15-final-delegators.json'
    java=Path(config['javaHome'])/'bin/java.exe'
    check=subprocess.run([str(java),'-cp',str(classes)+os.pathsep+cp,'VerifyResearchCallbackSurface',str(audit)],capture_output=True,text=True,encoding='utf8',timeout=30)
    (out/'callback-surface.json').write_text(check.stdout,encoding='utf8')
    if check.returncode:raise RuntimeError(check.stderr or check.stdout)
    receipt=dict(schema=1,researchOnly=True,productionAdmissions=0,sourcePolicySha256=sha(a.source_policy),
        config=str(out/'runtime-config.json'),policy=str(out/'research-policy.json'),compiler=version,
        sourceSha256=sha(HERE/'ForgeLandEngine.java'),classes={p.name:sha(p) for p in classes.glob('ForgeLandEngine*.class')},
        workerSourceSha256=sha(HERE/'ResearchGameWorker.java'),workerClasses={p.name:sha(p) for p in classes.glob('ResearchGameWorker*.class')},
        forgeJarSha256=sha(rt/'forge.jar'),gsonJarSha256=sha(rt/'gson.jar'),sharedReadOnlyResources=str(resources),
        scriptsSha256=sha(rt/'res/cardsfolder/cardsfolder.zip'),sourceManifestSha256=sha(source/'native-lab/bridge-card-manifest.json'))
    receipt.update(qualifiedPolicySha256=sha(effective),generatedManifestSha256=sha(root/'native-lab/bridge-card-manifest.json'),callbackAuditSha256=sha(out/'callback-surface.json'),callbackVerifierSourceSha256=sha(HERE/'VerifyResearchCallbackSurface.java'),callbackDelegatorSpecSha256=sha(audit))
    (out/'preparation.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(dict(config=receipt['config'],policy=receipt['policy'],compiled=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source-config','source-policy','output','javac'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--qualified-policy',type=Path)
    clone(p.parse_args())
