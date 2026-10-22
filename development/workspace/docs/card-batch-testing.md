# Card batch testing

The batch runner exercises authored scenarios through real Forge casts and
priority passes. It does not admit cards, edit the installed client or launch
Arena. Construction-only catalogue scans remain a separate, weaker check.

The first suite covers nine untargeted draw/life candidates from the pinned
catalogue work queue. It checks actual mana payment, illegal-color rejection,
no effects before resolution, original library object identities, life totals,
spell destination and hidden opponent identities. Conditional cases cover
power thresholds, same-named graveyard copies, distinct nonland mana values,
hand counts, and either graveyard reaching twenty cards. Initial fixtures seed
environments only; they do not inject intermediate effects or outcomes.

## Developer workflow

1. Author a suite with each card's required branches and independently expected
   results. A missing scenario stays listed as missing, even when other cases
   pass. Schema 2 supports explicit targets/cancellation, combat declarations,
   damage allocation, graveyard ordering, response stacks and actual history.
   Modes, searches, scry and other unmapped choices still require adapters and
   independent expectations; they must stop with a fidelity gap.
2. Run `ForgeBackend/prepare_card_batch.py` with explicit `--suite`, `--queue`,
   `--base-policy`, `--source-config`, `--javac` and a fresh `--output` folder.
   It accepts existing-effect review candidates from the pinned work queue,
   builds separate physical Forge resources and Java classes, and records
   identities. The policy is explicitly research-only. It does not review or
   declare Arena/Forge rules-text equivalence.
3. Run `ForgeBackend/run_card_batches.py` with `--config`, `--policy`,
   `--suite` and a new `--output` folder. Default cold execution gives each case
   a fresh process. `--execution warm --warm-max-cases 100` reuses only the
   initialized Forge database: every game gets fresh bridge classes, static
   state, session and IPC. Retained journals and assertions support comparison.
   Failed cases poison their worker; repeated systemic failures stop the batch.
4. Use `--resume` with the same inputs/output after interruption. Completed
   cases, including failures, are preserved. Use `--retry-failed` to retry only
   failed cases; passed cases remain untouched and previous attempts remain in
   the report. Changing source, compiled classes, dependencies or inputs requires
   a new output folder.
5. Review `RESULTS.md`, `report.json`, per-case logs and engine journals. Every
   card still needs source equivalence, original native assets/controls and
   complete shuffled-match verification before any separate admission step.

One driver owns a runtime at a time. The runner uses the same exclusive lock as
the full regression tool, two CPU cores, one Java process at a time, a 1 GiB
heap and a bounded per-case timeout. Its Windows process job stops only its own
descendants on timeout/exit. It refuses installed playable native labs and
nonresearch manifests/policies. Source, compiled classes, database, scripts,
dependencies, configuration and suite identities are pinned into every report.

`verify_card_batch_guards.py` checks false coverage and invalid suite boundaries.
`verify_card_batch_runtime.py` exercises rejected fixtures and a subsequent valid
cast through the actual independent Forge runtime. Existing draw/stack regression
tools can run against that same research configuration after the batch completes.

## Known limits

Passing all declared branches is headless evidence for that suite, not proof of
every possible interaction. Initial graveyard cards do not establish that a
creature died this turn. Life Goes On's death branch remains missing until an
actual death sequence is tested. The first suite also records a separate
unexercised Sphinx's Insight opponent-main-phase branch. No human choices may be silently
delegated to inherited AI callbacks and counted as verified interaction.

Reports and original game data remain private on D:. No GitHub release is made
by the preparer or runner.

## 2026-10-22 checkpoint

The initial full run passed 33 cases and 355 assertions across the nine cards.
A deliberately incorrect life expectation failed in the expected category, and
the following Revitalize case still passed. Resume preserved both results;
retry reran only the failure and preserved its earlier attempt. Changing an
input prevented resume without rewriting the report. An attempted concurrent
run could not acquire the runtime lock or create output. Eleven no-game guard
checks passed.

Actual invalid-fixture testing then exposed that Forge replaces the default
uncaught exception handler during initialization: its helper threads kept an
invalid startup alive. The engine now catches owner-thread failures explicitly
and exits. Six actual runtime checks passed after that fix, including rejection
under a nonresearch manifest and a valid cast after rejected fixtures. Original
pre-fix results and the failing startup log are preserved separately. The repaired
build also passes the complete 33-case, 355-assertion batch.

