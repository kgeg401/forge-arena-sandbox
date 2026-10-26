# Behavior and evidence ledger

Date: 2026-10-20 (local). Static analysis, headless execution and isolated native-client execution. Installed game files are unchanged; native tests use a separate copied lab and an AppContainer profile.

## Identity

Full fingerprints: `D:\GAMES\CodexAssets\ForgeArenaSandbox\research\build-identity.json`.

Installed version file reports `0.1.14517.1329972`; UnityPlayer reports `6000.3.14f1`. These are file observations, not proof of an active runtime.

Retained REA evidence:

- Core assembly metadata: `ev_a201d2ead9711360677e7e0a71c67cae30ec39fbfc977debd7cb38c1094a288b`.
- Core methods/CIL/call edges: `ev_fd732686631eac759694a169fab2118c06db295f06114b7e0ad28520e7b856d7`.
- SharedClientCore metadata: `ev_2cd25bdcdc1b6d79733ee908b935a2f64f6b38790ced73fdfab159c39ad6cdc4`.

Complete private REA bundle: `D:\GAMES\CodexAssets\ForgeArenaSandbox\research\arena-managed-evidence.json`. Large results were exported rather than repeated after a transport-size limit. Focused decompilations made with existing ILSpy 9.1.0.7988 are in the adjacent `decompiled` directory. These are recovered code, not original source, and must stay private.

## Verified boundaries

| Subsystem | Evidence | Implemented/tested | Remaining gap |
| --- | --- | --- | --- |
| Connection interface | Shipped `GreClient.Network.IGREConnection`; `MatchManager.Initialize` accepts it | Local implementation tested headlessly and bound in the isolated Unity client | Validate the rest of the native listener lifecycle and full matches |
| Incoming message path | Recovered `MatchManager.OnMessageReceived` tracks history and calls `GreInterface.OnMessageReceived` | Native MatchManager executed with full/diff messages through local transport | Wider message coverage and Forge translation |
| Parsing | Recovered `GreInterface` full/diff merge, message grouping and annotation parsing | Installed parser processes synthetic full + diff with a pending choice | Real card database and complete recorded sequences |
| Native presentation events | Recovered modified-life annotation parser and state-to-event pipeline | Native life event produced and displayed life changed 20 to 17 in Unity | Full event coverage, precise UI/audio timing |
| Player choice | Native `MulliganRequest.KeepHand` and request translator | Native response returned with state 2 / response ID 3 | Forge must validate/resolve it; two-seat routing design |
| Outgoing response routing | Recovered `MatchManager.Update` dequeues and calls connection send | Native response/concede command delivered to local callback | Request messages may omit `SystemSeatId`; route by associated local player, never assume it is populated |
| Scene startup | Recovered `MatchSceneManager.MatchStateChanged` queues DuelScene on GameInProgress; `OnSceneLoaded` calls `GameManager.Init` | Isolated native MatchScene/Battlefield_DAR/DuelScene loaded with real cached data | Cosmetics, additional battlefields and complete lifecycle |
| Native board updates | Recovered `GameManager.Update` retrieves updates and advances native presentation | Four cards and a subsequent life update visually verified in real renderer | Wider animations, audio and gameplay scenarios |
| Forge | Previously inspected engine/controller facilities | No backend adapter implemented | Stable local game host, card IDs, choices, priority, stack and event translation |

## Findings from failed attempts

1. `GreInterface` accepts a null database argument initially but later dereferences the original argument. Passing the shipped `NullCardDatabaseAdapter.Default` explicitly allows the headless parser to initialize. The earlier suspicion that the provider itself lacked a dependency was not the cause.
2. A plain 20-to-17 player-state diff changed parsed totals but produced no life-change presentation event in this test. Adding the schema-supported modified-life annotation produced the native event. A state-only Forge translation is insufficient for presentation parity.
3. The native keep-hand response contains no explicit system seat in this build. The initial test expectation of an explicit seat was wrong; state/request correlation does match. The connection must carry local-player routing separately when Forge is connected.

## Acceptance gates

- [x] Identify a build-bound connection entry and native message/presentation path.
- [x] Compile local adapter against shipped interface.
- [x] Execute installed parser and request translation headlessly on local messages.
- [x] Open a native Arena board driven by local data.
- [x] Verify basic real card rendering and native life-loss presentation (full animation/audio parity remains untested).
- [ ] Resolve local startup/session/content requirements; establish offline limitations.
- [x] Route a legal land action to Forge and show its result in Arena (Plains-only seeded scenario).
- [ ] Complete a rules-enforced 1v1 sandbox game.

Headless success does not establish a working Unity host, rendered board, animation parity, Forge integration or offline availability.

## Native Unity checkpoint, 2026-10-20 22:47 local

**Verified in the actual Arena renderer:**

- BepInEx 5.4.23.5 loaded `NativeHost.dll` inside the copied Arena Unity 6000.3.14f1 process.
- The launcher created the child suspended and checked `TokenIsAppContainer = 1` and zero token capabilities before resuming. The plugin independently checked the same conditions.
- The native persistent path is the isolated package path, not the normal LocalLow Arena profile. PlayerPrefs is redirected in memory to `native-lab\local-playerprefs.json`.
- Local preparation populated the native provisioner from 28,107 installed manifest entries, loaded the real localization and card databases, and initialized native card builders/match services. It never called the provisioner's download preparation method in this local preparation routine.
- `MatchManager.Initialize` now executed in Unity with the real database and `LocalGreConnection`. `MatchSceneManager.Load` loaded the native match scene. The native GameInProgress handling loaded `Battlefield_DAR` and `DuelScene`; the native pregame transition completed.
- A synthetic fixture rendered Plains and Hare Apparent: two cards in the local hand, Plains on the local battlefield, and Hare Apparent on the opponent battlefield. These use the installed database/renderer/assets, not recreated card visuals.
- A subsequent local diff and annotation changed native scene state 1 to 2 and the displayed local life total 20 to 17. The opponent stayed at 20. Native logs selected life-loss projectile/VFX/text assets. Before/after PNGs were opened and visually inspected.
- The native client emitted SetSettingsReq and UI messages to the local callback; none was sent to an official match service by this adapter.

The live test used a synthetic scene, not a valid game and not Forge rules. Avatars currently use default fallback visuals. The host's machine-readable phase deliberately remains `local-state-queued-native-render-unverified`; visual acceptance is recorded here and in `native-checkpoint.json`, not inferred from a queued state alone.

Evidence under `D:\GAMES\CodexAssets\ForgeArenaSandbox\research`:

- `native-checkpoint.json`: accepted visual/runtime checks and explicit gaps.
- `native-board-initial.png`: initial scene with cards and local life 20.
- `native-board-life17.png`: the changed scene with local life 17.
- `native-host-accepted-status.json` and `native-launch-accepted-receipt.json`: copied runtime state/launch evidence.
- `native-runtime-accepted.log`: copied Unity log.

### New native-test findings

1. The first container launch loaded the plugin but failed during PlayerPrefs writes because the ordinary registry location was unavailable. A lab-only preloader patch now redirects ten PlayerPrefs methods to a separate JSON store. The copied DLLs on disk are not rewritten.
2. A later launch crashed in native startup after integrations began initializing. The stack did not establish a definitive cause. The lab initialization config now leaves filesystem/prompt setup enabled but disables analytics, crash-upload, Steam-service and Unity-service initialization. The subsequent native startup succeeded. No authentication method or official account permission was patched.
3. Ordinary bootstrap still tries online startup/manifest requests, which fail inside the zero-capability container. The lab stops the bootstrap coroutine and initializes already installed assets explicitly. This is an experimental local bootstrap, not a claim that normal Arena is generally offline-capable.
4. An initial modified-life annotation used a player as affector. Headless parsing accepted it, but native presentation failed when the translator could not find a card and tried a null previous state. Repeating the native test with a present card instance as the affector passed. The future Forge translator must preserve valid event-source identities; parser acceptance alone is insufficient.
5. Native audio posting reports failures. Audio parity is not established. Normal priority/stack/rules processing and complete-game behavior are also unimplemented.

