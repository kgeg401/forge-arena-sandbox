# Forge x Arena development journal

## 2026-10-21 three-hour checkpoint

- Started 08:12:58 UTC; stop development and finish verified dev log by 11:12:58 UTC.
- Existing baseline: isolated Unity Arena lab and file IPC Forge backend, Plains mana/turns and Savannah Lions cast/resolve verified. Runtime D:\GAMES\CodexAssets\ForgeArenaSandbox; code here. Retail files/profile untouched.
- Skills: mod-any-game, reverse-engineering, showcase-video. Existing recon and pinned installed assembly/jar hashes retained. No new loader installation.
- Scope: player-controlled attack/block -> native combat/damage/life -> repeatable bounded match where verified. Captioned game-window dev logs for working increments and combined log. Preserve originals, decode and visual checks, Atlas receipt required; do not claim delivery without it.
- Native research: SharedClientCore DeclareAttackerRequest UpdateAttacker sends DeclareAttackersResp; SubmitAttackers sends SubmitAttackersReq. Attack selection and submission are separate operations. Captured native request samples in private research/combat-protocol.
- Forge phase loop calls controller synchronously during actual turn-based declaration actions. Keep all Forge mutation on its owning thread; expose a bounded nested file decision pump during controller calls, rather than approximating attack rules or changing phases with developer APIs.
- Design: on controller wait, publish decision.json correlated to the pending pass request; native bridge adopts intermediate engine state and emits native declaration request. Selection updates are validated against Forge legal choices; submit releases callback and original engine phase loop completes. Pending decision commands get authoritative final responses. Unknown interaction types remain explicit gaps.
- Knowledge base: no MTG Arena note; Forge name search matched unrelated Minecraft loader. No existing approach reused from those.
- Combat implemented and manually verified in the isolated native lab: original attacker/blocker controls, separate selection/submit requests, real Forge declaration callbacks/validation, tapping, player damage, creature damage and state-based deaths. Both public battlefields/graveyards now translated with ownership. Native damage/death annotations use captured protocol.
- Headless checks: combat-check-20261021-041934-d9e85a (10), combat-check-20261021-042703-674824 (6), combat-check-20261021-042714-03556a (6). The failed 042529 run exposed a Windows response-file replacement race: removed duplicate response write and bounded AccessDenied retries. Preserved failed evidence.
- Evidence: research/combat-protocol/{attack,block}-native-{status.json,wire.jsonl}; original videos in devlogs/2026-10-21-combat. Devlog 02 is 69.021 seconds, 5,718,181 bytes, full decode passed and contact sheet inspected.
- Native audio startup restored from the pinned Bootstrap/AudioManager sequence. The new isolated process reports initialized=true, loadError=false, 179 available packages. Process-only recording native-audio-01 contains peak 0.3404, RMS 0.02469 float audio; cached sound banks loaded locally. Network remains unavailable.
- Launch receipt transient empty Process.Path is retried for five seconds, still rejects mismatch. Fresh redeploy succeeded with token/board readiness verified.
- Native combat presentation correction: installed GreInterface.ModifyEventsList associates combat damage with a ModifiedLife event sharing its source. Supplying source zero reduced the displayed DamageDealt amount to zero, although the authoritative life total was right. Emit source-specific damage/life annotations. Installed parser replay now reports damageTotal=2 and one GameEndEvent for the victory sequence.
- Outcomes: real Forge lethal-win/defend-lethal checks passed 4 each (045411-2f7b45, 045421-53b059). Whole seeded duel reached turn 50 and Forge Milled loss (044703-3d7d7f, 5 checks). This is not normal match startup or arbitrary decks.
- Reused pinned PhaseHandler.checkStateBasedEffects before exposing priority, verified in installed bytecode; avoids an extra human pass after lethal damage and settles triggers/SBAs in Forge. No simulation or invented win condition.
- Native terminal protocol recovered: MatchComplete plus game/match ResultSpec, persistent LossOfGame reason, and IntermissionReq. The request creates native GameEndEvent and unlocks native MatchEndScene. Manually observed avatar death and VICTORY; evidence combat-protocol/victory-native*, native-victory-parser.json. Devlog 04: 27.021 seconds, 2,868,925 bytes, decode and contact inspection passed.
- Native hidden zones now carry IDs/counts without identities; public opponent cards and casts render from Forge. Real built-in Forge AI enabled only for duel. Manual turn 1 cast, opponent land/creature stack, turn 3 draw/untap/second cast, summoning-sick attacker exclusion, AI block and two graveyards all verified. Original takes native-duel-01/02 retained; screenshot/wire in combat-protocol/duel*.
- Cleanup: human callback replaces inherited AI discard choice. Native SelectNReq uses installed context Discard and installed prompt 14. Wrong count, duplicates and unoffered card rejected without zone changes; 5 checks in 051207-37f69d. Native UI disabled Submit with one choice, enabled with two, then Forge discarded exactly IDs 44/45, leaving seven. Evidence combat-protocol/discard-native*; original native-discard-01 retained.
- Spell regression updated for supported combat (8 checks, 045432-a284e2); Forge itself skips attacks when only summoning-sick creatures exist. Mana regression passed. Added installed-parser wire replay mode, preserving original synthetic transport probe.
- Corrected aggregate life-loss annotation for multiple attackers. Retained failed full-game evidence (26 rules damage versus eight native parsed damage); corrected three-attacker fixture gives six/six and complete native duel gives 26/26 across 131 states, native defeat, life 20/18/12/4/-6. audit_recorded_match.py passes 12 comparisons. Session 5b48ebe0-22f8-4b54-b574-598aed53c4d1; research/combat-protocol/complete-fixed-*.
- Concede: real Forge outcome, no synthetic life loss, 17 engine checks across normal play/attack/discard decisions. Native Options Concede observed. Timeout now stops with explicit restart gap.
- Fixed automatic priority input lifecycle: direct bridge pass left Arena's old workflow alive and stranded opposing Resolve; replaced with applied native ActionsAvailableWorkflow.OnAutoYieldEnabled, guarded by visible-state/UX-queue checks. Full corrected duel visually completed. Policy is limited to supported two-card slice and is not Arena smart-stop parity. Failed recordings retained.
- Default launch is seeded duel; Open-Playable.ps1 logs failure details and a desktop Forge Arena Sandbox shortcut targets it. Native Continue/home remains unsupported; fresh launch archives old session. Wrapper/shortcut runtime test pending at this entry.
- NativeHost and ParserProbe builds pass with zero warnings/errors; original headless transport/parser regression passes. Devlog 07 Multiple Hits: 22.021 seconds, 2,265,453 bytes, full decode/contact inspection passed.

