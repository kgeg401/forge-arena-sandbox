# Preserved development history

Historical scopes and limitations below are retained as recorded. See the repository README for current playability.

## Earlier normal-startup checkpoint: mulligans and targeted instants (2026-10-21)

`Open-Playable.ps1 -Scenario opening-duel` starts through the installed Forge `Match.startGame`, including zone preparation, shuffled 60-card practice decks, seven-card draws, London mulligans and the full normal game loop. Arena supplies its original Keep/Mulligan and drag-to-library London screens. Forge validates the selected bottom cards, plays the resulting hand, and determines the outcome. This scenario uses only Plains, Savannah Lions, Yoked Ox and Oreskos Swiftclaw; its duplicate-heavy practice decks are sandbox fixtures, not constructed-legal decks. Forge's coin toss now chooses who decides Play/Draw; a local winner uses Arena's original browser, while the opponent uses Forge AI's choice. Test fixtures may explicitly select the older local-first policy.

Forty startup assertions cover keeping seven, two redraws/keeping five, invalid bottom-card choices and concession during either setup prompt. A complete independently driven engine game reached turn 20 and LifeReachedZero. In the native client, Keep7 -> redraw -> Keep6 -> Return1 -> six-card first main -> land/cast/opponent turn was observed and recorded. Headless checks do not establish rendered parity beyond those observed cases.

The 56-second chapter 13 is saved under `D:\GAMES\CodexAssets\ForgeArenaSandbox\devlogs\2026-10-21-opening` and was delivered to the existing Atlas chat as a native attachment, acknowledged at 07:39 local. Originals remain preserved. Normal deck selection, arbitrary cards, general targeted/triggered effects, human multi-block damage ordering and home/Continue flow remain unfinished.

Chapter 14 records choosing Draw First, the opponent turn and the actual eighth card on the local first turn, followed by native concession. Twenty starting-choice assertions, four deliberate Windows file-sharing checks, and a complete normal-game replay with preserved journal pass. Native local single-game metadata uses no series win condition so the original workflow does not automatically hide the Play/Draw browser. This is an explicit sandbox policy.

`Open-Playable.ps1 -Scenario spell-duel` adds Divine Arrow to the normal-startup practice deck (five mapped cards). It targets only attacking/blocking creatures through Forge's candidate list and Arena's original SelectTargets controls, including deselection, Submit and Cancel before paying. The prepared `defend-arrow` scene verified two-mana payment, four native direct damage, death, graveyards and continued play. Twenty-five engine target checks pass. The complete five-card engine game also exercised AI responses that removed targets before resolution; no complete rendered five-card match is claimed. Chapter 15 records the prepared native target/cancel/resolve slice.

`duel` and `mixed-duel` retain the earlier fixed-hand scenarios and desktop launchers. Default launcher behavior remains the previously verified simpler duel. The section below documents that seeded checkpoint.

## Preserved seeded-duel checkpoint

The isolated Arena client now plays a local Plains/Savannah Lions game against Forge's built-in AI. Arena supplies the original board, card controls, attack/block selection, effects, sound, discard prompt and result screen. Forge owns legality, costs, stack resolution, turns, combat, state-based deaths, cleanup and the winner.

Run `Open-Playable.ps1`, or `Start-Sandbox.ps1` (default: `duel`). Double-click a Plains in hand to play it; double-click Savannah Lions to cast using available mana. The native button passes or resolves. Choose attackers/blockers when prompted and confirm. Empty supported priority windows advance automatically through Arena's own workflow; available lands/spells, opposing spells, combat choices and discards still require input. `-FullControl` holds every priority window for diagnostics. To start over, run the launcher again; it archives the previous session before resetting. The native result screen's Continue/home flow is not integrated.

A complete recorded game reached turn 10 and native DEFEAT. The human deliberately passed rather than playing cards, allowing the AI to win: this is a progression/loss-path test, not a competitive AI assessment. Forge and the installed Arena parser agreed on every life change (20, 18, 12, 4, -6), all 13 two-damage hits, the winner and one terminal match event. A separate seeded lethal attack showed native VICTORY. Three local attackers also dealt six with matching native hit events. Concede is handled by Forge from ordinary play and pending human decisions; the native Options button has been observed ending a game at unchanged life.

