# 0.01 alpha: validation and limits

Display release: **0.01 alpha**. Update version: **0.2.0-alpha.1**.
Acceptance work: 22 October 2026, on one Windows PC. This is an alpha, not a
claim that every Arena screen, card or animation has been reproduced.

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

The admission-policy SHA-256 is
`a3df92158b0d95ba37572818ed2803525340a554223f4b6b322ae40d6347516d`.
The packaged support index must identify that same policy and Forge scripts.

## Remaining gaps

Only **252 main-deck names**, plus the separately verified Brawl commanders and
token, are admitted. Unverified cards can be browsed, opened and stored but
cannot enter a match. Emry support does not imply that every Emry deck works.

Both queues use local Forge AI. Online matchmaking, multiplayer, account
services, full card coverage, retail format banlists and complete presentation
parity remain outside this release. Pack collation is custom; retail wildcard
rewards, bonus sheets and duplicate protection are absent. Matches do not resume
after closing the client.

An actual release ZIP must additionally pass package-content scanning,
activation/rollback and public-download verification. Release notes record those
shipping checks separately once performed. No recipient-PC install is claimed.