- Added two source-checked vanilla identities: Yoked Ox 69826/title43200 (W, 0/4, Ox) and Oreskos Swiftclaw 67742/title44266 (1W, 3/1, Cat Soldier). Source database hash and exact rows retained in research/vanilla-card-identities.json. Costs only affect native presentation; real Forge pays/validates them.
- New fixtures vanilla-costs, defend-ox and attack-swift pass 9/5/4 checks (062454-8a28dd, 062520-da1643, 062507-4f89a0). Native casts, tap costs, 0/4 block surviving damage, and 3-power player hit observed. Swift parser reports three and life17; Ox parser reports two card damage. Existing Lions spell regression passes eight (063755-805da7).
- Optional mixed-duel uses fixed six-card hands and 24-card libraries containing all four admitted cards, real Forge AI. Engine reached turn18 LifeReachedZero winner2 life0/9, five checks (063259-9dbe32). Native turn5 verified player/opponent casts, sickness and creature presentation; 65 installed-parser states, no observed bridge gap. Whole mixed-duel rendered outcome untested. Native human multi-block damage-order prompt remains absent; internal ordering inherits AI policy and is explicitly documented.
- Native concession from an open attack declaration recorded successfully; lowercase escape with a held key opens Options. Earlier immediate screenshots could precede the UI update. Game remained at life20/20 and showed native DEFEAT; evidence concede-pending-*.
- Devlogs 08 Concede, 09 Complete Duel, 10 Different Creatures and 11 Mixed Duel rendered, fully decoded and contact/end-frame inspected. Corrected Devlog09 edit to retain the actual defeat title after the avatar burst. All original takes retained. Combined 11-chapter original-quality log and full-duration sub-9MB chat copy are being generated.
- Desktop shortcut runtime test passed: launching the actual .lnk invoked Open-Playable.ps1, archived the prior mixed session, created a fresh isolated duel and reached native first main with six cards and 20/20 life. Launch log retained on D:.
- Combined log: 11 chapters, 587.093 seconds, 55,641,171-byte original-quality master. Chat copy 8,262,670 bytes, 587.098 seconds, H264/yuv420p/AAC, faststart. Both completely decoded, original contact sheet and compressed sample/end frames inspected; full chapter footage/audio retained. Chat copy is 640x360/12fps; master is 1280x720/30fps. Originals untouched.
- Atlas delivery: Library/user_message APIs unavailable. Existing Atlas chat opened through the user-authorized desktop UI; one initial conversation-open failure recovered with Try again. Native combined MP4 attachment and caption accepted with Read 6:45 AM, and Atlas replied that the checkpoint is attached. No resend of the accepted combined file. No Library ID is exposed by this UI route. Individual chapter delivery in progress at this entry.
- Final boundary audit found stale raw legalMana/legalCasts after concession (client hid them; tested post-concede cast could not pay). Added global terminal guard before all new gameplay and cleared legal offers; snapshot reads remain valid. Eight terminal checks pass, combat-check-20261021-065424-ddf2d3. Fresh native main-phase Concede still yields 20/20 defeat with all legal-action arrays empty. Devlog12 records this final hardening; assertions are explicitly captioned as headless checks.
- Automated Escape presses remained inconsistent; the reliable native Options target in the 1024x576 logical client is gear center (1517,318), rather than its left edge (1511,317). Do not treat the earlier held-key attempt as a keyboard automation fix. Original Options/Concede button footage is retained.
- Atlas UI receipts now confirm combined log plus all eleven initial individual chapters. Native attachment filenames were inspected per batch; recipient acknowledged all eleven. Multi-directory long file-dialog entry selected only the first two, so remaining files were sent in verified basename batches, without resending accepted files. Receipt JSON: research/atlas-video-delivery-receipt.json. The final added terminal chapter and revised compilation are being delivered separately; earlier originals remain intact.
- Final edition: 12 chapters, 609.114 seconds, master 57,641,603 bytes; full-duration chat copy 609.125 seconds, 8,272,298 bytes. H264/yuv420p/AAC, faststart, chapter count/duration/full decoding all pass. Native terminal chapter and final compressed last-frame visual check show actual DEFEAT. Earlier 11-chapter edition and all original takes retained.
- Final chapter12 and revised Final chat attachment accepted in existing Atlas, Read 7:04 AM. The eleven earlier individual chapters and first compilation were separately acknowledged; no accepted file was resent. UI route exposes no Library ID. Delivery receipt is retained on D:.
- Added optional Forge Arena Mixed Duel desktop shortcut and tested that actual shortcut. New session 0afd2c53-bd1e-48dd-be03-517684b0fa93 reaches first main, six cards, 20/20, nativeState1, gap null, AppContainer capabilityCount0. Original Forge Arena Sandbox shortcut still opens the two-card duel.
- Closing source check for the next milestone: installed GameAction.startGame(GameOutcome[, Runnable]) draws the opening hand in GameStage.Mulligan, calls MulliganService.perform, then enters Play/startFirstTurn and the game loop. Installed PlayerController exposes chooseStartingPlayer, chooseStartingHand, mulliganKeepHand and tuckCardsViaMulligan. Saved installed bytecode and an implementation-boundary summary under research/startup-protocol. This is research only; normal startup is not implemented, and the tested seed remains the current runtime.

## Four-hour continuation, 2026-10-21 11:13:49 to 15:13:49 UTC
- Prior checkpoint preserved at b8c53f9; fresh work targets actual Forge normal startup, opening hands and native mulligan UI. Existing four-card seeded duels remain regression routes. Captions/game audio and automatic Atlas video delivery remain authorized.
- Installed Match.startGame prepares all zones, GameAction draws hands and invokes LondonMulligan, then enters full PhaseHandler loop. A controller-boundary file pump returns actual abilities to that loop on one thread. No sentinel abort or parallel rules mutation. Installed LondonMulligan bottoms immediately after redraw before keep question; local starting seat is an explicit practice policy.

- Opening-duel implemented: Match.startGame owns setup and full priority loop. Controller returns selected LandAbility/mana/spell or null pass; replies at stable controller boundaries. Exact source/installed bytecode retained privately. Four startup cases pass 40 assertions (keep, double mulligan, concession during mulligan/bottom), evidence combat-check-20261021-072824-2797bc through -072857-4d379b. Complete independently driven normal game seed7274 reaches turn20 LifeReachedZero, winner2, -1/4 life (six checks), combat-check-20261021-073542-53d0b3.
- Live session ecc2474d-c641-43df-b342-2726761c34be: original MulliganWorkflow, Keep7->Keep6, GroupingContext_LondonMulligan/LondonWorkflow Return1, native GroupResp accepted by Forge, six-card first-main, legal land and creature cast, actual AI turn. AppContainer capabilityCount0. Wire/journal/status/parser saved in research/startup-protocol/opening-native-*. Native parser observes MulliganRequest, GroupRequest, Start->Play and actual actions.
- Automation: repeated WinDrive drag and cursor-only legacy drags did not trigger native dragging. A legacy relative mouse-motion event while held did trigger native drag; Done enabled and the actual GroupResp was recorded. Do not call the private DPI-aware WinDrive copy a solved input path. Initial failed/partial takes retained.
- Native London presentation adapter asks keep on seven before this installed Forge build's early bottom callback, then buffers answer for following keep callback. Only rejected hands auto-return first offered N because Forge immediately reshuffles them. Kept hands require human bottom selection, with duplicate/unoffered/count/stale-token checks. Local starts by explicit practice policy; starting-player choice is next.

- Starting-player choice implemented from actual Forge callback and native ChooseStartingPlayerWorkflow. Default is coin-toss; local-first is now a test policy. Twenty headless checks verify Play/Draw, eight-card second-player first main, invalid seats/tokens and startup concession. Native session722b9ced-6f4b-4fff-b541-872b22fee43e recorded DrawFirst->Keep7->opponent turn->local turn2 hand8->Concede->DEFEAT, gap null. Native wire parser14states, one result. Chapter14 is 50.021 seconds, 5,700,029 bytes, H264/yuv420p/AAC and full decode/visual check passed.
- First live play/draw take failed: decision.json sharing violation stopped Java owner thread. Fixed reader sharing (FileShare.Delete), bounded file retirement/replacement retry. Four deliberate conflicting Windows read-handle checks pass (combat-check-20261021-074729-1f2741). AWT kept failed owner PID alive, so added fail-closed uncaught exception exit; exact stale private backend PID was verified and stopped before restart. Nullable PowerShell seed boxing initially serialized null, corrected to direct long conversion; failed launch archived.
- Fixed terminal service overwriting normal-game journal: append after Match.startGame returns. Complete normal seed7274 now follows real AI coin win, reaches turn35 life0/5, seven checks including retained startup/gameplay history (combat-check-20261021-074918-b9e10a). Native metadata uses MatchWinCondition_None for single local game; SingleElimination would auto-choose Play in the original workflow. This is documented sandbox policy, not server parity.

- Atlas chapter14 native attachment accepted and acknowledged, Read07:56 local. No API Library ID exposed; receipt JSON updated. Chapter13 was separately acknowledged07:39. No accepted attachments resent.

