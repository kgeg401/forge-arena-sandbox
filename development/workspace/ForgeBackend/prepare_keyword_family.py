"""Source-qualify simple keyword creatures into a separate research policy.

No successful catalogue scan grants production admission. Every selected Forge
keyword must have an identical original Arena ability text; extra abilities,
traits, linked faces, digital cards and unusual costs are excluded.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zipfile
from runtime_paths import ROOT, DB, FORGE_SCRIPTS

ALLOWED = {'Flying', 'Reach', 'Vigilance', 'Haste', 'Defender', 'Flash',
           'Lifelink', 'First Strike', 'Double Strike', 'Menace', 'Hexproof'}


def prepare(base_policy, output, include_deathtouch=False):
    if output.exists():
        raise ValueError('Select a new evidence folder')
    policy = json.loads(base_policy.read_text())
    if policy.get('researchOnly'):
        raise ValueError('Start from a verified policy')
    folder = ROOT/'research/card-coverage'
    coverage = json.loads((folder/'arena-forge-coverage.json').read_text(encoding='utf8'))
    mappings = json.loads((folder/'arena-printing-mappings.json').read_text(encoding='utf8'))
    if hashlib.sha256(DB.read_bytes()).hexdigest() != coverage['summary']['sourceDatabaseSha256']:
        raise ValueError('Source database drift')
    if hashlib.sha256(FORGE_SCRIPTS.read_bytes()).hexdigest() != coverage['summary']['sourceForgeScriptsSha256']:
        raise ValueError('Source scripts drift')
    by = defaultdict(list)
    for row in mappings['printings']:
        by[row['name']].append(row)
    db = sqlite3.connect(DB.as_uri()+'?mode=ro', uri=True)
    definitions = {}
    with zipfile.ZipFile(FORGE_SCRIPTS) as archive:
        for card in coverage['cards']:
            name = card['name']
            if name in policy['verifiedNames'] or len(card['forgeScripts']) != 1:
                continue
            row = min(by[name], key=lambda r: (r['rebalanced'], r['grpId']))
            if ('Creature' not in row['types'] or set(row['types'])-{'Creature', 'Artifact'} or
                    row['supertypes'] or row['digitalOnly'] or row['linkedFaces'] or row['rebalanced']):
                continue
            if db.execute('SELECT HiddenAbilityIds FROM Cards WHERE GrpId=?', (row['grpId'],)).fetchone()[0]:
                continue
            raw = archive.read(card['forgeScripts'][0])
            text = raw.decode('utf-8-sig')
            fields = dict(line.split(':', 1) for line in text.splitlines() if ':' in line)
            keywords = re.findall(r'^K:(.+)$', text, re.M)
            allowed=ALLOWED | ({'Deathtouch'} if include_deathtouch else set())
            if not keywords or not set(keywords) <= allowed or len(keywords) != len(set(keywords)):
                continue
            if re.search(r'^(A|T|S|R|SVar):|^ALTERNATE', text, re.M):
                continue
            if not re.fullmatch(r'[0-9]+/[0-9]+', fields.get('PT', '')):
                continue
            if fields['PT'] != row['power']+'/'+row['toughness'] or not all(
                    value in fields.get('Types', '').split() for value in row['types']+row['subtypes']):
                continue
            cost = fields.get('ManaCost', '').split()
            if any(v not in ('W', 'U', 'B', 'R', 'G') and not v.isdecimal() for v in cost):
                continue
            native_cost = re.findall(r'o([0-9]+|[WUBRGC])', row['manaText'])
            def identity(parts):
                return sum(int(v) for v in parts if v.isdecimal()), Counter(v for v in parts if not v.isdecimal())
            if ''.join('o'+v for v in native_cost) != row['manaText'] or identity(cost) != identity(native_cost):
                continue
            native = []
            for ability in row['abilityIds']:
                result = list(db.execute('SELECT l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId WHERE l.Formatted=1 AND a.Id=?', (ability,)))
                if len(result) != 1:
                    break
                native.append(result[0][0])
            if len(native) != len(row['abilityIds']) or sorted(v.casefold() for v in native) != sorted(v.casefold() for v in keywords):
                continue
            definitions[name] = dict(grpId=row['grpId'], keywords=keywords, nativeTexts=native,
                abilityIds=row['abilityIds'], script=card['forgeScripts'][0],
                scriptSha256=hashlib.sha256(raw).hexdigest(), printedCost=cost,
                power=int(row['power']), toughness=int(row['toughness']))
    policy['researchOnly'] = True
    for name, definition in definitions.items():
        policy['verifiedNames'].append(name)
        policy['preferredPrintings'][name] = definition['grpId']
        policy.setdefault('colorIdentities', {})[name] = list(dict.fromkeys(v for v in definition['printedCost'] if v in ('W', 'U', 'B', 'R', 'G')))
    output.mkdir(parents=True)
    (output/'research-policy.json').write_text(json.dumps(policy, indent=2))
    (output/'keyword-candidates.json').write_text(json.dumps(definitions, indent=2))
    (output/'source-plan.json').write_text(json.dumps(dict(
        databaseSha256=coverage['summary']['sourceDatabaseSha256'],
        forgeScriptsSha256=coverage['summary']['sourceForgeScriptsSha256'],
        basePolicySha256=hashlib.sha256(base_policy.read_bytes()).hexdigest(),
        candidates=len(definitions), researchOnly=True,includeDeathtouch=include_deathtouch,
        scope='Exact keyword text qualification only; gameplay, decisions and rendering remain separate.'), indent=2))
    print(json.dumps(dict(candidates=len(definitions), output=str(output)), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-policy', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--include-deathtouch', action='store_true', help='Research candidates only; requires separate combat, native and admission checks')
    args = p.parse_args()
    prepare(args.base_policy, args.output,args.include_deathtouch)
