# Keep large rules-response parsing off the drawing thread

The remaining ten-player polling spikes included synchronous reading and
decoding of large immutable response files. `AsyncJsonRead` moves only those
two operations onto a worker. Selection, session/request validation,
`AdoptState`, native message delivery and animation readiness remain on the
calling thread. Decision files retain their existing path.

One read belongs to one exact response path. Repeated polls retain that read;
a new response or retired decision forgets it. A late result cannot enter a
newer request. Retired failures are observed, while a current malformed
response still fails on its polling owner. Detaching a match retires the read.
Files retain the original read/write/delete sharing behavior. There are no
Unity calls, resource changes or game actions in the worker.

## Verification

`JsonReadProbe` links the actual helper source and passes eleven bounded
ownership contracts: nonblocking pending reads, one load while polling,
worker-thread execution, exact result delivery, request replacement, obsolete
fault isolation, same-path invalidation and current parse-failure propagation.
Build it with the usual explicit `SandboxBuildRoot` and `ArenaManagedDir`,
then run the resulting DLL directly.

The frozen candidate 12 passes all 24 effect scenarios and ten payment groups,
including nested choices, real cancellation, mana recovery, escape and
sacrifice payments. A new original-handler case casts Giant Growth after the
first-strike hit and applies its power increase only to regular damage.

Actual original Unity repeats the normally shuffled ten-player scenario with
the same seed, decks, forty life and original controls. Both runs finish two
full table cycles. Mean bridge Poll is 0.268 and 0.269 ms/frame, compared with
0.460 after the earlier zone optimization and 3.246 before either optimization.
Frame p99 is 20.839 and 27.783 ms; the original baseline was 41.676 ms.
These bounded measurements establish improvement in main-thread work, not
uniform frame times, lower total CPU use, or complete-match reliability.
Rare larger spikes remain. The diagnostic observer excludes worker IO from
main-thread method timings and does not invoke Unity APIs on worker threads.

The rendered first-strike response retains the playable instant window after
the first original clip, accepts the original card and target callbacks, then
shows the increased second impact. First clip completion:
11:02:25.5446274 UTC; actual outgoing user Cast response:
11:02:32.4588579 UTC; regular clip start: 11:02:39.5416262 UTC.
The two real damage amounts are one and four, with no spill to the player.
`native_response_timeline.py` rejects early/late or duplicate casting,
wrong spells, missing completions and unchanged second damage.

The initial renderer report looked for this human cast in the automatic-pass
log. Its failure remains intact. A separately labeled review of the same
immutable capture uses the actual outgoing GRE Cast response and passes;
this is a reader correction, not a gameplay repair.

New lifelink/deathtouch controls also pass through original handlers: two
blockers and the attacker die, lifelink gains the actual two damage despite
the source dying, and Cruel Celebrant's later mandatory drain resolves with
no generic confirmation. These are bounded cases, not every combat interaction.

Private source/build/evidence: `ForgeArenaEightHour-20261102`, candidate 12,
`async-headless-before-native.json`, the two async performance reviews,
`first-strike-response-rendered-review-r2.json` and `async-reader-probe-02`.
Borrowed client state was independently restored. No installed client,
profile, server, public repository or update channel was changed.
# Additional rendered combat check

The integrated client also completed the original multi-block damage browser with Vampire Nighthawk against Giant Spider and Mammoth Spider. Each blocker requires one deathtouch damage; all three combatants die. The actual native combat clip contains the two exact impacts, lifelink raises life 20→22 despite the source dying, and Cruel Celebrant's subsequent mandatory trigger settles at 23/19 with no generic confirmation. This is a bounded real-client sequence, not a complete-game certification.
