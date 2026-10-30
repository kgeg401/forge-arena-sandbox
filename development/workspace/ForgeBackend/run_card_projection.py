"""Project pinned Forge definitions into private evidence, preserving provenance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','scope','output','javac'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();config=json.loads(a.config.read_text(encoding='utf-8-sig'));root=Path(config['privateRoot']);runtime=root/'forge-runtime'
    manifest=root/'native-lab/bridge-card-manifest.json';m=json.loads(manifest.read_text(encoding='utf-8-sig'));scope=json.loads(a.scope.read_text(encoding='utf-8-sig'))
    if m.get('researchOnly') is not True or (root/'native-lab/MTGA.exe').exists():raise ValueError('An isolated headless research runtime is required')
    if a.output.exists():raise FileExistsError(a.output)
    classes=a.output.parent/(a.output.stem+'-classes');classes.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).with_name('ProjectForgeCards.java');snapshot=classes/source.name;shutil.copy2(source,snapshot)
    jars=[runtime/'forge.jar',runtime/'gson.jar'];engine=root/'build/ForgeBackend/classes';cp=os.pathsep.join(str(p) for p in [classes,engine,*jars])
    compiler=subprocess.run([str(a.javac),'-version'],capture_output=True,text=True,check=True).stdout.strip()
    if not compiler.startswith('javac 17.'):raise ValueError('Use pinned Java 17')
    hashes={r['name']:m['cards'][r['name']]['forgeScriptSha256'] for r in scope['cards']}
    engine_classes=sorted(engine.glob('ForgeLandEngine*.class'))
    if not engine_classes:raise ValueError('Pinned engine classes are missing')
    before={str(p):sha(p) for p in [a.config,a.scope,manifest,*jars,source,*engine_classes]}
    subprocess.run([str(a.javac),'-J-Xmx512m','-encoding','UTF-8','-cp',cp,'-d',str(classes),str(snapshot)],check=True,timeout=60)
    with a.output.with_suffix('.log').open('w',encoding='utf8') as log:
        subprocess.run([str(Path(config['javaHome'])/'bin/java.exe'),'-Xmx1024m','-XX:ActiveProcessorCount=2','-cp',cp,'ProjectForgeCards',str(runtime),str(a.scope),str(a.output)],cwd=runtime,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if any(sha(Path(path))!=digest for path,digest in before.items()):raise RuntimeError('Projection inputs changed during generation')
    result=json.loads(a.output.read_text(encoding='utf8'));result['provenance']=dict(forgeJarSha256=sha(jars[0]),sourceScriptHashes=hashes,projectorSha256=sha(snapshot),inputs=before,compiler=compiler)
    a.output.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(dict(cards=len(result['cards']),tokens=len(result['tokens']),output=str(a.output),sha256=sha(a.output))))


if __name__=='__main__':main()
