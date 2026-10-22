# Consolidated 370-card publication

The user authorized publishing the current local state on 22 October 2026.
Published update version: `0.2.0-alpha.5`, a public prerelease on the existing test
channel. The production policy is exactly the locally tested 370-name policy.
This release consolidates the earlier unpublished catalogue work; old downloads
remain available for rollback. Shipping results are in the
[publication record](github-publication-0.2.0-alpha.5.md) and release notes.

Paradox Engine's unfinished policy/input are preserved under
`ForgeBackend/draft_policies/` and explicitly marked research-only. They cannot
be selected by the consumer package builder. Production source and the installed
client use the same verified policy. Owned game files, private profiles, raw
captures and native dumps remain local.

## Earlier preparation record (historical)

# Next consolidated GitHub update - local preparation

Status: development and local validation only. Do not publish each individual
change. Public test.6 remains the current release until the batch is ready.

Local candidate: `D:\GAMES\CodexAssets\ForgeArenaSandbox\packages\BatchCandidate-0.2.0-test.2.zip`
(979,600 bytes, SHA-256
`580552573291f5a14947cd11e3030acaf57eed70a684bff44b7b06a131ee9cdd`).
This is an unpublished candidate, not a new GitHub release. The earlier local
candidate is preserved. Gameplay source checkpoint: `c22d39d`.

## Included in the candidate

- Arena catalogue includes source-linked rebalanced primary entries and preserves
  A- names without merging them with paper-card identities.
- Coverage, deck storage and support diagnostics use consistent identities.
- Deck import reports every unsupported name together, with bridge-gap reasons
  when the included diagnostic index matches the release policy.
- Derived metadata refresh accounts for the identity/diagnostic helpers and index.
- Repeatable low-resource background audit and shared-mechanic regression runner.
- Per-engine/script constructor baselines and a shared-capability work queue.
- Five-color mana/cost mapping, capability-based ordinary combat allocation,
  vanilla/keyword creatures, fixed draw spells and twelve additional sample decks.

The candidate admits252 main-deck names, plus separately admitted commanders/token.
See [card-family-expansion.md](card-family-expansion.md) for the exact bounded
rules, original-client and source evidence. Unfinished Paradox Engine policy/deck
changes are excluded. Construction success does not expand card admission.

## Required before publishing

1. Finish the broad stable-Forge checkpoint and review every failure, timeout,
   fidelity gap and complete-match outcome. Preserve logs and policy/runtime hashes.
2. Run identity/support-boundary, background-cleanup and installer/update regressions.
3. Build one candidate with the matching support index; verify the whole manifest,
   approved prerequisite fingerprints and publication scan.
4. Validate candidate activation/rollback and saved-profile retention in a disposable
   installation. Do not switch the user's installed client during a gaming session.
5. Later, when native launches are available, verify deck UI/import and original
   board controls with regenerated metadata. No headless result can establish this.
6. Publish one newer GitHub prerelease only after reviewing the consolidated batch.

## Earlier sixteen-name candidate results (preserved)

- Catalogue/compatibility: 61 checks, 16,370 names, 20,420 printings, 16,331
  constructed candidates and 39 unmatched identities. No admission expansion.
- All 24 checkpoint stages passed across the original run and its linked retry,
  with 272 recorded engine assertions. All three complete-match seeds reached
  terminal engine outcomes. Original read-lock failures remain in their report.
- Support/admission boundaries: 23 checks. Source catalogue identity: 8 checks.
  Background bounds/descendant cleanup: 8 checks. Transient engine reads: 5 checks.
- Updater fixtures: 44 checks. Startup update fixtures: 22 checks.
- Final r2 candidate: 10 actual-package activation/rollback checks with saved
  fixtures preserved; 5 installer rejection checks. Publication scan: 79 files,
  zero failures and zero warnings. The packaged index loads against stable Forge
  and reports all unsupported sample-deck cards with plain-language reasons.
- No native launch, user-client activation, GitHub push or publication occurred.

Private evidence is in the stable test runtime's `research/background-runs`:
`20261021-224730-7c1dcb/report.json` and its linked successful retry
`20261021-225558-55f84b/report.json`. Final candidate roundtrip and installer
reports are under `research/packaging/candidate-roundtrip-2bfc4c11` and
`research/packaging/setup-check-c6aeaa04` in the main D: asset root.

## Expanded candidate checkpoint

- Ninety plain creatures and three basics,139 keyword-only creatures and four
  fixed draw spells expand admission16 to252. All233 new nonland printings pass
  original model/exact art checks. Fifteen representative new cards were cast
  through original native callbacks. Native keyword icons, haste, first/double
  strike, vigilance and lifelink are observed; complete animation parity is not.
- Twelve complete normally shuffled family games pass. Representative keyword
  semantics:50 checks; individual keyword casts/costs:1112; plain casts/payment:
  656; ordinary combat:53; fixed draw/timing:43.
- All252 scripts are identical in supported Forge distributions. The six adapter
  classes compile identically. Legacy runtime repeats50 keyword semantics and43
  draw/timing checks, plus every253 primary/commander source mapping.
- Original parser replays50 keyword states and9 draw states. The final ordinary
  native match uses verified252 policy, shuffled decks/seed8200, and synchronized
  deck/support metadata. Its original Keep/Pass/Plains controls pass. Existing
  installed tester/public release remain unchanged.
- Native deck-library import/printing round trips pass for all12 new samples;
  47 total storage/persistence checks. A full rendered deck-builder import is
  separate from this data-layer and original-board evidence.
- The actual test.2 archive activates and rolls back in a disposable installation:
  12 checks, preserving saved deck/collection fixtures. The old test assumed no
  gameplay expansion and rejected this intentional change; it now requires the
  independent verified policy hash and exact admitted names.
- Installer preflight:5 checks. Updater44, startup22, dependency39. Publication
  scan:92 files, zero failures/warnings. No original game files are packaged.

Private package evidence: `research/packaging/candidate-roundtrip-1a6cf875/report.json`
and `research/packaging/setup-check-cab260cc`. Family evidence is under
`research/broad-card-support`. The final252 broad regression run is
`research/packaging/forge-stable-2.0.15/isolated-tests/research/background-runs/20261022-004719-78d2fa/report.json`.
Its reviewed final result is **passed:25 stages,272 engine assertions**, including
all three complete-match regression seeds. No failed assertions or fidelity gaps
were recorded. GitHub publication, recipient-PC verification and exhaustive
whole-catalogue support remain separate.

No multiplayer, all-card playability, broader Arena-build compatibility or successful
recipient-PC installation is claimed by this work.