### Reproduction and footprint

- `Deploy-NativeLab.ps1` deploys/restarts only the prepared independent lab and archives the previous logs.
- `Open-NativeBoard.ps1 -Redeploy` checks installed/lab assembly identities, launches with zero network capabilities, prepares cached data, and opens the native board. Reaching its state condition still requires visual verification.
- `prepare_lab.py` created independent copies (no hard links) of runtime/assets, approximately 13.9 GiB on D:. Loader tools and evidence are also on D:. The only new profile location on C: is the dedicated AppContainer package.
- Remove the `native-lab` directory to remove the copied game and lab loader. The registered AppContainer profile is `Codex.ForgeArenaSandbox.LocalLab`; removal is a separate cleanup operation if requested. The retail game has no loader installed.

**Next gate:** replace the recording-only local command callback with a Forge-backed one-land-play sequence. Support native SetSettings responses, two-player routing, card/ability identities, request/state correlation and event-source annotations before calling the result playable.

## Forge land-play checkpoint, 2026-10-20 23:00 local

The native-board checkpoint's next gate above is now achieved for **one Plains land play**. This is not a full Forge/Arena match adapter.

### Engine and setup

- Compiled `ForgeLandEngine.java` against the installed `forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar`; exact installed and copied-runtime identity is in `research\forge-backend-identity.json`.
- Checked the installed binary APIs with `javap` before using the newer local Forge source as an explanation/reference.
- The separate Java process initializes a private Forge profile/cache and creates a two-player `Game`. The scenario setup uses Forge's developer setup API to seed first-main phase with local priority and two Plains in hand. This intentionally skips ordinary deck startup, shuffling and mulligans. **Normal action validation does not use ignore-timing, unlimited-land or developer overrides.**
- Legal offers come from `LandAbility.canPlay()`. Accepted actions call the installed engine's `LandAbility.resolve()`, which runs Forge's land move/count/event path. The bridge does not implement a one-land rule itself.
- Java strict headless mode failed because `GuiDesktop` statically queries screen scaling. The process runs with desktop-library access but creates no Forge window. This does not attach to or alter a user's running Forge JVM.

### Native round trip, verified

1. Forge reported hand IDs 1/2, both legal, landsPlayed 0 and an empty battlefield.
2. Arena displayed the corresponding native Plains cards with normal blue legal-action highlighting.
3. A card selection in the real Arena window generated `PerformActionResp` with native state 1, response ID 102 and Arena instance 1001.
4. The bridge mapped that instance to Forge card 1 and wrote a session-bound file request.
5. Forge accepted the action with `Forge resolved LandAbility`; its state became landsPlayed 1, hand count 1 and battlefield count 1, with no further legal lands.
6. The bridge sent native `ObjectIdChanged` and `ZoneTransfer`/`PlayLand` annotations plus updated zone lists and legal offers. Arena's scene reached state 2 and displayed the land on its battlefield, with the second Plains still in hand.
7. Native SetSettings requests receive local settings responses. UI hover messages remain local and do not become rules actions.

The native adapter supports only this land choice. Unsupported commands report a gap; raw fixture injection is rejected while Forge controls the board. Session/request/state correlation and one pending action are checked. Forge IDs and Arena zone-change instance IDs remain separately mapped.

### Negative/replay checks

- A direct second-land request to the same Forge process was rejected by `LandAbility.canPlay()`. Hand/battlefield counts and land counter stayed unchanged. Arena no longer advertised this land as playable. The negative backend request was deliberate test input, not a native UI-generated action.
- Replaying the exact first request ID/payload returned its cached result without applying another land play; the state stayed unchanged.
- The first desktop click used physical screenshot coordinates where the desktop tool expected logical/DPI-scaled coordinates and changed focus to the chat. It produced no Arena action. After re-observing/focusing Arena, the corrected native card selection produced the verified command. Never treat a sent click as action evidence.
- The launcher initially consumed a stale previous status snapshot and timed out. `Open-NativeBoard.ps1` now waits for a status timestamp newer than the current launch receipt. The subsequent existing-lab open completed normally.

### Evidence and remaining work

Under `D:\GAMES\CodexAssets\ForgeArenaSandbox\research`:

- `forge-land-checkpoint.json`: asserted positive, negative and replay outcomes.
- `forge-land-engine-journal.jsonl`: native-correlated request and Forge response.
- `forge-land-second-rejected.json`: rejected second land with unchanged authoritative state.
- `forge-land-native-status.json`, `forge-land-launch-receipt.json`, `forge-land-native-runtime.log`.
- `forge-land-before.png`, `forge-land-after.png`: native captures opened and visually inspected.

Remaining: general card/ability mapping, turns/priority advancement, mana abilities, casting, stack, targets, combat, opponent controls, normal game startup and complete games. Native audio remains incomplete. No broad rules or animation parity claim is made from this narrow success.


## 2026-10-20 30-minute development checkpoint

### Recovered protocol and installed APIs

Private `research/mana-protocol-sample.json` records captured native Plains unique ability 1001, Activate_Mana action, tapped annotation and mana pool shape. Savannah Lions identity is read from the installed read-only Raw_CardDatabase SQLite: GrpId 93859, TitleId 6953, white Cat, 2/1, no abilities. Forge installed APIs were checked with javap; newer local source explains `ComputerUtil.playNoStack`, `playStack`, and `PhaseHandler.mainLoopStep`.

### Implemented and observed

Mana activation checks the real Forge ability's canPlay and pays its costs via ComputerUtil.playNoStack. Snapshot mana records stable IDs and source cards. Native mana effects/tap and white count are visually verified. Native Pass goes through the installed phase loop with controllers that return pass; ordinary phase transitions do not use devModeSet. Developer setup still seeds the starting first main. Twenty Plains in each library avoid an immediate empty-library loss in this bounded scenario. Opponent cards/zones remain unrepresented; no full-board parity claim.

Savannah Lions is the single mapped spell. Forge determines cast legality and cost payment, owns its stack, and resolves it after local/passive-opponent priority. Native CastSpell and Resolve zone annotations retain separate engine and native object IDs. The native stack card, Resolve button, final 2/1, and mana spent were visually checked. Combat with creatures is explicitly blocked at COMBAT_BEGIN and exposed in native-host-status, preventing AI-controlled attack choices. Further targeting/trigger/combat/terminal-state handling remains unsupported.

Evidence: `mana-check-20261020-231909/checks.json` (10 checks), `spell-check-20261020-232405/checks.json` (8 checks, including combat rejection), `final-native-status.json`, `final-native-journal.jsonl`, `forge-spell-on-stack.png`, `forge-spell-resolved.png`, plus original recordings in devlogs/2026-10-20-mana. Native audio events fail initialization; recorded process audio is retained but no audible sound claim.

`Start-Sandbox.ps1` provides a repeatable fresh launch, verifies private backend PID identity, preserves old IPC folders and refuses a running retail Arena process. New tests compile without warnings. Preview delivery must be verified independently; a local video is not an Atlas receipt.

Final native follow-up: casting Savannah Lions with one untapped Plains and no floating mana also succeeds through Forge automatic cost payment. The Plains taps, mana remains zero after payment, and Lions appears on the native stack. Evidence: research/forge-automatic-cast-payment-journal.jsonl. The final preview uses the earlier explicit-tap sequence; it does not show this extra test.

## 2026-10-21 combat checkpoint