- Divine Arrow vertical slice added using installed Forge card definition/ability bytecode and Arena DB identity WARgrp69461/title336205/ability100370 (hash/evidence research/targeted-spell-protocol). Forge candidate enumeration and canTarget/count checks drive native SelectTargetsReq, selection/unselection/Submit and Cancel. Cancellation stays before payment; native CancelActionReq has state ID but zero response ID and is accepted only for current target request. Kept unique IDs/seat/session/token checks.
- Twenty-five headless target assertions pass in combat-check-20261021-080633-0308a1, -080644-0d34fa, -080655-b77d9b: idle creature rejection, empty submit, unselect, actual target, two mana, real stack, four noncombat damage, both graveyards, cancel and concede. First test harness incorrectly indexed omitted null decision; corrected to optional lookup; not a product failure.
- Native session0e1e85e3-2b3e-4f0c-b7ab-d8da09babdbe rendered original Arrow art, target prompt/highlight, ignored idle Ox, Cancel with hand/resources unchanged, recast, selected attacker, Submit1, target line, actual stack/mana taps, native hit/death and both graveyards. Parser9states/4damage. Persistent target-spec cleanup then added for stack removal and rechecked in session6f11b1a3-4010-4b23-8769-6fd9ff0f7a92: auto priority reaches next turn, native18states/4damage, no gap; source takes native-arrow-01/02 retained.
- spell-duel optional normal startup deck adds nine Arrows alongside three nine-creature sets/24Plains. Full engine seed7274 reaches turn45 LifeReachedZero, winner2, -3/20 life, seven checks; combat-check-20261021-081001-0da0eb. Six human target callbacks and six AI Arrow damage events; test controller sometimes targets its own attacker, then opponent Arrow resolves first and removes that target. This is stack/response coverage, not AI strategy evaluation. Do not call it a whole rendered five-card duel.
- Installed GameEventCardDamaged omits combat flag. Current admitted slice classifies Divine Arrow damage as noncombat and vanilla creatures as combat; general damage-source classification is not implemented. Native persistent TargetSpec derives actual cast event StackItemView targets for either player, and removes the spec when the spell leaves the stack.

- Final native damage audit corrected noncombat mapping from native DamageType_None0 to installed DamageType_Direct2. Fresh sessioncbeec84e-82ae-459f-96b9-69dcb4e0f187 reports4 Direct damage from grp69461; persistent target-spec900046 removed. Existing combat stays enumCombat1. Parser report now records damage type/source printing. Native-arrow-03 is the corrected take; 01/02 retained as earlier evidence. Chapter15:43.021seconds/4,391,221bytes, H264/yuv420p/AAC/full decode/visual contact passed. Atlas transfer in progress.

- Atlas chapter15 accepted and acknowledged, Read08:25 local. Native attachment route exposes no Library ID; receipt JSON updated. A transient Atlas refresh failure was retried before upload, then existing history including chapter14 recovered; no accepted videos resent.

- Orator slice implemented and manually verified in native session2b1d5607-8c18-4593-9723-13f0907965d2: actual ability stack panels, source links, ordered life gain20->21->22->23 and removal, no native gap. Headless trigger assertions20; full normal trigger-duel seed7274 ends turn15 winner2. Private evidence research/trigger-protocol/native-double-*, combat-check-20261021-083738-114449, -083750-6885e8, -084025-9936f9. Chapter16 56.021333 seconds/5,951,152 bytes passed decode and media checks; visual/delivery verification follows.

- Atlas chapter16 accepted and acknowledged Read08:42; receipt saved. Blue mana/Unsummon native slice verified with actual Forge target/cost/return rules, hidden opponent destination and visible friendly return/recast. Corrected prompt1010 after first take showed Arrow prompt1008. Headless13 assertions, full blue-duel seed7274 seven assertions and terminal turn17, native12states/gapnull. Details/evidence in ledger. Chapter17:46.021333sec/4,611,299bytes, full decode passed; delivery follows.

- Chapter17 delivered to Atlas and acknowledged Read08:55; receipt updated. Added validated supported-deck import, Java revalidation and optional two-file picker. Invalid deck/cancel preserve current game. Import20checks and separate full imported-game7checks pass. Native imported session6ee56a5b-6801-4997-aa85-b3160baaf923 reaches turn5 concession/DEFEAT,49parserstates and12auditchecks, with real AI Unsummon targeting our Orator. Chapter18:69.021333sec/6,090,773bytes, decode passed, original full4:27take retained.

- Chapter18 final edit73.021333sec/6,751,534bytes delivered and acknowledged Atlas Read09:12. Earlier undelivered edits retained under draft names. Custom-deck shortcut installed at Desktop/Forge Arena Custom Decks.lnk. Added actual Ajani/Sparky match avatar IDs via original PlayerCreatedMediator; native portrait/life23/concession checked in session0479a2a6-2e9b-4e65-a4a2-c920286a0714. Chapter19 40.021333sec/5,450,270bytes passed media/visual checks; delivery follows.

- Chapter19 delivered and acknowledged Atlas Read09:19; receipt saved. Actual creature-spell targeting and Essence Scatter counter slice added. Installed getNumCandidates fixes empty-Stack counter eligibility; real Countered events and native transfer source tracked. Headless23assertions, full counter-deck7checks and native7state counter reason/source audit pass. Initial seeded-AI cast attempt failed and remains evidence; fixture now actually pays/casts target during setup. Chapter20:40.021333sec/3,736,939bytes passed media/visual checks; delivery follows.

- Chapter20 delivered and acknowledged Atlas Read09:35; receipt saved. Human unordered vanilla damage choice now pauses actual Forge assignCombatDamage and translates Arena original damage browser/response.25 boundary/outcome checks and seven installed-parser/native outcome checks pass. Manual0/3 allocation differs from initial1/2 suggestion and is honored. Independent full seed9137 custom game reaches turn23 LifeReachedZero (-5/10), seven checks. Original332-second source retained; chapter21 49.021333seconds/3,135,770bytes passed full decode. Legacy/nonvanilla combat remains unsupported; see ledger for precise boundary.

- Added Forge Arena Practice desktop shortcut for a normal shuffled White-Blue-Counters versus White-Blue-Tempo match. First hidden launch failed on Windows PowerShell Get-FileHash module auto-loading; replaced that dependency with direct .NET SHA256 in reusable Assert-GameIdentity.ps1. Identity and optional build checks now precede stopping the current lab. Actual shortcut relaunch created PID61384, session9a4552aa-7f45-45bc-803d-20efb5490019, AppContainer capabilityCount0.
- This actual normally started native match was played through to turn14 natural LifeReachedZero (-4/13), original DEFEAT. Opening Play/Keep7, lands, Lion/Orator casts, double life gain, combat/deaths, actual AI Unsummon and repeated AI triggers all occurred. Later play deliberately passed casts and attacked into combat; this is progression coverage, not competitive AI testing. Installed parser170states/49damage/one result; recorded audit12checks passes, including all20life states and hidden-card omission. Evidence research/custom-deck-protocol/full-practice-*. Full game-window/audio take retained.
- Longer play exposes presentation/usability gaps: an opposing Orator source-link can look anchored toward a local card/portrait despite correct Forge source/native parent IDs; unresolved. Original yield mode changes and first pass work, but remaining windows still require manual passing; not smart-stop parity. Neither gap changes the audited rules outcome.

- Added Quick Study draw slice and White-Blue-Study60-card sample.15 engine assertions, full normally started Study/Tempo game7checks, native prepared draw/cleanup/decking sequence and installed-parser29state/zero-damage/one-result audit12checks pass. Source and exact evidence in ledger. Builds0warnings/errors. Chapter23 86.021333seconds/7,461,760bytes, original412.666seconds retained. Chapter22 final121.021333seconds/13,834,283bytes; separate full-footage chat121.037seconds/7,797,530bytes, decode and visual checks pass. Atlas transfer underway.

