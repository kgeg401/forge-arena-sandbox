# Arena-only card coverage: 30-minute checkpoint

Scope: existing installed Arena cards and assets only. Forge-only cards are not
added to the client. Dev logs are disabled at the user's request.

The **Forge Arena Hares** desktop shortcut starts the normal shuffled sample
against the existing white opponent. The current native diagnostic scene is
separate: its prearranged hand and mana isolate token creation/removal.

## Implemented

`ForgeBackend/build_card_coverage.py` reads the pinned owned Arena SQLite database
and installed Forge card scripts. It creates private name/script coverage and
per-printing mappings under `D:\GAMES\CodexAssets\ForgeArenaSandbox\research\card-coverage`.
The index covers 20,159 primary non-token printings and 16,140 English names.
15,814 names have a unique normalized script candidate; 326 have no script-name
match. Missing names can include naming/version differences: this report does
not assert that every unmatched card is absent from Forge.

Per-printing mappings include Arena identity, art ID, set/collector labels,
types, subtypes, supertypes, printed cost/stats, abilities and token links.
Feature tags are script-text hints, not validated mechanic coverage. Neither
matching names nor indexed printings establish playable support.

The native card-identity switch is replaced by a generated runtime manifest.
Explicit admission and preferred printings live in `ForgeBackend/bridge_support.json`.
The importer, deck catalogue and Java backend consume that policy/manifest.
The former source checks remain in place. Basic-land mana IDs 1001/1002 retain
the earlier recovered native convention; they are not present in the source
Cards.AbilityIds field and are recorded separately from database ability IDs.

Hare Apparent (Arena 93728, title 823196, trigger 175767) and its original linked
Rabbit token (94160) are connected. The token is sourced from Arena's own
AbilityIdToLinkedTokenGrpId link and Forge's existing w_1_1_rabbit script.
Dynamic power, toughness, damage, color, ownership and sickness come from Forge.
Token creation/deletion use the original installed annotation parsers rather
than treating tokens as ordinary newly listed objects.

## Verified

- Three actual Forge casts and independently identified ETB triggers create
  zero, one and two new Rabbits. The native Arena slice visibly shows three
  Hares and three original 1/1 Rabbit tokens. The native parser replays all ten
  states without errors. Screenshots, wire and journal are preserved privately.
- The expanded headless Hare test passes 22 checks, including selecting a token
  with Unsummon, its real state-based disappearance, and survival of the other
  two tokens. A separate native run also casts Unsummon, selects an actual Rabbit
  through the original target workflow, and visibly removes it while keeping
  the other two. Its 39-state recorded wire replays through the installed parser.
- A normal shuffled 60-card Hare deck, seed 7275, beats the existing white
  opponent on turn 14 at 16/-6 life. Seven complete-game checks pass; 170
  recorded response states include up to five Hares and fourteen Rabbit tokens.
  This is a complete headless game, not a complete rendered-game claim.
- Existing single/double Orator tests pass 7/13 checks. The earlier normal
  practice game still passes seven complete-game checks. Import/startup checks
  pass 20 checks; deck storage checks pass 23 checks. Eleven source mappings
  pass the retained identity/type/cost/subtype checks.

## Remaining gaps

The runnable match set is eleven names plus the Rabbit token, not 15,814 cards.
General keywords, activated abilities, additional mana/cost forms, mode/player
choices, replacements, transformations and broad card/ability presentation
remain outside this admitted slice. Whole-client Home navigation is unchanged.

Native casting in the focused Hare run was invoked through the original
workflow's CanClick/OnClick probe, producing its real outgoing action messages.
Mouse-driven Resolve buttons were exercised. Repeated OS double-click attempts
did not reliably cast; manual human input has not been independently confirmed
for this new slice. A full rendered normal Hare match still needs separate
verification before broader presentation claims.

Two test-harness issues were retained as evidence: seed 7274 kept a one-land
Hare opening and completed with fewer combat decisions than the generic test's
threshold; the deterministic token-bounce fixture initially spent its only blue
source on generic casting costs. A second normal-game seed and reserved-source
fixture addressed those test conditions without replacing Forge's rules.

## Next checkpoint

Validate manual play in the native client, then expand one
mechanic family at a time using the generated catalogue. Admission stays
separate from candidate mapping and requires explicit comparison evidence.

Name normalization strips Arena rich-text tags and decodes HTML entities before comparison. This recovered 612 additional name matches that raw localization markup initially obscured.