Recovered from installed request classes and captured native messages: attacker/blocker selection and submit are separate commands. Declared/Attacking/Blocking states, damage and SBA_Damage zone-transfer annotations drive the original presentation. Installed Forge controller callbacks run synchronously inside its phase loop; a correlated file decision pump pauses on that same thread until the human submits. No native intermediate state is fed back as rules.

Implemented: offered legal attacker/blocker choices from CombatUtil, staged selection/cancellation, submit-time Forge validation, stale-token/card/recipient rejection, real damage events, both owners' public zones and native object retirement on zone changes. Polling runs every Unity frame. Failed actions reissue the current native prompt.

Observed in actual Unity: choose a Lion, confirm one attacker, native arrow/tap/hit, opponent life 20 to 18. In the defender scenario choose local Lion then attacking Lion, confirm one blocker; native pairing line, hit/death effects and both graveyards; life stays 20/20. Research evidence is under combat-protocol. Engine scenarios passed 10/6/6 checks; see MODLOG for directories. Tests cover one vanilla attacker/blocker, not general combat ordering or card abilities.

Audio startup now follows the installed Bootstrap sequence using cached packages. Native initialized=true, loadError=false and 179 available packages; process recording has nonzero audio (peak 0.3404, RMS 0.02469). This establishes recorded output, not complete sound parity. Devlog 02 preserves the earlier combat footage's original audio; those takes preceded this audio fix.

Remaining at this checkpoint: normal match startup, hidden zones/library counts, useful AI, whole-game outcomes, arbitrary cards/targets/triggers, multi-block damage ordering and broader visual/audio comparisons. No full sandbox or parity claim.

## 2026-10-21 opponent, outcomes and cleanup

Implemented and observed after the preceding checkpoint: hidden library/hand counts with unknown identities omitted, public opponent cards/casts, Forge's built-in opponent AI in the seeded duel, native attack eligibility across turns, and player-controlled cleanup discards. The duel starts with fixed six-card hands and 24-card libraries; there is no mulligan or ordinary deck startup yet. The 50-turn engine test ended through Forge's Milled loss. Separate lethal scenarios verify both winners. Normal 20-life duel play was manually checked through the first AI block and graveyards, not visually played to completion.

Source-specific ModifiedLife annotations are required for nonzero native combat damage events. Corrected this after installed GreInterface inspection; previous life counters were correct but its combat event could be reduced to zero. Wire replay now measures two damage, one native GameEndEvent and the expected winner. MatchComplete results, LossOfGame annotation and IntermissionReq now produce the real avatar death and VICTORY scene. The earlier failed terminal attempts are retained separately. Defeat presentation still needs visual verification.

Forge's installed private pre-priority SBA/trigger routine is invoked before returning choices, following its verified bytecode. This prevents exposing a fake extra priority pass after lethal damage; all state changes stay in Forge. No snapshot query mutates gameplay. The original routine's identity is protected by the pinned installed jar hash.

Cleanup uses the real human controller callback and returns selected cards to Forge; the bridge does not move them itself. SelectNResp IDs must match offered cards, count and session/token. Five engine checks reject too few, duplicate and foreign choices. Native prompt 14 displays Discard 2 cards; Submit 1 is disabled, Submit 2 works, exact cards enter graveyard and seven remain. Evidence paths are listed in MODLOG.

Remaining: general card/deck mapping, normal match startup/mulligans, target/trigger choices, manual multi-block damage ordering, concede/restart flow, full native match replay and broad parity. Current fixtures contain Plains and Savannah Lions only. Earlier notes retain their original scope.

## 2026-10-21 completed native sequence and input lifecycle

A corrected complete duel was observed to native DEFEAT at turn 10 (human deliberately passes, opponent AI plays and attacks). Installed-parser replay: 131 states, 26 damage, one match result. The independent evidence audit passes 12 checks: every life change, each player hit, terminal winner/stage, no reported gap and no hidden names. Evidence prefix: research/combat-protocol/complete-fixed-*; original recording native-duel-workflow-fixed-04. This verifies the seeded loss path; native victory remains the separate two-life lethal fixture. It does not establish normal startup or arbitrary-card completeness.

Corrected multi-attacker annotations: all DamageDealt annotations precede one aggregate ModifiedLife per player per state, with an actual source. Separate source-specific life events incorrectly caused the installed parser to cap later hits at zero. The earlier full-duel run had correct life counters but only eight parsed damage out of 26; retained as failed evidence. Corrected three-attacker fixture yields six damage, and the full run yields all 26. No broad animation-parity claim follows from parser checks.

Automatic passing now submits the currently applied native ActionsAvailableWorkflow via OnAutoYieldEnabled. Directly advancing Forge bypassed native request completion and stranded the next opposing spell behind a disabled button; failed takes and journals are retained. The corrected native workflow was observed through repeated opponent spells, cleanup choices and terminal combat. It waits for the displayed state and UX queue, respects full-control/stops, never auto-selects human attackers/blockers/discards, and pauses opposing stack spells. This policy is limited to the admitted Plains/Lions actions.

Concession uses Forge's own concede and pre-priority checks, including the paused human decision pump. Seventeen engine checks cover normal play, attack selection and discard selection, wrong-seat rejection and repeated concession rejection. The native Options Concede command has no normal response/state correlation IDs, so it is explicitly treated as a global command; ordinary actions retain strict current-request checks. A backend timeout now stops once with an explicit restart gap instead of repeatedly throwing.

### Additional native creature and mixed-duel checkpoint

`Open-Playable.ps1 -Scenario mixed-duel` starts the optional four-card scenario: Plains, Savannah Lions, Yoked Ox and Oreskos Swiftclaw. Both fixed hands contain three Plains plus one of each creature. Libraries repeat a fixed 24-card sequence. The normal desktop shortcut retains the simpler two-card duel.

The additional identities, costs and subtypes were checked against the installed read-only Arena database and stored with its hash in private `research/vanilla-card-identities.json`. The adapter supplies identity/cost presentation; Forge supplies actual legality, payment, power, toughness, sickness and damage. Native Swiftclaw casting tapped two Plains and resolved a 3/1; Ox casting resolved a 0/4. Native Ox blocked a Lion, displayed damage and survived with player life unchanged. Swiftclaw dealt three and native life became 17; installed-parser replay also reports three. Eighteen engine checks cover these cost/stat/combat cases, plus eight prior Lions spell checks still pass.

Mixed-duel engine testing played all four admitted identities and completed at turn 18, winner 2, life 0/9. Native mixed play was checked through turn 5: player land/casts, opposing casts, summoning-sick attacker exclusion and all three creature presentations. This is not a whole mixed-duel rendered outcome test. Recordings and parser evidence have `vanilla-*`, `ox-block-*`, `swift-attack-*` and `mixed-duel-*` names under private combat-protocol/devlogs.

Human multi-block damage-order prompts remain untranslated. Those internal ordering/damage-assignment decisions currently inherit Forge AI policy; this is a known control limitation, not a claimed Arena-equivalent human choice. No custom deck, keyword, target or triggered-ability support is implied by these vanilla cards. Use one blocker per attacker when assessing the verified human combat controls.

## Final terminal-state boundary

A fresh conceded first-main session still exposed stale legalMana/legalCasts in the raw Forge snapshot, although the native adapter hid them and the tested cast failed to pay. The backend now clears every legal-action list once terminal and rejects every new gameplay operation before calling an ability. Snapshot reads remain permitted; cached exact-replay behavior remains unchanged. Eight engine checks verify concession, no offers, rejected land/mana/cast/pass/concede with byte-equivalent state, and readable snapshots. Evidence: combat-check-20261021-065424-ddf2d3. Fresh native main-phase concession still showed defeat with 20/20 life and empty terminal offers (terminal-final-native-*).

## Real-startup and London checkpoint