- Independent source-mapping audit found/fixed earlier Swiftclaw Cat/Soldier error: installed Forge and Arena enum77 both say Warrior. All10native mappings now pass identity/type/subtype/cost/color/ability/source-hash checks; audit runs before backend compilation. Native inspect visually confirms Cat Warrior in session65291da4-d1a4-4919-ab8c-4868e240475d. Chapter24 20.021333seconds/1,378,982bytes passes decoding/visual check.
- Chapter23 final action-aligned edit is95.021333seconds/8,488,820bytes; source pauses preserved in the original. Exact-frame checks show actual draw, selected Lion, submitted discard and20-life defeat. Earlier contact labels sampled near interval centers, so critical action timings were checked directly. Chapter22 accepted/acknowledged Atlas Read10:35.
- README now presents current playability and boundaries; earlier text is preserved verbatim under docs/checkpoint-history.md.

- All24chapter compilation:1298.370333seconds/125,777,196bytes master; chat1298.4seconds/8,245,465bytes,480x270/10fps. New13..24edit:689.256seconds/68,137,763bytes master; chat689.266seconds/8,235,463bytes,640x360/12fps. H264/yuv420p/AAC, faststart, full decoding, duration/chapter counts and exact-frame visual checks pass for both editions. Originals and earlier editions preserved. New compiler --from-chapter supports a focused checkpoint cut and adapts chat quality for the9MB limit.
- Atlas chapter23 acknowledged Read10:52, chapter24 Read10:55; both compilations accepted/acknowledged Read10:59. Receipt saved; no Library IDs exposed by native UI route.
- Practice default now includes White-Blue-Study. Actual desktop shortcut starts PID56460/session2d84491f-c228-4364-8f8c-ee2f8ac6757f, original Play/Draw, gapnull, capabilityCount0. Left awaiting the player.
- Final host check: no Forge TCP socket and no established Arena connection observed; Arena has ancillary listen0.0.0.0:62455. Mono debugger explicitly disabled. Exact listener owner component unconfirmed (module-level diagnostic requires elevation); no authentication changes made. Native startup logs show blocked DNS attempts. Network restrictions kept intact. Source-mapping audit also checks base creature stats.


## 2026-10-21 pack-opening hour (16:27:49–17:27:49 UTC)

Route: original owned booster chamber/prefabs and native reveal machinery, scoped local inventory adapters in the existing zero-capability AppContainer. Retail installation and account balances remain unchanged. Added source-derived private catalog: 51 sets / 13,326 eligible primary printings, 100 initial packs per set, explicitly custom 5C/2U/1R-or-M collation. LocalPackProfile atomically commits debit, all collection gains and idempotent receipt, preserves backup. PackProfileProbe: 15 checks pass; native audit currently 22 checks across three actual pack transactions, 24 copies. Final bulk/render evidence still being collected.

Recovered original MainNavigation camera/canvas/light settings by loading only its scene and inspecting it without wrapper-service initialization. Original hover prefab must be instantiated as GameObject then child view selected. Its second camera must be a URP overlay or it clears the whole screen. Native preload leaks the first card's detached world pose into the last reveal slot; inspection found z28.33/scale0.67 versus original prefab z0/scale1. Scoped pool reset to owned prefab pose fixes all eight cards, native visual/probe verified.

Failed attempts preserved privately: first startup used stale status and sent prepare too early, causing a native crash; launcher now requires status newer than its verified launch receipt. Original offline set service provides no collations; a narrow independent pack metadata adapter replaces that dependency. Mono File.Replace hit AccessDenied inside the AppContainer despite desktop tests passing; flushed MoveFileEx atomic replacement works in a native opening. Wrong initial canvas scale clipped cards; recovered native layout replaces the guess. Windows 125% DPI means automation uses 1024x576 logical client coordinates for 1280x720 recordings. Failed black-screen take1 is preserved and will not be used as a successful preview.

- Final pack persistence checks: 19 passed, including rejected read-only saves, ignored uncommitted pending files, defensive snapshots and unsupported-schema rejection. Expanded test initially found a read-only backup inherited from a failed write; save now rejects protected primary profiles before creating backups.
- Native openings: two WOE singles, one M20 single, one ELD single and WOE Open x10: five transactions, fourteen packs,112 collection copies. WOE88/M2099/ELD99 remain after restart. The entire profile matches the pre-restart snapshot byte-for-data. Native bulk/replay audit50checks passes, all80 identities/final positions match the durable receipt, and retained final evidence has all80 revealed. Replay did not change revision5 or award more cards.
- Native mouse rare reveal, hover preview and Continue verified. Bulk auto-scroll, reveal-all and source-ID projection run. Automated manual bulk drag did not move the list reliably; raycast probe shows native card-holder/content/hitbox targets and ManualScrollDragAllowed=true, no popup-canvas blocker. Human manual bulk browsing remains unverified; do not claim drag parity.
- Added Forge Arena Packs desktop shortcut. Original recordings and unsuccessful attempts preserved. Chapter25 final71.021333seconds/33,753,604bytes; chat71.041016seconds/7,406,811bytes,854x480/24fps. Updated25chapter master1369.392seconds/159,529,353bytes; chat1369.402seconds/7,963,180bytes. Full decoding, H264/yuv420p/AAC, faststart, duration and visual checks pass. Earlier unaccepted69second edit and compilation retained as superseded. Atlas delivery pending receipt.

- Atlas accepted both chapter25 and the updated25-chapter22:49compilation, marked Read13:19America/New_York and explicitly acknowledged both, including the stated limits. Native attachment receipt retained privately; no Library API/ID was available. Practice regression opens a healthy normal custom-duel, seven-card mulligan, sessiona7aa8353-551b-419a-bd73-edc8e44d748c, no bridge gap. Returned to ready WOE pack carousel, balances88/99/99 and112copies unchanged. Source catalog builder now independently checks the pinned collation assembly and retains the enum-evidence digest as well as the owned database hash.
# 2026-10-21 Arena-only catalogue and Hare checkpoint

User timebox: 18:09:23–18:39:23 UTC, no dev log. Reused the existing offline lab,
owned SQLite and installed Forge scripts. Generated coverage: 20,159 printings,
16,140 names, 15,814 unique script candidates, 326 unmatched; candidates are not
playable coverage. Stripping localization rich-text tags recovered 612 matches.
Per-printing identity/art/types/stats/ability/token mappings are private on D:.

Replaced native card identity switch with generated manifest; centralized explicit
admission/preferred printings in bridge_support.json. Eleven names now admitted,
including Hare Apparent. Retained recovered basic mana IDs separately from empty
source land ability lists. The original ten mappings pass source checks unchanged.

Recovered Hare trigger175767 -> original token94160 from owned database and read
installed Forge h/hare_apparent.txt / w_1_1_rabbit.txt. Original native token-created
and token-deleted annotation parsers supply presentation. Native run visibly
creates three Rabbits from three casts, then Unsummon removes one. Native casting
and target selection used original workflow CanClick/OnClick QA callbacks;
Resolve mouse buttons also worked. OS hand double-click automation was unreliable;
human manual input and a complete rendered normal Hare match remain unverified.

Checks: Hare engine22 (including token disappearance), Orator7/13, previous normal
duel7, Hare normal duel7 (seed7275, turn14 win,16/-6,170 response states,max14tokens),
import/startup20, deck storage23, source mappings11. Native creation parser10states;
creation+removal parser39states. Evidence: research/card-coverage on D: and
docs/card-coverage.md. Generic test threshold failed for a completed one-land
seed7274 game; token-bounce fixture initially lacked reserved blue mana. Both
harness conditions were corrected and retained as failed-attempt evidence.

## 2026-10-21 compatibility and family-tester checkpoint

Added a repeatable all-catalogue constructor/capability audit and explicit
per-card blockers; current results and limits are in docs/card-support-audit.md.
15,840 script candidates are distinct from eleven admitted playable names.
Fixed admission so unverified mapped names cannot become enabled implicitly.
Report58, source11, admission exclusion/invalid-policy, Hare22 and complete
normal Hare7 checks pass. No new card names were admitted this checkpoint.

