# Large-stack bridge performance

Replace repeated stack-ability membership scans with transition-local sets.
Keep iteration over the original ordered arrays; reuse the existing prior-card
index for source lookup. No trigger is combined or removed.

Use Java's filesystem notifications to wake the sole rules owner when a request
arrives instead of waiting out each 25/40 ms polling interval. Registration
precedes game startup and the first request scan. Every wake rescans the actual
request directory; notifications never contain or authorize gameplay actions.
Timed stop checks remain. Unsupported notifications or an invalidated watch key
retain the previous timed polling. Close the watcher after reusable research
cases. Compact JSON removes indentation without changing serialization policy,
request/reply IDs, archived-reply integrity, hidden views, or decision ownership.

## Measured scenario

An explicitly seeded research battlefield has four Impassioned Orators and
Doubling Season. Actual paid Raise the Alarm and three Second Harvest casts
create 4, 12, 36 and 108 tokens. The largest actual stack has 288 life-gain
triggers. All 436 resolution passes execute individually through Forge; all
tokens remain and life ends at 452. Existing fixture bounds were not widened.
This is a stress scenario, not a normally shuffled Commander deck/game.

| Measurement | Before | After |
| --- | ---: | ---: |
| Rules-driver resolution time, 436 passes | 29.69 s | 15.84 s |
| Original Arena input-handler resolution time, headless | 67.54 s | 56.91 s |
| Serialized rules replies, rules-driver case | 131.39 MB | 78.86 MB |
| Recorded-state native conversion, 440 transitions | 3.922 s | 3.532 s |

Times sum action-to-reply measurements, including each test driver's file
handoff/read overhead. They exclude startup and rendered animation. The rules
path improves 46.7%; the original-handler path improves 15.7%. These are bounded
local measurements, not a frame-rate, internet-speed or rendered-game promise.
A separate optimized rules repeat takes 15.04 s with the same complete states.
Scheduling/JIT/file-cache variation remains.

All 441 states match across the before/after rules and original-handler runs
after removing only each match's session UUID. Complete native GRE messages
match over the captured large stack (882 messages) and six existing scenarios
(224 messages), including copies, hidden choices, replacement choices, phasing,
equipment and token combat. This is projection equivalence; it does not replace
the separate actual Forge/input-handler execution.

Ten real filesystem wake/fallback/cleanup contracts, eleven archive-integrity
contracts, 39 native input/ownership/replay contracts and 40 normal-game
startup/mulligan/land/concession checks pass. Java and managed builds pass.
The current changes do not shorten original animations, bypass presentation
readiness or skip player response/choice boundaries.

Source snapshots, frozen binaries, complete raw states/messages, JVM recording,
timings and independent comparisons are private under
`C:\Users\loula\Documents\Codex\ForgeArenaStackPerformance-20261103`.
All owned rules/handler tests exited. Only fresh task-owned runtime state was
written; saved user profiles and existing installations were not changed.

## Deployment boundary

Implemented and tested locally. No installed-client replacement or GitHub
release/update-channel promotion in this task. Rendered large-stack timing
and a real two-PC multiplayer performance test remain unmeasured.
