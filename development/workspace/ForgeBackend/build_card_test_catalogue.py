"""Create per-Arena-card test requirements and independently sourced proposals.

Static plans and source-qualified proposals never count as executed tests or
admission. Unknown directives, choices and conditional effects remain explicit.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import zipfile

WORDS={'a':1,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
KEYWORDS={'Flying','Reach','Vigilance','Haste','Defender','Flash','Lifelink','First Strike','Double Strike','Menace','Hexproof','Deathtouch','Trample'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def parameters(value):
    return {k.strip():v.strip() for part in value.split('|') if '$' in part for k,v in [part.split('$',1)] if not k.strip().endswith('Description') and not k.strip().startswith('AI')}


def parse(text):
    rows=[];fields=defaultdict(list);svars={};faces=0;unknown=[]
    known={'Name','ManaCost','Types','PT','Oracle','K','A','T','S','R','SVar','DeckHas','DeckHints','AI','Colors','V','SetInfo','AlternateMode','AlternateCost'}
    for i,line in enumerate(text.splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):continue
        if line=='ALTERNATE':faces+=1;continue
        if ':' not in line:unknown.append(dict(line=i,text=line));continue
        k,v=line.split(':',1);fields[k].append(v)
        if k not in known:unknown.append(dict(line=i,directive=k))
        if k=='SVar' and ':' in v:
            name,v=v.split(':',1);svars[name]=v
        if k in ('A','T','S','R','SVar'):rows.append(dict(kind=k,line=i,params=parameters(v)))
    return dict(fields=dict(fields),rows=rows,svars=svars,extraFaces=faces,unknown=unknown)


def native_fixed_effects(texts):
    text=html.unescape(re.sub('<[^>]+>','', '\n'.join(texts))).replace('\\n','\n').strip()
    effects=[]
    while text:
        m=re.match(r'^(Draw (a|one|two|three|four|five|six|seven|eight|nine|ten|[0-9]+) cards?\.|You gain (one|two|three|four|five|six|seven|eight|nine|ten|[0-9]+) life\.)',text)
        if not m:return None
        raw=m.group(2) or m.group(3);amount=WORDS.get(raw,int(raw) if raw.isdecimal() else None)
        if amount is None or not 1<=amount<=20:return None
        effects.append(dict(kind='Draw' if m.group(2) else 'GainLife',amount=amount))
        text=text[m.end():].strip()
    return effects or None


def forge_fixed_effects(parsed):
    fields=parsed['fields']
    if parsed['extraFaces'] or parsed['unknown'] or fields.get('K') or any(fields.get(k) for k in ('T','S','R')) or len(fields.get('A',[]))!=1:return None
    first=parameters(fields['A'][0]);effects=[];seen=set()
    while True:
        api=first.get('SP',first.get('DB'))
        allowed={'SP','DB','Defined','NumCards','LifeAmount','SubAbility','StackDescription'}
        if api not in ('Draw','GainLife') or set(first)-allowed or first.get('Defined','You')!='You':return None
        number=first.get('NumCards','1') if api=='Draw' else first.get('LifeAmount','')
        if not number.isdecimal() or not 1<=int(number)<=20:return None
        effects.append(dict(kind=api,amount=int(number)))
        if 'SubAbility' not in first:break
        key=first['SubAbility']
        if key in seen or key not in parsed['svars']:return None
        seen.add(key);first=parameters(parsed['svars'][key])
    if set(parsed['svars'])!=seen:return None
    return effects


def cost(row):
    tokens=re.findall(r'o([0-9]+|[WUBRG])',row['manaText'])
    if not tokens or ''.join('o'+t for t in tokens)!=row['manaText']:return None
    total=sum(int(t) if t.isdecimal() else 1 for t in tokens)
    if total>20:return None
    return dict(total=total,generic=sum(int(t) for t in tokens if t.isdecimal()),symbols=[t for t in tokens if not t.isdecimal()])


def requirements(card,parsed):
    result={'identity.arena-forge-equivalence','construction','presentation.assets','presentation.zone-lifecycle','sequence.complete-match'}
    f=parsed['fields'] if parsed else {}
    types=' '.join(f.get('Types',[])).split()
    if 'Land' in types:result.update(('land.legality','mana.production'))
    else:result.update(('cast.legal-timing','cast.payment','cast.response-window','cast.resolution'))
    if 'Creature' in types:
        result.update(('combat.attack-legality','combat.block-legality','combat.damage','combat.death','combat.summoning-sickness'))
    for api in card['apis']:result.add('effect.'+api)
    for kw in card['keywords']:result.add('keyword.'+kw.split(':',1)[0])
    if parsed:
        if parsed['extraFaces']:result.add('identity.face-lifecycle')
        if parsed['unknown']:result.add('review.unknown-script-directives')
        for row in parsed['rows']:
            p=row['params'];kind=row['kind']
            if kind=='T':result.update(('trigger.condition','trigger.timing','trigger.order','trigger.identity'))
            if kind=='S':result.update(('continuous.applies','continuous.expires','continuous.layers'))
            if kind=='R':result.update(('replacement.applies','replacement.choice','replacement.order'))
            if 'AB' in p:result.update(('activation.legality','activation.cost','activation.response','activation.resolution'))
            if any(k.startswith(('ValidTgt','Target','MinTgt','MaxTgt')) for k in p):result.update(('target.legal','target.illegal','target.cancel','target.invalidated','target.hexproof-owner'))
            if any(k.startswith('Condition') for k in p) or kind=='SVar' and any(k in p for k in ('Count','Number','PlayerCountPlayers')):result.add('resolution.conditional-branches')
        if any(b.startswith('bridge.choices') or b=='bridge.zone_choices' for b in card['blockers']):result.add('decision.human-no-ai-fallback')
    for b in card['blockers']:
        if b.startswith('mapping.'):result.add('identity.'+b)
    return sorted(result)


def build(a):
    if a.output.exists():raise ValueError('Choose a new catalogue evidence directory')
    audit=json.loads(a.audit.read_text(encoding='utf8'));mappings=json.loads(a.mappings.read_text(encoding='utf8'));policy=json.loads(a.policy.read_text(encoding='utf-8-sig'))
    provenance=audit['summary']['provenance']
    if policy.get('researchOnly') or provenance['policySha256']!=sha(a.policy):raise ValueError('Audit and verified baseline differ')
    if provenance['sourceDatabaseSha256']!=sha(a.database) or mappings['sourceDatabaseSha256']!=sha(a.database) or provenance['sourceForgeScriptsSha256']!=sha(a.scripts):raise ValueError('Source data changed after audit')
    by=defaultdict(list)
    for row in mappings['printings']:by[row['name']].append(row)
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True)
    texts={}
    for ability,text in db.execute('SELECT a.Id,l.Loc FROM Abilities a JOIN Localizations_enUS l ON a.TextId=l.LocId WHERE l.Formatted=1'):
        texts.setdefault(ability,[]).append(text)
    hidden={g:t for g,t in db.execute('SELECT GrpId,HiddenAbilityIds FROM Cards')};db.close()
    rows=[];proposals=[];counts=Counter()
    with zipfile.ZipFile(a.scripts) as archive:
        for card in audit['cards']:
            name=card['name'];parsed=None;raw=None
            if len(card['forgeScripts'])==1:
                raw=archive.read(card['forgeScripts'][0])
                if hashlib.sha256(raw).hexdigest()!=card['sourceForgeScriptSha256']:raise ValueError('Script mismatch: '+name)
                parsed=parse(raw.decode('utf-8-sig'))
            required=requirements(card,parsed);counts.update(required)
            row=dict(name=name,arenaGrpIds=card['arenaGrpIds'],forgeScripts=card['forgeScripts'],sourceScriptSha256=card['sourceForgeScriptSha256'],
                construction=card['construction'],apis=card['apis'],keywords=card['keywords'],requirements=required,
                implementationBlockers=[b for b in card['blockers'] if not b.startswith('verification.')],
                admission='existing-bounded' if name in policy['verifiedNames'] else 'not-admitted',
                executionCoverage='not-evaluated-by-this-static-plan',generatedTemplates=[],unknownDirectives=parsed['unknown'] if parsed else [])
            eligible=[p for p in by[name] if not p['digitalOnly'] and not p['rebalanced'] and not p['linkedFaces'] and not hidden.get(p['grpId'])]
            if parsed and eligible and card['construction']=='constructed-not-playtested':
                printing=min(eligible,key=lambda p:(p['grpId']!=policy.get('preferredPrintings',{}).get(name),p['grpId']))
                native=[]
                for ability in printing['abilityIds']:
                    values=texts.get(ability,[])
                    if len(values)!=1:break
                    native.append(values[0])
                if len(native)==len(printing['abilityIds']):
                    native_effects=native_fixed_effects(native);forge_effects=forge_fixed_effects(parsed)
                    mana=cost(printing)
                    forge_cost=' '.join(parsed['fields'].get('ManaCost',[])).split()
                    matching_cost=mana and all(t.isdecimal() or t in ('W','U','B','R','G') for t in forge_cost) and sum(int(t) for t in forge_cost if t.isdecimal())==mana['generic'] and Counter(t for t in forge_cost if not t.isdecimal())==Counter(mana['symbols'])
                    if matching_cost and set(printing['types']) in ({'Instant'},{'Sorcery'}) and native_effects and native_effects==forge_effects:
                        row['generatedTemplates'].append('fixed-untargeted-draw-life-v1')
                        proposals.append(dict(name=name,template='fixed-untargeted-draw-life-v1',printing=printing['grpId'],nativeTypes=printing['types'],
                            oracleEffects=native_effects,nativeTexts=native,nativeAbilityIds=printing['abilityIds'],printedCost=mana,
                            sourceScriptSha256=card['sourceForgeScriptSha256'],status='source-qualified-proposal-not-executed',
                            remainingGates=['strict human callback coverage','actual costs and timing','ordered resolution','native assets/controls','full matches']))
                    f=parsed['fields'];keywords=f.get('K',[])
                    plain_creature=(matching_cost and 'Creature' in printing['types'] and set(printing['types'])<={'Creature','Artifact'} and not printing['supertypes'] and
                        not parsed['extraFaces'] and not parsed['unknown'] and not parsed['svars'] and not any(f.get(k) for k in ('A','T','S','R')) and set(keywords)<=KEYWORDS and
                        len(keywords)==len(set(keywords)) and sorted(v.casefold() for v in native)==sorted(v.casefold() for v in keywords) and
                        re.fullmatch(r'[0-9]+/[0-9]+',' '.join(f.get('PT',[]))) and f['PT'][0]==printing['power']+'/'+printing['toughness'] and
                        all(t in ' '.join(f.get('Types',[])).split() for t in printing['types']+printing['subtypes']))
                    if plain_creature:
                        row['generatedTemplates'].append('simple-creature-cast-v1')
                        proposals.append(dict(name=name,template='simple-creature-cast-v1',printing=printing['grpId'],nativeTypes=printing['types'],nativeTexts=native,nativeAbilityIds=printing['abilityIds'],
                            oracleCharacteristics=dict(power=int(printing['power']),toughness=int(printing['toughness'])),keywords=keywords,printedCost=mana,
                            sourceScriptSha256=card['sourceForgeScriptSha256'],status='source-qualified-cast-proposal-not-executed',
                            remainingGates=['actual costs and timing','each keyword behavior and combat','strict human callback coverage','native assets/controls','full matches']))
            rows.append(row)
    assert len(rows)==len({r['name'] for r in rows})==audit['summary']['arenaNames']
    result=dict(schema=1,arenaNames=len(rows),existingAdmission=len(policy['verifiedNames']),newAdmissions=0,executedCases=0,
        provenance=dict(auditSha256=sha(a.audit),mappingsSha256=sha(a.mappings),databaseSha256=sha(a.database),scriptsSha256=sha(a.scripts),policySha256=sha(a.policy),generatorSha256=sha(Path(__file__))),
        requiredCapabilityCounts=dict(counts.most_common()),proposalCount=len(proposals),cards=rows,
        scope='Static requirement inventory and narrowly source-qualified proposals. No generated proposal is counted as executed, supported or admitted. Requirements are minimum review obligations, not exhaustive interaction proofs.')
    a.output.mkdir(parents=True)
    (a.output/'card-test-catalogue.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf8')
    (a.output/'test-proposals.json').write_text(json.dumps(dict(schema=1,provenance=result['provenance'],proposals=proposals,newAdmissions=0,executedCases=0),indent=2,ensure_ascii=False),encoding='utf8')
    (a.output/'SUMMARY.md').write_text(f"# Arena card test catalogue\n\n{len(rows):,} Arena names mapped to minimum test requirements. {len(proposals)} independently source-qualified proposals across fixed draw/life and simple-creature casting templates. Zero cases executed or cards newly admitted by this scan.\n\nA successful creature cast does not prove its keywords or combat. Unknown directives and missing human decisions remain explicit review obligations. Native rendering and complete games remain separate.\n",encoding='utf8')
    print(json.dumps(dict(cards=len(rows),sourceQualifiedProposals=len(proposals),newAdmissions=0,output=str(a.output))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('audit','mappings','policy','database','scripts','output'):p.add_argument('--'+key,type=Path,required=True)
    build(p.parse_args())