Prepared an unpublished portable tester package and tested an actual separate
local installation. Root guards and an early AppContainer-token check retain
offline isolation. Local copies, dependencies and data are separate from adapter
versions; actual update/rollback retains sample decks byte for byte. Update44,
setup-negative5 and root/token6 checks pass. Original board/deck scenes and
native audio initialized; automated hand-card input remains unverified. Added
optional observation-only input diagnostics rather than changing handlers.

Packaging pitfalls corrected: fresh install required a separately licensed Gson
jar; restricted children cannot inspect ancestors outside their ACL; direct
ordinary-token launch must exit before game code; test imports must not write
bytecode into immutable version folders; generator-only updates must invalidate
derived indexes. Retained failed evidence privately. Final publication lint has
zero failures/warnings. No GitHub upload, second-PC delivery, multiplayer or full
catalogue playability is claimed. Setup still needs a friendly prerequisite UI.
See docs/sharing-and-updates.md. No new dev log was created.

## 2026-10-21 one-hour Brawl foundation checkpoint

Added explicit arena-brawl import and independent engine validation for one
commander plus99main, singleton basics exceptions and the restricted monocolor
identity policy. Source-checked Isamaru72175 is commander-only admission; the
ordinary eleven-name policy stays bounded. Normal Forge Match.startGame now
registers Brawl commanders at25life, uses the actual command may-play options,
commander tax and free first London mulligan. Human graveyard return choices
are explicit; unsupported hand/library replacements stop with a fidelity gap.

Connected original Arena commander designation, changing object identity,
versus-screen metadata, command-zone casts and Command/Graveyard OptionalAction
workflow. Actual native test: commander died in combat, returned, then paid2W
(three real Plains tapped) and resolved with commandCasts2. Installed parser
replayed194states retaining one commander per player. A fresh desktop-shortcut
launch and original free-mulligan callback redrew seven with zero cards to bottom.
Native QA invoked original observed UI callbacks; physical mouse play remains
unverified. Corrected command return's category from the old PlayLand fallback
to source-supported Put; latest rendered validation is recorded separately.

Completed normal engine games exercise return/recast, declining return and
repeated tax through93mana/decking. Import16, Java admission14, London mulligan12,
source mappings12, Hare22, normal constructed7 and catalogue report58 pass.
Exact scenario receipts and screenshots remain private on D:. See docs/brawl.md.
Emry abilities, arbitrary commanders and broad Brawl legality are not implemented.
The existing preview.12 tester package was not updated or published. No dev log.

Final checks: a fourth normally started Brawl game repeated the commander-only
sequence with153checks and the same turn186 decking result. Modified replay of
the command-return category parses Put correctly across194states; rendered Put
timing remains unverified. Native free redraw showed seven/zero-bottom correctly,
but Keep on the redrawn hand emitted no response. This separate native workflow
gap is open; keeping the first hand is the bounded native path exercised earlier.

## 2026-10-21 Emry mechanics continuation (first pass; completed below)

Time box23:15:33Z to01:15:33Z. Reused owned source scripts and native IDs:
Emry70190 affinity177, mill86971, tap/graveyard permission136098; Ornithopter75832
flying8; Spellbomb72518 bounce86974/draw4921. Three new ordinary mappings and
Emry commander mapping. Explicit color identities separate colorless artifacts
from colored activated costs. Forge computes offered costs including affinity/tax.

Added real activated-ability inputs, graveyard may-play alternatives, native
multiple ability identities/actions, target prompt5287, correct mill/ability
presentation metadata. Normal input-only Emry practice sequence245checks passes
through turn15: discount2U/1U/U, real payment, four own-library instances milled,
sickness, target restrictions/cancel, tap cost, targeted permission, cost/timing,
re-entered graveyard object rejection, expiry and permission after source leaves.
Evidence research/combat-check-20261021-192931-c2b27f on D:. Initial smoke against
mirror AI repeatedly had Emry bounced before untapping; changed to vanilla Ox
opponent. First assertion script assumed an undrawn Ornithopter; fixed harness
to wait via actual turns/draws, without state injection.

Native first launch hit Windows delete-pending decision.json access denied despite
valid inherited AppContainer ACL. Added bounded nonblocking retry (one second),
retaining persistent permission failure. Native replay/retry ongoing; no claim
that full native Emry interaction or all deck cards are supported yet. No devlog.

## 2026-10-21 Emry mechanics verified checkpoint

Completed Emry's three own abilities within the explicitly admitted artifact
slice. Added Emry, Ornithopter, Spellbomb, Seat of the Synod and Crypt as ordinary
source-checked mappings, and Emry as a blue Brawl commander. Sixteen ordinary
names plus the separate Isamaru commander now have seventeen unique source
mappings. Affinity, permission and commander rules remain Forge-owned; native
offers use actual adjusted costs and recovered ability IDs rather than guessed
rules. Card color, color identity and produced mana are separate; Spellbomb is
colorless with blue identity, and Seat is a colorless artifact land producing U.

Normal input-only games pass core251, Brawl affinity/tax106, bounce109 per owner
branch, legend105 per survivor, artifact-land65, target-invalidation137,
commander exile77/123, and short-library419 checks. These include shared phase
and input assertions, not distinct mechanics counts. Real casts, payments,
combat deaths, sacrifices and Crypt exile drive the tests. A target removed
before resolution grants no permission; expiry, timing, source departure,
artifact-land targeting and newly returned graveyard objects are covered.
Short mill does not lose until a later failed draw. Exile commander choices
preserve command history; tax is offered only in command, and after Crypt leaves
the taxed recast really pays five. Both owner branches are explicit human inputs.

Native observations: Emry cost/art, source-bound mill, original graveyard picker,
purple graveyard cast, two actual Spellbomb sacrifice/recast loops, legend keep
choice and Seat blue mana. Actual OS mouse clicks selected Spellbomb Draw and
Crypt's local-player avatar; the latter really sacrificed Crypt and exiled ten
cards. That first exile capture used the prior transfer-category fallback;
source enum inspection corrected it to Exile, with fresh validation tracked in
the checkpoint receipt. A fresh native run with the matching new DLL really
exiled five cards; all five parse as Exile across44states, with no host gap.
Separate parser replays: ordinary two loops80states,
legend/Seat56, Crypt102, Emry Brawl command cast/mill88. Parser evidence alone
is not animation or rendered proof.

Added repeatable Mechanics and Brawl desktop shortcuts and Open-Emry.ps1.
Exact Brawl shortcut launched the isolated zero-capability client at25life,
free-redrew seven, then successfully kept seven into turn one. It also cast
Emry from command with real three-land payment and resolved the entry mill.
The full saved Emry export remains unsupported: current source admission covers
31/100copies across6/75names, not all deck interactions. Preview.12 and the
portable test installation were not updated; no new publication or dev log.

Corrected the earlier native Keep diagnosis: a fixed-delay QA driver overwrote
pending clicks with inspections. A serialized atomic dispatcher now waits for
consumption and verifies original workflow/state and a matching action receipt.
Stale native actions reject before callbacks without setting a fatal game gap;
an intentional invalid-context live test confirms rejection and continued play.
The driver also binds decisions to the observed state so a Pass intended for
upkeep cannot silently be refreshed into a main-phase Pass. Native failures and
successful receipts remain distinct. Windows125percentDPI explains earlier
unscaled mouse misses; current physical tests map1280x720 captures to1024x576
logical client coordinates.

Preserved regressions: mana10, Hare22, normal duel7 (natural turn35 defeat),
counter cases23 total, Brawl mulligan12, practice import20, Brawl import25,
independent Java admission14, source mappings17 and catalogue report58. Updated
the all-catalogue constructor/report with unchanged15,840candidates and the
same one failure/two diagnostics. Report anchors were refreshed after removal
of obsolete implementation strings;86/102callbacks still inherit Forge AI.
Constructor success never broadens admission. Detailed scope, launch controls
and limits: docs/emry.md. Private receipts: research/emry-mechanics on D:.

