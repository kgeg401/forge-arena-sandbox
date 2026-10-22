"""Apply/rollback a real candidate ZIP in a disposable launcher installation."""
import argparse
import json
from pathlib import Path
import uuid
from setup_client import install_launcher
from tester_common import sha, verify_tree, metadata_recipe
from update_tester import apply_archive, rollback


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--expected-policy',type=Path,help='Independently verified gameplay policy when this candidate deliberately expands admission')
    args=parser.parse_args()
    folder=args.workspace.resolve()/('candidate-roundtrip-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    install=folder/'Disposable Client'
    baseline=verify_tree(args.baseline)
    install_launcher(args.baseline,install)
    profile=install/'data/native-lab/local-profile'
    (profile/'decks.json').write_text('{"fixture":"preserve these exact deck bytes"}')
    (profile/'collection.json').write_text('{"fixture":"preserve these exact collection bytes"}')
    before={p.name:sha(p) for p in profile.iterdir()}
    checks=[]
    def check(label,ok):
        assert ok,label
        checks.append(label)
    applied=apply_archive(install,args.candidate)
    active=json.loads((install/'active-version.json').read_text())
    app=install/'versions'/active['version'];candidate=verify_tree(app)
    check('Actual candidate ZIP activates a newer release',active['version']==candidate['version'] and active['version']!=baseline['version'])
    check('Original adapter stays available for rollback',(install/'versions'/baseline['version']).is_dir())
    check('Candidate update retains all saved fixture bytes',before=={p.name:sha(p) for p in profile.iterdir()})
    check('Updated package includes catalogue and support helpers',all((app/p).is_file() for p in ('ForgeBackend/arena_catalog.py','ForgeBackend/card_support.py','ForgeBackend/card-support-index.json')))
    check('New helper/index inputs invalidate derived metadata',metadata_recipe(app)!=metadata_recipe(install/'versions'/baseline['version']))
    index=json.loads((app/'ForgeBackend/card-support-index.json').read_text(encoding='utf8'))
    check('Candidate diagnostics match its exact admission policy',index['provenance']['policySha256']==sha(app/'ForgeBackend/bridge_support.json'))
    info=json.loads((app/'release-info.json').read_text())
    if args.expected_policy:
        expected=json.loads(args.expected_policy.read_text())
        check('Expected policy is a verified release policy',not expected.get('researchOnly'))
        check('Candidate policy exactly matches the independent verified checkpoint',sha(app/'ForgeBackend/bridge_support.json')==sha(args.expected_policy))
        check('Candidate release info names exactly the verified checkpoint',set(info['admittedNames'])==set(expected['verifiedNames']))
    else:
        check('Candidate keeps the verified gameplay checkpoint',set(info['admittedNames'])==set(json.loads((args.baseline/'release-info.json').read_text())['admittedNames']))
    undone=rollback(install)
    check('Rollback selects the original real release',json.loads((install/'active-version.json').read_text())['version']==baseline['version'])
    check('Rollback also retains every saved fixture byte',before=={p.name:sha(p) for p in profile.iterdir()})
    check('Rollback pauses automatic updates',json.loads((install/'sandbox-install.json').read_text())['automaticUpdates'] is False)
    report=dict(checks=len(checks),passed=checks,candidateArchiveSha256=sha(args.candidate),expectedPolicySha256=sha(args.expected_policy) if args.expected_policy else None,applied=applied,rollback=undone,
                scope='Actual package activation/rollback in a disposable launcher installation. No game copy, game launch, installed-client switch or recipient-PC test.')
    (folder/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(checks=len(checks),evidence=str(folder/'report.json')),indent=2))


if __name__=='__main__':
    main()
