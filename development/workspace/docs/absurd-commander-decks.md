# Two optimized Commander experiments

Both are 100-card singleton Commander lists with 40 starting life. They target
upper Bracket 4 play; that is a design goal, not a tested competitive rating.
Exact lists, color identity, singleton restrictions and Commander legality were
checked against current card metadata. There is no budget or Arena-only limit.

## Everybody Get In — Miirym, Sentinel Wyrm

Import `decks/Commander-Everybody-Get-In.txt`, or choose **Everybody Get In
(Miirym Mass Arrival)** from the client's saved decks. It has 33 lands and
66 nonland cards in the main deck.

The most literal line is **Maskwood Nexus + Doubling Season + Sarkhan Unbroken**.
Nexus makes every creature in the library a Dragon. Doubling Season gives
Sarkhan eight starting loyalty, so his -8 can be used immediately to find every
creature and put them onto the battlefield together. Without Season, Deepglow
Skate can double Sarkhan's loyalty after he enters; otherwise build loyalty
normally. These cards do not change the original Commander rules.

**Genesis Wave** is the other mass-arrival spell. Choose X at least as large as
the remaining library and the highest mana value you want to put into play.
Deadeye Navigator paired with Peregrine Drake can repeatedly pay two mana to
blink Drake and untap five lands, producing arbitrarily large mana when those
lands can produce more than the blink costs. This pays for a library-sized Wave.
Kindred Summons with Nexus and enough creatures is another simultaneous route.
Primal Surge is deliberately absent: it puts permanents in one at a time.

Miirym copies the incoming nontoken Dragons. Nexus lets that include the mana
creatures, clones and other utility creatures. Doubling Season, Parallel Lives,
Molten Echoes, Panharmonicon, Roaming Throne and Mirror March multiply different
parts of the sequence. The originals enter together; their resulting triggers
then resolve in order, creating further arrivals rather than one enormous
uninterruptible action.

Dragon Tempest, Scourge of Valkas, Terror of the Peaks, Impact Tremors and
Purphoros turn arrivals into damage. Ganax makes Treasure, Lathliss makes more
Dragons, and Utvara adds another army when the Dragons attack. Spark Double,
Sakashima and Phyrexian Metamorph duplicate useful engines. The cheap ramp,
tutors and free/cheap interaction support the expensive spectacle.

Keep protection for the decisive turn. Decline Temur Ascendancy's optional draws
if the library is empty. Creature tutors cannot find Genesis Wave or Sarkhan;
use the appropriate spell tutor or draw engine. Miirym is not required to make
the Sarkhan line function, but dramatically increases its output.

## Your Deck But Toxic — Zaxara, the Exemplary

Import `decks/Commander-Your-Deck-But-Toxic.txt`, or choose **Your Deck But Toxic
(Zaxara Copy Army)**. It has 34 lands and 65 nonlands in the main deck.

This is a real-card adaptation of the requested fantasy: it copies opponents'
**battlefield creatures/permanents**, not hidden library cards. Opposing originals
stay where they are; the copying spells do not mill their libraries.

With Zaxara ready to tap, **Freed from the Real** or **Pemmin's Aura** produces
arbitrarily large colored mana: tap Zaxara for two blue, spend one to untap it,
and repeat, generating the other colors when needed. Freed's activated untap
ability belongs to the Aura; Pemmin's grants its abilities to the creature.
Greaves, Boots and Thousand-Year Elixir help start the engine immediately.

Spend that mana on **Doppelgang** to create X copies of each of X target
permanents. It can copy lands and artifacts as well as creatures. Clone Legion
copies all creatures controlled by one player; kicked Rite of Replication makes
five copies of one creature. Second Harvest doubles the token army at instant
speed; Extravagant Replication keeps building it on later upkeeps. Counters are
not copied: a copy of an ordinary 0/0 Hydra dies without a separate bonus.

Zaxara also creates an X/X Hydra when an X spell is cast. **Esix, Fractal Bloom**
can replace the first token creation each turn with copies of a creature on the
battlefield, including an opponent's creature; Zaxara's X counters still get put
on those copies. Adrix and Nev, Parallel Lives and Doubling Season multiply the
tokens. Have Sakashima out before making several copies of the same legendary
permanent, or the ordinary legend rule will make you keep only one.

**Triumph of the Hordes** gives the entire current creature army +1/+1, trample
and infect for the turn. Cast it after creating the army and when those creatures
can attack; Finale of Devastation at X>=10 can supply haste and a huge team bonus.
Triumph itself does not give haste or affect creatures created later. Infect
deals poison counters instead of life loss to players, and ten poison eliminates
a player even in 40-life Commander. Tainted Strike, Phyresis, Grafted Exoskeleton
and Corrupted Conscience provide individual infect threats. Witness, Regrowth
and Noxious Revival recover key spells. Tokens normally need to survive a turn
before attacking unless another effect gives them haste.

## Verification boundaries

The original Forge rules and original native action handlers execute the tests.
Seeded tests check simultaneous arrivals (with Ganax last in the library to
detect sequential behavior), doubled Miirym copies, actual X counters, opponent
copy identities with unchanged opposing libraries, Esix, paid untap/blink loops,
infect combat and poison elimination. Each newly admitted deck card also has a
bounded play/cast/resolution check; that is not every effect branch.

Paper cards and the exact 0/0 green Hydra token have separate presentation records
and downloaded illustrations, preserving existing cards and art. Infect uses an
explicit paper-keyword text identity because the installed Arena catalogue does
not provide that keyword; no original Arena identity is claimed. All damage,
counters, copying and win conditions still come from Forge. The verified
370-name policy stays separate from experimental deck admission.

An Astral Dragon prototype exposed an existing presentation gap for copy-added
intrinsic Flying, and Progenitor Mimic's retained upkeep has an unmapped source.
Both are excluded instead of being advertised as working. Full games, matchup strength, very large late-game trigger queues and
every possible copied opposing card have not been exhaustively verified.

Rules references: [Miirym release notes](https://media.wizards.com/2022/wpn/w22/EN_MTGCLB_ReleaseNotes_04282022.pdf),
[Sarkhan card text](https://media.wizards.com/2024/wpn/marketing_materials/mkm/mkm_product_guide_en.pdf),
[official Commander brackets](https://magic.wizards.com/en/formats/commander).
