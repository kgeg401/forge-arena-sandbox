# Validation and limits

The current release's enabled names are generated into
[SUPPORTED-CARDS.md](SUPPORTED-CARDS.md). Its exact update version is recorded in
`release-info.json`; its support policy is `ForgeBackend/bridge_support.json`.
This remains an alpha, not a claim that every Arena card or animation works.

The native-menu acceptance below records the original **0.01 alpha** checkpoint
on 22 October 2026, on one Windows PC. Later catalogue batches add evidence for
specific mechanics; they do not turn these historical checks into an exhaustive
validation of every interaction.

## 370-card catalogue checkpoint

The 22 October 2026 delivery checkpoint expanded the locally installed policy
from 278 to 370 verified Arena card names. The earlier public release had 252.
These additions cover trample creatures, removal, fixed creature damage,
temporary stat changes, and reviewed draw/life effects.

- The final 59 effect cards passed 477 targeted rules scenarios / 10,301
  assertions, 62 fresh-process reference comparisons, 24 complete shuffled
  Forge games, 899 original native control checks and 59 native model/art checks.
- The first 33 additions reuse reviewed, sealed source and gameplay evidence.
- Production regression passed 25 stages / 272 recorded engine assertions and
  three complete games. Compiled package classes match the gameplay-tested ones.
- A normally shuffled installed game completed 75 original native control
  actions over 31 turns. Native stats and annotations confirm Bombard, Ragefire,
  Giant Growth and Titanic Growth. An earlier short loss lacked burn coverage;
  it is retained as a coverage shortfall. The longer game's bounded timeout was
  resumed in the same session without replaying accepted inputs.
- Installed acceptance checks policy, enabled deck-builder names, support index,
  the live zero-network native process and original Home together. Existing
  decks, collection, preferences and play selection were preserved. Only the
  two declared new practice decks were added.
- Activation/rollback/reapply preserved saved profiles. Paradox Engine remains
  a disabled research draft and is not a supported card.

These are bounded mechanic and integration checks on one PC. Representative
complete games do not establish every possible Magic interaction, complete
animation parity or a successful installation on another PC. Release shipping
checks are recorded separately in the release notes.

## Native client checks

These checks ran the installed sandbox's actual Arena process, in its
zero-network-capability AppContainer. They are separate from headless fixtures.

| Area | Observed result |
| --- | --- |
| Dedicated launcher | Opens native Home; a second launch focuses the same game process. |
| Persistent menus | Home, Decks, Packs and the original Play panel share one lifetime. Advertising and online account/reward controls are omitted. |
| Brawl queue | Both Emry and Isamaru starters reached the native board with 25 life and the original mulligan controls. |
| Emry | Cast from the command zone through native card controls; Forge resolved the entry trigger and moved four cards to the graveyard. |
| Complete game | An Isamaru Brawl game reached turn 12 and a natural Forge defeat, with the original native result presentation. Continue returned Home; a Practice match then started in the same process. |
| Mouse handoff | After a separate Brawl concede and native Continue, a physical mouse click opened Decks in the same process. The menu input module now survives match-scene unloading. |
| Queue cancellation | The original loading presentation's local Cancel control returned Home without starting a second match. |
| Engine failure | Stopping the exact owned Forge process showed the original message view. Return Home recovered without repeating the notice. |
| Deck editor | Original search, color/land controls, advanced type/rarity/mana controls, size toggle, card zoom, deck rows and commander controls were exercised. |
| Deletion | Physical selection and the original confirmation dialog: Cancel retained the deck; Delete removed only that selected deck. Restart did not recreate the deleted starter. |
| Fresh profile | Eight friendly starter decks appeared without a tutorial or account login. |
| Pack opening | A physical pack click and Reveal All/Continue used the original presentation. Exactly one pack was consumed and eight cards saved. Navigating away and restarting preserved the receipt and balance without another grant. |
| Preferences | A dirty deck saved on normal exit. A changed master volume reopened with its saved value; legacy preference bytes were retained. |
| Display | Native Options changed resolution from 1280x720 to 1600x900, then to 2560x1440 fullscreen. Separate real restarts reopened at both saved sizes/modes; native capture dimensions and the launch receipt agreed. Restored 1280x720 windowed after acceptance. |

Native callbacks used for automated gameplay go through the installed game's
original controls. They do not write a desired result or intermediate Forge
state into the match. Some checks use physical Windows mouse/keyboard input.

## Headless checks

- **70** compiled deck-profile checks: parsing, counts, printings, Brawl
  construction, save failures, persistence and one-time friendly starter seeds.
- **7** compiled preference checks, including a separate-process reopen,
  legacy migration and rejection of corrupt data.
- **4** real process-lifetime checks: startup cleanup closes only its exact
  held native child and preserves an unrelated process.