Additional live Brawl proof: original blocker clicks assign Emry to Isamaru,
combat kills her, original Graveyard choice declines command return, Crypt is
activated during opponent combat and physically targets the local avatar.
The actual Exile134 commander prompt displays Command/Exile; Command returns
Emry preserving one prior command cast and tax2. Replay49states; native decline
of the exile choice and hand-replacement rendering remain separately unverified.
The same native game subsequently offered4U, tapped five real Islands, resolved
Emry with commandCasts2 and milled four more; its extended replay has101states.

## 2026-10-21 Paradox Engine implementation

Continuing the existing isolated native-client/Forge route; no new loader,
account or retail-install changes. Owned source identity rechecked. Installed
Forge script p/paradox_engine.txt has SpellCast / ValidActivatingPlayer You /
Battlefield trigger executing UntapAll for Permanent.YouCtrl+nonLand. Owned
Arena printing75836/title51970 has exactly trigger76767/text51972; installed
English text matches the Forge oracle. Private source/hash evidence is under
research/paradox-engine on D:. Existing tap/untap and generic explicit trigger
adapters are reused; no separate hand-coded untap rule is introduced. Admission
and normal shuffled practice fixture staged for rules and native validation.


## 2026-10-21 Broad card-family expansion (in progress)

Route: retain the isolated original Arena UI and Forge rules bridge. Public test.6 remains unchanged; no per-step release. Private experimental policy and evidence live in D:/GAMES/CodexAssets/ForgeArenaSandbox/research/broad-card-support. Existing unfinished Paradox policy is preserved. User authorizes native launches after gaming. Local profile backup: C:/Users/loula/.universal-modder/backups/arena-broad-card-support/20261021-233644.zip.

Owned database confirms intrinsic mana abilities 1001/1002/1003/1004/1005 as W/U/B/R/G in Abilities joined to formatted English text. Arena CardColor ordinals are W1/U2/B3/R4/G5; Forge mana masks are W1/U2/B4/R8/G16. Previous shared mapping only exercised W/U and conflated those conventions. Cost mapping now accepts repeated and mixed WUBRG symbols, retaining explicit gaps for hybrid/snow/X. Combat allocation removes the creature-name whitelist while retaining keyword/ordered-allocation gaps. Native mana pool entries retain the source ability identity.

Ninety research plain-creature candidates require empty native AbilityIds, no source supertypes or digital-only flag, matching Forge name/types/P/T, empty Oracle and no executable traits/keywords. Test admission is explicitly researchOnly and cannot be packaged as supported gameplay. Per-card cast/payment/resolution checks run against fixed official Forge 2.0.15 in the independent stable test root. Production admission and native asset validation remain pending.


## 2026-10-22 Plain-family verified expansion

Verified release checkpoint109 names excludes the separate Paradox draft. New90 plain creatures plus Swamp/Mountain/Forest pass656 seeded cast/payment/resolution checks,53 generic combat checks, five complete shuffled games/seeds8100-8104 and271 original native model/art checks matching source art IDs. Native callbacks cast/resolve five representative bodies; native mana callbacks activate B/R/G; inspected original Arena board shows correct art/colors/stats. Original parser replays11states. Physical DPI-aware input reaches original pointer handlers and generates blue mana. Source art diagnostic reads effective renderer property blocks, not shared MissingArt defaults. Per-family evidence scope is recorded; full16k support is unfinished. All109 scripts match supported legacy/stable distributions byte-for-byte. No new GitHub publication. Evidence/backups and limits: docs/plain-creature-family.md.


## 2026-10-22 Keyword and draw family expansion

Verified release checkpoint252 extends109 by139 source-exact keyword creatures and four fixed untargeted draw spells. All139 pass1112 real cast/payment/resolution checks,50 representative semantic checks,139 original model/art checks, six original native casts and five shuffled complete games. Original native haste and mixed combat reaches life24/opponent2 with distinct strike steps and vigilance untapped. Four draw spells pass43 timing/draw checks, four native casts/art checks and two complete games. Every252 script matches supported legacy/stable distributions. Research setup remains initial-only, bounded and research-policy gated. The original model probe now accounts for showcase-frame material names. Independent manifest checks generalize source costs/colors/types and remain separate from gameplay. Full regression and consolidated candidate validation follow; no publication or devlog. Details: docs/card-family-expansion.md.


## 2026-10-22 Consolidated252 verification checkpoint

Final production-policy checkpoint passed25 stable stages and272 engine assertions, with source mappings and all three full-game regression seeds. Legacy repeats50 keyword and43 draw/timing checks plus253 source mappings. Native parser replays50 keyword and9 draw states. All12 new samples import and preserve printing identities through the actual deck library;47 storage checks. The final normally shuffled native match/seed8200 runs with verified252 and matching deck/support metadata. Twelve actual-package update/rollback checks preserve saved fixtures; five installer checks,44 updater,22 startup,39 dependency,8 background and5 transient-read checks pass. The old update test intentionally pinned unchanged admission; expansion now requires the independent verified policy hash/exact names. Scan:92 files, zero warnings/failures. Candidate0.2.0-test.2 is979600bytes, SHA256580552573291f5a14947cd11e3030acaf57eed70a684bff44b7b06a131ee9cdd. No GitHub publication;16,118 catalogue names remain unadmitted. Private receipt: research/broad-card-support/checkpoint-252.json.


## 2026-10-22 - 0.01 alpha persistent client implementation

- Scope: dedicated launcher, persistent original Home/Decks/Packs/Play, local Practice and Brawl bot queues. Seven-hour overnight work window; no devlog.
- Recovered owned Home, navigation, Play Blade and Settings interfaces. Local adapters replace their account/event data dependencies; no retail service is connected.
- Rendered native Brawl launch through physical Play controls; 25 life, commanders and free first mulligan observed. Two further Brawl starts/returns used one native process. Match scenes are unloaded before Home is shown.
- Added a bounded per-client coordinator with independent saved-deck validation, duplicate/stale request protection, cancellation, graceful shutdown and process ownership. 33 protocol/ownership checks pass.
- Added Brawl commander presentation and local format selection. The deck persistence/printing/admission probe passes 63 checks. The fuller Isamaru bot deck completed a normal Forge game with command payments 1, 3 and 5.
- Restored shared Packs navigation and derived its private catalog from the installed enum/database; 51 sets and 13,326 printings. Native preloading must settle before showing the carousel.
- Existing startup regression: 22 checks; updater regression: 44 checks. Installed alpha acceptance and final publication are still pending.
- The separately unfinished Paradox Engine admission remains excluded. Verified release gameplay stays at the existing 252-name policy.


## 2026-10-22 - Native client alpha acceptance and persistence

- Installed candidates now use one dedicated Windows launcher and the persistent original Home, Decks, Packs and Play prefabs. The shared popup camera retains deck-list stencil; original card zoom remains functional. Native search/filter/sort APIs drive catalogue presentation, including color/land, type/rarity/mana and card-size controls.
- Installed alpha.0.2 completed a natural Brawl defeat on turn 12 through original callbacks (Forge/board life -10 and 42, winner 2), including free mulligan, commander casting, cleanup and combat. A physical result-screen Continue returned to Home and another Practice match started in the same PID 26436. Queue cancellation also returned cleanly.
- Installed alpha.0.3 demonstrated full-size native engine-failure notices and Return Home without the stale duplicate notice (PID 45876). Actual native Audio changed master volume to 60 percent, retained it after restart and preserved the legacy preference file. Normal Exit Game saved a dirty local Brawl deck's name, commander and cards. Updates retained six existing profile-file hashes.
- Headless verification: 70 deck-storage/printing/Brawl/seed checks, 7 compiled preference-store checks, 33 coordinator checks, 44 updater checks, 22 startup checks and 39 prerequisite checks passed. These are separate from the native observations above.
- Curated eight-deck starter metadata, native two-button deletion confirmation, a clear sandbox window caption and player-facing release guides are implemented for the next fresh-profile acceptance pass. All packaged corresponding source is authored; original assets and decompiled references remain private.
- Admission stays at the verified 252 main-deck names and the two verified Brawl commanders. The unrelated working-tree Paradox admission/test/deck remains excluded. No general-card or complete retail UI parity claim is made.

