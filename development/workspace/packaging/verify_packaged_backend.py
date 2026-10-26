"""Compare a real package against independently gameplay-tested engine classes."""
import argparse
import json
from pathlib import Path
from tester_common import sha, verify_tree


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--reference-classes', type=Path, action='append', required=True)
    p.add_argument('--expected-policy', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Choose a new verification receipt')
    manifest = verify_tree(a.package)
    build = json.loads((a.package/'backend-build.json').read_text())
    requirements = json.loads((a.package/'requirements.json').read_text())
    checks = []

    def check(label, passed):
        checks.append(dict(check=label, passed=bool(passed)))
        assert passed, label

    check('Rules source matches the recorded fresh compilation', build['sourceSha256'] == sha(a.package/'adapter-source/ForgeLandEngine.java'))
    check('Compiler is Java 17', build['compiler'].startswith('javac 17.'))
    compiled_variants = [v for v in requirements['forgeVariants'] if build['forgeJarSha256'] == v['files'][v['jar']]]
    check('Compilation uses one exact supported pinned Forge dependency', len(compiled_variants) == 1)
    check('Compilation uses the packaged Gson dependency', build['gsonSha256'] == sha(a.package/'third-party/gson/gson.jar'))
    classes = {p.name: sha(p) for p in (a.package/'backend').glob('ForgeLandEngine*.class')}
    check('Recorded and packaged engine classes agree exactly', bool(classes) and classes == build['classes'])
    for path in (a.package/'backend').glob('ForgeLandEngine*.class'):
        data = path.read_bytes()
        check('Java 17 binary format '+path.name, data[:4] == b'\xca\xfe\xba\xbe' and int.from_bytes(data[6:8], 'big') == 61)
    for reference in a.reference_classes:
        expected = {p.name: sha(p) for p in reference.glob('ForgeLandEngine*.class')}
        check('Exact independently tested binary classes '+str(reference), classes == expected)
    policy = json.loads(a.expected_policy.read_text())
    check('Independent policy is a verified checkpoint', not policy.get('researchOnly'))
    check('Packaged admission exactly matches that checkpoint', sha(a.package/'ForgeBackend/bridge_support.json') == sha(a.expected_policy))
    info = json.loads((a.package/'release-info.json').read_text())
    check('Release info has exactly the checkpoint card names', set(info['admittedNames']) == set(policy['verifiedNames']))
    result = dict(version=manifest['version'], checks=len(checks), results=checks, testedReferenceClasses=list(map(str, a.reference_classes)),
                  scope='Manifest, source, dependency and binary equivalence to separately gameplay-tested references. Not a fresh installed-game or recipient-PC test.')
    a.output.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(dict(version=result['version'], checks=len(checks), report=str(a.output))))


if __name__ == '__main__':
    main()
