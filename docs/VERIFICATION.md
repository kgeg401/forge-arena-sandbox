# Current gameplay alpha: 0.2.0-alpha.10

The verified baseline remains **370 names**. **1,285 additional names are enabled
experimentally**, for 1,655 admitted primary names. This release adds 942 names
from the Arena-compatible portion of Moxfield's 50 most-viewed public Commander
decks captured on 30 October 2026. Its pinned Forge dependency remains the
official 2.0.16 snapshot from 25 October. The card pool is restricted to identities
in the owned, pinned Arena catalogue; that is not a retail-format legality claim.

See [Moxfield coverage](MOXFIELD-COVERAGE.md) for the captured deck links and
[per-card evidence](MOXFIELD-CARD-COVERAGE.csv). The 1,188-card pool has complete
identity/presentation bindings; 1,173 generic cast/land walkthroughs complete,
and 15 require dedicated scenarios. Of 284 first-activation attempts, 215 complete
and 69 need particular fixtures. Those are bounded smoke tests, not exhaustive
effect verification, and none promotes an experimental card to verified.

## Changes and direct evidence

- Mandatory triggers use the native Auto Order Triggers preference. Default
  ordering avoids a needless prompt; manual ordering remains available. Forced
  one-option choices and irrelevant graveyard ordering advance automatically.
  Genuine targets, optional choices, library ordering and response windows remain.
- The original Auto Choose Replacement Effects preference is now forwarded too.
  Automatic mode uses Forge's pinned replacement chooser; this is not a claim
  that its ranking matches Arena's server heuristic. Manual mode preserves the
  ordering picker. Native tests cover both Coldsteel Heart modes, the actual
  color decision, Chatterfang/Took token outcomes and a live preference change.
  A rendered two-copy Coldsteel Heart sequence also passes after toggling the
  actual setting inside the same match. Manual effects from the same source
  still use numbered labels; their presentation is not fully reconstructed.
- Mixed spell/permanent targeting, relationship-dependent target legality,
  divided spell damage, cancellation, gift-dependent availability and X targets
  use the original Forge rules. The native spell-damage spinners replace the
  inappropriate combat-order browser. Five damage scenarios and cancellation
  pass native handlers, including an actual rendered Inferno allocation.
- Twenty-four dedicated card scenarios pass native handlers for counters,
  redirects, copying/control, gift, kicked Sowing Mycospawn, Peerless Recycling,
  Stolen by the Fae and Warping Wail modes. Six delve cases and both Sauron's
  Ransom pile selections pass; the original pile browser was visually checked.
- Invasion of Ikoria uses its chosen protector as the attack destination,
  retains defense counters and transforms through its actual defeat trigger.
  Eleven native checks cover X=2, search, attacking the player's own Battle,
  six damage, Zilortha and no damage redirected to the opposing player.
- Eleven ninjutsu scenarios cover nine names, combat timing, return payments,
  reduced costs and Yuriko from both hand and command zone. Twenty-eight
  hand/graveyard scenarios cover cycling, typecycling, channel, unearth,
  graveyard activation and eternalize. Sokenzan's temporary token haste retains
  its real source and expires; Fanatic of Rhonas uses its original eternalized
  token presentation and original copy-factory characteristics.
- Protection tests cover colorless and card-type choices, restrictions and
  expiration. Wizard Class tests cover levels, draws, targets, bounce/reset and
  expired level-three behavior. Rendered acceptance confirms level-two draws,
  level three, two genuine target clicks and the resulting two +1/+1 counters.
- Eleven conditional-activation cases cover Wirewood Symbiote's once-per-turn
  limit, Inventors' Fair's artifact condition/search, Chthonian Nightmare's
  actual energy/sacrifice/return costs, Shifting Woodland's copy and expiration,
  Mycosynth Gardens at X=0 and X=2, and Bolas's Citadel's ten-permanent sacrifice.
  Insufficient mana/energy are rejected without spending resources; declining
  energy retains the original objects and permits retry. X-dependent targeting
  is checked before announcement without choosing X for the player.
- Fourteen context cases cover six/seven-card threshold boundaries, Dinosaur
  recovery, Haywire Mite's exclusion of creature artifacts and actual death
  trigger, Kogla/Plaza protection and expiration, Volatile Fault's search and
  Treasure, Mistveil Plains' white-permanent condition and actual bottom-card
  draws, one/two-attacker Minas Tirith history, and Swarmyard regeneration
  replacing a real Doom Blade without a death trigger.
