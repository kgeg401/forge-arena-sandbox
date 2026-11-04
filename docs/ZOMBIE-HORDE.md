# Zombie Horde — experimental solo mode

In **Play**, choose **Zombie Horde (Solo)** for a 40–250-card practice deck, or
**Zombie Horde (Commander Deck)** under Brawl for 99 cards plus a commander.
Both start you at **40 life**. These are local sandbox formats, not Arena queues.

With a commander deck, preparation turns equal the commander's original mana
value, with a minimum of one turn. A five-mana commander gets five turns;
Darien gets six. Normal land-drop and payment rules apply: this does not give
lands, mana, or a free commander cast. Practice decks keep three prep turns.
Its shuffled **500-card Zombie Legion** contains **300 physical 2/2 Zombie
token cards and 200 support cards**. Every creature in this list is a Zombie;
all named support cards are real Magic cards with their original Arena art.
Repeated copies are intentional Horde deck construction, not Commander legality.

| Copies | Card |
| --- | --- |
| 300 | Physical 2/2 black Zombie token card |
| 12 | Champion of the Perished |
| 10 each | Death Baron; Lord of the Accursed; Wayward Servant |
| 8 each | Undead Augur; Headless Rider; Diregraf Captain; Bladestitched Skaab; Diregraf Colossus; Stitcher's Supplier; Undead Butler; Gravedigger; Ghoulraiser; Rise from the Grave; Liliana's Mastery |
| 6 each | Gray Merchant of Asphodel; Mire Triton; Diregraf Rebirth; Geralf's Messenger; Accursed Marauder; Skinrender; Archghoul of Thraben |
| 4 each | Rise of the Dark Realms; Mikaeus, the Unhallowed; Necroduality; Open the Graves; Army of the Damned; Murder; Go for the Throat |

Champion and the lords grow the incoming army. Wayward Servant rewards arrivals;
Diregraf Captain and Undead Augur reward deaths. Headless Rider, Open the Graves
and Mikaeus rebuild after casualties, while mill fills the graveyard for the
reanimation spells. Necroduality copies incoming nontoken Zombies, Colossus
rewards Zombie spells, and Army of the Damned adds thirteen tapped Zombies.

Each Horde turn reveals cards through the first non-token and casts that wave
without paying its ordinary mana costs. These are real spells on the response
stack: counterspells, removal, blocking and other normal interactions still use
Forge's rules. Horde creatures have haste, attack the survivor when able, and
do not block. Returned or drawn cards can join casting in its main phase, with
each physical card attempted at most once per wave to bound recursion.

The Horde selects **one spell at a time**, resolves the real response stack, and
reassesses its public board and graveyard. It prioritizes engines and lords
before incoming Zombies, saves Gray Merchant until other permanents establish
devotion, and considers revival more urgently when creatures are in its graveyard.
Murder and Go for the Throat require a legal opposing creature: they are never
used just to kill the Horde's own army. Attack-all and no-block rules still apply.
The policy does not inspect your hidden hand or library.

Revival targets and optional Horde triggers use Forge's normal AI. Rise of the
Dark Realms can take creatures from either graveyard, and Rise from the Grave
can turn a stolen creature into a Zombie, according to their actual rules.
**Deliberate Horde variant:** a revealed spell with no useful legal targets waits
until the other useful wave spells have resolved, then goes to the Horde's
graveyard rather than remaining in its hand indefinitely. Ordinary
countering and targets becoming illegal still follow the normal stack rules.

**The Horde's avatar number means library cards remaining, not life.** Damage
to the Horde mills that many cards using Forge's normal mill effect. An empty
library alone does not win: clear its battlefield and any pending hand/stack
cards too. Your own life, damage, draws and losses follow the normal rules.

## First-version boundaries

- Solo only; cooperative/network play is not included.
- The Horde deck is fixed. Custom Horde decks, planeswalker attack allocation,
  infinite-mana tax interactions, and automated use of paid activated abilities
  or flashback are not implemented or certified by this version.
- The card-count avatar badge deliberately reuses Arena's normal numeric widget.
  It is a format presentation change, not a claim that Arena has a Horde UI.
- Existing card admission and experimental-card limitations still apply. Being
  selectable does not certify every card effect, combination or deck's strength.
