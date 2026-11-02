# Ten-player polling and zone projection

Two measured costs in the existing bridge were reduced without changing rules,
turn delays, animation speed, or response windows.

* The per-frame presentation callbacks searched the Unity scene for GameManager.
  Keep a reference for this match and reacquire it after destruction or
  deactivation. Starting another match creates another closure. The existing
  UXEventQueue, state ID, workflow type and Applied-state checks remain intact.
* Zones scanned all physical cards once per zone. Build one ordered zone index
  for each projection instead. Do not retain it between states. Preserve stack
  order, casting cards not yet registered on the stack, retired IDs and all zone
  metadata.

## Measured native comparison

Original Unity client, 1280x720, the same normally shuffled ten-player world,
seed 7274, forty life each, real Isamaru/Emry/Selvala opponent decks and the same
original Keep, land, commander and attack callbacks. Each case reached the
third local turn after two full table cycles. Forge rules build 06 and complete
card metadata remained unchanged. Managed timings are inclusive and must not
be added together.

| Measurement | Before | Cached manager | Cached manager + zone index |
|---|---:|---:|---:|
| Mean bridge Poll, ms/frame | 3.246 | 0.688; repeat 0.638 | 0.460 |
| Mean Zones, ms/update | 12.916 | 12.916 | 0.793 |
| Mean AdoptState, ms/update | 25.436 | 25.436 | 12.904 |
| Frame p95, ms | 13.892 | 6.953 | 6.953 |
| Frame p99, ms | 41.676 | 41.676 | 27.784 |

Zones/AdoptState before-values come from the additional instrumentation on the
cached build; they isolate the second change. This is a bounded scenario,
not a guarantee of frame rate on every board or a claim that all stutter is
gone. File reading, parsing, message conversion and rare larger spikes remain.
Disabling detailed event recording alone did not remove the original spikes.
The player rail and Canvas were measured rather than presumed responsible.

## Compatibility evidence

128 offline projections from actual ten-player, double-strike, token-army and
planeswalker response captures produce deeply identical results through the
old and new frozen binaries. All zone fields and ordered identity arrays match;
the outputs have identical SHA-256
`96a7b795126cfae720ba870142859f29c4e354bbc91642f0ceb0eac9a96190e2`.
This is adapter equivalence evidence, not an independent gameplay replay.

On the optimized build, original Unity double-strike/trample controls still
show two complete combat clips and exact 3 then 1+2 damage. The next automatic
rules pass occurs 7.1726 ms after the first clip completes, never before it.
Original future-phase icon selection stops at the requested next upkeep and
draw, then expires while the next land is playable. Four original-handler
planeswalker allocation cases and Winota, Bowmasters, combined taxes and
normal Commander K'rrik cancellation regressions pass.

Frozen source/builds and raw evidence remain private under
`ForgeArenaEightHour-20261102`: `native-readiness-candidate-10`,
`native-zones-candidate-11`, `zone-parity`, `poll-details-performance-r1.json`,
`zones-performance-review-r1.json`, `strike-rendered-zones11-review.json` and
the exact per-session receipts. All completed borrowed-client sessions were
restored and independently rehashed. No user installation, update channel,
server or public release was changed.