- **11** compiled display-profile checks: defaults, saved window size,
  borderless/exclusive launch arguments and invalid-file rejection without
  modifying the saved file. Fullscreen native acceptance covered borderless;
  exclusive mode has argument checks only.
- **33** coordinator checks: queue identity, independent saved-deck validation,
  stale requests, cancellation, shutdown and process ownership.
- **44** updater checks, **22** startup/feed checks and **39** prerequisite/setup
  checks. These also pass from the reorganized public source tree.
- Separate Forge Brawl runs: **29** Isamaru checks through turn 20, including
  repeated command-zone returns and costs 1/3/5; **26** Emry starter checks
  through turn 22 against the Isamaru bot.

The retained broader card checkpoint has 25 stages, 272 assertions and 139
spell casts / 1,112 checks. It is a bounded rules/bridge regression, not evidence
that every possible interaction among those cards has been exhaustively tested.
The UI release does not expand that admission policy.

Public CI can run the authored Python checks without game files. It cannot
establish rendered gameplay, pixel parity or installation on another person's PC.

## Pinned compatibility

Arena: **Client0.1.14517.1329972 / Unity 6000.3.14f1**.
Forge: **2.0.15**. The installer verifies the exact files in `requirements.json`
and `dependencies-lock.json` before use. For source checkouts, those files are
under `client/`.

The packaged support index must identify the exact SHA-256 of that release's
admission policy and its pinned Forge scripts. The running client's generated
manifest and deck builder must agree with it.

## Remaining gaps

Only names in the current supported list, plus the separately verified Brawl
commanders and token, are admitted. Unverified cards can be browsed, opened and stored but
cannot enter a match. Emry support does not imply that every Emry deck works.

Both queues use local Forge AI. Online matchmaking, multiplayer, account
services, full card coverage, retail format banlists and complete presentation
parity remain outside this release. Pack collation is custom; retail wildcard
rewards, bonus sheets and duplicate protection are absent. Matches do not resume
after closing the client.

An actual release ZIP must additionally pass package-content scanning,
activation/rollback and public-download verification. Release notes record those
shipping checks separately once performed. No recipient-PC install is claimed.

## Jace Brawl alpha.7

Adds the exact 100-card Jace Superfriends Brawl starter, using Jace, Multiverse
Architect as the WUBR planeswalker commander. The separately pinned official
Forge 2.0.16 snapshot supplies its original rules script. The launcher upgrades
the private Forge runtime and retains the previous runtime for rollback.

Focused native-handler tests cover draw-two/bottom-one, all three reveal-until
outcomes, loyalty costs and once-per-turn activation, both combat-tax branches,
and attacks on Jace and other planeswalkers. Narset rebound is checked through
next upkeep, including the free second cast. Ichormoon's granted proliferate is
checked against actual loyalty changes. A normally started 100-card match
completed 30 turns / 570 actions without an engine exit or mapping gap.

The verified catalogue remains 370 names. The 343 additional experimental
names are explicitly distinguished from that baseline. A completed match and
per-card smoke checks do not establish every card branch or combination.
No complete Arena catalogue or retail Brawl legality claim is made.

Final alpha.7 acceptance: 100 distinct deck cards passed native play/cast smoke
checks (61 spell resolutions and 39 land plays); all 21 planeswalkers also used
one legal loyalty ability. The 51 regression groups passed with final repeats
for optional payment, automatic mana and Tower sacrifice. Eight automatic
turn-flow/response modes passed. These counts describe the scenario scope, not
every branch on each card.

The installed-client acceptance upgraded the private Forge engine, retained
all prior deck records unchanged, seeded the Jace starter, opened Brawl Bot,
and rendered a normally started game with the original mulligan UI, 25 life
and Jace in the command zone. The owned Arena compatibility pin is unchanged.
The dependency archive is about 285 MiB and is only needed once per engine
upgrade; the small Windows adapter download remains separate.

## Mana Drain alpha.8 hotfix

Alpha.7's play/cast smoke check resolved Mana Drain's counterspell, but did not
reach the delayed mana trigger. A live game then stopped at the following main
phase because that trigger lacked its original native presentation identity.

Forge's DelayedTriggerEffect promotes SpellDescription to TriggerDescription.
The source projector now does the same for delayed-trigger sub-abilities, so the
existing exact-text binder connects Mana Drain to its original hidden native
ability. Regenerated card metadata changes only Mana Drain's ability bindings;
the gameplay adapter, rules engine, admission and other cards are unchanged.

The dedicated native sequence test follows countering during the opponent's
turn through the next local main phase, checks the exact colorless amount and
original trigger identity, then verifies clearing and no repeated trigger on
the following local turn. It includes mana values 0, 2, 3 and an uncounterable
4-mana spell. This hotfix requires reopening an already running match client
because each match loads its integration bindings at startup.
