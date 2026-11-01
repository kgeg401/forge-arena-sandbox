# Zombie Horde — experimental solo mode

In **Play**, choose **Zombie Horde (Solo)** for a 40–250-card practice deck, or
**Zombie Horde (Commander Deck)** under Brawl for 99 cards plus a commander.
Both start you at **40 life**. These are local sandbox formats, not Arena queues.

You take three preparation turns before the Horde's first turn. Its shuffled
**200-card deck** contains 120 physical 2/2 Zombie token cards and the following
80 Arena-present cards. Every creature is a Zombie or Horror; the sorceries
reanimate creatures.

| Copies | Card |
| --- | --- |
| 12 each | Gravedigger; Ghoulraiser |
| 8 each | Rise from the Grave; Diregraf Rebirth; Undead Butler |
| 6 | Mire Triton |
| 4 each | Rise of the Dark Realms; Death Baron; Lord of the Accursed; Phyrexian Rager; Walking Corpse; Rotting Mastodon |
| 2 | Phyrexian Gargantua |

Each Horde turn reveals cards through the first non-token and casts that wave
without paying its ordinary mana costs. These are real spells on the response
stack: counterspells, removal, blocking and other normal interactions still use
Forge's rules. Horde creatures have haste, attack the survivor when able, and
do not block. Returned or drawn cards can join casting in its main phase, with
each physical card attempted at most once per wave to bound recursion.

Revival targets and optional Horde triggers use Forge's normal AI. Rise of the
Dark Realms can take creatures from either graveyard, and Rise from the Grave
can turn a stolen creature into a Zombie, according to their actual rules.
**Deliberate Horde variant:** a revealed spell with no legal targets is put in
the Horde's graveyard rather than left in its hand indefinitely. Ordinary
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
  life. Its opponent and three setup turns make it a Horde variant, rather than
  an Arena-legal Brawl queue.

## Verification checkpoint — 2026-11-01

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
