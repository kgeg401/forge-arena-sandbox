"""Independent-oracle and evidence-mutation boundaries, without a game."""
import json
from pathlib import Path
import tempfile
from build_card_test_catalogue import native_fixed_effects,forge_fixed_effects,parse,cost
from compare_card_batch_runs import canonical_trace,difference
from prepare_generated_pump_batches import native_pump,forge_pump


def run():
    results=[]
    def check(name,condition):
        if not condition:raise AssertionError(name)
        results.append(name)
    check('Native words supply an ordered life/draw oracle',native_fixed_effects(['You gain 3 life.','Draw a card.'])==[dict(kind='GainLife',amount=3),dict(kind='Draw',amount=1)])
    for text in ('You may gain 3 life.','Draw a card, then discard a card.','Draw a card. If you control an artifact, draw another card.','Target player draws two cards.','Draw 0 cards.','You gain life equal to your hand size.'):
        check('Unknown native semantics are never truncated: '+text,native_fixed_effects([text]) is None)
    fixed='Name:Test\nManaCost:1 U\nTypes:Instant\nA:SP$ Draw | NumCards$ 2\n'
    check('Literal Forge effect independently agrees with native oracle',forge_fixed_effects(parse(fixed))==native_fixed_effects(['Draw two cards.']))
    for suffix in ('SVar:X:Count$CardsInYourHand\n','T:Mode$ Drawn | Execute$ Something\n','R:Event$ Draw | ReplaceWith$ Something\n','UnknownBehavior:Something\n','ALTERNATE\nName:Other face\n'):
        check('Extra source behavior rejects fixed template: '+suffix.split(':')[0],forge_fixed_effects(parse(fixed+suffix)) is None)
    check('A conditional effect cannot become a literal oracle',forge_fixed_effects(parse(fixed.replace('NumCards$ 2','NumCards$ 2 | ConditionPresent$ Creature.YouCtrl'))) is None)
    cycle='Name:Test\nManaCost:U\nTypes:Instant\nA:SP$ Draw | NumCards$ 1 | SubAbility$ Next\nSVar:Next:DB$ Draw | NumCards$ 1 | SubAbility$ Next\n'
    check('Cyclic subabilities terminate as unsupported',forge_fixed_effects(parse(cycle)) is None)
    for text in ('oXoU','o2/W','oSoG','o1oU trailing'):
        check('Unsupported native mana forms rejected: '+text,cost(dict(manaText=text)) is None)
    pump='Name:Test\nManaCost:G\nTypes:Instant\nA:SP$ Pump | ValidTgts$ Creature | NumAtt$ +3 | NumDef$ +3\n'
    check('Native target-pump words supply exact independent deltas',native_pump(['Target creature gets +3/+3 until end of turn.'])==dict(power=3,toughness=3))
    check('Literal Forge target-pump separately agrees',forge_pump(parse(pump))==dict(power=3,toughness=3))
    for text in ('Target creature gets +3/+3.','Target creature you control gets +3/+3 until end of turn.','Target creature gets +3/+3 and gains trample until end of turn.','Up to one target creature gets +3/+3 until end of turn.','Target creature gets +X/+X until end of turn.','Target creature gets +3/+3 until end of turn. Draw a card.'):
        check('Pump oracle never truncates native semantics: '+text,native_pump([text]) is None)
    for extra in (' | KW$ Trample',' | Duration$ Permanent',' | ValidTgts$ Creature.YouCtrl',' | ConditionPresent$ Creature',' | SubAbility$ Next',' | TargetMax$ 2'):
        candidate=pump.replace('NumDef$ +3','NumDef$ +3'+extra)
        # A duplicate native target restriction must not be laundered as the
        # original unrestricted target; parameter parsing keeps its last value.
        check('Additional pump semantics reject the fixed template: '+extra,forge_pump(parse(candidate)) is None)
    for suffix in ('K:Conspire\n','SVar:Next:DB$ Draw | NumCards$ 1\n','ALTERNATE\nName:Other face\n'):
        check('Additional pump source behavior rejects the template: '+suffix.split(':')[0],forge_pump(parse(pump+suffix)) is None)
    with tempfile.TemporaryDirectory(prefix='forge-evidence-guard-') as tmp:
        a=Path(tmp)/'a.jsonl';b=Path(tmp)/'b.jsonl'
        a.write_text(json.dumps(dict(session='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',life=20,forgeId=45))+'\n')
        b.write_text(json.dumps(dict(session='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',life=20,forgeId=45))+'\n')
        check('Random UUID renaming preserves otherwise identical evidence',difference(canonical_trace(a),canonical_trace(b)) is None)
        b.write_text(json.dumps(dict(session='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',life=21,forgeId=45))+'\n')
        check('A one-life error is never normalized away',difference(canonical_trace(a),canonical_trace(b))['path']=='$[0].life')
        b.write_text(json.dumps(dict(session='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',life=20,forgeId=46))+'\n')
        check('A changed card identity is never normalized away',difference(canonical_trace(a),canonical_trace(b))['path']=='$[0].forgeId')
    print(json.dumps(dict(checks=len(results),passed=results),indent=2))


if __name__=='__main__':run()
