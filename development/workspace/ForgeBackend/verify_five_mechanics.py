"""Check the five deck payloads and their generated native presentation graph.

Pass each build's experimental JSON and its full generated bridge manifest.
This checks packaging identities, not gameplay; native rules cases are separate.
"""
from pathlib import Path
import argparse,json,re
from prepare_paper_deck import native_mana_text

def main(path,manifest):
    root=Path(__file__).resolve().parents[1]
    data=json.loads(path.read_text(encoding='utf8'));cards=json.loads(manifest.read_text(encoding='utf8'))['cards']
    assert native_mana_text(['2','X','G','R/P','W/U','2/B'])=='o2oXoGo(R/P)o(W/U)o(2/B)'
    assert all(not any('/' in symbol and not (symbol.startswith('(') and symbol.endswith(')')) for symbol in c.get('paperDefinition',{}).get('manaText','').split('o') if symbol) for c in cards.values())
    assert all(cards[name]['grpId']==card['grpId'] for name,card in data['cards'].items())
    extension=data['paperExtension'];abilities={a['id']:a for a in extension['abilities']}
    assert len(abilities)==len(extension['abilities'])
    for ability in abilities.values():
        for child in ability.get('modalChildIds',[]):
            assert ability['id'] in abilities[child]['modalParentIds']
        for parent in ability.get('modalParentIds',[]):
            assert ability['id'] in abilities[parent]['modalChildIds']
        assert all(identity in abilities for identity in ability.get('hiddenAbilityIds',[]))
    for name in ('Pyroblast','Red Elemental Blast'):
        assert len(abilities[cards[name]['abilityIds'][0]]['modalChildIds'])==2,name
    # Tivit has two rules triggers representing one printed instruction.
    tivit=abilities[cards['Tivit, Seller of Secrets']['abilityIds'][0]]
    trigger_text=[extension['localizations'][str(abilities[i]['textId'])] for i in tivit['hiddenAbilityIds'] if abilities[i]['category']==2]
    assert len(trigger_text)==len(set(trigger_text)) and sum("Council's dilemma" in t for t in trigger_text)==1,trigger_text
    assert data['humanChoices']['typeEnumIds']['SubType']['assembly-worker']==data['humanChoices']['typeEnumIds']['SubType']['<nobr>assembly-worker</nobr>']
    content=json.loads((root/'packaging/starter-content.json').read_text())
    files=('Commander-Rebel-Printer.txt','Commander-One-Damage-Is-Enough.txt','Commander-Snake-Oil-Factory.txt','Commander-Definitely-Not-Rigged.txt','Commander-Worst-Gift-Ever.txt')
    for filename in files:
        rows=[(int(m[1]),m[2]) for line in (root/'decks'/filename).read_text(encoding='utf8').splitlines() if (m:=re.fullmatch(r'(\d+) (.+)',line))]
        assert sum(n for n,_ in rows)==100 and rows[0][0]==1
        assert len({name for _,name in rows})==len(rows)
        assert all(name in cards for _,name in rows)
        main={str(cards[name]['grpId']):count for count,name in rows[1:]}
        commander={str(cards[rows[0][1]]['grpId']):1}
        matches=[d for d in content['decks'] if d['main']==main and d['commander']==commander]
        assert len(matches)==1,filename
        assert all(content['cards'][identity]>=count for pile in (main,commander) for identity,count in pile.items())
    print(json.dumps(dict(passed=True,decks=5,modalParents=2,uniqueTivitRule=True,reciprocalPresentationLinks=True,exactTypeAlias=True,collectionGrants=True)))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('experimental',type=Path);p.add_argument('manifest',type=Path);args=p.parse_args();main(args.experimental,args.manifest)