Recovered installed `Match.startGame`, `GameAction.startGame`, `PhaseHandler.mainLoopStep` and `LondonMulligan` bytecode defines the startup/ability sequence; private evidence is in `research/startup-protocol`. The `opening-duel` controller waits on the same Forge owner thread, returns actual selected abilities to the normal loop and acknowledges requests at its next stable boundary. It never aborts `startGame` to seed a turn or mutates rules on another thread. Match prepares/shuffles the practice decks and draws the hands. Optional test-only `randomSeed` is recorded in snapshots.

This Forge version tucks immediately after redraw, before asking whether to keep. The adapter asks Arena's Keep question while seven cards are visible and buffers its answer for Forge's following callback. A kept hand uses the real native London browser and human bottom-card selection. A rejected hand returns the first offered N only because Forge immediately reshuffles that obsolete hand; this explicit controller policy is not a claim about Arena server internals. Native GroupResp must partition the offered hand; Forge-side selection rejects duplicates, unoffered IDs, wrong counts and stale tokens. Local-first remains an explicit practice policy at this checkpoint.

Forty headless assertions cover initial keep, double mulligan/keep five, first-player draw skip, normal land play, hidden names, invalid bottom choices and concession during setup. Complete normal game seed7274 reaches turn20, LifeReachedZero, winner2, life -1/4 with six checks (`combat-check-20261021-073542-53d0b3`). Prior spell/concession regression checks pass. Native session ecc2474d-c641-43df-b342-2726761c34be visually renders original Keep7/Keep6/Return1, accepts native GroupResp, then renders six-card first main, land, creature cast and AI play. Installed-parser replay sees MulliganRequest -> GroupRequest -> ActionsAvailableRequest and Start -> Play. This is not arbitrary-card or whole-animation parity evidence.

### Starting-player and handoff hardening

Default opening-duel now honors Forge's coin winner. A local winner pauses in the actual chooseStartingPlayer callback and uses native ChooseStartingPlayerWorkflow; AI winners use their installed controller. The old local-first behavior remains an explicit test policy. Local single-game metadata has MatchWinCondition_None because the shipped SingleElimination workflow silently auto-selects Play. No multi-game series scoring is claimed. Native Draw First -> Opponent Goes First -> Keep7 -> opponent land/cast -> turn2/local8-card hand -> Options/Concede -> DEFEAT was observed in session 722b9ced-6f4b-4fff-b541-872b22fee43e. Its recorded wire produces 14 installed-parser states and one terminal event.

Twenty engine assertions check both starting seats, first draw rules, unoffered seats/wrong player/stale tokens, and concession before hands are drawn. Evidence: combat-check-20261021-074440-2b4798, -074452-bfbac3, -074504-d2b154. Normal-game seed7274 now follows the actual opponent coin win and reaches turn35 LifeReachedZero, winner2, life0/5; seven checks include preserving the entire startup/gameplay journal (-074918-b9e10a).

The first live draw-first take failed because Windows denied deletion of decision.json while the Unity reader held it. The native reader now permits FileShare.Delete; Java file retirement/replacement retries bounded transient file-system failures. Four engine assertions deliberately hold conflicting non-delete-sharing Windows read handles and then complete normal setup/concession (-074729-1f2741). The failed take and exception remain preserved. AWT helpers had kept the crashed backend PID alive, so uncaught failures now terminate the dedicated helper process with an error. Normal end-of-game service appends to its journal rather than truncating the completed evidence.

## Targeted instant checkpoint

Divine Arrow is admitted using the installed Forge definition (1W, four damage to an attacking or blocking creature) and read-only Arena WAR identity grp69461/title336205/ability100370. Other printings and identity evidence are in private research/targeted-spell-protocol/card-identity.json. The human controller enumerates Forge TargetRestrictions candidates, stages selection/unselection, revalidates canTarget/count, then executes ComputerUtil.playStack and real resolution. The native client uses original SelectTargetsRequest/Workflow, matching target indices/ability/source IDs and native Cancel/Submit. CancelActionReq uses current state with response ID0 in this installed client; that exception is admitted only while the current target choice is pending.

Twenty-five engine checks cover unavailable timing/no combat target, idle-creature rejection, empty submit, unselect, target assignment, two-Plains payment, real stack, four damage/death, cancel and concession. The optional spell-duel has real startup, nine copies each of three vanilla creatures/Arrow plus24Plains; seed7274 reaches turn45 LifeReachedZero, winner2, life-3/20 with seven checks (-081001-0da0eb). Six human target callbacks and AI responses were exercised. The test controller sometimes targets its own attacker; the opponent's Arrow can remove that target first, so those local spells fail to resolve. This is response/fizzle coverage, not a strategy assessment.

Native sessions 0e1e85e3-2b3e-4f0c-b7ab-d8da09babdbe, 6f11b1a3-4010-4b23-8769-6fd9ff0f7a92 and cbeec84e-82ae-459f-96b9-69dcb4e0f187 verify prepared target/cancel/stack/death/continued-turn scenes. Final parser replay reports exactly four DamageType.Direct from grp69461. The first two takes used unspecified native damage type; the final mapping uses the installed enum Direct2 rather than None0. Actual Forge card-damage events omit a combat flag, so this narrow slice classifies Arrow as noncombat and vanilla creatures as combat; general source classification remains a gap. Persistent TargetSpec comes from actual cast StackItemView targets and is explicitly deleted when the spell leaves the stack (observed removal900046). No arbitrary-target, multiplayer, triggered-ability or broad animation parity is implied.


## 2026-10-21 triggered-ability slice

Installed Forge Orator definition and MagicStack/SpellAbilityStackInstance APIs were checked. Nonspell objects have independent adapter keys (-1-stackInstanceId), source-card identities and top-first order from the real Forge stack. Positive life events name the actual resolving stack object. These are namespace translations, never engine card IDs. Unknown ability sources suspend gameplay with an explicit fidelity gap.

Impassioned Orator is mapped to installed Arena grp75451/title279479/ability122104. Native AbilityInstanceCreated, original ability panel, ResolutionStart/Complete, ModifiedLife with actual ability affector, and deleted instance IDs are implemented. Headless one/two-Orator scenarios pass 20 assertions: no self trigger, exact sources/order, separate resolutions and life20->21->23. Native session2b1d5607-8c18-4593-9723-13f0907965d2 reproduces this manually through original UI; installed parser sees 10 states and three +1 events sourced by distinct native ability objects. Captured game audio and effects retained.

The bridge exposes abilities directly in the stack snapshot; original pending-trigger-zone timing is not reconstructed. Forge's AI controller orders simultaneous identical life-gain triggers; there is no human trigger-order UI. General abilities, arbitrary cards and complete presentation parity are not claimed.

Optional trigger-duel is a genuine shuffled 60-card practice deck (24 Plains, eight each Lions/Swiftclaw/Orator, six each Ox/Arrow), not constructed-legal. Full seed7274 engine game reaches turn15 LifeReachedZero, winner2, life-3/21, seven checks. Native full trigger-duel playthrough remains pending; the native proof is the bounded seeded double-trigger sequence. Evidence: private research/trigger-protocol and combat-check-20261021-084025-9936f9.


## 2026-10-21 blue mana and return-to-hand slice

Installed Forge Island/Unsummon definitions, installed Arena SQLite identities and an earlier native Island record establish blue mana ability1002, Unsummon grp75477/title398/ability22505 and original target prompt1010. Native mana production/payment now carries actual white/blue color; costs and candidate legality stay in Forge. Return zone category is source-observed. Floating mana paid after SubmitTargets now derives the actual newly stacked spell, rather than a reset pending-action ID.

Headless checks13 cover rejecting white-only payment and land targets, actual blue pool/spending, opponent hidden return, local visible return, no damage/death, graveyard resolution and a recast Lion with sickness/zero damage. Evidence combat-check-20261021-084946-ac8fb9 and -084957-abe800. Full blue-duel seed7274 ends turn17 LifeReachedZero, winner2, life0/20, seven checks; combat-check-20261021-084724-509166.

