"""Enable private experimental commander roles only for captured Arena identities.

Does not add a card, change verified status, or prove partner-deck support.
The currently supported roles here are explicitly requested legendary creatures.
"""
import argparse,json,hashlib
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ('capture','manifest','output','report'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();capture=json.loads(a.capture.read_text());m=json.loads(a.manifest.read_text())
if a.output.exists() or a.report.exists():raise ValueError('Use fresh evidence paths')
if m.get('researchOnly') is not True or not capture.get('complete') or capture.get('format')!='commander':raise ValueError('Complete Commander capture and explicit research manifest required')
names=sorted({c['name'] for d in capture['decks'] for c in d['cards'] if c['board']=='commanders'});enabled=[];excluded={};changed=[]
for name in names:
    card=m['cards'].get(name)
    if not card or not card.get('admitted'):excluded[name]='Absent from admitted installed-Arena research identities';continue
    if 'Legendary' not in card['supertypes'] or 'Creature' not in card['types']:excluded[name]='Not a supported legendary-creature commander role';continue
    if not card.get('commanderAdmitted'):changed.append(name)
    card['commanderAdmitted']=True;enabled.append(name)
report=dict(schema=1,researchOnly=True,newCardIdentities=0,newVerifiedCards=0,enabled=enabled,newRoles=changed,excluded=excluded,sourceHashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in (a.capture,a.manifest,Path(__file__))},scope=__doc__)
m['experimentalCommanderRoleProvenance']=report
a.output.write_text(json.dumps(m,indent=2));a.report.write_text(json.dumps(report,indent=2));print(json.dumps(dict(enabled=len(enabled),newRoles=len(changed),excluded=len(excluded))))