This is a narrow playable prototype: fixed six-card starting hands, 24-card libraries, two mapped card identities, and a first-main-phase seed. Normal deck selection, mulligans, arbitrary cards, targeting/triggers, manual multi-block damage ordering, home UI and broad presentation parity remain unfinished. Automatic passing is an explicit convenience policy for these admitted cards, not a reconstruction of Arena's server-side smart-stop system.

Retail Arena files and preferences remain unchanged. The private lab runs in a zero-network-capability Windows AppContainer. Code is here; private builds, copied assets, original recordings and evidence are under `D:\GAMES\CodexAssets\ForgeArenaSandbox`. See `behavior-ledger.md` and `MODLOG.md` for the source/implementation/observation distinctions and failed attempts retained as evidence.

Useful checks: `ForgeBackend/verify_mana.py`, `verify_spell.py`, `verify_combat.py`, `verify_combat_cases.py`, `verify_outcomes.py`, `verify_duel.py`, `verify_discard.py`, `verify_concede.py`; installed parser replay via ParserProbe, followed by `audit_recorded_match.py` for a recorded complete match. The final recorded audit is `research/combat-protocol/complete-fixed-audit.json` under the private root.

The optional mixed duel is available through Open-Playable.ps1 -Scenario mixed-duel. It adds Yoked Ox (0/4) and Oreskos Swiftclaw (1W, 3/1), with actual native art and Forge costs/stats. Native casting, a surviving Ox block, and a three-damage Swiftclaw hit were checked; the mixed engine game completed at turn 18. Human multi-block damage ordering still inherits Forge AI policy rather than a translated human prompt. Default desktop play retains the simpler two-card duel.

Two desktop launchers are available: **Forge Arena Sandbox** for the simpler duel and **Forge Arena Mixed Duel** for the four-card variant. Both were launched and checked in the native client. The final 12-chapter, 10:09 dev log is D:\GAMES\CodexAssets\ForgeArenaSandbox\devlogs\2026-10-21-combat\Forge-Arena-Devlog-Combined-2026-10-21-Final.mp4; its sub-9-MB copy and individual chapters were sent as native attachments in the existing Atlas chat. Terminal-action rejection checks are in ForgeBackend/verify_terminal.py.

## Historical checkpoints

The sections below preserve earlier scopes and limitations; they are not the current feature list.

## Current checkpoint: native combat and sound (2026-10-21)

Player-controlled attack and block declarations now run through Arena's original controls and Forge's actual controller callbacks. Selection is staged until submission; Forge validates declarations, taps attackers, deals combat damage and moves dead creatures to their owners' graveyards. Native unblocked damage (20 to 18), blocker pairing, hit/death effects and graveyards were visually verified.

Start with Start-Sandbox.ps1 -Scenario attack-open, -Scenario attack-blocked, or -Scenario defend; the default remains the land/mana/casting starter. -Build recompiles. These are seeded Plains/Savannah Lions scenarios, not complete arbitrary-card games. Use the native Pass button to advance, choose attackers/blockers and confirm. A fresh launch archives the prior session evidence.

Native cached audio now initializes through the original AudioManager startup calls. The isolated process reports 179 available packages, no load error, and a recorded nonzero audio signal. Retail Arena and preferences remain unchanged. General cards, target/trigger choices, normal match startup, a playable opponent and terminal game presentation remain unfinished.

Combat checks: ForgeBackend/verify_combat.py and ForgeBackend/verify_combat_cases.py. Source/API research, native messages, original recordings and the 69-second captioned combat dev log are under D:\GAMES\CodexAssets\ForgeArenaSandbox. See behavior-ledger.md for evidence and limits.

The following sections describe earlier checkpoints at their original scope.

## 30-minute checkpoint: mana, turns, and a creature spell

Verified on 2026-10-20 in the isolated native Arena lab:

- Native Plains click -> Forge pays the tap cost, resolves its mana ability, and Arena displays one white mana with its own tap and resource effects.
- Native pass button -> Forge `mainLoopStep`, including passive-opponent priority, phase changes, mana cleanup, next-turn untap/draw and renewed land permission. Two Plains produce two separately sourced white mana.
- Native Savannah Lions click -> Forge validates/pays its cost and places it on its stack. Native Resolve -> both players pass and Forge resolves the 2/1 onto Arena's battlefield.
- Combat with a creature stops at an explicit gap; attack/block choices are not delegated silently to the AI.
- Exact request replay is idempotent; a different payload reusing the ID is rejected.

This remains a seeded test with Plains and Savannah Lions. Normal match setup, arbitrary cards/targets/triggers, combat choices, opponent presentation, terminal game states, and sound initialization are unfinished. Phase stepping is verified for the empty-board/Plains scenario; it is not a claim of complete match correctness. Installed Arena and Forge files/preferences remain separate from the private lab.

Start a fresh playable test with `Start-Sandbox.ps1` (`-Build` also recompiles). This closes only the exact lab process, stops its verified private Forge backend, archives the prior session evidence, and launches a new network-isolated native board. Double-click a Plains in hand, double-click it on the battlefield, then double-click Savannah Lions and press Resolve. Combat progression stops at the current gap. Restart to repeat, or leave Lions uncast to exercise turns and further land plays.

Run `ForgeBackend/verify_mana.py` and `ForgeBackend/verify_spell.py` for bounded engine regression scenarios. Reports and videos live under `D:\GAMES\CodexAssets\ForgeArenaSandbox`.

The sections below record earlier checkpoints and their limitations at the time.

# Forge Arena Sandbox

Target: Arena's actual installed presentation with a local Forge rules backend for a 1v1 sandbox.

## Current checkpoint

**A Forge-validated land play now works through Arena's native interface.** A native card selection generated `PerformActionResp`; the separate installed Forge engine accepted/resolved its `LandAbility`; the bridge returned an object-ID/zone-transfer update; Arena displayed Plains moving from hand to battlefield.

Verified: first land accepted, second land in the same turn rejected by Forge without changing state, and exact request replay did not apply the land twice. This is a seeded first-main-phase scenario with two Plains. It does not advance turns or implement mana abilities, spells, stack, combat or opponent actions. Audio initialization remains incomplete.

Evidence: `D:\GAMES\CodexAssets\ForgeArenaSandbox\research\forge-land-checkpoint.json`, `forge-land-before.png` and `forge-land-after.png`.

## Earlier native-board checkpoint

The actual Arena board now renders a local synthetic scene inside an isolated lab copy. The real installed database supplies Plains and Hare Apparent in hand/on the battlefield. A subsequent local message changed the displayed life total from 20 to 17. Before/after screenshots and a runtime receipt are saved on D:.

That native-board checkpoint was a presentation proof. The later land-play slice above adds an actual Forge-validated action; complete sandbox games and broad animation parity remain unverified.

Reproduce the lab board with `Open-NativeBoard.ps1 -Redeploy`. It runs only the prepared independent lab in a Windows AppContainer with zero network capabilities. Do not launch the lab executable directly. The lab copy occupies approximately 13.9 GiB on D: and leaves the normal game installation unchanged.

Native evidence: `D:\GAMES\CodexAssets\ForgeArenaSandbox\research\native-checkpoint.json` and `native-board-life17.png`.

## Earlier headless checkpoint

Implemented a socket-free `IGREConnection` adapter and tested it against the **installed Arena parser**, not a replacement parser. The adapter targets .NET Standard 2.1; the headless probe runs on .NET 8.

Verified on 2026-10-20:

- Supplied a synthetic full two-player state and a following diff to the installed `GreInterface`.
- Parsed life totals of 20/20 and then 17/20, preserving the second player.
- Produced Arena's native `UpdatePlayerLifeTotal` event using a modified-life annotation.
- Created an actual Arena `MulliganRequest`, called its `KeepHand`, and received its native response locally with matching state/request IDs.
- Exercised outgoing-command delivery, disconnected/missing-backend rejection, nonlocal join rejection, message cloning, bounded queue overflow and close/reconnect queue clearing.
- Compiled both projects with zero warnings/errors.