Native session0aff7726-e9db-4403-9a1f-4fabd3b1e9f8 manually verifies Island blue pool, original Unsummon card, correct Target a creature prompt, native return effect, opposing card back, local visible returned Lion and recast/resolution. Parser12states, zero damage, gap null. First take had the old Arrow-specific target prompt; retained as failed presentation evidence, corrected take02 and final result03 are used in chapter17. Private research/blue-protocol and devlogs/2026-10-21-blue. Eight mapped cards only; arbitrary cards/decks and general targeting remain unsupported.


## 2026-10-21 imported practice decks

Added bounded Arena-text import for the eight admitted names. Counts merge case-insensitively; exported set/collector labels are accepted but the bridge intentionally uses its pinned verified printing. Unknown cards, malformed/zero/fractional/negative counts, sideboards and totals outside40..250 are rejected without dropping lines. Copy counts remain unrestricted sandbox policy; no sanctioned-format legality claim. Forge independently validates incoming JSON card names/counts/duplicates/totals before initialization, then Match.startGame shuffles the supplied lists and draws real hands. Source path/hash and exact lists remain in the session evidence.

Twenty import/startup checks pass: research/deck-import-check-20261021-085813.json, engine combat-check-20261021-085802-6e4b21. Separate full imported white versus white/blue game seed7274 reaches turn27 LifeReachedZero, winner2, life0/19, seven checks (combat-check-20261021-085811-7d03df). Launcher invalid-card and picker-cancel tests preserve live native PID41848/session0aff7726-e9db-4403-9a1f-4fabd3b1e9f8.

Native picker selections launch session6ee56a5b-6801-4997-aa85-b3160baaf923 with exact White-Lifegain and White-Blue-Tempo files, original Keep7 screen, normal play/draw, land and creature casts, actual AI Swiftclaw/Unsummon/Ox actions, public-to-local-hand return and native DEFEAT after concession on turn5. Installed parser49states, one result; recorded-match audit12checks passes. No natural whole rendered match claim for this import take. Evidence research/custom-deck-protocol and custom-deck-native-parser/audit.json. Original Arena deck editor/home screen are not implemented; deck choice uses the Windows file picker before launching the native match.


## 2026-10-21 original avatar presentation

Installed MatchManager.PlayerInfo.AvatarSelection is consumed by original PlayerCreatedMediator, which calls AvatarView.Init and ProfileUtilities native asset-tree portrait resolution. Installed ProfileUtilities names Avatar_Basic_AjaniGoldmane as its default-login fallback; installed AvatarIdConstants supplies Sparky. The lab sets these two match-local choices before loading the scene; original native code resolves both portrait paths. No account profile is read or changed.

Native session0479a2a6-2e9b-4e65-a4a2-c920286a0714 shows original Ajani portrait, separate life gains to23 and original avatar/concession/DEFEAT effects. Source and evidence under research/cosmetics-protocol, full game-window/audio take in devlogs/2026-10-21-avatars. Fixed defaults only; profile/avatar selection UI is not implemented. This changes presentation, not Forge rules.


## 2026-10-21 actual spell targets and counters

Installed TargetRestrictions.hasCandidates returns true for Stack zones without requiring a candidate. Replaced admitted-spell eligibility with installed getNumCandidates>0. Essence Scatter uses actual SpellAbilityStackInstance candidates/canTargetSpellAbility and submits a SpellAbility target, not a battlefield Card. Current snapshots read target cards/spells directly from the actual stack entry. Independent source/card/stack namespaces remain explicit; copied spells and arbitrary ability targets are outside scope.

Counter evidence comes from actual GameEventCardChangeZone while the resolving Essence Scatter targets that spell. Native Countered zone-transfer reason and source are observed in the earlier Arena recording; original installed ZoneChangeEvent parser confirms this exact reason. No counter result is manufactured from final graveyard state.

23 headless assertions pass across no target, wrong mana, actual counter, invalid permanent, empty submit, cancel and concede. Private counter-protocol evidence and combat-check-20261021-092704-b37ef2 through -092746-3f424e. Full custom counter-deck seed7274 reaches turn13 LifeReachedZero, life0/21, seven checks, with one actual counter effect; combat-check-20261021-092756-98768c. Test-controller choices are legal but not a strategy evaluation.

Native sessione302b9e8-b9ca-4159-9ae4-87edce72c706: original Essence Scatter card and Target a creature spell prompt1077; only the Lion on stack highlighted, not idle Ox. Cancel preserves resources, recast/select/Submit1 puts counter above target, actual cost taps both lands, counter removes Lion before battlefield entry; both graveyards, life20/20, gapnull. Installed parser7states reports Stack->Graveyard reasonCountered, source10000, affected10002 and empty final stack. This is a prepared fixture whose creature was cast/payed by actual Forge during setup; the attempt to have the seeded opponent independently cast it did not do so and is retained separately (-092258-ea7c57). Normal full-match AI uses the genuine game loop, not this fixture.

Essence Scatter brings the allowlist to nine names. White-Blue-Counters.txt is a supported60-card practice sample. Original target/counter presentation is observed for this slice, not general counterspell/animation parity.


## 2026-10-21 human combat damage allocation

Installed GameRules defaults to unordered combat damage. Recovered original AssignDamageWorkflow/Translation, DamageAssigner and MtgDamageAssignmentExtensions plus observed native AssignDamageReq. The local Forge controller now pauses its real assignCombatDamage callback for multiple recipients, publishes legal recipient identities/total/suggested split, then returns the submitted map to Forge. Its AI suggestion is only an initial value. Exact recipient/count/integer/nonnegative/total/token checks guard the boundary; installed Forge trusts this controller return rather than providing a second general validation API. Only admitted vanilla creatures and unordered combat are implemented; no trample, deathtouch, replacements or legacy ordering parity.

25 headless assertions cover alternate allocations, missing/duplicate/foreign recipients, negative/fractional/overflow/under/over totals, stale token and concession. Evidence combat-check-20261021-094248-5f8355, -094259-507635, -094309-2a58cc. A complete new shuffled counter/tempo game seed9137 reaches turn23 LifeReachedZero, life-5/10, seven assertions (combat-check-20261021-095101-efe2de).

Native sessionc9f897c5-4688-49dc-b32d-d668047cb6d8: real original browser, Auto Allocate disabled, manually changed suggestion Lion1/Ox2 to Lion0/Ox3, Done submitted actual AssignDamageResp. Forge killed Swiftclaw from Lion2, preserved Lion undamaged and Ox with3 marked damage; players20/20. Installed parser9states reports AssignDamageRequest and actual Combat hits2/3. Seven native evidence checks pass, research/combat-protocol/native-manual-damage-audit.json. Original take332seconds retained; chapter21 edits the actual interaction without long inspection pauses.


## 2026-10-21 complete rendered normal match

Actual installed Forge Arena Practice desktop shortcut now starts normal imported white/blue decks, without file selection. Reusable .NET SHA256 identity validation avoids an observed hidden Windows PowerShell helper auto-load failure; full source/lab identity verification is preserved and runs before stopping a current match. Optional builds also precede closure.

Native session9a4552aa-7f45-45bc-803d-20efb5490019 started through real Match.startGame, original Play First/Keep7 and manual card controls, reached turn14 natural LifeReachedZero (-4/13), then original DEFEAT. Initial local play cast Lion and two Orators, gaining to23; opponent cast creatures/Unsummon and gained life. Later testing deliberately passed casts and attacked. No concession or fabricated outcome. Installed parser170states,49damage,one result; recorded audit12checks matches all20life states, all hits/total, winner and hidden identities. Original recording includes research pauses.