## 2026-10-22 — Persistent native menu input acceptance

Preserved a dedicated instance of the installed CustomUIInputModule and EventSystem with the menu lifetime. Native match scene unloading had destroyed the prior input system while leaving the restored menu visible. The menu input is inactive during a match and restored on return.

Installed acceptance 0.2.0-alpha.0.5: physical Home-to-Decks selection, original delete dialog Cancel/Confirm, native pack click/Reveal All/Continue, and a Brawl concede/Continue-to-Home/physical Decks click passed in the same process (PID 56328). Restart (PID 55648) retained the deleted starter, one opening receipt, eight collected cards and balance 99. Duplicate launcher launch retained the same receipt/PID. Native Graphics changed to 1600x900 and the menu/screens were visually inspected. Fresh test profile was archived and the original installed profile and legacy preferences restored byte-for-byte.

Authored consumer docs distinguish source-reused UI from complete parity, local Forge queues from online matchmaking, and 252 admitted main names from the searchable catalogue. Public source fixtures passed 44 updater, 22 startup, 39 prerequisites and 33 coordinator checks.

## 2026-10-22 — 0.01 alpha published and installed

Published v0.2.0-alpha.1 titled 0.01 alpha: https://github.com/kgeg401/forge-arena-sandbox/releases/tag/v0.2.0-alpha.1 . Public source commit 770fec26af7e85a9151b8835243a2aa4612732bc passed 164 hosted Windows source checks. ZIP SHA-256 6b5d5b7ad47527f7e0cd0127253871dd8bfba307facaf8a4c09b4248d676c8df; anonymous public download validated all 110 manifested files. Final package scan: 111 files, zero failures/warnings. Actual test.3 activation/rollback: 12 checks; final installer rejection preflight: 5.

The dedicated launcher fetched this public release, preserved the copied Desktop profile bytes during activation, and opened native Home. The published build cast Emry from command, milled four local cards, and returned Home through native result Continue in PID 30416. Retained all 17 prior opening receipts and 928 collected copies byte-for-byte. Original Desktop profile remains at the original lab; previous installed test fixture is archived privately. Removed only our known QA commander deck from the migrated working copy.

Updated the existing Desktop Forge Arena Sandbox shortcut to the dedicated published client, preserving the old shortcut privately. Cold Desktop launch reopened native Home in PID 71516 and retained Brawl Bot and the selected Emry deck. Client left at Home. Native display persistence separately passed real windowed 1600x900 and borderless 2560x1440 restarts; final setting restored to 1280x720 windowed. One- and ten-pack native presentations completed with single durable transactions.

Evidence: D:/GAMES/CodexAssets/ForgeArenaSandbox/research/alpha-client-20261022/final-release-acceptance.json . The release retains the verified 252-name admission policy. Unverified Paradox work was preserved in the developer checkout and excluded from shipping. No complete UI parity, general-card coverage, multiplayer or recipient-PC installation claim.


## 2026-10-22 — Deathtouch catalogue checkpoint278

Added generic human deathtouch damage allocation and verified 26 source-exact keyword-only creatures. Both supported Forge distributions pass208 cast/payment/resolution,290 per-card combat and29 cross-keyword assertions each. All26 original models/art and all26 original native casts/Resolve callbacks pass. Native damage Done submits one response with1+1 damage; both reach blockers and Nighthawk die and life becomes22/20. Two normal shuffled human/AI matchups finish. The baseline252 regression passes25 stages and272 assertions. Hash-linked promotion requires1,210 family assertions and all independent source/native gates. New audited main-deck count278; published0.01 alpha remains252, and unfinished Paradox work stays excluded. Details and remaining16,092 names: docs/deathtouch-checkpoint.md. No publication or devlog.


## 2026-10-22 — Installed278 and consolidated update preparation

The committed278-name policy passes25 stable stages and272 assertions independently of the252 baseline. Both distributions produce byte-identical rules classes. A normally shuffled native match finishes on turn14 after145 original control actions, life-9/13, without a fidelity gap. Bounded QA resumes the same session without replaying accepted inputs. Native QA now distinguishes rejected unpublished observations from failures after accepted actions; four boundary checks pass.

Package construction compiles current rules instead of copying a stale cache. The unpublished0.2.0-alpha.2 candidate passes16 source/dependency/binary checks,12 real update/rollback checks and5 negative installer checks. Six promotion-boundary checks reject incomplete/changed evidence or existing receipts. Normalized policy output matches committed bytes. Installed the private candidate locally with backup/rollback; all14 original deck records and eight other profile files remain unchanged. Added Black Green Deathtouch, verified its native import and Practice queue admission, and started an installed match through original controls. Public0.01 alpha stays unchanged at252. The remaining16,092 names are grouped by joint capability gaps; nine existing-effect candidates still require full verification. No publication or devlog.


## 2026-10-22 — Installed checkpoint acceptance

Installed private0.2.0-alpha.2 completes a naturally shuffled Practice Bot game on turn12,36 original control actions, life-8/15, no fidelity gap. No replay seed is exposed or invented. Physical result Continue returns Home; physical Decks navigation works in the same native PID27384. The root launcher returns0 and focuses that existing process. Client is left Home with the saved Black Green Deathtouch practice deck. All14 prior deck records remain identical. Native QA now re-reads the engine after observing the screen and defers disagreeing automatic-yield snapshots; accepted inputs remain ineligible for resending. Family and package counts retain their bounded scopes. Final private receipt: research/catalogue-hour-20261022/checkpoint-278.json. No GitHub publication.


## 2026-10-22 — Release admission boundary

Package creation now requires an explicit committed gameplay checkpoint; the unrelated working admission draft cannot silently supply release policy. Two boundary checks reject missing gameplay selection before creating output and preserve existing staged packages. Installed278, its saved profiles and public releases are unchanged by this build-time guard.


## 2026-10-22 — Isolated conditional card batch testing

Added source-pinned research runtime preparation, declarative input-driven spell suites, independent bounded workers, incremental reports, missing-branch accounting, exclusive runtime leases and resume/retry with immutable prior attempts. Repaired owner-thread failure exit after discovering Forge replaces the default uncaught exception handler during initialization. Final build passes33 conditional/illegal-color cases and355 assertions across nine existing-effect candidates, plus one eight-spell interaction sequence and104 assertions:34 cases,459 assertions. Existing draw/cleanup/decking regression passes15 assertions. Six real fixture boundaries and eleven schema/false-coverage guards pass. Deliberate wrong life expectation is grouped as a life failure while the next case passes; resume, retry, input-drift rejection and concurrent-lease rejection are exercised. Final-build resume performs no new engine runs.

Seven cards cover every currently authored headless branch; Life Goes On still needs actual creature-death coverage and Sphinx's Insight needs opponent-main-phase coverage. All nine retain source-equivalence, native-controls/assets and full-match admission gates. No new card admission, installation, publication or devlog. Installed278 and unrelated Paradox drafts remain unchanged. Evidence: D:/GAMES/CodexAssets/ForgeArenaSandbox/research/card-batch-20261022/guard-revision ; workflow: docs/card-batch-testing.md.


## 2026-10-22 — Five-hour catalogue engineering, first milestone

Research database reuse uses a fresh bridge classloader, game/session and IPC per case, bounded retirement and owned-process watchdogs. Initial33 cases match all95 cold/warm journal entries (UUID renaming only), measured31.876s warm versus352.248s cold. Research human controls explicitly map7 public callbacks, reject85 inherited AI callbacks and audit9 final delegators against pinned parent bytecode. Fixed basic-land payment and mandatory taps are explicit supported automation. Eight authored schema2 target/history scenarios pass153 assertions both ways and match58 records, including actual death/turn expiry for Life Goes On, opponent-main Sphinx, target legality/cancel/stale/hexproof/zone changes.

