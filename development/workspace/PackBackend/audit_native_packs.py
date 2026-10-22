"""Audit persisted local rewards against native card IDs and catalog provenance."""
from pathlib import Path
from collections import Counter
import json, datetime, argparse

ROOT=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox')
LAB=ROOT/'native-lab'
profile=json.loads((LAB/'local-profile/packs.json').read_text(encoding='utf-8-sig'))
catalog=json.loads((LAB/'pack-catalog.json').read_text(encoding='utf-8-sig'))
parser=argparse.ArgumentParser();parser.add_argument('--native',type=Path,default=LAB/'pack-host-status.json');parser.add_argument('--output',type=Path,default=ROOT/'research/pack-opening/native-pack-audit.json');args=parser.parse_args()
native=json.loads(args.native.read_text(encoding='utf-8-sig'))
checks=[]
def check(label,condition):
    checks.append({'check':label,'passed':bool(condition)})
    if not condition: raise AssertionError(label)

sets={s['collationId']:s for s in catalog['sets']}
spent=Counter();owned=Counter();ids=[]
for receipt in profile['openings']:
    check('receipt has a unique request ID',receipt['id'] not in ids);ids.append(receipt['id'])
    col=sets[receipt['collationId']];spent[receipt['collationId']]+=receipt['quantity']
    check('receipt has exactly eight cards per pack',len(receipt['cards'])==8*receipt['quantity'])
    check('pack debit matches receipt',receipt['packsBefore']-receipt['packsAfter']==receipt['quantity'])
    for pack in range(receipt['quantity']):
        cards=[c for c in receipt['cards'] if c['packIndex']==pack]
        rarity=Counter(c['rarity'] for c in cards)
        check('custom slots and distinct printing IDs match',len({c['grpId'] for c in cards})==8 and rarity[2]==5 and rarity[3]==2 and rarity[4]+rarity[5]==1)
        check('all rewards belong to source-derived set and rarity pools',all(c['set']==col['set'] and c['grpId'] in col['pools'][str(c['rarity'])] for c in cards))
        owned.update(str(c['grpId']) for c in cards)
check('every local pack balance agrees with committed receipts',all(profile['packs'][str(s['collationId'])]==s['initialPacks']-spent[s['collationId']] for s in catalog['sets']))
check('entire collection agrees with committed receipts',dict(owned)==profile['cards'])
check('native collection count agrees with durable profile',native['collectionCopies']==sum(owned.values()))
check('native opening count agrees with durable profile',native['openingCount']==len(ids))
if native.get('revealCards'):
    check('native displayed identities exactly match latest receipt',Counter(c['grpId'] for c in native['revealCards'])==Counter(c['grpId'] for c in profile['openings'][-1]['cards']))
    check('every native card reached its final animation position',all(c['InFinalPosition'] for c in native['revealCards']))
check('native presentation reports no bridge error',native.get('presentationError') is None)
result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checksPassed':len(checks),'checks':checks,'sets':len(sets),'openings':len(ids),'packsOpened':sum(spent.values()),'collectionCopies':sum(owned.values()),'nativeViewCount':native['nativeViews'],'sourceDatabaseSha256':catalog['sourceDatabaseSha256'],'scope':'Reward/debit/provenance/native identity/animation state. Pixel appearance is separately inspected in recordings.'}
result.update(nativeEvidence=str(args.native),nativeObservedUtc=native['utc'])
args.output.write_text(json.dumps(result,indent=2))
print(json.dumps({k:result[k] for k in ('checksPassed','openings','packsOpened','collectionCopies','nativeViewCount')}))