Source-link visual placement during opposing Orator triggers remains suspect despite correct sourceForgeId/parentId; pending-trigger/presentation parity remains unclaimed. The native yield toggle currently performs its initial pass but does not advance every later priority window. Manual Pass works. These are documented presentation/usability gaps, separate from matching rules results.


## 2026-10-21 spell draws, cleanup and library exhaustion

Quick Study is admitted from installed Forge definition (2U instant, draw2) and pinned read-only Arena DB: WOEgrp86756/title731368/ability23607, card/source hash saved under research/draw-protocol. Uses actual ComputerUtil payment, real stack resolution and Forge draw actions; adapter supplies original card identity/color/cost. No synthetic drawn cards or intermediate hand feed. New White-Blue-Study.txt sample is60cards with unrestricted practice copies. Allowlist now10names.

15 headless checks pass (combat-check-20261021-102202-e4bc93, -102213-345657): wrong color, actual payment, both original hidden library IDs enter hand only upon resolution, six->eight cards, original discard callback, chosen drawn card reaches graveyard, next draw causes actual Milled loss at20/20, terminal offers cleared. A complete normally started Study-vs-Tempo engine game seed7274 reaches turn11 LifeReachedZero (-6/23), seven checks (-102833-995317). Quick Study actually resolved on turn6 from hand6 to hand8, then graveyard; final game cleanup later removes that graveyard snapshot.

Native prepared session0751dfbb-1075-41f4-8799-6fb46012106a renders original Quick Study art/2U, actual three tapped sources, Resolve, two drawn original cards and native hand-size warning. Original cleanup SelectNReq chooses drawn Lion, Submit1, actual graveyard; next required draw on turn3 produces original DEFEAT at20/20. Installed parser29states, zero damage, one result; recorded audit12checks passes. Full412.666second source retained; chapter23 edits actual actions. This is a prepared two-card-library exhaustion fixture, not a whole normal rendered Study deck game.


## 2026-10-21 complete source-mapping audit

Added independent read-only comparison of importer names, Java admission and native mappings against pinned Arena SQLite and installed Forge card definitions. Validates source DB hash, identity/title/ability IDs, generic/colored costs, presentation card type and exact subtypes. Installed Enums/SubType joins Localizations_enUS Formatted1; no numeric-enum-name guessing. Initial harness errors (regex Match slicing, Forge basic ManaCost:no cost) were corrected before evaluating mappings.

Audit then caught a real earlier adapter error: Swiftclaw had Cat/Soldier. Both Forge Types:Creature Cat Warrior and Arena subtype77=Warrior agree. Corrected native tuple. All10mappings pass and the audit now runs before compilation. Native session65291da4-d1a4-4919-ab8c-4868e240475d original inspect visibly shows Creature - Cat Warrior,3/1. Private research/subtype-correction-native.json retains wire and source enums. Chapter24 records this correction; earlier videos retain the historical bug.


## 2026-10-21 local pack opening

Recovered code: BoosterChamberController inventory request boundary and VisuallyOpenBooster, native card sorting/reveal status/tagging, BoosterCardSpawner/Holder, original pool warm-up, original MainNavigation camera/canvas/lights and hover UI. Implemented: custom local pack generator, atomic per-opening rewards/debit/receipt, local inventory projection and original native chamber. Observed: WOE and M20 openings, real rare mouse click, native Continue, original hover preview; persisted collection survives restarts. Source-derived catalog and 51 loaded carousel views do not prove every pack/card's rendering. Custom collation is not retail odds. Gameplay allowlist remains ten cards. Bulk and final preview evidence pending final hour checkpoint.

Pack checkpoint verification: 19 actual persistence tests pass. Rendered native test opened14packs across5transactions and kept112copies through restart. Native bulk audit50checks, all80mapped identities and final positions match the receipt; final retained state marks all80revealed. Native rare clicks, hover and Continue work. Pool pose correction restores the owned prefab pose, not a replacement animation. Manual bulk dragging under automation remains unresolved despite native drag-enabled state and expected raycast targets; human browsing is not claimed verified. Custom distribution, local set metadata and ten-card match admission remain explicit boundaries.
# 2026-10-21 Arena-only coverage and Hare Apparent

Recovered: installed Hare script, Arena card93728/title823196/ETB175767, linked
Rabbit94160, original token-created/deleted annotation parsers. Implemented:
Arena/Forge catalogue join, generated native metadata, explicit admission policy,
Hare casting/ETB and real token object lifecycle. Observed: native three-Hare /
three-Rabbit board, Unsummon token removal with two survivors, source/parser
comparisons; headless normal Hare game reaches actual turn14 win. Name coverage
15,814/16,140 does not establish gameplay support. Runtime set remains11 names
plus the token. Full rendered normal Hare game and human manual input remain gaps.

## 2026-10-21 catalogue blockers and independent tester installation

Recovered/checked: owned database identity and 20,159 primary non-token printings,
16,140 normalized English names; 15,840 unique installed Forge script candidates
and 300 unmatched names after split-title notation normalization. A bounded
constructor/trait probe checks all matched names and exposed faces without
starting a match or resolving effects. Results: 15,837 without diagnostics, two
with diagnostics, one failed. Construction does not prove correct rules or play.
Installed controller reflection exposes 102 relevant signatures, 89 inherited
from AI. Installed legend-rule bytecode confirms an inherited human-choice path.

Implemented: per-name conservative capability blockers and source anchors/hashes,
CSV/JSON and searchable HTML report, reproducible receipts and 58 report checks.
Six names have no detected static blocker but remain unverified/unadmitted.
Human combat's name gate, legend choice, additional costs, restricted mana,
library/hand choices and digital/face behavior are explicitly represented.
Java admission now requires an explicit boolean and atomically replaces its
allowlist only after complete validation. Mapping/token/candidate entries alone
cannot enter admission. Four malformed-policy cases preserve the old allowlist.
Runtime remains eleven names plus separately mapped Rabbit tokens.

Implemented for sharing: own-file-only package, exact local prerequisites,
independent asset/resource copies, configurable runtime roots, versioned program
folders, separate profile, backup/stage/checksum/compatibility update and rollback.
Six normal-use Windows shortcuts use local Python without changing execution
policy. Generated indexes refresh after generator or policy changes. No retail
files, game assemblies, private profile or decompiled source are distributed.
Unmodified Gson 2.13.2 is included with its license/source. The original native
client retains a zero-capability AppContainer; the early preference preloader
exits an ordinary token before game assemblies load. No isolation ACL was widened
to let the restricted child inspect parent directories.

Observed: a full fresh local copy reached original Play/Draw, mulligan and deck
browser, initialized 179 native audio packages and retained five native-created
sample decks. Actual update/rollback/update preserved saved deck/backup bytes.
The newest generator-refresh candidate also reached the original deck browser.
This is the same PC, not a recipient-PC installation. Automated Play First/Keep
worked, but hand-card input remained unreliable. Optional input diagnostics only
observe original handlers; a complete manual game on the new install is not
verified. Previous developer-lab rendered evidence remains a separate claim.

Checks/evidence: 58 report boundaries; eleven pinned card mappings; 44 authored
update checks; five negative installation checks; six own-code isolation/root
checks; repeated Hare22 and normally started Hare game7 (turn14 win,16/-6).
Private roots: research/card-coverage and research/packaging on D:. Actual profile
preservation receipt: real-profile-update-rollback.json. Fresh install failures
(missing Gson, early ancestor access, generated test bytecode) are retained with
their fixes; immutable folders still reject unexpected code. Publication lint
passes with zero failures/warnings. The HTML report's browser visual interaction
is unverified because local-file navigation was denied; no alternate route was
used. Nothing was published, uploaded to GitHub or delivered to another person.
No dev log was made, per the user's instruction.

