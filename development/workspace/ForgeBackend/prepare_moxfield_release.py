"""Prepare a private, explicitly experimental Arena-only release inventory.

This does not promote walkthroughs to verified gameplay or ship research fixtures.
The presentation overlay is prepared separately against a regenerated base.
"""
import argparse, copy, hashlib, json
from pathlib import Path


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(a):
    old=json.loads(a.previous.read_text()); added=json.loads(a.additions.read_text())
    bound=json.loads(a.bound.read_text()); policy=json.loads(a.policy.read_text())
    audit=json.loads(a.audit.read_text()); captured=json.loads(a.capture.read_text())
    if policy.get('researchOnly') or bound.get('researchOnly') is not True or audit.get('arenaOnly') is not True:
        raise ValueError('Require production baseline, private research bindings and Arena-only audit')
    if len(captured.get('decks',[]))!=50: raise ValueError('Require the complete fifty-deck capture')
    for key in ('sourceDatabaseSha256','sourceForgeScriptsSha256','policySha256'):
        if not old.get(key) or old[key]!=added.get(key) or old[key]!=bound.get(key):
            raise ValueError('Pinned inventory input drift: '+key)
    if sha(a.policy)!=old['policySha256']: raise ValueError('Production baseline changed')
    verified=set(policy['verifiedNames']); candidates=set(policy.get('candidateNames',[])); selected=set(old['cards'])|set(added['cards'])
    arena={c['nativeName'] for c in audit['cards'] if c['status']=='identity-candidate'}
    if not set(added['cards'])<=arena or selected&verified:
        raise ValueError('New identities must come from the Arena audit without overwriting verified cards')
    if not arena<=selected|verified: raise ValueError('Arena pool is incomplete')
    result={k:copy.deepcopy(v) for k,v in old.items() if k not in ('cards','humanChoices')}
    result['cards']={}
    for name in sorted(selected):
        source=bound['cards'][name]; prior=old['cards'].get(name,added['cards'].get(name))
        if any(source.get(k)!=prior.get(k) for k in ('grpId','forgeScriptSha256')):
            raise ValueError('Original printing or script changed: '+name)
        if not source.get('experimental') or source.get('verified') is not False or not source.get('admitted') or source.get('token') is not False:
            raise ValueError('Unverified primary identity required: '+name)
        result['cards'][name]=copy.deepcopy(source)
    if set(result['blockedCards'])&selected: raise ValueError('Blocked and admitted inventories overlap')
    filtered=copy.deepcopy(bound); removed=[]
    for name,card in list(filtered['cards'].items()):
        presentation=any(card.get(k) for k in ('token','facePresentation','emblemPresentation'))
        if not presentation and name not in selected|verified|candidates:
            removed.append(name);del filtered['cards'][name]
    for name,card in list(filtered['cards'].items()):
        if card.get('parentName') and card['parentName'] not in filtered['cards']:
            removed.append(name);del filtered['cards'][name]
    result['moxfieldProvenance']=dict(schema=1,arenaOnly=True,deckCount=50,
        sourceHashes={p.name:sha(p) for p in (a.previous,a.additions,a.bound,a.policy,a.audit,a.capture)},
        newExperimentalNames=len(selected-set(old['cards'])),verifiedPromotions=0,
        status='Experimental access only; specific scenario evidence is reported separately')
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'experimental-unbound.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    (a.output/'filtered-research-bindings.json').write_text(json.dumps(filtered,indent=2),encoding='utf8')
    report=dict(verifiedNames=len(verified),experimentalNames=len(selected),primaryNames=len(verified|selected),
        arenaPoolNames=len(arena),newExperimentalNames=len(selected-set(old['cards'])),
        excludedResearchObjects=sorted(removed),verifiedPromotions=0)
    (a.output/'preparation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('previous','additions','bound','policy','audit','capture','output'):p.add_argument('--'+key,type=Path,required=True)
    prepare(p.parse_args())
