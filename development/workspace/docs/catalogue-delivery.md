# Catalogue delivery checkpoint

The delivery target is playable cards installed in the local client. Research
counts do not substitute for delivery. The 2026-10-22 two-hour checkpoint starts
from 278 supported main-deck names and targets 100 additional cards where their
mechanics and validation can be completed within the time limit.

## First reviewed batch

`promote_catalogue_families.py` reviews the sealed prior source/gameplay evidence,
checks its artifact hashes and unchanged rules/native implementation, and emits
a separate policy. It does not install or publish anything. The first batch
qualifies 33 names: 22 source-exact trample creatures, Shorecomber Crab, Revitalize,
Ritual of Rejuvenation and eight fixed temporary creature pump spells.

Each card has exact native source qualification, relevant authored gameplay
cases, original artwork/model checks and original cast/resolve callbacks.
Temporary pumps additionally have per-card native targeting, Cancel, Submit,
stat change and cleanup expiration. Trample has per-card blocked allocation
cases and shared original damage-browser checks. Complete normally shuffled
games cover representatives of each shared mechanic. This follows the existing
plain-creature family's distinction between per-card rules checks and shared
mechanic sequence checks; exhaustive Magic interactions are not claimed.

The second review adds28 creature-removal spells,13 fixed creature-damage
spells,11 signed temporary modifiers and7 individually reviewed conditional
draw/life formulas. Together with the first33, the reviewed production policy contains370
names, a92-card increase. These additions have477 passing authored scenarios,
62 matching fresh-process reference cases, original per-card artwork and control
checks, and24 complete shuffled engine games. The conditional native sequence
ends at the independently expected46 life and12 cards.

Source index presence does not prove
retail legality, ownership or release status. Rebalanced/digital/linked-face
versions are rejected by the source qualifier for these families.

## Delivery gates

Before updating the client, run the complete production regression against the
committed policy; freshly compile/package the rules and native adapter; verify
package identities; back up profiles; apply the existing reversible local
updater; launch the actual installed client and verify its new metadata and
playable behavior. Preserve the unfinished Paradox Engine draft outside the
committed package policy. Keep the prior version available for rollback.

`promote_tested_effect_families.py` consumes explicit family evidence paths and
checks actual case journals, source snapshots, native reports and full-game
traces. Fizzles are recorded separately and receive no resolution credit.
`verify_installed_catalogue.py` checks the running native process, policy,
runtime admission, deck builder and support index together, plus preservation
of existing saved decks and profile files. A review receipt alone is not delivery.

Installed delivery completed at370 names in private0.2.0-alpha.4. All25 final
production stages/272 recorded engine assertions and three complete regression
games passed. The installed client completed a75-action/31-turn native win with
Bombard/Ragefire damage and Giant Growth/Titanic Growth stat evidence. Its
18 acceptance checks confirm the policy, deck catalogue, actual active support
index, live zero-network native process and preservation of saved profiles.

The user subsequently authorized consolidating all current source and shipping
the370-name state as public0.2.0-alpha.5. Disabled Paradox research is preserved
separately. Original game data, raw native evidence and private profiles remain
local. Publication is verified separately from these gameplay checks.