Minimum test requirements cover all16,370 source-indexed names. Independent native English/stats and Forge definitions qualify289 casting proposals, generating1,145 cases; all pass7,668 assertions. Native checks resolve289 exact original models/art,24 original cast/draw/life checks and11 original Unsummon target controls. Twenty-two oracle/evidence mutation boundaries pass. No new admission or publication; this is bounded casting/timing/stat evidence, not keyword combat or whole-catalogue support. Work continues until17:33:44UTC. Installed idle Home client was backed up and closed for zero-network primary-lab native tests; restoration is required. Evidence and running work: docs/catalogue-five-hour-engineering.md and research/catalogue-engineering-20261022/checkpoint-progress.json. Unrelated Paradox draft remains unstaged.


## 2026-10-22 R10 catalogue engineering checkpoint

- Preserve batch source bytes; reject mid-run source/input drift and incompatible resume.
- Verify 838 source-qualified combat scenarios (20,477 assertions), 89 cold-reference cases (971 exact records) and two isolated partitions (8,999 exact serial records).
- Add an explicit graveyard-order decision and the original Arena Order Cards browser. Owned protocol OrderReq/OrderResp, prompt85 and reversed response IDs were inspected locally; extracted source stays private on D:. Both authored permutations and original native callbacks pass.
- Four genuinely shuffled strict-controller games pass after surfacing the missing ordering callback. The278-card baseline passes25regression stages and272engine assertions. No new admission or publication.
- Retain source/failure/worker boundary evidence, native casting/stack checks and a per-card evidence ledger. See docs/catalogue-five-hour-engineering.md; this is an interim milestone inside the five-hour window.


## 2026-10-22 R12 catalogue engineering checkpoint

- Add explicit source-validated trample/player allocation with original native toggles/spinners and correct lethal thresholds. Default, manual5/1 and6/0 allocations pass; all66 generated cases match864 cold/warm records.
- Qualify eight fixed temporary pump spells independently from native words/costs and Forge definitions. All64 scenarios pass1,664 assertions and664 cold/warm records; all eight original native cast/target/expiration sequences pass200 checks. Map only their recovered creature-target prompt; unknown sources still stop explicitly.
- Verify blocked double strike, including real Giant Growth, in two additional scenarios (67 assertions,27 exact records).
- Consolidate2,134 distinct gameplay cases and33,936 assertions across300 indexed names. Keep297 native model/art checks,41 names' original controls and14 names' actual resolutions in32 complete shuffled games as separate stages. Seal actual game inputs, sources, journals and outcomes;22 full-game evidence boundaries pass.
- A further visible native match ends normally on turn12 after135 original actions and164 observations; Giant Growth and Infuriate resolve for both seats. No forced outcome or concession.
- Restore the exact original lab plugin/metadata/flag, archive final IPC, stop the research processes and reopen installed private0.2.0-alpha.2 at Home. All8 research and11 installed profile files remain identical. No new admission or publication; installed support remains278.
- Final evidence: research/catalogue-engineering-20261022/ledger-final and docs/catalogue-five-hour-engineering.md. Unrelated Paradox draft remains unstaged.


## 2026-10-22 two-hour catalogue delivery checkpoint

Private evidence: D:\GAMES\CodexAssets\ForgeArenaSandbox\research\catalogue-delivery-20261022-1915. Deadline21:14:57UTC.

The installed278 policy was deliberately frozen by the previous checkpoint; testing alone had delivered no new cards. The new milestone carries reviewed mechanic families through a reversible local package update. A reviewed33-card batch passed25 production stages/272 assertions and three complete regression games. Private0.2.0-alpha.3 is installed at311 names. Its new mono-green test deck was imported through the original client, accepted for practice, and completed a39-action/12-turn native game. Original journals confirm Titanic Growth6/6, Giant Growth9/9 and a later Titanic Growth6/6 on an original2/2 actor. The live QA observer initially missed transient stack states under automatic passing; a read-only journal/native-stat checker recovered the actual evidence without resending accepted actions.

Next:28 exact creature removal spells,13 fixed creature damage spells,11 signed temporary modifiers. Native prompt IDs/text are checked against the owned database and carried in an explicit manifest binding. No guessed prompt fallback was added. All215 removal cases/4287 checks,129 damage cases/3077 checks and88 signed-modifier cases/2288 checks pass on the new rules source. Fresh-process per-card reference subsets are being compared to reused-worker runs. Original model/art and cast/control checks remain separate.

Real expansion bug: GameEventCardDamaged has no combat boolean; the old bridge hardcoded Divine Arrow as its only noncombat source. The replacement uses synchronous stack-resolution state versus actual combat damage steps, with an explicit unsupported-context error. This is bounded to supported ordinary spells and creature combat, not an exhaustive replacement-effect hook. Raw installed Forge bytecode evidence is private on D:. Native removal QA also needed authoritative current zone membership: original animation objects can remain in the observed object inventory after their card transfers zones.

Complete-match QA now records legitimate fizzles separately and never credits them as successful resolutions. Six actual removal games pass with Murder/Final Death/Doom Blade/Reave Soul resolving for both seats. The evidence validator independently checks fizzle lists against actual traces;22 false-evidence mutation probes still pass. Earlier failed attempts and old-source reference results are preserved. The old cold run stopped on intentional source drift after71 passes; it is not claimed as a complete passing batch.

Profiles: installed11 files and research8 files backed up under session-backup. Research metadata/plugin originals also retained there. The unfinished Paradox Engine policy, verifier and practice deck are preserved outside committed package admission. No GitHub publication is authorized by this checkpoint.

### Installed 370-card acceptance — completed

Private0.2.0-alpha.4 adds92 names over the278 baseline:23 creatures,8 positive pumps,2 fixed draw/life,28 removal,13 fixed creature damage,11 signed modifiers and7 conditional draw/life spells. The final59 review references1846 artifacts; all rehash successfully. Current-source targeted validation totals477 cases/10301 assertions,62 fresh-process references/672 exactly matching journal records,24 complete shuffled engine games,899 original native checks and59 native model/art checks. Final production regression passed25 stages/272 engine assertions/three complete games. The compiled package passed17 checks; updater fixtures44. An actual update/rollback/reapply preserved11 profile files and restored the update preference.

Installed full native match:75 accepted gameplay actions,31 turns, local winner, final life12/-3. Original native controls and journals confirm Titanic Growth/Giant Growth stats, Bombard4 damage, and Ragefire3 damage. Its initial8-minute timeout remains recorded; resume continues the same session without replaying accepted actions. An earlier23-action loss never produced burn coverage and is preserved as a coverage shortfall, not a passing integration test. Installed read-only acceptance passes18 checks at370 names. It uses the versioned support index that card_support.load_index actually prefers; the first checker incorrectly assumed a research/runtime copy and its failure log is preserved.

Every original saved deck object, collection file, preference and prior play selection is preserved. Only Fire and Growth / Trample and Growth were seeded. The installed client is left at original Home under zero-network AppContainer. Research native process is stopped; four original plugin/metadata files and eight profile files match their backups. Full catalogue support remains unfinished. Eight counterspell candidates remain source-scan-only and are not admitted. No GitHub publishing occurred. Checkpoint: D:\GAMES\CodexAssets\ForgeArenaSandbox\research\catalogue-delivery-20261022-1915\CHECKPOINT.md.

## 2026-10-22 consolidated publication preparation

User authorizes updating local state and publishing the consolidated client/source
on the existing public GitHub repository. Production policy remains the exact
reviewed370-name bytes. The unfinished Paradox Engine policy is preserved under
ForgeBackend/draft_policies with researchOnly:true; its input/verifier are
retained as disabled development work. Planned public update0.2.0-alpha.5 keeps
the verified gameplay implementation and adds current documentation/source.
Private profiles, native dumps, owned assets and credentials are not published.

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
