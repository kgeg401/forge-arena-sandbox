# Headless match stability checkpoint — 2026-10-28

This work uses a fresh private Forge profile and the owned Arena rules parser
and response handlers without starting Unity. It does not change the installed
client, current match, deck collection, admission policy or public release.
Rendered prompts, animation timing and physical input remain separate checks.

## Added coverage

`ForgeBackend/verify_native_blocker_recovery.py` starts an explicit initial
combat with Boggart Brute attacking two Yoked Oxen. The expected menace
restriction, three damage and player life totals are literal independent
expectations; no intermediate combat state is injected.

For each of three branches it first rejects stale tokens, duplicate blockers,
duplicate attackers, a fractional identity and a valid-first/invalid-second
batch before any request reaches Forge. Complete actual rules state and the
rules request journal must stay unchanged. A subsequent legitimate selection
proves that those rejected inputs did not consume the original handler.

Forge then rejects a complete single-blocker menace declaration. The native
adapter must provide a new response handler for the same pending decision.
The branches correct it to two blockers, clear the assignment and take three
player damage, or concede while the callback is waiting. The first two must
return to main phase with exact damage and no gap; concession must finish
without inventing combat damage. All three branches passed in the initial run.
This did not reproduce a new gameplay defect, and it is not a claim that all
historical pauses are repaired.

## Repeatable pod campaign

`ForgeBackend/run_headless_shared_regression.py --group pod` combines blocker
recovery, split combat, player targeting, commander return/tax, mulligans and
elimination, two-player Commander/Brawl regression, and turn yield across all
three opponents. Supply the existing explicit configuration, policy, worker,
managed assemblies, empty fixture and output arguments, plus `--probe` pointing
to a built `TurnFlowProbe.dll`.

The runner rejects an unmarked runtime or one containing MTGA.exe before
starting a game. Evidence must use a fresh absolute directory outside source.
Jobs run serially with bounded owned processes and retained failure evidence.
Use `FORGE_ARENA_TEST_THREADS=2` and `DOTNET_PROCESSOR_COUNT=2` to limit CPU work;
the existing child launcher uses below-normal priority on Windows.

Reports pin the configuration, manifest, fixture, policies, Java engine classes,
Forge libraries/card scripts, native test DLLs, runner and selected test sources.
A changed input ends the campaign rather than combining incompatible results.
This evidence establishes rules/message behavior, not rendered UX or newly
supported catalogue counts.

Private evidence and exact builds:
`D:\GAMES\CodexAssets\ForgeArenaSandbox\research\headless-stability-20261028`.
The initial seven-job campaign and final pinned rerun are retained separately.

## Final results

The final fingerprinted campaign passes all seven groups (15 focused scenario
branches) in 196.532 seconds, with zero input drift. Three malformed campaign
configurations also reject before output creation or game startup. The earlier
runs and build failure from missing restore files remain in private evidence;
the fresh worker and turn probe subsequently build with zero warnings/errors.

These results add three blocker recovery branches and a reusable campaign;
the other pod/duel scenarios are regressions of existing behavior. No new
match-stall defect was reproduced, no runtime gameplay fix was installed, and
no cards were promoted based on these results. Visual retry prompts and turn
smoothness still require a later rendered check.
