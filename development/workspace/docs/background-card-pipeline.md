# Background card-support pipeline

This work uses an independent rules-test runtime. It does not open Arena, Forge
windows, a browser, or any other game, and it does not interact with the desktop.
The runner uses one worker, below-normal Windows priority, at most two inherited
CPU affinity processors, two Java processors and a 1024 MiB Java heap. Each stage
has a timeout; a Windows job contains that stage and closes leftover descendants.
This bounds the test workers, not the memory or CPU of the user's games.

## Catalogue identity

The owned, hash-checked Arena database supplies the catalogue. Primary non-token
entries are retained. Rebalanced rows are added only when their source-counterpart
link names a primary non-token entry. Linked secondary faces are not treated as
standalone main-deck cards: face links are bidirectional and cannot determine
which side is primary.

Arena's `arena_a` sprite is preserved as the `A-` identity prefix. For example,
The One Ring and A-The One Ring are separate catalogue/rules candidates. HTML
formatting removal must not merge them. Source metadata remains distinct from
release availability, deck legality, an account's ownership, and offline assets.

The current fixed official Forge 2.0.15 audit indexes **16,370 names across
20,420 printings**, including **261 source-linked rebalanced primary printings**.
There are **16,331 unique script candidates** and **39 unmatched names**. All
16,331 candidates constructed without diagnostics in this exact engine/script
distribution. That is construction evidence, not gameplay verification.
The former three construction problems belonged to the older snapshot. The
regression checks now pin their expectations to both engine and script hashes.

## Support and deck diagnostics

The generated support index describes mapping/construction/bridge gaps for every
catalogue name. It does not contain rules text, art or game binaries. Explicit
`bridge_support.json` policy remains the sole admission authority. A matching
script, successful constructor, or a modified report cannot enable a card.
Commander-only admission is checked in its own context.

The practice/Brawl text importer now collects every unsupported name before
rejecting a deck. When a matching support index is present, it adds explanations
of the missing bridge capabilities. Missing or stale diagnostic data cannot relax
admission. Diagnostics check both engine and script hashes; an older snapshot
installation receives generic rejection rather than incorrect stable-engine
construction findings. A separate headless deck report preserves all four export sections and
reports every card, copy count and parse failure; that report does not replace
format/deck-size/color-identity validation.

`build_development_queue.py` ranks shared capabilities by catalogue impact and
lists how often each is the only detected implementation blocker. Counts overlap.
Even a card with no detected implementation blocker still needs rules, interaction,
asset and native-control evidence. These numbers are priorities, not promises of
how many cards become playable after a change.

## Repeat a background checkpoint

From the project root, run `ForgeBackend/run_background_validation.py` with:

- `--config`: the prepared independent stable-Forge test config.
- `--javac`: the installed Java 17 compiler; the game tests still run with the
  configured Java runtime, including the downloaded private JRE.
- `--policy-ref`: the verified Git checkpoint to audit. The default is the same
  sixteen-name admission checkpoint used for public test.6. It deliberately
  excludes the separate unfinished Paradox Engine changes in the working tree.

The runner recompiles the authored adapter against the actual test engine,
rebuilds the owned-card audit and deck catalogue, emits the support index, and
runs 16 shared rules regression groups plus three seeded complete matches.
Those groups cover mana/turn cleanup, spell stack, targets, color payment,
bounce, counterspells, triggers, tokens, combat, damage assignment, drawing,
discarding, mulligans, outcomes, terminal rejection, concession and deck import.
They exercise the existing admitted slice; counters, replacement effects and
other unimplemented families remain explicitly blocked.

Every checkpoint stores a unique report, policy copy, runtime config, source
hashes, bounded stage logs, engine evidence paths, assertions and failures.
Catalogue snapshots are retained. An incomplete audit stops later stages rather
than using a stale report. A dedicated file lock prevents simultaneous drivers
from sharing the same test runtime.

The completed baseline checkpoint passed all 24 stages with 272 recorded engine
assertions after replaying two complete matches affected by a transient Windows
response-file read lock. The reader now retries only bounded file reads; it never
resubmits a gameplay action. The original failed report is retained. A follow-up
report links its hash, records changed source hashes and combines the previously
passing stages with the two successful replays. All three seeds reached actual
Forge terminal outcomes. This does not imply all-card or rendered-game coverage.

Use `--retry-report` only for failed stages of a finished full checkpoint. Changed
rules-engine source, engine binary or admission policy requires a new full run.
The transient-read boundaries also have five dedicated checks.

Run `verify_catalogue_identities.py` to independently compare both generated
catalogues with a read-only SQL selection; run `verify_background_resources.py`
to exercise bounds and descendant cleanup with disposable Python processes.
`build_development_queue.py` emits the capability queue after a successful audit.

## Release boundary

Keep changes local and accumulate one larger release. A source commit or local
candidate is not a public update. The next package may include the compact
support index using the builder's `--support-index` argument, which checks exact
policy and supported Forge-script hashes. Publication still requires packaging,
update/rollback checks, game-file/secret scanning and later native/manual checks.
No new card admission is inferred from this background work.
