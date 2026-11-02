# MTG client development checkpoint — 2 November 2026

Requested work window: 05:41:40–13:41:40 UTC. The first two hours covered the Moxfield card pool; the remaining six covered original-client combat, animation, turn flow, and performance. This is local development work, with no user installation or GitHub publication.

## Card pool and effects

The 20 most-viewed public Moxfield Commander lists contained 937 distinct names. Of these, 634 matched the installed Arena catalogue and 303 were excluded by the Arena-only scope. All 634 already had primary admissions; this was not 634 new additions or 634 successful gameplay certifications.

Corrected original modal bindings for Oltec Matterweaver, Dawnbringer Cleric, Hullbreaker Horror, and Plundering Barbarian. Corrected K'rrik's mixed mana/life availability, cancellation, and deferred life charges. The integrated focused suite covers 24 scenarios and 128 assertions, with separate payment and shared-effect regressions. Original rendered modal selection and K'rrik cancellation/retry were exercised.

## Turn flow, combat, and original presentation

- Phase stops now apply to their requested step and side. Future stops no longer pause unrelated main phases. Set/clear and transient expiry are checked through the original phase ladder.
- Planeswalker and Battle trample use the actual Forge defender and damage allocation. Original noncreature impact events no longer disappear. Real blocked Battle combat, defeat, search, and back-face casting were exercised in the original client.
- First/double strike, a real instant response between damage steps, deathtouch multi-block allocation, lifelink despite the source dying, and a subsequent mandatory death trigger were checked through original handlers and rendered controls. Genuine responses remain available; mandatory triggers do not acquire a generic confirmation.
- Teferi's Protection retains physical identities through phasing and next untap. Tokens, counters, equipment, and targeted indirect phasing are covered. The original phase-out/return visuals are used.
- Akroma's Will's compound protection no longer stops presentation. Its single modes and commander-both mode work through native handlers, original modal art, two combat clips, lifelink, and expiry. Heroic Intervention's indestructible combat and cleanup were also rendered.

See [phasing](phasing-2026-11-02.md), [combat protection](combat-protection-2026-11-02.md), [non-player combat](nonplayer-combat-2026-11-02.md), and [response handling](async-responses-2026-11-02.md) for the bounded evidence and limitations.

## Larger tables

Cached match-manager lookup, one-pass zone indexing, and background parsing of immutable responses reduce drawing-thread work. The original two-cycle ten-player comparison improved frame p99 from about 42 ms to about 21–28 ms in the measured runs. Total CPU reduction and elimination of all rare spikes are not claimed.

Longer testing then exposed retained historical board responses exhausting Java memory. The response archive repair preserves retries while moving those snapshots out of RAM. A controlled original-client run now completes six table cycles at the same memory limit; a separate native-handler run completes 100 turns. Both use real saved opponent decks. Neither is a completed match. See [the memory investigation](response-memory-2026-11-02.md).

## Boundaries and remaining work

The 634-card pool is not individually verified. Full catalogue interaction coverage, complete-match endurance, every protection/phasing variant, and full visual parity remain open. Native assets and private reverse-engineering extracts are not source-release content.

The tested working tree retains the user's earlier recovery edits separately from this pass's local commits. Private test sources, binaries, hashes, original failures, and captures remain preserved. The installed client, personal profiles, and unrelated shared server are preserved.

## Final checks and cleanup

A fresh, unpublished adapter package passed 23 source/dependency/binary checks, including exact equality with all 14 tested Java classes. Its actual packaged scripts and sanitized metadata reconstructed the same 1,939 presentation objects and 1,791 primary admissions. Those are preserved inventory counts, not new gameplay certifications. The setup program was not installed or published, and the update channel was not changed.

Thirteen research-worker checks also preserve fresh game/session/cache isolation, aborted-choice recovery, deadline handling, and worker retirement with the new nested archive class. Seven existing recovery-handoff guards still pass; this does not establish lossless recovery after a rules-process exit.

The final read-only frame study completed two more original ten-player cycles with screenshots disabled. Rare long frames remain: only one of fourteen frames over 50 ms coincided with a recorded collection in that sample. This leaves the cause open; it does not justify changing native animation speeds or garbage-collector settings.

All owned game/rules tests are closed. Independent hashes verify restoration of the 12 original private-runtime groups and 35 borrowed renderer groups, four immutable renderer assets, and the 165 manifest-listed files of the installed rail.7 package. Earlier recovery source remains byte-preserved and separate. The private checkpoint contains the restoration and process receipts.
