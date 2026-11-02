# Keep replay history without retaining every board in RAM

The long ten-player check exposed a real memory failure. The private rendered test exhausted its 768 MiB Java limit at turn 54. A separate native-handler run at the consumer's existing 1024 MiB limit reached turn 67, then saturated that limit and timed out. The failed results and original logs remain preserved.

The bridge's completed-request map retained every full Gson response, including every historical board snapshot. At the failed larger run, the all-object histogram contained about 427 MB of Gson tree nodes alone. This was separate from drawing-thread frame time and ordinary Forge AI work.

Completed responses now live in compressed per-match files. The memory index keeps integrity hashes, while the existing request-body registry preserves conflict detection. A repeated request reloads its original response; it does not execute its action again. Missing or changed archive files fail closed. Case-sensitive IDs use distinct hash-derived filenames on Windows. The existing atomic JSON writer, UTF-8 behavior, owner-thread rules loop, and original game decisions remain intact.

## Verification

- Eleven small archive contracts cover exact typed/Unicode/null replay, caller independence, historical answers, compact index values, Windows case distinctions, missing/tampered files, invalid IDs, and the original JSON writer contract.
- A real rules sequence replays an earlier mana activation after later turns and a conflicting reuse. It receives the original answer while the current land remains untapped with zero mana. Case-distinct IDs also replay independently through the real Windows request loop.
- Twenty-four integrated effect cases pass 128 assertions with the archive change. Final phasing and payment regressions additionally exercise nested native decisions with the filename hardening.
- The same rendered ten-player scene, seed, decks, native binary, callback policy, and 768 MiB limit now complete six full table cycles to turn 61. The only runtime code change in that comparison is the response-history repair. The first 552 native game-state payloads match after excluding the ephemeral match ID. Four later states differ where the old run had AI timeouts; those differences are retained, not normalized away.
- A separate handler run completes ten table cycles to turn 101 with 165 battlefield objects at the existing consumer limit. Its point-in-time final heap reading is about 529 MiB. This is neither a peak-memory bound nor a complete-match certification.
- The final filename-hardening build is also checked through actual original-client modal choices, combat, and cleanup, using the integrated native host and final Java classes.

The rendered comparison used the first archive implementation; the final hardening changes only archive filename derivation to preserve Windows case distinctions. Its additional unit and real-request checks are recorded separately. No memory-limit increase, manual forced pass, rules simplification, or bot-deck replacement was used to obtain the successful comparison.

Small request/index metadata and disk history still grow with match length. This removes retained historical board graphs; it is not a claim of constant total resource use or that every remaining Forge AI bottleneck is fixed. The user installation and update channel remain unchanged.