- Rendered normal combat with Magda and Toski advances through four mandatory
  triggers to the next playable main phase without confirmation clicks. Eight
  separate turn-flow modes preserve stops, responses, yield and Resolve All.
- Normal-match regression covers opening/starting-player, draw, counters,
  targets, damage and twelve shuffled duel seeds. Eight Emry regressions pass.
  Paradox Engine remains a disabled research draft and is not added here.
- Conceding before the opening play/draw choice now returns cleanly through
  Forge's startup callback without drawing hands or terminating the rules owner.
  Starting-player and target-cancellation scenarios were rerun after that fix.
- Life and Phyrexian payment confirmations now carry the actual Forge cost
  into Arena's original localized question. The first rendered check caught
  a positional-parameter error that parser-only tests missed; the corrected
  prompt is checked separately on screen. Other optional-effect wording is
  not yet fully mapped to retail prompts. Original fixed energy questions for
  one through four energy and source-card return-payment wording are connected;
  arbitrary higher energy amounts do not yet have a mapped amount-specific
  retail question. Rendered Chthonian Nightmare acceptance confirms the original
  two-energy symbols and named return question, one remaining energy, the
  sacrificed Elf, Nightmare in hand and the returned 2/2 Grizzly Bears.
- Seven four-player regressions pass, covering blockers, split attacks, targets,
  commander return/tax, 40-life boundaries, mulligans, elimination and yield.
  A separate 100-turn native pod ends through commander damage. Its Plains-only
  test opponents validate protocol and elimination, not realistic bot strength.

The pod remains **one human and three local Forge bots**, not network multiplayer.
Home Resume keeps the same running match; closing the client ends it. Partner
commander pairs, every card combination, complete Arena presentation parity and
installation on another person's PC are not established by these checks.
Package/update acceptance is recorded separately in the release notes.

---

# Historical gameplay alpha: 0.2.0-alpha.9

The verified baseline remains 370 names; 343 other names are enabled experimentally. The current dependency is the pinned official Forge 2.0.16 snapshot from 25 October. Earlier sections below describe historical releases and their original scope.

The local queues are Practice Bot, Brawl Bot, Commander Bot (40 Life) and Commander Pod (4 Players). The pod is one human and three Forge bots on this PC, not network play. Its shared table and per-seat public-zone controls remain experimental. Home Resume retains a running match only; closing the client ends the match.

The human controller now identifies itself as human before Forge installs its first controller and caches PlayerView. Actual native opening-hand checks reproduced the old AI classification in both a duel and pod, then verified the corrected identities through Keep and land play. A separate real Forge factory check covers renamed seats, an old global match, cached views and a human shuffle that leaves order and RNG unchanged. Bots retain AI classification.

Explicit cancellation of a prepayment target choice is now acknowledged as a successful UI action. Forge still cancels the unplayed spell/ability and retains its costs. A failure to complete costs without that explicit cancellation remains a rejection. The normal Emry sequence covers cancellation, retry and real tap/mana payments. Its fixed-color assertions now use the current explicit color-options schema.

Original hidden trigger and linked token-face data now retain Jace, Cunning Castaway's combat-loot effect, Mana Drain's delayed mana and the active Phyrexian face of Incubator. These are presentation bindings for Forge's rules, not replacement card scripts. The source projection is regenerated against exact pinned local data. UTF-8 test readers prevent Windows' legacy encoding from misreading native card-name text.

A fresh source-to-native binding audit covers the 713 currently admitted primary names. It found the missing Seat of the Synod manual mana identity; its original blue-mana binding is restored and checked through native mana activation, Emry affinity, actual mana payment and the artifact-land graveyard target restriction. The audit is a static presentation-contract check, not 713 gameplay validations. Existing explicit Orator/Hare trigger fallbacks and shared keyword mappings remain unchanged.

Planeswalker presentation now distinguishes numeric printed loyalty outside the battlefield from actual battlefield counters. Jace, the Perfected Mind shows printed five before casting; original native-handler checks cover paying Phyrexian life to enter with three and paying mana to enter with five. This is presentation data; Forge retains the actual rules counters and payments.

Whole-catalogue support, exhaustive card combinations, network multiplayer, complete Arena UI parity and recipient-PC installation are not established by these checks. Final release receipts distinguish the package tests and rendered acceptance performed for this release.

---

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
