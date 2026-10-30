"""Audit a captured deck union against owned Arena metadata and pinned Forge scripts.

An identity match never implies working gameplay. All remaining scenarios stay pending.
"""
import argparse
from collections import Counter, defaultdict
import hashlib,json,sqlite3,zipfile,re
from pathlib import Path
from arena_catalog import clean_name,indexed_printings

def audit(cards_file,database,scripts,policy,manifest,output):
    source=json.loads(cards_file.read_text(encoding='utf-8'))
    if source.get('complete') is not True:raise ValueError('Collect the full ranking before auditing its pool')
    admission=json.loads(policy.read_text(encoding='utf-8-sig'))
    runtime=json.loads(manifest.read_text(encoding='utf-8-sig'))
    db=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    rows={r['GrpId']:dict(r) for r in db.execute('SELECT c.*,l.Loc AS EnglishName FROM Cards c JOIN Localizations_enUS l ON l.LocId=c.TitleId AND l.Formatted=1')}
    names=defaultdict(list)
    for row in indexed_printings(rows):names[clean_name(row['EnglishName'])].append(row)
    definitions=defaultdict(list)
    with zipfile.ZipFile(scripts) as archive:
        for path in archive.namelist():
            if not path.endswith('.txt'):continue
            raw=archive.read(path);text=raw.decode('utf-8-sig')
            faces=[line[5:].strip() for line in text.splitlines() if line.startswith('Name:')]
            # Both faces must belong to the same definition. Do not bind a split
            # card merely because a different card shares its front-face name.
            aliases=set(faces)
            if len(faces)>1:aliases.add(' // '.join(faces))
            for name in aliases:definitions[name].append(dict(path=path,sha256=hashlib.sha256(raw).hexdigest()))
    results=[]
    for card in source['cards']:
        name=card['name'];native=names.get(name,[]);front=name.split(' // ')[0]
        alias=False
        if not native and front!=name:
            required=set(name.split(' // '))
            native=[r for r in names.get(front,[]) if required<={clean_name(r['EnglishName'])}|{
                clean_name(rows[int(i)]['EnglishName']) for i in re.findall(r'\d+',r.get('LinkedFaceGrpIds') or '') if int(i) in rows}]
            alias=bool(native)
        native_name=front if alias else name
        rule=definitions.get(native_name,[])
        status='outside-installed-arena' if not native else 'missing-forge-script' if not rule else 'ambiguous-forge-script' if len(rule)!=1 else 'identity-candidate'
        entry={**card,'status':status,'nativeName':native_name if native else None,'splitNameAliasNeedsReview':alias,
               'nativeGrpIds':sorted({r['GrpId'] for r in native}),'scripts':rule,
               'previouslyAdmitted':native_name in admission['verifiedNames'],
               'runtimeMapped':native_name in runtime.get('cards',{}),'gameplayTest':'pending','newAdmission':False}
        results.append(entry)
    report=dict(schema=1,arenaOnly=True,rankedDecks=50,distinctCards=len(results),counts=dict(Counter(r['status'] for r in results)),
                arenaCards=sum(bool(r['nativeGrpIds']) for r in results),previouslyAdmitted=sum(r['previouslyAdmitted'] for r in results),
                runtimeMapped=sum(r['runtimeMapped'] for r in results),newAdmissions=0,
                provenance={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [cards_file,database,scripts,policy,manifest]},cards=results)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['cards','provenance']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['cards','database','scripts','policy','manifest','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();audit(a.cards,a.database,a.scripts,a.policy,a.manifest,a.output)
