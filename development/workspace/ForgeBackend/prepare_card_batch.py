"""Build a fresh, private batch-test runtime from a pinned work queue.

Research identities are not production admission or reviewed rules equivalence.
Never writes to the source runtime or copies original Arena files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from run_card_batches import validate

HERE=Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def prepare(a):
    suite=validate(json.loads(a.suite.read_text(encoding='utf8')))
    queue=json.loads(a.queue.read_text(encoding='utf8'))
    policy=json.loads(a.base_policy.read_text(encoding='utf-8-sig'))
    source=json.loads(a.source_config.read_text(encoding='utf-8-sig'))
    src=Path(source['privateRoot']).resolve()
    if a.output.exists() or src==a.output.resolve() or src in a.output.resolve().parents:
        raise ValueError('Choose a fresh evidence folder outside the source runtime')
    if policy.get('researchOnly') or queue['provenance']['policySha256']!=sha(a.base_policy):
        raise ValueError('Work queue must match the verified baseline policy')
    eligible={c['name']:c for c in queue['existingEffectCandidates']}
    needed=set(suite['cards']) | {n for c in suite['cases'] for values in c['fixture'].values() if isinstance(values,list) for n in values} | {s['card'] for c in suite['cases'] for s in c['steps'] if 'card' in s}
    additions=needed-set(policy['verifiedNames'])
    if additions-set(eligible):
        raise ValueError('This preparer only supports the existing-effect review queue')
    mappings_path=src/'research/card-coverage/arena-printing-mappings.json'
    mappings=json.loads(mappings_path.read_text(encoding='utf8'))
    candidates={}
    scripts=Path(source.get('forgeResourcesRoot',str(src/'forge-runtime')))/'res/cardsfolder/cardsfolder.zip'
    if sha(scripts)!=queue['provenance']['engineAudit']['sourceForgeScriptsSha256']:
        raise ValueError('Queue no longer matches source scripts')
    with zipfile.ZipFile(scripts) as archive:
        for name in sorted(additions):
            candidate=eligible[name]
            if len(candidate['scripts'])!=1:
                raise ValueError('Require one explicit script identity')
            raw=archive.read(candidate['scripts'][0])
            if hashlib.sha256(raw).hexdigest()!=candidate['sourceScriptSha256']:
                raise ValueError('Candidate script identity drift: '+name)
            rows=[r for r in mappings['printings'] if r['name']==name and not r['rebalanced'] and not r['digitalOnly'] and not r['linkedFaces']]
            if not rows:
                raise ValueError('No bounded original Arena printing: '+name)
            row=min(rows,key=lambda r:r['grpId'])
            policy['verifiedNames'].append(name)
            policy['preferredPrintings'][name]=row['grpId']
            policy.setdefault('colorIdentities',{})[name]=[{'1':'W','2':'U','3':'B','4':'R','5':'G'}[c] for c in row['colors'].split(',') if c in ('1','2','3','4','5')]
            candidates[name]=dict(printing=row,script=candidate['scripts'][0],scriptSha256=candidate['sourceScriptSha256'],forgeText=raw.decode('utf-8-sig'),rulesEquivalenceReviewed=False)
    policy['researchOnly']=True
    root=a.output/'runtime'
    runtime=root/'forge-runtime'
    a.output.mkdir(parents=True)
    runtime.mkdir(parents=True)
    # Independent physical resources: no mutable junction into a playable install.
    shutil.copytree(src/'forge-runtime/res',runtime/'res')
    for filename in ('forge.jar','gson.jar'):
        shutil.copy2(src/'forge-runtime'/filename,runtime/filename)
    (runtime/'forge.profile.properties').write_text('userDir='+str(runtime/'user').replace('\\','/')+'\ncacheDir='+str(runtime/'cache').replace('\\','/')+'\n',encoding='utf8')
    (root/'native-lab').mkdir();(root/'research').mkdir()
    config={**source,'privateRoot':str(root.resolve()),'forgeResourcesRoot':str(runtime.resolve())}
    config_path=a.output/'runtime-config.json'
    config_path.write_text(json.dumps(config,indent=2),encoding='utf8')
    policy_path=a.output/'research-policy.json'
    policy_path.write_text(json.dumps(policy,indent=2),encoding='utf8')
    env={**os.environ,'FORGE_ARENA_CONFIG':str(config_path.resolve()),'FORGE_ARENA_POLICY':str(policy_path.resolve()),'PYTHONIOENCODING':'utf-8'}
    with (a.output/'mapping.log').open('w',encoding='utf8') as log:
        subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'build_card_coverage.py')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    classes=root/'build/ForgeBackend/classes';classes.mkdir(parents=True)
    cp=os.pathsep.join(map(str,[runtime/'forge.jar',runtime/'gson.jar']))
    with (a.output/'compile.log').open('w',encoding='utf8') as log:
        subprocess.run([str(a.javac.resolve()),'-J-Xmx512m','-J-XX:ActiveProcessorCount=2','-cp',cp,'-d',str(classes),str(HERE/'ForgeLandEngine.java'),str(HERE/'ResearchGameWorker.java')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    receipt=dict(schema=1,researchOnly=True,productionAdmissions=0,baselinePolicySha256=sha(a.base_policy),
        workQueueSha256=sha(a.queue),suiteSha256=sha(a.suite),mappingSourceSha256=sha(mappings_path),
        config=str(config_path),policy=str(policy_path),compiler=str(a.javac.resolve()),
        sourceSha256=sha(HERE/'ForgeLandEngine.java'),classes={p.name:sha(p) for p in sorted(classes.glob('ForgeLandEngine*.class'))},
        workerSourceSha256=sha(HERE/'ResearchGameWorker.java'),workerClasses={p.name:sha(p) for p in sorted(classes.glob('ResearchGameWorker*.class'))},
        forgeJarSha256=sha(runtime/'forge.jar'),gsonJarSha256=sha(runtime/'gson.jar'),candidates=candidates,
        scope='Prepared initial-state research identities only. No source-equivalence, native-game or gameplay admission claim.')
    (a.output/'preparation.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(dict(config=str(config_path),policy=str(policy_path),cards=len(candidates))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('suite','queue','base-policy','source-config','javac','output'):
        p.add_argument('--'+name,type=Path,required=True)
    prepare(p.parse_args())
