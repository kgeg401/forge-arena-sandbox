"""Actual Forge casts for a source-checked research family; never admits cards."""
import json
from pathlib import Path
from engine_test_client import Engine
from runtime_paths import ROOT, SUPPORT_POLICY

source=ROOT/'research/card-coverage/arena-printing-mappings.json'
printings={r['grpId']:r for r in json.loads(source.read_text(encoding='utf8'))['printings']}
manifest=json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text())
policy=json.loads(SUPPORT_POLICY.read_text())
if not policy.get('researchOnly') or not manifest.get('researchOnly'):
    raise ValueError('This family probe requires an isolated research-only policy/manifest')
names=json.loads(Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\research\broad-card-support\plain-creature-candidates.json').read_text())
out=ROOT/'research/plain-family-checks';out.mkdir(exist_ok=True)
reports=[]
for start in range(0,len(names),6):
    group=names[start:start+6]
    e=Engine('card-family',fixtureHand=group,fixtureLands=[n for n in ('Plains','Island','Swamp','Mountain','Forest') for _ in range(20)])
    try:
        e.check('Exact requested hand is represented',[c['name'] for c in e.state['hand']]==group)
        for name in group:
            definition=manifest['cards'][name];row=printings[definition['grpId']]
            card=next(c for c in e.state['hand'] if c['name']==name);id=card['forgeId']
            e.check(name+' actual Forge printed stats match owned Arena row',(card['power'],card['toughness'])==(int(row['power']),int(row['toughness'])))
            expected_mask=sum({'White':1,'Blue':2,'Black':4,'Red':8,'Green':16}[c] for c in definition['colors'])
            e.check(name+' distinct source color enums map to Forge bits',card['colorMask']==expected_mask)
            offer=next(o for o in e.state['castOffers'] if o['forgeId']==id)
            expected={c['color']:c['count'] for c in definition['coloredCost']}
            if definition['genericCost']:expected['Generic']=definition['genericCost']
            e.check(name+' actual payable cost preserves every colored symbol',{c['color']:c['count'] for c in offer['manaCost']}==expected)
            tapped=sum(c['tapped'] for c in e.state['battlefield'])
            r=e.send('cast_spell',id);e.check(name+' input casts the actual spell',r['accepted'] and id in [c['forgeId'] for c in e.state['stack']])
            e.check(name+' actual costs tap the correct number of sources',sum(c['tapped'] for c in e.state['battlefield'])-tapped==sum(expected.values()))
            e.pass_or_decision()
            resolved=next(c for c in e.state['battlefield'] if c['forgeId']==id)
            e.check(name+' engine resolves the creature with summoning sickness',resolved['sick'] and (resolved['power'],resolved['toughness'])==(int(row['power']),int(row['toughness'])) and not e.state['stack'])
            e.check(name+' produces no fidelity gap',not e.state['fidelityGap'])
        reports.append(dict(names=group,evidence=str(e.ipc),checks=len(e.checks),passed=True))
        print(json.dumps(reports[-1]),flush=True)
    finally:e.close()
e=Engine('card-family',fixtureHand=['Dune Beetle','Grizzly Bears','Feral Maaka','Fusion Elemental','Gigantosaurus'],fixtureLands=['Plains']*20)
try:
    e.check('White mana cannot satisfy black/red/green/multicolor or repeated-green costs',not e.state['legalCasts'])
    for c in list(e.state['hand']):
        r=e.send('cast_spell',c['forgeId']);e.check('Wrong-color request rejected '+c['name'],not r['accepted'] and not e.state['stack'])
    reports.append(dict(names=['wrong-color-boundaries'],evidence=str(e.ipc),checks=len(e.checks),passed=True))
finally:e.close()
e=Engine('card-family',fixtureHand=['Grizzly Bears'],fixtureLands=['Plains','Island','Swamp','Mountain','Forest'])
try:
    for name,color in [('Plains',1),('Island',2),('Swamp',4),('Mountain',8),('Forest',16)]:
        c=next(c for c in e.state['battlefield'] if c['name']==name)
        r=e.send('activate_mana',c['forgeId']);e.check(name+' activates its actual intrinsic mana ability',r['accepted'] and any(m['sourceForgeId']==c['forgeId'] and m['color']==color for m in e.state['mana']))
    reports.append(dict(names=['all-five-basic-mana-abilities'],evidence=str(e.ipc),checks=len(e.checks),passed=True))
finally:e.close()
result=dict(researchOnly=True,cards=len(names),checks=sum(r['checks'] for r in reports),reports=reports,
            scope='Seeded cast/payment/resolution scenarios only. Not combat, native rendering or production admission.')
(out/'report.json').write_text(json.dumps(result,indent=2))
print(json.dumps(dict(cards=len(names),checks=result['checks'],report=str(out/'report.json')),indent=2))
