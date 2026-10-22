import hashlib,json,os,pathlib,shutil,subprocess,sys

subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('build_card_coverage.py'))],check=True)
subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('verify_card_manifest.py'))],check=True)

ROOT=pathlib.Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox')
RUNTIME=ROOT/'forge-runtime'
RUNTIME.mkdir(exist_ok=True)
INSTALL=pathlib.Path(r'C:\Users\loula\Games\Forge')
jar=INSTALL/'forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar'
identity_path=ROOT/'research'/'forge-backend-identity.json'
digest=hashlib.sha256(jar.read_bytes()).hexdigest()
if identity_path.exists() and json.loads(identity_path.read_text())['sha256']!=digest:
    raise SystemExit('Installed Forge changed; review its API/evidence before replacing the pinned backend.')
shutil.copy2(jar,RUNTIME/'forge.jar')
shutil.copy2(pathlib.Path(r'C:\Users\loula\Documents\FlyMagicLab\runtime\gson.jar'),RUNTIME/'gson.jar')
if not (RUNTIME/'res').exists():
    subprocess.run(['powershell.exe','-NoProfile','-Command',"New-Item -ItemType Junction -Path 'D:\\GAMES\\CodexAssets\\ForgeArenaSandbox\\forge-runtime\\res' -Target 'C:\\Users\\loula\\Games\\Forge\\res' | Out-Null"],check=True)
(RUNTIME/'forge.profile.properties').write_text('userDir=D:/GAMES/CodexAssets/ForgeArenaSandbox/forge-runtime/user\ncacheDir=D:/GAMES/CodexAssets/ForgeArenaSandbox/forge-runtime/cache\n')
identity_path.write_text(json.dumps({'installedJar':str(jar),'sha256':digest,'runtime':str(RUNTIME),'profile':'private user/cache; installed resources are read through a junction'},indent=2))
classes=ROOT/'build'/'ForgeBackend'/'classes';classes.mkdir(parents=True,exist_ok=True)
compiler=r'C:\Users\loula\Games\ForgeRuntime-Java17\jdk-17.0.20.1+1\bin\javac.exe'
source=pathlib.Path(__file__).with_name('ForgeLandEngine.java')
subprocess.run([compiler,'-cp',str(RUNTIME/'forge.jar')+';'+str(RUNTIME/'gson.jar'),'-d',str(classes),str(source)],check=True)
print('Compiled isolated Forge backend')
