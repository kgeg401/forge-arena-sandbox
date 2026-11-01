# Exert and combat-priority checkpoint — unreleased, 1 November 2026

This source checkpoint connects optional Exert choices to Forge and repairs a
native presentation pause after combat damage. It does not update an installed
client, publish a release, widen card admission, or establish complete Arena parity.

## Rules and card presentation

`ForgeLandEngine` forwards Forge's original eligible attacking creatures as an
optional 0..N human selection. Forge still pays the cost, creates the original
reflexive trigger, schedules extra combat, and skips the appropriate untap.
The bot path is unchanged. No human decision is delegated to the bot.

`ProjectForgeCards` now includes triggers attached to original OptionalAttackCost
static abilities. `build_human_choice_bindings.py` connects those effects only
when the owned native card graph has one matching linked hidden effect. The
source-tagged reflexive prefix is normalized in this path; ambiguous or missing
matches remain gaps. There is no arbitrary card-name or ability-ID fallback.

The tested private overlay changes Combat Celebrant's presentation bindings
without changing admitted names, verified flags, experimental flags or printing
identities. Derived bindings and the original game data remain private.

## Combat-damage priority

The owned native ActionsAvailableWorkflow cannot apply on a presentation frame
that carries combat damage. Sending a priority request with that frame could
leave no usable Next button while Forge correctly waited for a response.

The rendered host now sends the damage presentation without an immediate action
request. After the existing native readiness callback confirms presentation has
finished, it sends one clean view update and the request for the **same** Forge
priority window. It does not pass priority, replay damage, advance a rules phase,
or use a fixed animation delay. Full control and legal responses remain available.
The Unity plugin explicitly enables this behavior; parser-only workers retain
their existing immediate-request contract.

## Direct evidence

Private evidence is retained under `ForgeArenaTwoHourHorde-20261101`:

| Check | Actual result |
| --- | --- |
| Exert accept, decline, invalid-then-accept | 33 checks through original native handlers and Forge; extra combat, damage, next-untap skip and following untap |
| Two eligible Exert sources, choose zero/one/both | 27 checks; exact optional bounds, identities, trigger effects and zero/one/two extra combats |
| Ordinary regression | 20 jobs with the changed rules engine and prior r6 host, including 12 complete seeded duels |
| Turn-flow regression | All eight established scenarios pass with the new host |
| Presentation contract | Real Forge combat and native parsing; controlled unready/ready presentation, no duplicate rules request or damage, explicit player pass retained |
| Rendered Exert | Original chooser and stack trigger; extra combat, exact damage, skipped next untap and later untap |
| Rendered full-control damage | Both damage windows in an Exert sequence have a usable original Next button |
| Rendered instant response | Cast, target, automatically pay and resolve Giant Growth during combat-damage priority, then pass normally |
| Rendered two-source subset | Select one of two attackers without forcing the maximum; explicit Submit remains available |
| Rendered double strike | Life 20→19→16 across distinct first-strike/normal windows; instant response works, empty windows then advance to the next playable turn |
| Rendered combat deaths | Both creatures move to their original owners' graveyards; native death/zone-transfer presentation completes and Next remains usable |

The last sequence contains exactly three native damage annotations (1, 1, 2)
and two aggregate life changes. View refreshes do not duplicate damage.

Reproduce Exert with `ForgeBackend/verify_exert_combat.py` and explicit private
config, worker, managed-assembly, fixture and output arguments. The three
`multiple-*` cases cover subset selection. Run the presentation contract with
`ForgeBackend/verify_turn_flow.py --mode combat-presentation` and the corresponding
TurnFlowProbe build. Presentation readiness in that probe is controlled; it is
not a replacement for the separately recorded Unity checks.

Earlier failures remain retained: missing human Exert callback, unmapped hidden
trigger, the original full-control damage pause, and a first adapter experiment
that incorrectly deferred parser-only requests. The final renderer opt-in fixes
the latter without changing the parser-only contract.

## Packaging preservation

Incremental binding preparation now requires explicit `--incremental` when the
input already contains an earlier overlay. It checks that parent, preserves
existing overrides and presentation objects, and requires complete reconstruction
of the expected card map. An implicit drop, wrong parent, absent presentation
object, admission change or overwrite of prior evidence is rejected.

Six preparation checks pass. Two fresh consumer catalogue generations differ
only in Combat Celebrant's new binding: all 1,796 presentation entries, 1,655
admitted primary names, existing 139 presentation objects, printing identities
and admission flags are preserved. A private, unpublished development package
passes 18 backend checks, including exact class equivalence to the independently
tested rules engine. This is package evidence, not an installed-client update.

## Remaining limits

Exert currently uses the original general card-selection workflow, not Arena's
special attack-with-Exert widget. This is not widget parity. The evidence covers
Combat Celebrant and specific combat sequences; it does not qualify every Exert
card, every simultaneous trigger ordering, multiplayer combat, or all stop settings.
Private native tests restore their own backed-up files and preserve the user's
installed client, decks and unrelated game/server state.
