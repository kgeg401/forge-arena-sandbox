# Emry mechanics checkpoint

The local sandbox now connects all three of **Emry, Lurker of the Loch's own
abilities** to the real Forge rules engine and Arena's original match interface.
This is a bounded artifact test, not support for the entire saved Emry deck or
complete Arena presentation parity. Retail Arena remains unchanged.

## Try it

- **Forge Emry Mechanics Test** on the desktop starts the repeatable 60-card
  practice deck against a vanilla opponent. It contains repeated Emrys,
  Ornithopters and Aether Spellbombs to make the loop easy to find. It deliberately
  uses unrestricted practice copy counts and starts at 20 life.
- **Forge Emry Brawl Test** starts Emry in command with 99 main cards and 25 life.
  This legal-size singleton fixture is deliberately land-heavy: 96 Islands,
  Ornithopter, Spellbomb and Unsummon. It tests commander behavior rather than
  representing a useful competitive deck.
- Source launchers: `Open-Emry.ps1` and `Open-Emry.ps1 -Brawl`. Re-run to restart;
  the previous session's evidence is archived. `Install-EmryShortcuts.ps1` creates
  the shortcuts without replacing existing files.

Use the original Play/Draw and Keep controls. Double-click hand cards to play
them. After Emry has survived to your next turn, click it, choose an artifact in
the original graveyard picker, and let the ability resolve. The permitted card
appears as Arena's purple graveyard-cast card near your hand. Double-click it at
a legal time and pay its normal cost. Click Spellbomb and choose its draw or
bounce ability in the original ability selector. Spellbomb's sacrifice and draw
let you repeat the loop after Emry untaps. Choose which Emry to keep when the
original legend-rule prompt appears.

## Verified rules

All test games start normally, shuffle, draw and advance through public inputs.
They do not inject intermediate battlefield state, permissions or zone changes
into Forge.

| Behavior | Evidence |
| --- | --- |
| Artifact cost reduction, including artifact lands | Real offers 2U, 1U, U; actual blue payments; Seat counts as an artifact and cannot remove the final U |
| Entry trigger | Source-bound trigger 86971 moves exactly four actual own-library card instances to the graveyard; opponent library unchanged |
| Short library | Repeated real casts mill the remaining fewer-than-four cards without losing; only the later failed draw causes loss |
| Tap ability | Summoning sickness, actual tap cost, only your graveyard artifacts, cancellation before payment, target/token/seat validation |
| Casting permission | Only the chosen card, only after resolution, costs and normal timing preserved, expires at end of turn, new graveyard object needs a new permission |
| Source and target changes | Permission survives Emry leaving; a target exiled by a real Crypt activation before resolution gives no permission; tap cost remains spent |
| Artifact lands | Seat produces blue mana; it is a valid artifact target but Emry cannot cast or play a land through that permission |
| Legend rule | Human chooses either old or new Emry; the second entry still mills four when the newly entered Emry dies to the legend rule |
| Brawl commander | Affinity and tax combine correctly; first command payment two mana with an artifact, taxed recast four; failed insufficient payment rejected |
| Commander bounced toward hand | Decline return: goes to hand, no command tax on hand recast; accept: returns to command and the next command cast pays tax |
| Commander exiled from graveyard | Real combat death, decline graveyard return, Crypt self-target, then explicitly keep Emry exiled or return to command; taxed recast pays five after Crypt leaves |

Final headless receipts are private under
`D:\GAMES\CodexAssets\ForgeArenaSandbox\research\emry-mechanics`:
core 251 checks; Brawl affinity/tax 106; hand/command bounce 109 per branch;
legend keep-old/keep-new 105 per branch; artifact-land 65; target invalidation
137; short library 419; commander exile 77/123 for decline/return. These totals include shared turn/input assertions, not that many distinct
card mechanics. Individual `verify_emry_*.py` files reproduce the sequences.

## Native observations

Original Emry art/cost, four-card mill, original graveyard target prompt 5287,
purple graveyard casting, real Emry tapping and two complete Spellbomb
sacrifice/recast loops have been exercised in the isolated client. Spellbomb's
Draw option was also selected with an actual OS mouse click in the original
ability picker. The old and new Emrys render in the original legend chooser;
selecting the old one leaves it alive and resolves the second mill. Seat has
produced an actual blue mana entry through its original battlefield interaction.
Crypt's original player-target screen was exercised with an actual OS mouse
click on the local avatar; its real sacrifice and resolution moved all ten
graveyard cards into exile. That live recording predates the correction of the
exile transfer's presentation category from the old fallback to source-supported
`Exile`; the game-object zones and rules result were correct. A fresh rendered
run now repeats the player click and Crypt resolution with the current DLL:
four milled cards plus sacrificed Crypt leave the graveyard, and all five
transfers parse as `Exile` across the 44-state recording. The original match
continues with no host gap. Both recordings are retained separately.

The exact **Forge Emry Brawl Test** desktop shortcut launches the current isolated
client, shows Emry in command and starts at25life. Its first free mulligan redraws
seven, and Keep on that redraw now enters turn one with seven and no bottom
selection. The earlier supposed Keep-workflow failure was a test-driver race:
an inspection could overwrite an unconsumed click. Requests are now serialized
and atomically published, with original callbacks and state checks preserved.
The newer live Brawl session also cast Emry from command, paid three real blue
lands, recorded command cast count one and resolved its four-card entry mill.
The installed parser replays 88 states with the commander identity preserved.
Another live Brawl sequence assigned Emry to block Isamaru through the original
blocker workflow, kept the dead commander in the graveyard, activated Crypt
during the opponent's combat, selected the local player, and displayed the
original **Command / Exile** prompt. Choosing Command returned Emry with one
previous command cast and two tax. Its separate parser replay covers49states.
That same live game then played five actual Islands, showed the original 4U
commander offer, paid all five, resolved Emry and recorded command cast count
two with another four-card mill. The extended replay covers101states.

Recorded messages replay through the installed Arena parser separately from
rendering evidence. A parser pass alone is not a rendered or physical-input
claim. QA uses original callbacks for most interactions and one serialized
native request file; do not run multiple native input drivers concurrently.

## Remaining boundaries

The saved 100-card Emry export has 75 distinct names. Current admission covers
31 copies across six of those names: 26 Islands, Emry, Ornithopter, Spellbomb,
Seat and Crypt. The remaining 69 names/copies need their own adapters and
interaction checks. The saved export was inspected locally, not freshly pulled
from the account. The rebalanced A-The One Ring catalogue omission remains;
the original Ring is not substituted.

General tutors, counters on permanents, equipment, additional costs, replacements,
ordering and other unsupported card families remain outside admission. Commander
library replacement is recognized but not sequence-tested; exile commander
return has both headless owner-choice branches and the native return-to-command
path; native decline-exile and commander hand-choice rendering remain unverified.
Other commanders need their own tests. Smart yield, complete visual
and animation parity, a full rendered Emry Brawl game, and general manual play
are not claimed. Some legal activation windows require extra Pass clicks.

The preview.12 tester package and the other local portable installation were
not updated by this checkpoint. No publication, multiplayer, account mutation
or new dev log is included.