## 2026-10-21 saved Emry Brawl compatibility test

Saved Emry Arena export SHA83001f46d8e4a32da63252258eb99d3b56b808f352b43a77bc2a2579c6fd743a
matches the ranked export and installed Forge Commander list: 100 copies,
75 names, Emry plus99main. Only Island26 is bridge-admitted. Actual production
importer rejects Commander and then Ornithopter when testing main-only; actual
Java admission rejects Emry. No production admission was changed or bypassed
for gameplay. The current account deck was not freshly exported.

Read-only installed Forge probe resolves75exactnames and constructs75without
diagnostics. Brawl registration has Emry and25startinglife; ordinary current
registration defaults20. Installed Brawl format expects59main and rejects this
99main deck, so it cannot be treated as Arena100cardBrawl without adapting format
setup. This is constructor/registration evidence only: no match start, casts,
resolutions, commander-tax loop, deck combos or full native test.

Found primary-catalogue omission: A-The One Ring is a nonprimary rebalanced
Arena entry; its exact Forge rebalanced script exists and constructs. Original
Ring was not substituted (the two scripts have different activation costs).
Evidence/private per-card checklist: research/emry-brawl-check on D:.
Details and next acceptance gates are in docs/card-support-audit.md. No retail
queue, account edits, deck changes or new dev log were made.

## 2026-10-21 Brawl rules and native workflow checkpoint

Recovered: installed Forge Brawl registration, free London mulligan, commander
may-play alternative, commander cast history/tax and post-death confirmation;
installed Arena designation parser, versus-screen commander metadata and original
zone-transfer OptionalAction prompt parameters/localized prompts133..136.

Implemented: narrow100card mode, source-checked Isamaru commander-only admission,
mono-white99main policy,25life, free first mulligan, actual Forge command casting
and explicit human graveyard return/decline. Unsupported human commander
hand/library replacement stops instead of taking the inherited AI answer.

Observed: three completed normally started headless Brawl games; real command
payments1/3 and repeated1..93, graveyard decline, London bottoming tozero,
and both players surviving more than21commander combat damage before decking.
Native callbacks exercised Keep, land, commander cast, combat, original
Command/Graveyard choice and taxed recast (offer2W, three Plains actually tapped,
commander resolved with cast count2). Native parser194states retained one
commander identity per seat through object changes. Desktop shortcut opened a
fresh isolated Brawl match and its native free-mulligan button kept seven after
redraw with no bottoming. Retained failures: initial null versus-screen commander
metadata; base cast ability lacking command may-play; unreliable OS mouse input;
early screenshot before choice animation settled. Fixes and limitations remain
separate from complete rendered/manual play claims.

Gaps: Emry/artifacts, advanced replacement and exile paths, other commander
identities/types, format banlist, full native match/presentation parity and
physical mouse reliability. Source-supported Put replaces the old command-return
PlayLand fallback; fresh rendering evidence is tracked in the private checkpoint.
No dev log, tester package update, external upload or account change.

Final recheck: fourth full engine game153checks, turn186, repeated tax1..93 and
explicit no21commander-damage loss. Source-supported Put passes a modified
recorded-sequence parser replay194states; not a live rendering claim. Native
free redraw keeps seven with zero bottoming but Keep after redraw emitted no
outgoing response. Preserve as an unresolved native workflow gap; do not equate
the headless London pass with complete native mulligan playability.

Read-only native redraw diagnostics: Keep/Mulligan each have one subscriber both
before/after; Keep's subscriber targets the current workflow. The missing-output
cause is not established. Final clean shortcut launch accepted original Play
and initial Keep callbacks, entered real turn1 at25/25, with no host gap.

## 2026-10-21 Emry continuation: current bounded support

Recovered source: Emry70190 static affinity177, entry mill86971 and graveyard
permission136098; Spellbomb72518 bounce86974/draw4921; Ornithopter75832 Flying8;
Seat93331 blue mana1002; Crypt72023 player target/exile12870. Source manifest
checks seventeen unique identities. Forge source color identities are checked
again at engine startup. Source enums/prompts distinguish Mill, Sacrifice,
SBA_Legend, Exile, command Put and actual card/player target requests.

Implemented: actual adjusted Forge costs, graveyard alternative-cast options,
explicit activated-ability source bindings, player targets with collision-free
internal references, source-correct stack identities, native graveyard casts,
human legend selection, commander hand replacement and exile return choices.
The independent rules engine, not the UI, decides legality, payments, permissions,
timing, targeting, zone-object freshness and commander history.

Verified headless: 251core,106Brawl tax/affinity,109per commander bounce branch,
105per legend survivor,65artifact-land,137target invalidation,77/123commander
exile branches,419short-library. Full normally shuffled games and real public
inputs; no injected zones/permissions or native intermediate-state replay.
Costs2U/1U/U, four own-library instances, sickness/tap/cancel, targeted permission,
expiry, normal timing, repeated object rules, source departure, artifact lands,
target exile and both relevant commander owner choices have separate assertions.
The short-library scenario really mills fewer than four, then loses only on draw.

Observed native: original art/cost, mill, graveyard target picker and purple cast;
two Spellbomb sacrifice/recast loops; original legend chooser and surviving
Emry/second mill; Seat produces U. Physical mouse input selected Spellbomb Draw
and Crypt's player target. Crypt sacrificed and exiled ten actual graveyard cards.
The first exile recording predates the presentation-category correction; fresh
verification with the matching new DLL has five actual transfers parsed as
Exile across44states, original native play continuing without a gap. Original Emry Brawl
command cast/mill and exact desktop shortcut/free-redraw/Keep also work. Parser
replay is retained separately from rendered observations and physical input.

Correction to earlier failure diagnosis: native QA could overwrite an unconsumed
click and could refresh an old Pass decision into a later phase. Atomic serialized
requests now bind to the original observation and require matched receipts.
Stale-context rejection is nonfatal and never invokes the UI callback; an actual
negative native test and subsequent successful play verify that boundary. The
earlier stalled Keep recording remains valid failure evidence, but does not
establish a bug in the original Keep workflow. Native free-redraw plus Keep is
now successfully exercised. Original mouse automation used unscaled pixels;
current125percentDPI physical tests use the actual logical client rectangle.

Remaining: the saved Emry deck still lacks69names/copies (31/100copies and6/75
names admitted). Generic inherited choices, broader keywords/costs/replacements,
rebalanced catalogue policy, full native animation parity, rendered commander
hand/exile choices, library replacement sequence, full rendered Brawl game,
multiplayer and recipient-PC installation remain unverified or unimplemented.
Supported own abilities do not imply support for all deck cards or combinations.
The previous package was preserved; no publication, account changes or dev log.

Later native extension closes the return-to-command exile screen: original
blocker assignment, real combat death, Graveyard decline, Crypt during opponent
combat, player click, then original Exile134 Command/Exile prompt and Command
response. Emry is really in command with history1/tax2; replay49states. Thus
native exile return is now observed; native exile decline and the hand-choice
screen remain unverified. This supersedes the earlier exile-screen gap above.
The subsequent native recast showed4U and really paid five Islands, resolved
Emry, incremented command history to2 and milled four again; extended replay101.

## 2026-10-22: four-hour headless shared-interface checkpoint

This extends development evidence; it does not supersede the native observations
above or establish new rendered acceptance. The installed/public alpha.5 build
and production policy still admit370names. No installation, release, account,
game window or GPU validation was changed/launched for this checkpoint.

Recovered source: original native SelectN/Group/Order/Numeric/CastingTimeOptions
and optional-action handlers; literal counter/color/keyword/type identities;
attachment and ability-add/remove model semantics; original Human-controller
forced sole static/replacement selection and mandatory untargeted trigger play.
Harvest's exact source/native labels additionally pass the original Core pure
option translator and prompt-button workflow selector, without a rendered
workflow. Private owned decompilation and bytecode stay outside the repository.