- Commander-deck Horde uses the sandbox's commander framework at 40 starting
  life. Its opponent and preparation rules make it a Horde variant, rather than
  an Arena-legal Brawl queue.
- Physical Horde token cards retain the original token-card marker. Although
  they occupy the library and graveyard, Forge treats them as tokens for
  token/nontoken restrictions. Necroduality, Headless Rider and Open the Graves
  therefore support the regular Zombie creatures, not the physical token cards.
  Lords, Champion, Wayward Servant, Augur, Captain and Zombie-cast triggers can
  still work with the token waves according to their actual printed rules.
- The AI is a bounded Horde-specific sequencing policy plus Forge's normal
  targeting/trigger AI. It is not an optimal-play solver or a balance guarantee.

## Verification checkpoint — 2026-11-04 UTC

The 500-card update passed 47 bounded original-parser/input-handler cases:
11 opening/revival cases, seven existing Horde regressions, 16 sequencing and
synergy cases, four commander/preparation cases, seven checks on the other
supported Arena build, one interactive full-game policy, and one artifact-only
removal boundary. Both complete 500-card games ended in actual Horde victories:
one against a pass-only survivor and one against a scripted Hare Apparent /
Impassioned Orator survivor that cast creatures, attacked and blocked.

The smaller starting-pool tests separately observed counters, Zombie-cast
tokens, arrivals/deaths draining life, creature copying, death replacement
armies, graveyard returns, thirteen tapped Army of the Damned tokens, legal
enemy removal and the physical-token/nontoken distinction. Deferred revival
successfully used a fresh death in its first wave. Preparation still allowed
one-, three-, five- and six-mana commanders to be cast before the first wave
when the test policy played the necessary colors.

These are headless tests using original native handlers and real Forge effects.
They do not establish a freshly rendered UI acceptance, optimal AI, balance,
every possible interaction, or a survivor win against this larger pool. The
earlier results below describe their historical decks, not this 500-card list.

## Earlier verification checkpoint — 2026-11-01

Alpha 12 also tests Ghoulraiser returning a physical Zombie token from the
graveyard: its temporary reveal retains the exact original token identity,
the acknowledgement completes, and the permission does not expose other
hidden cards or persist afterward. This fixes a native presentation stall.

The 40-life/200-card update passed an actual Commander opening in the original
rendered client. Separate native-parser tests observed Gravedigger and Ghoulraiser
returns, both targeted reanimation spells, mass revival under the Horde's
control, Undead Butler's exile/return trigger, Horror drawing, lord buffs, and
the no-legal-target boundary. The seven original Horde regressions also passed
with the final engine, including a complete ordinary 200-card game won by the
Horde against a pass-only survivor. These are bounded cases, not a claim that
every possible revival chain or commander interaction has been verified.

The initial 45-card prototype established the following earlier baseline:
Seven bounded original-parser/input-handler cases passed: an unmodified
45-card Horde defeating a pass-only survivor; combat and spell damage milling;
survivor victory after clearing the Horde; no early victory while creatures
remain; countering a normal Horde spell and a physical Zombie token spell; and
bouncing/recasting the same card in a later wave. Small-pool mechanic cases are
initial-state fixtures, not full 45-card win claims. Several basic scripted
survivor strategies lost ordinary games; balance and broad deck coverage remain
unverified.

Original rendered Home/Play, saved-deck selection, normal opening/Keep, land and
creature play, three preparation turns, physical Zombie art and haste attacks,
human combat damage/mill and the changing library badge were observed. These
bounded checks do not establish complete UI parity or all-card support.

The private player launcher was also checked with the saved **Emry Brawl** deck:
selection through the original Play menu, Emry in the command zone, casting her
with ordinary mana and artifact cost reduction, and her four-card mill resolving.
Closing and reopening retained the selected deck. Other commander decks remain
subject to their existing card-support checks; this is not certification of every
saved deck or combo.

Rules reference: Peter Knudson's [original Horde article](https://www.quietspeculation.com/2011/09/horde-magic-a-new-way-to-play-magic-and-survive-zombie-invasions/)
and [follow-up](https://www.quietspeculation.com/2011/10/horde-magic-an-open-source-project/).
