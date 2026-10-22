# Arena Brawl foundation

Run `Open-Brawl.ps1`, or the local **Forge Arena Brawl Test** desktop shortcut.
This developer mode starts a normally shuffled 100-card local match against
Forge AI using the original isolated Arena client. Retail Arena is unchanged.
The earlier private tester ZIP (preview.12) predates this mode and was not updated.
See [Emry mechanics](emry.md) for the newer **Forge Emry Brawl Test** shortcut,
the artifact loop and current evidence. The earlier recorded Keep-after-redraw
failure was an automation race: the old driver could overwrite an unconsumed
action with its next inspection request. Serialized native QA now launches the
Emry shortcut, redraws seven for free and successfully keeps those seven into
the real turn-one match at25/25. Wire/state evidence is under
`research/emry-mechanics/native-brawl-free-keep-*` on D:.

The first commander is **Isamaru, Hound of Konda**: a source-checked vanilla 2/2
for W, installed Arena printing72175. This originally isolated commander rules
before Emry's artifact abilities were connected. The test main deck contains93Plains and six
different supported white cards; its high land count is a test constraint, not a
recommended deck. Normal practice now admits sixteen names; Isamaru is admitted
only as the designated commander in this restricted Brawl mode.

## Implemented and checked

- Exactly99 main plus one commander, singleton nonbasics, separate commander
  admission, and the current monocolor identity boundary. Python import and Java
  independently reject malformed/off-color/unsupported lists. No queue banlist
  or full Arena-format legality claim is made.
- The installed Forge Brawl variant owns commander registration and gameplay;
  both players start at25. Our 99-main policy replaces the installed preset's
  59-main deck-size validation for this Arena sandbox.
- Free first London mulligan, real bottom selections, and valid progression to
  a zero-card keep. Native presentation uses the recovered free-mulligan field.
- Real command-zone casting uses Forge's alternative/may-play spell options.
  Forge owns payment, zone changes, history and accumulated commander tax.
- The local player explicitly chooses whether a dead commander stays in the
  graveyard or returns to command. Stale/wrong-player/malformed answers fail.
- Original Arena command zone, commander designations, Brawl versus-screen
  metadata,25-life display, card art and native casting/control workflows.
- Original commander OptionalAction workflow and source prompts133–136 were
  recovered. The graveyard133 path is rendered and connected to Forge. The
  hand136 replacement and exile134 return are tested headlessly in both
  directions. The live Emry exile134 choice now renders and returns her to
  command with history/tax preserved. Native hand-choice rendering, exile
  decline and the library path are not yet claimed.

## Earlier Isamaru checkpoint evidence

Private outputs are under
`D:\GAMES\CodexAssets\ForgeArenaSandbox\research\brawl-foundation` and the
named combat-check folders beside it.

Four normally started engine games completed: foundation return/recast17checks
(turn32, actual costs1/3); decline-return15checks (turn30, commander stays in
graveyard); and commander-plus99Plains152checks (turn186, actual costs1..93 in
steps of2,46 return choices, genuine decking). The last game dealt22/24 commander
combat damage and ended with both players alive at3/1 before the decking loss,
confirming that Brawl does not use Commander's21-damage loss condition. These
are headless input-driven games, not rendered whole-game claims.
The final repeat of the commander-plus99Plains game passed153checks, including
an explicit no21commander-damage-loss assertion, with the same turn186 result.

Other checks:16 importer boundaries,14 Java admission boundaries,12 real London
mulligan assertions, twelve source mappings (eleven normal plus this commander),
existing Hare22 and normal constructed7 regressions. Existing catalogue audit58
still passes; its callback inventory now has87 inherited AI signatures out of102,
with the Brawl-specific confirmation overrides kept separate from generic support.

Native evidence includes original Keep, land and command-zone casting through
the native UI callbacks, original combat and the actual Command/Graveyard choice.
The local commander died in combat, returned through that original choice, and
was recast: the native offer was 2W, Forge tapped three Plains, and the commander
resolved onto the battlefield with two command casts recorded. Replay parsed194
states with one commander identity per player throughout the changing object IDs.
The new desktop shortcut also launched a fresh isolated match; its original free
mulligan button redrew seven with zero bottom cards after the first rejection.
Keep on the resulting hand failed to emit a native response. This was retained
as a separate native UI gap; successful engine mulligans do not resolve it.
Read-only diagnostics show one Keep and one Mulligan subscriber before and after
redraw, with Keep targeting the current workflow. A missing browser subscriber
is therefore not established as the cause. Do not bypass the native submission
path to call this fixed; trace the request/submission lifecycle next.
The installed parser replay keeps one commander identity per player as native
object IDs change. Native screenshots and wire evidence remain private. Mouse
automation was unreliable; callback-driven validation is not a physical mouse
test. No dev log or video was created.

## Remaining boundaries

**The complete saved Emry deck is not playable yet.** Emry's own discount, mill
and graveyard-casting abilities now have normal-game sequence and native loop
checks. Current saved-list admission covers31/100copies and6/75names. The other
69 names and the rebalanced catalogue omission remain; do not infer complete
deck support from the Emry fixture.

The installed commander hand/library replacement is recognized explicitly,
with headless hand-return/decline checks. Library replacement is not
sequence-verified. Other unmapped replacements stop rather than choosing an
inherited AI answer. Native exile decline, advanced zone/replacement
interactions, planeswalker/partner/multicolor commanders, commander selection in
the deck editor and broader manual-input verification remain unfinished.
Complete native presentation/animation parity and a full rendered Brawl game
are not claimed. The newer Emry fixture and current checks are documented
separately in [Emry mechanics](emry.md).

The command-return category was corrected from PlayLand to source-supported Put.
An explicitly modified replay parses the return as Put across194states; this is
parser evidence only, not a new rendered return-sequence claim.