That earlier probe alone did not render Unity. The later native checkpoint above establishes basic Unity hosting, card rendering and a life-change presentation update. It does not establish a playable Forge-backed game.

## Run the checkpoint

Run `Run-ParserProbe.ps1` from this directory. It checks the installed DLL identities, builds the probe and executes it headlessly. It does not launch Arena, install a loader, modify game files or make network connections.

On another machine, restore the two SDK projects before using this local no-restore runner. This machine already has the required SDK/reference packs.

Code is here; builds, fixtures and private evidence are under:

`D:\GAMES\CodexAssets\ForgeArenaSandbox`

Latest test report:

`D:\GAMES\CodexAssets\ForgeArenaSandbox\research\parser-probe-result.json`

## Next implementation checkpoint

Extend the narrow Forge-backed land slice to controlled turn progression and mana/spell handling, preserving Arena's actual presentation. Keep unsupported actions explicit rather than pretending the complete rules adapter exists.

Keep scene readiness checks and independent local launch isolation. Do not replace an official match's connection. The current host has a seeded scenario and delegates supported land actions to Forge. Raw fixture injection is disabled while Forge owns the board.

Unsupported translations must stop with a documented gap; the adapter does not invent rules.

See `behavior-ledger.md` for evidence and remaining work.

The current native lab uses `NativeHost`, a lab-only preference preloader, and `LabLauncher`. The launcher verifies an AppContainer token with zero capabilities before resuming Arena. The preloader changes only in-memory lab assemblies: isolated preference storage and nonessential integration initialization. It does not patch authentication or rewrite retail files.

## Forge backend

`ForgeBackend/ForgeLandEngine.java` compiles against the installed Forge 2.0.15-SNAPSHOT jar. Its runtime, user profile and cache are on D:. It reads installed resources through a junction; it does not change the existing Forge preferences or decks. `ForgeBackend/prepare_backend.py` prepares/compiles it and refuses a changed engine identity. `start_backend.py` starts a separate Java process without a Forge window; Forge's library still needs access to display information during initialization, so the JVM is not in Java's strict headless mode.

The backend and Arena exchange atomic request/response files under `native-lab/forge-ipc`. No socket capability is granted to the Arena lab. `enable-forge-land-test.flag` enables the native adapter. Starting a new native land test requires a fresh backend scenario; the host refuses to reopen a completed scenario as if it were new. Preserve the IPC journal before resetting or recreating the test.



Optional `.\Open-Playable.ps1 -Scenario trigger-duel` starts a real shuffled 60-card practice match with Impassioned Orator, Divine Arrow and the admitted vanilla white creatures. Orator triggers are real Forge stack abilities presented by Arena's original UI. This is a six-card allowlist, not arbitrary deck support. Simultaneous identical triggers use Forge's ordering; pending-trigger animation timing and general ability-choice UI remain gaps.


`.\Open-Playable.ps1 -Scenario blue-duel` uses a real shuffled 60-card white/blue practice deck: 12 Plains, 12 Island and six each of the six mapped spells. Island and Unsummon add colored payment and creature returns to either owner's hand. Opponent hidden cards remain unknown. Copy counts are intentionally unrestricted practice settings, not constructed legality.


Choose supported deck files with `.\Open-Playable.ps1 -ChooseDecks`, or pass `-DeckPath <file> -OpponentDeckPath <file>`. Omitting the opponent file mirrors your deck. Canceling either picker leaves the existing game open. Examples are in `decks/White-Lifegain.txt` and `decks/White-Blue-Tempo.txt`; edit counts or Arena-export card lines for the eight supported names. Totals40..250, unrestricted copies, no sideboards. Unsupported cards fail before closing the running sandbox. Export printing labels are ignored in favor of verified native art. This is a launcher file picker, not Arena's original deck editor or home screen.
