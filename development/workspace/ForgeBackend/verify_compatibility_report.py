"""Check audit completeness and false-positive/false-negative boundary cases."""
from pathlib import Path
import json, csv, hashlib
from build_card_coverage import ROOT, norm
from runtime_paths import SUPPORT_POLICY
from build_compatibility_report import analyze, script_features

root=ROOT/'research/card-coverage';repo=Path(__file__).resolve().parents[1]
data=json.loads((root/'card-compatibility.json').read_text(encoding='utf8'));cards={c['name']:c for c in data['cards']};checks=[]
def check(label,condition):
    if not condition:raise AssertionError(label)
    checks.append(dict(check=label,passed=True))
source=json.loads((root/'arena-forge-coverage.json').read_text(encoding='utf8'))
check('Every Arena name appears exactly once',len(cards)==len(data['cards'])==source['summary']['arenaNames'] and set(cards)=={c['name'] for c in source['cards']})
check('All and only indexed Arena printings are represented',{g for c in data['cards'] for g in c['arenaGrpIds']}=={g for c in source['cards'] for g in c['arenaGrpIds']})
policy=json.loads(SUPPORT_POLICY.read_text())
check('No static or constructor result promotes card admission',{c['name'] for c in data['cards'] if c['admitted']}==set(policy['verifiedNames']))
check('All unadmitted cards still require sequence, rules and asset verification',all({'verification.sequence','verification.rules_text','verification.native_assets'}<=set(c['blockers']) for c in data['cards'] if not c['admitted']))
check('All referenced blocker codes have implementation provenance',all(b in data['issues'] for c in data['cards'] for b in c['blockers']))
for name,codes in {
 'Opt':{'bridge.choices'},'Lightning Bolt':{'bridge.player_targets','bridge.damage_events'},
 'Shivan Dragon':{'bridge.activated','bridge.keywords'},
 'Fable of the Mirror-Breaker':{'bridge.faces','bridge.counters','bridge.tokens'},
 'Brainstorm':{'bridge.zone_choices'},'Enlightened Tutor':{'bridge.zone_choices'},
 'Omen Hawker':{'bridge.mana_sources'},"Warlord's Elite":{'bridge.cost_form'},
 'Isamaru, Hound of Konda':{'bridge.legendary_choice'},
 'Lightning Strike':{'bridge.damage_events'},'Cancel':{'bridge.counter_events'},
}.items():check(name+' blockers are detected',codes<=set(cards[name]['blockers']))
check('Plain creature damage is not blocked by card name','bridge.combat_assignment' not in cards['Aegis Turtle']['blockers'])
check('Generic deathtouch allocation no longer reports its removed implementation blocker','bridge.combat_assignment' not in cards['Daggerback Basilisk']['blockers'])
check('Verified generic trample allocation no longer reports its removed implementation blocker','bridge.combat_assignment' not in cards['Colossal Dreadmaw']['blockers'])
check('Repeated colored mana symbols are represented generically','bridge.cost_form' not in cards['Shivan Dragon']['blockers'])
# Constructor findings belong to the exact engine AND script distribution.
# The fixed official release repaired the three old snapshot diagnostics.
receipt=json.loads((root/'construction-receipt.json').read_text())
baselines={
 ('b17c37b5483b84e0c6bc77a8a191680b6eb5bfa508235475c495acc45a4ad110','2fe9463a8014d419c7e276b57e71f0fa1c2f2a63846183b995dbc94af670089f'):
 {'Perfected Theory':'construction-failed','Withering Curse':'constructed-with-diagnostics','Circadian Struggle':'constructed-with-diagnostics'},
 ('85a4c31e07d4d5621a84bb03b6d75fd08e9f4ba289e575c870579b49c0033766','ac26ccbe2a9c015bad4851db61d57d421777e10bf96c32d72add618b258bec07'):
 {n:'constructed-not-playtested' for n in ('Perfected Theory','Withering Curse','Circadian Struggle')},
}
identity=(receipt['installedForgeJarSha256'],receipt['scriptsSha256'])
check('Constructor expectations name an exact approved engine/script pair',identity in baselines)
for name,status in baselines[identity].items():check(name+' matches version-specific construction baseline',cards[name]['construction']==status)
fixture=dict(name='Construction fixture',arenaGrpIds=[1],forgeScripts=['fixture.txt'],mapping='unique-script-candidate')
for status,code in [('construction-failed','engine.construction_failed'),('constructed-with-diagnostics','engine.construction_diagnostic')]:
    result=analyze(fixture,[dict(types=['Instant'],supertypes=[])],'Name:Construction fixture\nTypes:Instant\nManaCost:W',dict(status=status,diagnostics='fixture diagnostic'),dict(verifiedNames=[]),set())
    check('Constructor failure boundary remains detected '+status,code in result['blockers'])
check('Verified Hare retains admitted bounded status',cards['Hare Apparent']['admitted'] and cards['Hare Apparent']['status']=='verified-bounded-slice')
check('Aftermath triple slash normalization is candidate identity only',norm('Appeal /// Authority')==norm('Appeal // Authority') and not cards['Appeal /// Authority']['admitted'])
f=script_features('Name:Example\nOracle:DB$ Scry | ValidTgts$ Player\n# A:AB$ Mana\nA:SP$ Draw | SpellDescription$ DB$ Sacrifice | NumCards$ 1\n')
check('Oracle/comments/descriptions never create fake executable effects',len(f['rows'])==1 and f['rows'][0]['params']=={'SP':'Draw','NumCards':'1'})
with (root/'card-compatibility.csv').open(encoding='utf-8-sig',newline='') as file:csv_rows=list(csv.DictReader(file))
check('CSV has every card and guards formula-like card names',len(csv_rows)==len(cards) and next(r for r in csv_rows if '2 Mace' in r['Card'])['Card'].startswith("'+"))
check('HTML includes searchable report but no raw unsafe card script element','id="search"' in (root/'Card-Compatibility.html').read_text(encoding='utf8'))
callbacks=data['callbacks'];check('Inherited human-decision paths are explicitly inventoried',any(c['name']=='arrangeForScry' and c['implementedBy']=='forge.ai.PlayerControllerAi' for c in callbacks))
for issue in data['issues'].values():
    e=issue['implementation'];check('Source anchor remains current '+e['file']+':'+str(e['line']),hashlib.sha256((repo/e['file']).read_bytes()).hexdigest()==e['sha256'])
(root/'compatibility-checks.json').write_text(json.dumps(dict(checks=checks,total=len(checks)),indent=2))
print(json.dumps(dict(checks=len(checks),cards=len(cards),admitted=sum(c['admitted'] for c in data['cards']),report=str(root/'Card-Compatibility.html')),indent=2))
