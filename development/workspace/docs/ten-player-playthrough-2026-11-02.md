# Ten-player native playthrough - 2026-11-02

One normal-menu Commander ten-player session was played through natural human defeat at global turn 162. The human used the saved Isamaru Brawl deck against nine real Isamaru/Emry/Selvala decks. At least 257 permanents were sampled. This is not a completed whole-pod winner: the client deliberately pauses the remaining nine bots after human elimination.

## Confirmed issues

| Priority | Finding | Evidence |
| --- | --- | --- |
| Turn flow | Opposing Soul-Guide Lantern exiling four human graveyard cards unnecessarily opens mandatory "Order cards for Exile" / Done. | exile-order-prompt.json, exile-order-prompt.png, exile-order-confirmation.json |
| Usability | Ten-player commander-damage dialog places the last players and Close below the initial view. Scrolling and Escape work. | commander-damage-live.png, details-escape-result.json |
| Minor | Clicking a disabled empty graveyard/exile counter falls through to the parent player row and pins it. | zone-count-review.json |
| Usability | Settings retains retail Report a Bug / Contact Support / Repair Game Files actions rather than client-specific help. No external submission or repair was performed. | settings-physical-window.png |
| Feature gap | Human elimination pauses all remaining bots; there is no continue-spectating path. | natural-loss-window.png, native-loss-settled.json |

The exile ordering originates in `ForgeLandEngine.orderMoveToZoneList`. Any correction should preserve meaningful library, graveyard, stack and face-down-pile ordering; ordinary face-up exile is different. See [Comprehensive Rules 400.5](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).

## Passed and limitations

- Original Keep, lands, creatures, commander tax/returns/recasts, attacks, blocking, deaths and lifelink ran in the same session. Observed attacks followed the nearest-left restriction while more than four players remained.
- All ten displayed life, graveyard and exile counts matched authoritative data at the audited checkpoints. Player pin/follow and populated graveyard browsing/Done worked through physical controls.
- Natural defeat settled without a renderer/rules gap. Physical Return Home reached Home with an inactive match and idle coordinator. No hard crash occurred.
- Two instrumented 30-second frame windows averaged 7.76 and 8.38 ms; occasional larger spikes remain. Inspection overhead was present, so this is not a quiet-control performance comparison.
- Passive bot attacks were observed, but no live AI defender-selection instrumentation established a cause. Final-four reflow, a whole-pod winner and all-card coverage remain untested.

## Log follow-up

The extension log contained no Exception/Error/Fatal matches. Original Unity logs contained offline DNS/manifest failures in the deliberately network-blocked test. Separately, seven life-update events could not find their affector (IDs 1/2/5), one elk sound event failed, and ten component-on-destroy messages occurred at scene unload. These are retained presentation/teardown investigation candidates: audited life totals were correct, so they do not establish incorrect life accounting or a crash.

## Evidence and cleanup

Private evidence root: `C:\Users\loula\Documents\Codex\ForgeArenaTenPlayerPlaythrough-20261102`.

The complete report is `playthrough-report.json`. Native captures and action receipts are under `Native Card Validation\sessions\20261102T145108Z-1db86465\playthrough`. All owned test clients, service and rules engine exited. All 36 original private mutable groups and four immutable game assets were independently hash-verified restored. No gameplay source repair, user-client install, GitHub publication or updater promotion occurred in this test.