The mixed sequence suite passes eight distinct casts in one initialized game:
Feed the Clan, Frantic Inventory, Life Goes On, Revitalize, Ritual of Rejuvenation,
Sphinx's Insight, Sudden Insight and Union of the Third Path. Its 104 assertions
check the evolving state: Sudden Insight draws four from the earlier spells'
distinct mana values; Union gains ten from the resulting real hand. This is one
additional interaction case, giving 34 final-build cases and 459 assertions.
The suite attributes primary branch coverage to Sudden Insight and does not
grant admission to any card. Compatible casts can share a fixture to avoid
reinitializing Forge for each card.

Private evidence root:
`D:/GAMES/CodexAssets/ForgeArenaSandbox/research/card-batch-20261022`.
Final-build batch results are under `guard-revision/stable-results`.
The installed client's 278-card policy and public release are not changed.

## Scaling beyond the first suite

`build_card_test_catalogue.py` inventories minimum requirements for every
source-indexed Arena name. It does not infer ownership, retail release, format
legality or gameplay support from catalogue presence. A matching constructor
remains `constructed-not-playtested` until actual input-driven evidence exists.

`prepare_generated_card_batches.py` requalifies exact native words, costs and
stats against Forge definitions before generating cases. Its initial templates
cover fixed untargeted draw/life spells and creatures with literal stats and
known keywords but no other scripted behavior. Casting a keyword creature does
not prove its keyword. `prepare_generated_combat_batches.py` and
`prepare_generated_trample_batches.py` supply separate combat oracles.

`prepare_generated_pump_batches.py` is a separate narrow family qualifier. It
accepts only an exact native positive single-target power/toughness bonus until
end of turn, independently matching a plain Forge Pump definition. Extra
keywords, conditions, subabilities, permanent duration, multiple targets,
different target restrictions, digital/rebalanced printings and hidden abilities
are rejected. Its scenarios test both owners, actual expiration, cancellation,
hexproof ownership, underpayment, wrong colors, combat timing and a target
returned to hand by a real response before the original spell fizzles.

Expected outcomes must be authored before execution. Seed initial objects,
inputs, environment and timing only; never copy Forge's observed intermediate
effects into an allegedly independent oracle. Keep every untested branch and
unsupported interaction visible. Whole-family templates are minimum obligations,
not exhaustive Magic rules equivalence.

## Reuse and independent partitions

Compare cold and warm reports with `compare_card_batch_runs.py`. Both must use
the same authored cases, copied rules dependencies and compiled classes. The
comparison permits bijective UUID renaming only; actual IDs, fields, requests,
responses and event order remain exact. `--allow-right-superset` permits an
explicit fresh-process sample of a larger warm run without hiding differences.

`run_card_batch_shards.py` partitions complete card branches across up to four
independent runtimes. Give each worker a disjoint two-processor `--cpu-mask`.
Classes, mutable profiles, caches, locks, process jobs and IPC remain separate;
only pinned immutable resources are shared. `compare_card_batch_shards.py`
checks every child report against a serial reference. A failed executed case
must remain counted as failed, rather than disappearing into `notRun`.

Worker isolation checks cover A/B/A history, failure retirement, timeouts,
stale sessions, old request IDs and bounded lifetimes. Unknown local human
callbacks reject explicitly instead of inheriting Forge AI. The audited final
delegators are pinned to the supported engine bytecode. This contract is
distribution-specific; a different Forge build needs its own audit.

## Original client and complete games

Native assets, original controls and rules outcomes are distinct gates.
`run_native_pump_family.py`, for example, launches a fresh isolated native fixture
for each qualified pump, checks original Cancel/target/Submit/Resolve callbacks,
then observes the real buff and cleanup expiration in native objects and rendered
scenes. These are original callbacks, not evidence of physical keyboard/mouse
operation or complete animation parity. Unknown prompts still fail explicitly.

`verify_catalogue_full_matches.py` runs normally shuffled decks using explicit
test-bot input policies. It records real terminal outcomes and every required
card's actual successful resolutions by seat. A game that naturally casts no
local spells contributes no local cast coverage; it must not be fabricated into
a useful card test. Missing requested seat coverage keeps the report incomplete.
Per-game time/input bounds, runtime leases, source/dependency seals and artifact
hashes are retained. No intermediate state or outcome is injected.

`build_card_evidence_ledger.py` combines pinned scenario runs, native assets,
native controls and schema-2 complete-game reports. `--additional-proposals`
accepts separately source-qualified families with the same catalogue provenance.
Every complete game is rechecked against its actual fixture, assertions, input
journal, strict-controller states, terminal result and resolution events.
Duplicate games and reports cannot inflate credit. Narrow scenario branches and
complete-game observations remain separate from playable admission.

Only a separate reviewed promotion/package checkpoint may change the verified
policy. The batch runner, qualifiers, partitions and evidence ledger never do.
