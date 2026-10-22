"""Conservative per-card bridge blockers from owned data, scripts and construction.

No static/constructor result can promote admission. This is a work queue, not a
claim of complete engine correctness, downloaded assets, or Arena availability.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv, hashlib, html, json, re, zipfile
from build_card_coverage import ROOT, FORGE, POLICY, norm

REPO=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/card-coverage'

# Each rule links to the implementation that imposes the boundary. Effect to
# callback hints are planning hints; polymorphic Forge effects can call more.
ISSUES={
 'mapping.no_script':('No unique Forge script candidate','ForgeBackend/build_card_coverage.py','matches=sorted'),
 'mapping.ambiguous':('Multiple candidate scripts need identity review','ForgeBackend/build_card_coverage.py','matches=sorted'),
 'engine.construction_failed':('Installed Forge cannot construct the candidate','ForgeBackend/CardCapabilityProbe.java','Card.fromPaperCard'),
 'engine.construction_diagnostic':('Forge construction emitted diagnostics needing review','ForgeBackend/CardCapabilityProbe.java','diagnostics.toString'),
 'engine.identity_mismatch':('Constructed Forge face names differ from the indexed script','ForgeBackend/CardCapabilityProbe.java','row.put("state"'),
 'engine.not_audited':('No complete source-matched constructor audit','ForgeBackend/CardCapabilityProbe.java','writer.write'),
 'bridge.mana_colors':('Mana production needs an explicitly mapped source and native ability identity','ForgeBackend/ForgeLandEngine.java','static SpellAbility manaAbility'),
 'bridge.mana_sources':('Other mana creatures, restricted sources and multiple options need adapters','ForgeBackend/ForgeLandEngine.java','static SpellAbility manaAbility'),
 'bridge.cost_form':('Additional cost forms require review beyond the admitted simple mana costs','ForgeBackend/ForgeLandEngine.java','static List<Map<String,Object>> manaCost'),
 'bridge.card_type':('Card type needs presentation beyond the bounded creature/instant/artifact/land slice','NativeHost/ForgeLandBridge.cs','if(identity.Instant)'),
 'bridge.faces':('Alternate faces/state transitions have no native identity lifecycle','NativeHost/ForgeLandBridge.cs','["overlayGrpId"]=identity.Grp'),
 'bridge.keywords':('Keyword icons, restrictions and combat choices are not translated generically','NativeHost/ForgeLandBridge.cs','["hasSummoningSickness"]'),
 'bridge.combat_assignment':('Special keyword or legacy ordered damage needs additional allocation support','ForgeBackend/ForgeLandEngine.java','Unmapped keyword combat damage allocation'),
 'bridge.legendary_choice':('Legend choices require admitted identities and a verified selection sequence','ForgeBackend/ForgeLandEngine.java','class PassiveController'),
 'bridge.damage_events':('Damage paths beyond the verified ordinary spell/combat cases need attribution review','ForgeBackend/ForgeLandEngine.java','Unmapped card damage outside resolving stack'),
 'bridge.counter_events':('Countered-spell event attribution is pinned to Essence Scatter','ForgeBackend/ForgeLandEngine.java','getName().equals("Essence Scatter")'),
 'bridge.activated':('Activated abilities require explicit recovered identity bindings and verified costs/choices','NativeHost/ForgeLandBridge.cs','private JArray Offers'),
 'bridge.triggers':('Stack ability identities are restricted to explicitly recovered bindings','ForgeBackend/ForgeLandEngine.java','Unmapped stack ability'),
 'bridge.replacements':('Replacement selection/events require a native adapter','ForgeBackend/ForgeLandEngine.java','class PassiveController'),
 'bridge.static':('Continuous ability/type/keyword changes need native representation','NativeHost/ForgeLandBridge.cs','private JObject CardObject'),
 'bridge.targets':('Target prompts require explicit recovered bindings or mapped cards','NativeHost/ForgeLandBridge.cs','private int TargetPrompt'),
 'bridge.player_targets':('Player-target interactions beyond the admitted Crypt path need verification','ForgeBackend/ForgeLandEngine.java','else if(target instanceof Player'),
 'bridge.tokens':('Token identities/creation mappings are explicit; only Hare Rabbit is mapped','ForgeBackend/bridge_support.json','"tokens"'),
 'bridge.counters':('Counters/loyalty/defense are absent from native object translation','NativeHost/ForgeLandBridge.cs','private JObject CardObject'),
 'bridge.choices':('Human choice would use an inherited AI callback without a native decision adapter','ForgeBackend/ForgeLandEngine.java','class PassiveController'),
 'bridge.effects':('Effect requires event/state translation beyond the verified slice','NativeHost/ForgeLandBridge.cs','private void AdoptState'),
 'bridge.extra_zones':('Extra-zone lifecycles require source-checked physical mappings and decisions','NativeHost/ForgeLandBridge.cs','private static int ZoneId'),
 'bridge.zone_choices':('Search/reorder/zone choices need a human selection adapter','ForgeBackend/ForgeLandEngine.java','class PassiveController'),
 'bridge.digital':('Digital/rebalanced identity and persistent modifications need version review','ForgeBackend/build_card_coverage.py','rebalanced=bool'),
 'verification.rules_text':('Candidate rules/face equivalence has not been reviewed','ForgeBackend/build_card_coverage.py','A match is not engine compatibility'),
 'verification.native_assets':('Printing asset resolution/rendering has not been exercised offline','ForgeBackend/bridge_support.json','"preferredPrintings"'),
 'verification.sequence':('No admitted complete scenario and native interaction evidence','ForgeBackend/bridge_support.json','"verifiedNames"'),
}
CHOICES={
 'Scry':['arrangeForScry'],'Surveil':['arrangeForSurveil'],
 'Charm':['chooseModeForAbility'],'ChooseNumber':['chooseNumber'],
 'ChooseColor':['chooseColor','chooseColors'],'ChooseType':['chooseSomeType'],
 'NameCard':['chooseCardName'],'ChooseCard':['chooseCardsForEffect','chooseSingleEntityForEffect'],
 'ChoosePlayer':['chooseSingleEntityForEffect'],'GenericChoice':['confirmAction','chooseModeForAbility'],
 'Sacrifice':['choosePermanentsToSacrifice'],'Discard':['chooseCardsToDiscardFrom'],
 'Dig':['chooseCardsForZoneChange'],'DigUntil':['chooseSingleCardForZoneChange'],
 'PeekAndReveal':['chooseSingleEntityForEffect'],'TwoPiles':['chooseCardsPile'],
 'ChangeTargets':['chooseNewTargetsFor'],'CopySpellAbility':['chooseTargetsFor'],
 'RollDice':['chooseRollToIgnore'],'Draft':['chooseSingleCardFace'],
 'Learn':['confirmAction','chooseSingleCardForZoneChange'],
}
KNOWN_EFFECTS={'PermanentCreature','PermanentNoncreature','Mana','Draw','GainLife','Token','ChangeZone','Counter','DealDamage','Cleanup'}
COUNTER_APIS={'PutCounter','PutCounterAll','RemoveCounter','RemoveCounterAll','MoveCounter','MultiplyCounter','Proliferate','AddOrRemoveCounter','ReplaceCounter'}
TOKEN_APIS={'Token','CopyPermanent','Amass','Incubate','Investigate','MakeCard','Clone','ReplaceToken','Cloak','Manifest','ManifestDread'}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def code_evidence(file,needle):
    path=REPO/file;lines=path.read_text(encoding='utf-8-sig').splitlines()
    found=[i+1 for i,line in enumerate(lines) if needle in line]
    if not found:raise ValueError(('Stale implementation anchor',file,needle))
    return dict(file=file,line=found[0],sha256=digest(path))

def script_features(text):
    """Structural directives only; Oracle/descriptions/AI hints are not rules."""
    rows=[];keywords=[];svars={};metadata=defaultdict(list)
    for number,line in enumerate(text.splitlines(),1):
        if not line or line.startswith('#') or ':' not in line:continue
        prefix,value=line.split(':',1);metadata[prefix].append(value.strip())
        if prefix=='K':keywords.append(dict(value=value.strip(),line=number))
        if prefix=='SVar':
            if ':' not in value:continue
            label,value=value.split(':',1);svars[label]=value
        if prefix not in ('A','S','T','R','SVar'):continue
        params={k.strip():v.strip() for part in value.split('|') if '$' in part for k,v in [part.split('$',1)] if not k.strip().endswith('Description') and not k.strip().startswith('AI')}
        if params:rows.append(dict(kind=prefix,line=number,params=params))
    return dict(rows=rows,keywords=keywords,metadata=dict(metadata),svars=svars)

def walk_traits(traits):
    for t in traits:
        yield t
        if t.get('subAbility'):yield from walk_traits([t['subAbility']])

def analyze(card,printings,text,compiled,policy,callback_names):
    name=card['name'];admitted=name in policy['verifiedNames'];f=script_features(text or '')
    blockers=set();findings=[];apis=set();params=[]
    def add(code,detail=None):
        blockers.add(code)
        if detail is not None:findings.append(dict(code=code,evidence=detail))
    if card['mapping']=='no-script-name-match':add('mapping.no_script')
    elif len(card['forgeScripts'])!=1:add('mapping.ambiguous')
    if len(card['forgeScripts'])==1:
        if compiled is None:add('engine.not_audited')
        elif compiled['status']=='construction-failed':add('engine.construction_failed',compiled.get('error'))
        elif compiled.get('diagnostics'):add('engine.construction_diagnostic',compiled['diagnostics'])
        if compiled and compiled.get('faces'):
            names=f['metadata'].get('Name',[]);constructed={norm(x['name']) for x in compiled['faces']}
            # Split cards can additionally have a combined original face.
            expected={norm(n) for n in names}
            if not expected<=constructed:add('engine.identity_mismatch',dict(scriptNames=names,constructedNames=sorted(constructed)))
        for row in f['rows']:
            params.append(row['params'])
            for k in ('AB','SP','DB'):
                if k in row['params']:apis.add(row['params'][k])
        if compiled:
            for face in compiled.get('faces',[]):
                for trait in walk_traits(face['traits']):
                    params.append(trait.get('params',{}))
                    if trait.get('api'):apis.add(trait['api'])
        types=set(t for p in printings for t in p['types'])
        costs=f['metadata'].get('ManaCost',[])
        native_mana=set(policy.get('nativeManaColors',{}))
        if 'Land' in types and name not in native_mana:add('bridge.mana_colors')
        if 'Land' not in types:
            for cost in costs:
                symbols=cost.split();colored=[x for x in symbols if x in 'WUBRG' and len(x)==1]
                if any(not x.isdecimal() and x not in ('W','U','B','R','G','C') for x in symbols):add('bridge.cost_form',cost)
        if types-{'Land','Creature','Instant','Sorcery','Artifact'} or ('Land' in types and name not in native_mana):add('bridge.card_type',sorted(types))
        if 'Creature' in types and any(re.match(r'(?i)^banding\b',k['value']) for k in f['keywords']):add('bridge.combat_assignment')
        if any('Legendary' in p['supertypes'] for p in printings):add('bridge.legendary_choice',dict(callbackHint='chooseSingleEntityForEffect',scope='Global legend SBA, including otherwise vanilla cards'))
        if len(f['metadata'].get('Name',[]))>1 or f['metadata'].get('AlternateMode') or any(p.get('linkedFaces') for p in printings):add('bridge.faces')
        gameplay_kw=[x for x in f['keywords'] if not x['value'].startswith('A deck can have any number')]
        if gameplay_kw:add('bridge.keywords',gameplay_kw)
        if any('AB' in p and p['AB']!='Mana' for p in params):add('bridge.activated')
        if name not in native_mana and 'Mana' in apis:add('bridge.mana_sources')
        for p in params:
            # The printed mana line misses alternative/additional SP costs.
            if 'Cost' in p and 'SP' in p:add('bridge.cost_form',dict(spellCost=p['Cost']))
        trait_kinds={t['kind'] for face in (compiled or {}).get('faces',[]) for t in face['traits']}
        if ('T' in f['metadata'] or 'trigger' in trait_kinds) and name not in ('Impassioned Orator','Hare Apparent'):add('bridge.triggers')
        if 'R' in f['metadata'] or 'replacement' in trait_kinds:add('bridge.replacements')
        if 'S' in f['metadata'] or 'static' in trait_kinds:add('bridge.static')
        target_values=sorted({p['ValidTgts'] for p in params if 'ValidTgts' in p})
        if target_values and name not in ('Divine Arrow','Unsummon','Essence Scatter','Emry, Lurker of the Loch','Aether Spellbomb',"Tormod's Crypt") and name not in policy.get('targetPromptBindings',{}):add('bridge.targets',target_values)
        if any(re.search(r'\b(Any|Player|Opponent)\b',v) for v in target_values):add('bridge.player_targets',target_values)
        if apis&TOKEN_APIS and name!='Hare Apparent':add('bridge.tokens',sorted(apis&TOKEN_APIS))
        if apis&COUNTER_APIS or types&{'Planeswalker','Battle'} or any('CounterType' in p or 'AddCounters' in p for p in params):add('bridge.counters')
        choices=sorted({method for api in apis for method in CHOICES.get(api,[])})
        if any(p.get('Optional')=='True' or p.get('OptionalDecider') for p in params):choices=sorted(set(choices)|{'confirmAction'})
        if choices:add('bridge.choices',dict(callbackHints=choices,matchedInstalledCallbacks=[m for m in choices if m in callback_names],scope='Structural planning hints; actual effect paths require dynamic tests'))
        extra=sorted(apis-KNOWN_EFFECTS)
        if extra:add('bridge.effects',extra)
        if apis&{'DealDamage','DamageAll','Fight','EachDamage'} and name!='Divine Arrow':add('bridge.damage_events')
        if 'Counter' in apis and name!='Essence Scatter':add('bridge.counter_events')
        zones={v for p in params for k in ('Origin','Destination','ChoiceZone') if k in p for v in p[k].split(',')}
        if apis&{'ChangeZone','ChangeZoneAll'} and name!='Unsummon':add('bridge.zone_choices')
        if zones-{'Any','Battlefield','Hand','Library','Graveyard','Stack'}:add('bridge.extra_zones',sorted(zones))
        if any(p.get('digitalOnly') or p.get('rebalanced') for p in printings):add('bridge.digital')
    if not admitted:
        blockers.update(('verification.rules_text','verification.native_assets','verification.sequence'))
    # Admission is source policy, never inferred by this scanner. Existing
    # admission has bounded evidence and may still expose known global gaps.
    implementation=[b for b in blockers if b.startswith('bridge.') or b.startswith('engine.') or b.startswith('mapping.')]
    status='verified-bounded-slice' if admitted else 'blocked' if implementation else 'candidate-needs-verification'
    family=next((f for f in policy.get('verificationFamilies',[]) if name in f['names']),{})
    return dict(name=name,arenaGrpIds=card['arenaGrpIds'],forgeScripts=card['forgeScripts'],mapping=card['mapping'],
        construction=(compiled or {}).get('status','not-audited'),admitted=admitted,status=status,
        blockers=sorted(blockers),findings=findings,apis=sorted(apis),keywords=[k['value'] for k in f['keywords']],
        tokenScripts=sorted({v for p in params for k in ('TokenScript','TokenScriptFrom') if k in p for v in p[k].split(',')}),
        sourceForgeScriptSha256=card.get('forgeScriptSha256'),
        gates=dict(catalogue='installed-primary-or-source-linked-rebalanced-metadata',rules=family.get('rules','bounded-scenarios') if admitted else 'candidate-not-equivalence-verified',
                   decisions=family.get('decisions','bounded-slice') if admitted else 'not-verified',assets=family.get('assets','observed-pinned-printing') if admitted else 'metadata-only',
                   sequences=family.get('sequences','bounded-native-and-headless-evidence') if admitted else 'not-tested'),
        digitalOnly=any(p.get('digitalOnly') for p in printings),rebalanced=any(p.get('rebalanced') for p in printings))

def build():
    policy=json.loads(POLICY.read_text());coverage=json.loads((OUT/'arena-forge-coverage.json').read_text(encoding='utf8'))
    mappings=json.loads((OUT/'arena-printing-mappings.json').read_text(encoding='utf8'))
    inputs=json.loads((OUT/'forge-compile-input.json').read_text(encoding='utf8'))
    rows=[json.loads(line) for line in (OUT/'forge-construction.jsonl').read_text(encoding='utf8').splitlines()]
    compiled={r['script']:r for r in rows}
    expected={r['script']:r['sha256'] for r in inputs['scripts']}
    if len(rows)!=len(expected) or {k:v['sha256'] for k,v in compiled.items()}!=expected:raise ValueError('Incomplete, duplicate or stale construction audit; run the pinned probe first')
    if digest(FORGE)!=inputs['sourceForgeScriptsSha256']:raise ValueError('Forge scripts changed since constructor probe input')
    callbacks=json.loads((OUT/'controller-callbacks.json').read_text());callback_names={c['name'] for c in callbacks}
    by_name=defaultdict(list)
    for p in mappings['printings']:by_name[p['name']].append(p)
    cards=[]
    with zipfile.ZipFile(FORGE) as archive:
        for c in coverage['cards']:
            text=archive.read(c['forgeScripts'][0]).decode('utf-8-sig') if len(c['forgeScripts'])==1 else None
            cards.append(analyze(c,by_name[c['name']],text,compiled.get(c['forgeScripts'][0]) if len(c['forgeScripts'])==1 else None,policy,callback_names))
    if {c['name'] for c in cards if c['admitted']}!=set(policy['verifiedNames']):raise ValueError('Admission drift')
    issues={key:dict(description=value[0],implementation=code_evidence(value[1],value[2])) for key,value in ISSUES.items()}
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),arenaNames=len(cards),arenaPrintings=len(mappings['printings']),
        mappingCounts=dict(Counter(c['mapping'] for c in cards)),constructionCounts=dict(Counter(c['construction'] for c in cards)),
        statusCounts=dict(Counter(c['status'] for c in cards)),blockerCounts=dict(Counter(b for c in cards for b in c['blockers'])),
        apiCounts=dict(Counter(api for c in cards for api in c['apis'])),admittedNames=policy['verifiedNames'],
        unmatchedNames=[c['name'] for c in cards if c['mapping']=='no-script-name-match'],
        constructionProblems=[dict(name=c['name'],status=c['construction'],findings=[f for f in c['findings'] if f['code'].startswith('engine.')]) for c in cards if c['construction'] in ('construction-failed','constructed-with-diagnostics')],
        inheritedCallbackSignatures=sum(c['implementedBy']=='forge.ai.PlayerControllerAi' for c in callbacks),controllerCallbackSignatures=len(callbacks),
        provenance=dict(sourceDatabaseSha256=coverage['summary']['sourceDatabaseSha256'],sourceForgeScriptsSha256=digest(FORGE),
          probeOutputSha256=digest(OUT/'forge-construction.jsonl'),policySha256=digest(POLICY),probeSourceSha256=digest(Path(__file__).with_name('CardCapabilityProbe.java'))),
        limitations=['Construction is not gameplay execution or complete script validation.',
          'Structural blocker and callback hints are conservative, not an exhaustive dynamic call graph.',
          'Installed catalogue presence does not prove release, format legality, account ownership or asset availability.',
          'Rules text and digital/rebalanced equivalence remain unverified outside the admitted slice.',
          'Only pinned printings are observed; alternate printing assets require their own offline rendering check.',
          'Existing slice still has documented manual-input, yield and complete presentation limitations.'])
    payload=dict(schema=1,summary=summary,issues=issues,callbacks=callbacks,cards=cards)
    (OUT/'card-compatibility.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
    (OUT/'compatibility-summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf8')
    with (OUT/'card-compatibility.csv').open('w',newline='',encoding='utf-8-sig') as file:
        writer=csv.writer(file);writer.writerow(['Card','Status','Admitted','Arena printings','Forge script','Construction','Blockers','Effect APIs','Keywords'])
        for c in cards:
            # Spreadsheet-safe names; preserve exact identities in JSON/HTML.
            name=c['name'];name="'"+name if name.startswith(('=','+','-','@','\t','\r')) else name
            writer.writerow([name,c['status'],c['admitted'],','.join(map(str,c['arenaGrpIds'])),','.join(c['forgeScripts']),c['construction'],';'.join(c['blockers']),';'.join(c['apis']),';'.join(c['keywords'])])
    page=HTML.replace('__SUMMARY__',html.escape(json.dumps({k:summary[k] for k in ('arenaNames','arenaPrintings','mappingCounts','constructionCounts','statusCounts')},indent=2)))
    # Embedded JSON cannot close a script element through a card title.
    page=page.replace('__DATA__',json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('&','\\u0026'))
    (OUT/'Card-Compatibility.html').write_text(page,encoding='utf8')
    print(json.dumps(summary,indent=2,ensure_ascii=True))

HTML='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Arena sandbox card support</title><style>
body{font:16px system-ui;margin:28px auto;padding:0 22px;max-width:1300px;background:#111820;color:#e8edf2}h1{font-size:28px}p{line-height:1.55;max-width:1000px;color:#c1ccd7}input,select,button{font:inherit;padding:10px;color:inherit;background:#202d3a;border:1px solid #607589;border-radius:5px;margin:4px}input{width:min(500px,80%)}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:10px;vertical-align:top;border-bottom:1px solid #354656}th{position:sticky;top:0;background:#202d3a}summary{cursor:pointer;color:#a5d6ff}code{font-size:12px}pre{white-space:pre-wrap}small{color:#9aadc0}.yes{color:#93dfac}#count{margin:15px 4px}a{color:#a5d6ff}</style>
<h1>Arena sandbox: card support and blockers</h1>
<p>This report covers the installed Arena catalogue only. A matching Forge script or successful card construction does <strong>not</strong> mean that card is playable. The admitted set remains a bounded, tested slice. This report is a work queue.</p>
<details><summary>Snapshot totals and limits</summary><pre>__SUMMARY__</pre><ul id="limits"></ul></details>
<label for="search">Search card or mechanic</label><br><input id="search" placeholder="Hare Apparent, Scry, planeswalker…" autocomplete="off">
<label for="status">Show</label><select id="status"><option value="">All cards</option>verified-bounded-slice</option><option>candidate-needs-verification</option><option>blocked</option></select>
<label for="issue">Blocker</label><select id="issue"><option value="">All blockers</option></select>
<div id="count" aria-live="polite"></div><table><thead><tr><th>Card / printings</th><th>Support</th><th>What is missing</th></tr></thead><tbody id="rows"></tbody></table>
<p><button id="prev">Previous</button><button id="next">Next</button> <small id="page"></small></p>
<script id="data" type="application/json">__DATA__</script><script>
const data=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);let page=0;
function text(tag,value){let e=document.createElement(tag);e.textContent=value;return e}
for(const limit of data.summary.limitations)$('limits').append(text('li',limit));
for(const [key,value] of Object.entries(data.issues)){let o=text('option',value.description+' ('+(data.summary.blockerCounts[key]||0)+')');o.value=key;$('issue').append(o)}
function render(){const q=$('search').value.toLocaleLowerCase(),s=$('status').value,b=$('issue').value;
const found=data.cards.filter(c=>(!s||c.status===s)&&(!b||c.blockers.includes(b))&&(!q||[c.name,...c.apis,...c.keywords,...c.blockers].join(' ').toLocaleLowerCase().includes(q)));
page=Math.max(0,Math.min(page,Math.ceil(found.length/60)-1));$('rows').replaceChildren();
for(const c of found.slice(page*60,page*60+60)){const tr=document.createElement('tr'),name=text('td',c.name);name.append(text('br',''),text('small',c.arenaGrpIds.join(', ')));tr.append(name);
const support=text('td',c.status);if(c.admitted)support.className='yes';support.append(text('br',''),text('small',c.construction));tr.append(support);
const notes=document.createElement('td');if(c.blockers.length){let ul=document.createElement('ul');for(const key of c.blockers)ul.append(text('li',data.issues[key].description));notes.append(ul)}else notes.append(text('span','See bounded test evidence.'));
const details=document.createElement('details');details.append(text('summary','Rules and evidence'));details.append(text('pre',JSON.stringify({script:c.forgeScripts,sha256:c.sourceForgeScriptSha256,apis:c.apis,keywords:c.keywords,gates:c.gates,findings:c.findings},null,2)));notes.append(details);tr.append(notes);$('rows').append(tr)}
$('count').textContent=found.length.toLocaleString()+' cards match. '+data.summary.admittedNames.length+' names admitted for bounded play.';$('page').textContent='Page '+(page+1)+' of '+Math.max(1,Math.ceil(found.length/60));$('prev').disabled=page===0;$('next').disabled=(page+1)*60>=found.length}
for(const id of ['search','status','issue'])$(id).addEventListener('input',()=>{page=0;render()});$('prev').onclick=()=>{page--;render()};$('next').onclick=()=>{page++;render()};render();
</script></html>'''

if __name__=='__main__':build()
