"""Read-only proof that the installed running client exposes the reviewed cards."""
import argparse
import hashlib
import json
from pathlib import Path
from tester_common import verify_tree,sha
from launch_tester import win_processes


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def verify(a):
    install=a.install_root.resolve();config=read(install/'sandbox-install.json');active=read(install/'active-version.json');app=install/'versions'/active['version'];release=verify_tree(app)
    policy=read(a.policy);expected=set(policy['verifiedNames']);checks=[]
    def check(label,value):
        checks.append(dict(check=label,passed=bool(value)))
        if not value:raise AssertionError(label)
    check('Selected release has the exact reviewed production policy',not policy.get('researchOnly') and sha(app/'ForgeBackend/bridge_support.json')==sha(a.policy))
    check('Release metadata lists exactly the reviewed card names',set(read(app/'release-info.json')['admittedNames'])==expected)
    data=Path(config['privateRoot']);lab=data/'native-lab';manifest=read(lab/'bridge-card-manifest.json');catalog=read(lab/'deck-catalog.json')
    # Match card_support.load_index: the versioned release takes precedence
    # over the research/runtime fallback. A normal launch need not copy it.
    index_path=app/'ForgeBackend/card-support-index.json'
    if not index_path.is_file():index_path=lab/'card-support-index.json'
    index=read(index_path)
    check('Runtime, deck builder and support report share the exact policy',manifest['policySha256']==catalog['policySha256']==index['provenance']['policySha256']==sha(a.policy))
    scripts=Path(config.get('forgeResourcesRoot',config['forgeInstall']))/'res/cardsfolder/cardsfolder.zip'
    check('Active support report belongs to the installed Forge engine and scripts',index['provenance']['forgeJarSha256']==sha(data/'forge-runtime/forge.jar') and index['provenance']['sourceForgeScriptsSha256']==sha(scripts))
    check('Runtime enables every reviewed name and no extra research card',not manifest.get('researchOnly') and {n for n,c in manifest['cards'].items() if c.get('admitted')}==expected)
    check('Deck builder enables the same names',set(c['name'] for c in catalog['cards'] if c.get('matchSupported'))==expected)
    launch=read(lab/'launch-receipt.json');host=read(lab/'native-host-status.json');ui=read(lab/'client-ui-status.json')
    check('Owned native client is actually running',any(p['ProcessId']==launch['pid'] and p.get('ExecutablePath') and Path(p['ExecutablePath']).resolve()==lab/'MTGA.exe' for p in win_processes()))
    check('Native launch has zero network capabilities',launch['appContainer'] and launch['capabilityCount']==0 and launch['networkCapability'] is False)
    check('Original Home is ready without a fidelity gap',ui['screen']=='home' and ui['nativeHome'] and ui['nativeNavigation'] and not ui['error'] and host['realDatabase'] and not host['gap'])
    old=read(a.before_profile/'decks.json');current=read(lab/'local-profile/decks.json');byid={d['id']:d for d in current['decks']};oldids={d['id'] for d in old['decks']}
    check('Every existing saved deck is unchanged',all(byid.get(d['id'])==d for d in old['decks']))
    added=[d for d in current['decks'] if d['id'] not in oldids]
    check('Only declared new sample decks were added',sorted(d['name'] for d in added)==sorted(a.allow_new_deck))
    mutable={'decks.json','decks.json.bak','seeded-decks.json','seeded-decks.json.bak'}
    for source in a.before_profile.rglob('*'):
        if source.is_file() and source.name not in mutable:
            target=lab/'local-profile'/source.relative_to(a.before_profile)
            check('Original profile file preserved: '+source.name,target.is_file() and sha(source)==sha(target))
    result=dict(passed=True,version=active['version'],cards=len(expected),nativePid=launch['pid'],policySha256=sha(a.policy),releaseManifestSha256=sha(app/'release-manifest.json'),supportIndexPath=str(index_path),checks=checks,newSampleDecks=[d['name'] for d in added],published=False)
    a.output.mkdir(parents=True,exist_ok=False);(a.output/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('install-root','policy','before-profile','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--allow-new-deck',action='append',default=[]);verify(p.parse_args())
