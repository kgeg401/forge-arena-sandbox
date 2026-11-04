# Cancellable large-stack resolution

The faster local resolution path is implemented. **A universal 30-second limit is not achieved.** The paired 304-trigger headless scenario improved from 273.76 seconds to 36.31 seconds. The original rendered 40–44-second measurements used a global clock override, which has now been removed following user feedback. They are retained as historical measurements, not evidence of normal animation pacing.

## Behavior

- After an explicit native resolve/yield preference, a local stack with at least 64 objects enters accelerated playback. This also applies to local AI pods and Horde; the new fast path is disabled for network multiplayer.
- Forge still executes every real priority pass, cost, replacement and effect. Only unused action-availability forecasts are deferred during that yield. A normal snapshot restores current legal actions without resolving another object.
- The original blue secondary Cancel button stops further automatic submissions. Already executed effects and a bounded window of up to four queued native updates finish presenting; cancellation does not undo them. Resolve can resume the stack.
- Required choices, Full Control and the end of the explicit yield stop acceleration. Resolve-mine acceleration stops at an opponent-controlled object, even when ordinary no-action progression can continue.
- The sandbox never changes Unity's global time scale. Arena retains its own repeated-resolution pacing, card movements, effects, avatars and other animation clocks. The backend forecasting, immutable snapshot, asynchronous read and bounded lookahead optimizations remain active.

## Implementation

Single-player acknowledgements, decision publication and `state.json` reuse one immutable controller-boundary snapshot. Historical request replay still returns its original answer without republishing that historical state as current. Multiplayer retains separate viewer projections.

The adapter starts reading the exact immutable response in the background while Forge calculates. Retiring a request cancels its publication waiter; no gameplay request is retried. Native validation and state adoption stay on their owning thread.

During an explicit large-stack yield, the adapter overlaps the next rules request with assembly of the current native update, within a four-state presentation window. Every state and effect annotation remains emitted in order. Native diffs omit only exactly unchanged card objects; changed objects, zones, player state and annotations remain present. Duplicate object identities fall back to full updates.

Card projections reuse identical input only while instance mappings are unchanged and no chooser is active. Cached projections remain detached from output containers, and their source references advance to the current snapshot, avoiding retention of historical complete views. Forge's rules data is not cached across effects.

## Evidence

The stress scenario uses actual paid casts through original Arena handlers: five Dockside Extortionists, Second Harvest and Secure the Wastes for X=19. Doubling Season and Parallel Lives produce 216 Treasures and 76 Soldiers. Four Impassioned Orators produce 304 real triggers. Goldspan Dragon, Maskwood Nexus and a remaining Cyclonic Rift exercise the costly mana-availability case. The declared initial position is a research fixture, not a reconstructed full match.

| Check | Result |
| --- | --- |
| Previous source, manual original-handler passes, all 304 triggers | 273.76 s; life 344; 292 tokens |
| Candidate, explicitly yielded original-handler path, all 304 triggers | 36.31 s; life 344; 292 tokens |
| Earlier native Unity presentation at 960×540, with the superseded global override | about 40–44 s; same final life and objects |
| Rendered original Cancel callback, pause, original Resolve callback, completion | Passed; stopped at 235 remaining, fresh Cyclonic Rift offer, time scale 1; then all 304 finished at life 344 |
| Full rules comparison | All 305 burst boundaries match except session identity and deliberately deferred action forecasts |
| Eager final state | Every field, including restored action offers, matches except session identity |
| Original native parser comparison | All 345 updates match for recorded card identity/state, counters, damage, deletions and phase records |

Offline replay through the original parser qualified the event differences: 448 additional `CardChangedEvent.Actions` notifications and two additional hypothetical-action notifications clear and restore availability forecasts. No other card-property event counts differ. The original physical rules states and actual effect-event histories match throughout.

Additional checks passed:

- Cancel/resume, rejected foreign cancellation, stable remaining stack and restored instant availability.
- An optional confirmation reached **after acceleration was already active**, retaining the unanswered real choice.
- A mixed 416-trigger stack: 208 local Soul Warden triggers resolve, then resolve-mine acceleration stops with 208 opponent triggers remaining.
- Eleven malformed/foreign yield-request checks, including strict boolean/policy handling and a snapshot that restores actions without passing priority.
- Three real zero-cost/Thalia cases: free, unaffordable taxed, and actually paid taxed Lotus Petal.
- Twenty-two native cast-availability checks; eight human-payment regression groups covering sacrifice, automatic payment, Phyrexian life, loyalty, mana recovery/combinations and zero-cost discard/sacrifice.
- Historical request replay and a naturally shuffled normal match: paid casts, native combat and an actual turn-seven win after 73 inputs.
- Existing mana-loop regression; 15 asynchronous-read checks and 16 playback ownership/pause/restoration checks.
- Both reviewed Arena assembly variants compile. The rendered checks use the current variant; this is not a new full-catalogue or internet-multiplayer validation claim.

Private evidence is retained under `ForgeArenaLargeStack-20261104`, including `full-equivalence.json`, the property-level wire replays and `rendered-r11/cancel-proof.json`. Earlier failures and a card-reference transport experiment are retained separately. That transport experiment did not improve elapsed time and is excluded from this change.

## Normal-clock correction

The 16× `Time.timeScale` override and its now-obsolete ownership probe were removed. No replacement global, animator or spline speed override was introduced. The installed game's `ResolutionEventTranslator` already reduces the waits for repeated resolutions; that native behavior is retained.

The same paid original-handler 304-trigger setup and seed completed in the actual Unity client at 1280×720 with time scale 1 throughout all 322 recorded samples. Its complete final state equals the prior demo's final state except for the session identifier: zero remaining triggers, 344 life and all objects/effect history preserved. The board-ready observation lasted 40.31 seconds, with 294 triggers remaining at the first sample; this excludes setup/loading and is not a total 304-trigger timing or a retail Arena benchmark. The rendered take and independent comparison are retained under `ForgeArenaStackPacing-20261104`.

Both supported assembly variants compile without warnings. The correction changes presentation-clock ownership only; existing rules/priority/choice/cancellation safeguards are unchanged.

## Limits and deployment

The captured user's match peaked at 267 abilities; 77 observed automatic single-object reductions took 220.64 seconds. Response-file/wire timestamps placed most of that time before the backend reply. Its shuffle seed was not recorded, so the new stress fixture is representative rather than a lossless replay of that match.

The 30-second rendered target remains open. Human decisions, opponent responses and nonterminating loops cannot have an unconditional completion deadline. Further work should measure native response decoding/presentation costs, rather than skip effects or repeatedly tune animation speeds.

The original performance checkpoint did not restart the user's client. The faster-stack package was subsequently installed locally by request; the normal-clock correction is a separate change. No public release or updater promotion is implied. Both private validation passes restored and independently checked their own original files and ACL before handoff.
