"""Propose a plain-creature research policy from both installed source datasets.

This never changes production admission. Successful gameplay/native evidence is
required separately before a caller can promote a proposed family.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import zipfile
from runtime_paths import ROOT, FORGE_SCRIPTS


def prepare(base_policy,output):
    if output.exists():raise ValueError('Choose a new research output folder; prior evidence is preserved')
    policy=json.loads(base_policy.read_text())
    if policy.get('researchOnly'):raise ValueError('Start from a verified production policy')
    folder=ROOT/'research/card-coverage'
    coverage=json.loads((folder/'arena-forge-coverage.json').read_text(encoding='utf8'))
    mappings=json.loads((folder/'arena-printing-mappings.json').read_text(encoding='utf8'))
    if hashlib.sha256(FORGE_SCRIPTS.read_bytes()).hexdigest()!=coverage['summary']['sourceForgeScriptsSha256']:raise ValueError('Forge scripts changed since catalogue scan')
    by=defaultdict(list)
    for row in mappings['printings']:by[row['name']].append(row)
    names=[];definitions={}
    with zipfile.ZipFile(FORGE_SCRIPTS) as archive:
        for card in coverage['cards']:
            name=card['name']
            if name in policy['verifiedNames'] or len(card['forgeScripts'])!=1:continue
            row=min(by[name],key=lambda r:(r['rebalanced'],r['grpId']))
            if 'Creature' not in row['types'] or set(row['types'])-{'Creature','Artifact'} or row['abilityIds'] or row['supertypes'] or row['digitalOnly'] or row['linkedFaces']:continue
            text=archive.read(card['forgeScripts'][0]).decode('utf-8-sig');fields=dict(line.split(':',1) for line in text.splitlines() if ':' in line)
            if any(re.match(r'^(A|T|S|R|K|SVar):|^ALTERNATE',line) for line in text.splitlines()) or fields.get('Oracle','').strip():continue
            if not re.fullmatch(r'-?\d+/-?\d+',fields.get('PT','')):continue
            cost=fields.get('ManaCost','').split()
            if any(v not in ('W','U','B','R','G') and not v.isdecimal() for v in cost):continue
            names.append(name);definitions[name]=dict(grpId=row['grpId'],script=card['forgeScripts'][0],scriptSha256=hashlib.sha256(text.encode()).hexdigest(),printedCost=cost,power=row['power'],toughness=row['toughness'])
    policy['researchOnly']=True
    for name in ['Swamp','Mountain','Forest',*names]:
        if name in policy['verifiedNames']:continue
        policy['verifiedNames'].append(name)
        policy['preferredPrintings'][name]=min(by[name],key=lambda r:(r['rebalanced'],r['grpId']))['grpId']
        if name in definitions:policy.setdefault('colorIdentities',{})[name]=list(dict.fromkeys(v for v in definitions[name]['printedCost'] if v in ('W','U','B','R','G')))
    for name,color,id,symbol in [('Swamp','Black',1003,'B'),('Mountain','Red',1004,'R'),('Forest','Green',1005,'G')]:
        policy['nativeBasicManaAbilityIds'][name]=id;policy['nativeManaColors'][name]=color;policy.setdefault('colorIdentities',{})[name]=[symbol]
    output.mkdir(parents=True)
    (output/'research-policy.json').write_text(json.dumps(policy,indent=2))
    (output/'plain-creature-candidates.json').write_text(json.dumps(names,indent=2))
    (output/'plan.json').write_text(json.dumps(dict(researchOnly=True,sourceDatabaseSha256=coverage['summary']['sourceDatabaseSha256'],forgeScriptsSha256=coverage['summary']['sourceForgeScriptsSha256'],basePolicySha256=hashlib.sha256(base_policy.read_bytes()).hexdigest(),candidates=definitions,scope='Source-qualified candidates only; not gameplay or production admission.'),indent=2))
    print(json.dumps(dict(creatures=len(names),researchOnly=True,output=str(output)),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-policy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();prepare(a.base_policy,a.output)
