"""Read-only package/runtime admission check, including explicit experimental names.

Works with a disposable preview or an installed runtime. This does not install,
launch, mutate profiles, or certify card effects; rendered acceptance is separate.
"""
import argparse
import json
from pathlib import Path
from tester_common import sha, verify_tree


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def verify(a):
    package=a.package.resolve();config=read(a.config);root=Path(config['privateRoot']);lab=root/'native-lab'
    tree=verify_tree(package);info=read(package/'release-info.json');policy_path=package/'ForgeBackend/bridge_support.json'
    policy=read(policy_path);experimental=read(package/'ForgeBackend/experimental-admission.json')
    verified=set(policy['verifiedNames']);extra=set(experimental['cards']);expected=verified|extra
    manifest=read(lab/'bridge-card-manifest.json');catalog=read(lab/'deck-catalog.json');checks=[]
    def check(label,value):
        checks.append(dict(check=label,passed=bool(value)))
        if not value:raise AssertionError(label)
    check('Verified and experimental inventories remain separate',not verified&extra and not policy.get('researchOnly'))
    check('Release metadata has exactly both declared inventories',set(info['admittedNames'])==verified and set(info['experimentalNames'])==extra)
    check('Production metadata shares the packaged policy',manifest['policySha256']==catalog['policySha256']==experimental['policySha256']==sha(policy_path) and not manifest.get('researchOnly'))
    check('Explicit experimental status is retained',manifest.get('experimentalAdmission') is True and set(manifest['experimentalNames'])==extra and all(c.get('experimental') and c.get('verified') is False for c in experimental['cards'].values()))
    primary={n for n,c in manifest['cards'].items() if c.get('admitted') and not any(c.get(k) for k in ('token','facePresentation','emblemPresentation'))}
    check('Runtime admits exactly the consumer primary names',primary==expected)
    check('Deck editor admits exactly the same names',{c['name'] for c in catalog['cards'] if c.get('matchSupported')}==expected)
    check('Blocked cards are not admitted',not set(experimental['blockedCards'])&expected)
    check('Catalogue and overlay use the same owned database',manifest['sourceDatabaseSha256']==catalog['sourceDatabaseSha256']==experimental['sourceDatabaseSha256'])
    check('Pinned Forge scripts match the overlay',sha(Path(config.get('forgeResourcesRoot',config['forgeInstall']))/'res/cardsfolder/cardsfolder.zip')==manifest['sourceForgeScriptsSha256']==experimental['sourceForgeScriptsSha256'])
    for name in ('NativeHost.dll','LocalTransport.dll'):
        check('Loaded bridge file matches package: '+name,sha(lab/'BepInEx/plugins/ForgeArenaSandbox'/name)==sha(package/'binaries'/name))
    for path in (package/'backend').glob('*.class'):
        check('Runtime rules class matches package: '+path.name,sha(root/'build/ForgeBackend/classes'/path.name)==sha(path))
    if a.require_home:
        from launch_tester import win_processes
        launch=read(lab/'launch-receipt.json');host=read(lab/'native-host-status.json');ui=read(lab/'client-ui-status.json')
        check('Native process is running from this private runtime',any(p['ProcessId']==launch['pid'] and p.get('ExecutablePath') and Path(p['ExecutablePath']).resolve()==(lab/'MTGA.exe').resolve() for p in win_processes()))
        check('Native launch has zero network capabilities',launch['appContainer'] and launch['capabilityCount']==0 and launch['networkCapability'] is False)
        check('Original Home is ready without a reported gap',ui['screen']=='home' and ui['nativeHome'] and ui['nativeNavigation'] and not ui.get('error') and host['realDatabase'] and not host.get('gap'))
    result=dict(passed=True,version=info['version'],verified=len(verified),experimental=len(extra),primary=len(expected),checks=checks,packageManifestSha256=sha(package/'release-manifest.json'),runtimeManifestSha256=sha(lab/'bridge-card-manifest.json'),scope=__doc__)
    if a.output.exists():raise FileExistsError(a.output)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','scope')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('package','config','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--require-home',action='store_true');verify(p.parse_args())