Implemented in the independent research path: explicit scry/surveil partitions,
library/graveyard/exile ordering, reveal acknowledgement, constrained discard,
entity/zone/effect selection, source-bound modes/generic choices, bounded
number/confirm/color/counter-type primitives, actual typed counters and events,
attachments, current types/colors, source/lifetime-bound keyword grants and
ability removals. Unsupported contexts remain gaps. General payments, arbitrary
generic labels and competing effects do not acquire an approximate fallback.

Verified:179authored interface scenarios /4583saved assertions,92of which are
choice permutations. Additional evidence covers12normally shuffled full-match
seeds; existing opening/target/combat/draw regressions; nineEmry/Brawl/Paradox
scripts; strict native input/replay contracts; four simultaneous fresh starts;
profile boundaries and owned-descendant timeout cleanup. Selected evidence has
244native sessions /7567model updates. Counts include multiple games and seed
discovery sessions; these are not244cards or179new admissions.

The native model is checked on each update for life/counters, attachment edges
in both directions, current types/colors, creature stats, tap/sickness and
effective known keyword layers. Four mixed cases prove matching-color
protection removes Frogify/Pacifism through Forge state-based actions, unrelated
protection preserves them, and attachment/type/keyword presentation follows.
Only local-owned exile order is submitted by the human; the bot owns its order.

Failed attempts remain linked beside corrections. They include the fixed
first-start directory race, an old test bot keeping a no-mana hand, a native
driver coercing activation IDs, newly explicit mill/exile ordering prompts,
an obsolete test attack field and invalid bot-ordering assumptions. Original
rules/outcome assertions were retained; changed authored fixture assumptions
are called out rather than concealed as implementation fixes.

Static planning audit:16370Arena names /16331unique script candidates /39unmatched;
9816names mention audited interface families,264have exact modal text bindings.
Those numbers do not prove gameplay, native visuals or Arena/Forge rules parity.

Remaining headless gap: the final inheritance audit finds AI implementations
outside the named choice-guard surface, including cost-decision/assist, ability
selection, draw offers, sideboarding, shuffle hook and isAI. Owned code confirms
the AI cost factory and identity flag; the shuffle hook is conditional and
GameRules defaults its cheat flag tofalse. Reachability and human-controller
parity require further reconstruction and regression. Therefore the named guard
must not be described as exhaustive closure against all inherited AI behavior.
Other gaps include competing/optional/targeted trigger/replacement choices,
broader costs, type/card-name choices, copy/face/token and digital mechanics.

Next acceptance gate: close inherited human-controller/cost paths, expand mixed
mechanic evidence, then render/input-test representative original workflows
before any catalogue promotion or release. Full UI/art/animation parity and
recipient-PC acceptance remain separate from these headless results.

Reproduction and source boundaries: docs/headless-shared-bridge.md. Private
evidence: C:\Users\loula\Documents\Codex\ForgeArenaHeadless-20261022-1729\
checkpoint-validation-final.json. This report binds prepared classes, owned
native libraries, authored inputs, saved assertions, native completion receipts
and explicit failed-run/corrected-run provenance.

## Turn pacing: local preview 0.2.0-alpha.5.turnflow.2

- Recovered bridge cause: 650 ms state/settings dwell and one-second retry;
  opponent stack always held even without an offered response.
- Implemented: readiness-driven automatic pass, one submission per native
  state/request, 50 ms monotonic retry only for an unready workflow, automatic
  pass of opponent spells when Forge offers no legal non-mana action.
- Preserved: Forge's full rules progression, original native request retirement,
  presentation completion, playable actions, combat/other choices, explicit
  stops, full control, terminal and fidelity-gap holds.
- Headless evidence: five real Forge/native-handler scenarios, including a
  payable Essence Scatter hold and wrong-color no-response progression.
- Rendered evidence: 12 passing checks in a normal local practice match; original
  card/Pass callbacks, turn2 to turn4 progression and an interactive native
  Choose attackers screen, with captured frame inspected.
- Installed: pacing-only local build based on alpha.5. Native DLL hash verified
  against the tested DLL. Existing engine/catalogue policy retained. No public
  update or new supported-card claims.
- Gaps: complete Arena smart-stop/stop-setting semantics, broader card/payment
  support, physical input and frame-by-frame animation parity are unproven.

Receipt: C:/Users/loula/Documents/Codex/ForgeArenaTurnFlow-20261023/completion.json.

## 2026-10-23 native turn-flow acceptance and alpha.6 release preparation

Recovered native turn/phase annotation and next-phase fields from owned capture
and parser evidence. Implemented quiet rules-only progression, original phase
presentation, contextual Next/End Turn, turn-yield expiry and Resolve All clear.
Eight real Forge/native scenarios and twelve rendered checks pass. User accepts
the installed alpha.5.turnflow.4 behavior and explicitly authorizes publication.
NativeHost SHA256: 1318894da0578f3417debfb297b8670057be38ea582f5a8f16b1fd61858877b0.
Ship a selective patch over alpha.5: rules, policy and 370-name admission unchanged.
Shared-card research remains unreleased. Full smart-stop/complex lookahead and
frame-level animation parity remain unproven. See docs/turn-flow.md.
Private evidence: ../ForgeArenaTurnFlowParity-20261023/completion.json.
Publication and updater verification require separate receipts.

## 2026-10-22 user-authorized experimental admission

User explicitly requests unblocking the eight deck drafts despite incomplete
verification. Add an optional experimental admission inventory separately from
the verified policy. Generate 342 source/native identities plus four commanders;
exclude Jace and 45 absent native presentations. Preserve structural validation,
exact identities and runtime fidelity gaps. The private candidate includes the
shared-controller research paths as unverified work. Python admission and real
stable-Forge initial match startup pass for Chatterfang, Derevi and Squirrel Girl.
Native/rendered acceptance and local deployment are separate pending gates.
See docs/experimental-card-admission.md and ../ForgeArenaExperimental-20261023.

## Bojuka Bog targeted-trigger regression

Observed: experimental.1 Chatterfang turn2, play_land card46, exits in
HeadlessChoiceController.orderAndPlaySimultaneousSa. Recovered: pinned Forge
human controller orders triggers then calls PlaySpellAbility; setupTargets calls
chooseTargetsFor once per targeting subability. Implemented: source-bound single
mandatory target path, noncancelable target choice, exact Bog trigger/prompt and
black-mana bindings, zero-mana payment, precise fatal error receipt. Evidence:
../ForgeArenaBogFix-20261023/native-final.json (five real Forge/original native
handler scenarios), turn-flow-regression/report.json (eight pass),
coordinator-final.json (37 authored protocol checks), fatal-report-check.json
(actual subprocess failure receipt). Rendered target UI, complete Chatterfang
game, optional/multiple triggers and other experimental cards remain unverified.
No verified card promotion or public publication.

## Chord availability / convoke callback

Observed: experimental.2 turn6 after Chatterfang resolves, snapshot's Chord
affordability check exits in chooseCardsForConvokeOrImprovise. Recovered: cost
adjustment invokes the human payment callback even during canPayCost. Original
X costs are found in CostPartMana.getMana().countX, not reliably isAnnouncing.
Implemented: explicit nonfatal per-action gaps in experimental offer queries,
no decision creation in those queries, restoration of the prior fatal gap,
strict real-effect handling and once-per-match source-specific native notice.
Verified: repeated queries do not tap or change events/mana; rejected casts
leave the engine healthy; independent spells resolve; normal Match.startGame
reaches Chatterfang plus Chord. Three real Forge and three original-native
handler cases pass. Convoke, X picker and complete deck interactions remain
unimplemented/unverified. Private evidence: ../ForgeArenaConvokeFix-20261023.
