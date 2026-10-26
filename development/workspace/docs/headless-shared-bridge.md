# Shared bridge development: headless evidence

This is unreleased development work. The installed/public alpha.5 policy still
admits the same 370 names. Headless parser checks do not establish rendered UI,
art, animation, prompt layout or complete card compatibility.

## First milestone (2026-10-22)

The research controller exposes explicit partition, ordered selection, bounded
card/entity selection, modes, numeric and boolean choice contracts. Unmapped
callbacks within the audited named choice surface fail instead of selecting an
AI answer. A callback audit
distinguishes headless mappings from rendered/native acceptance.

Actual Forge scenarios cover Opt, Preordain, Consider, Anticipate, Impulse,
Strategic Planning and both You Meet in a Tavern modes. Fourteen scenarios pass
through the real C# adapter, shipped Arena parser/choice handlers, back into the
running Forge owner process and then into Arena's native game-state model.
Oracles specify initial library order and selected inputs independently, then
check actual draws, destinations, remaining order and creature stats. Random
remainder tests assert object conservation and the untouched library prefix.

Malformed, duplicate, missing, out-of-range and stale choices are rejected.
Consecutive choices acknowledge at stable controller boundaries. Native scry
and surveil partition order is preserved; native OrderRequest's reversal is
undone before returning Forge movement order. Temporary peek identities are
chooser-only and are concealed again in the native model afterward.

Modal presentation uses owned parent/child ability identifiers only when the
Forge mode descriptions and native child text match exactly after markup and
whitespace normalization. Missing/ambiguous bindings remain explicit gaps.
The complete static catalogue audit finds 264 names with such bindings. It is
not a gameplay test or an admission list.

## Reproduction and boundaries

Prepare a fresh independent research runtime with
`ForgeBackend/clone_research_runtime.py`; `--copy-resources` avoids links where
Windows junction creation is unavailable. Preparation snapshots the authored
sources and regenerates mappings even when admission policy is unchanged.
Receipts bind source, compiled classes, pinned Forge jars/scripts and mappings.

Build `ForgeBridgeProbe/ForgeBridgeProbe.csproj` with a private
`SandboxBuildRoot`, `-m:1` and `UseSharedCompilation=false`. Run
`ForgeBackend/verify_shared_choices.py` against the prepared config/policy;
its optional native-probe arguments enable the complete live adapter path.
The probe requires a research manifest, no game executable in that runtime,
and an IPC directory inside that runtime's research folder.

Private run inputs, outputs, failed attempts and native inspection stay outside
the repository under `ForgeArenaHeadless-20261022-1729`. No game or rendered
application is launched. The original installed client and user profile are
not updated, and no development changes are published automatically.

## Four-hour checkpoint: shared interfaces

The implementation now has a persistent headless native client, rather than
validating each response in a newly reset native model. Every valid action goes
through the owned Arena request handler, the local adapter, the running Forge
rules owner, and back into that same Arena model. This exercises request
retirement, consecutive questions, hidden identity lifetimes and state deltas.
It does not construct a Unity scene or a rendered chooser workflow.

Implemented research interfaces include:

| Interface | Headless scenarios | Remaining boundary |
| --- | --- | --- |
| Scry, surveil and ordered partitions | Top/bottom permutations, duplicate card names, short libraries, invalid submissions | Rendered input/layout acceptance |
| Look, reveal, constrained discard and selection | Duress, Thoughtseize, Mind Rot; private views and nonselectable revealed cards | Additional reveal/choice contexts and multiplayer visibility |
| Zone ordering | Library, graveyard and exile, using original object identities | Other destinations and their presentation bindings |
| Modes and generic ability choices | Both Tavern modes; Harvest land/nonland branches, misses and empty library | Unbound descriptions/prompts remain explicit gaps |
| Counters | Actual typed totals, add/remove events and exact counter-type selection | Aggregate-reset annotations and further counter interactions |
| Attachments | Aura resolution, equipment activation/reattachment, bounce and removal | Further player/permanent attachment contexts |
| Colors and protection | Explicit color choices and source-bound protection keyword lifetimes | Non-color protection choices |
| Temporary keywords | Source-bound grants, expiry and native modifier order | Unknown or text-modified keyword layers |
| Ability/type changes | Frogify, overlapping Auras, grant-before-loss and loss-before-grant, Aura removal | Wider copy/face/digital effects and unbound current types |
| Stack targeting | Actual counterspell targets and counter-plus-surveil resolution | More complex chained/retargeting contexts |
| Fixed payments and forced controller paths | Bound fixed land mana, sole reducer, sole replacement effect, one mandatory untargeted trigger | X, hybrid, snow, alternate costs, competing effects and optional/targeted triggers |

The last row reproduces bounded original Human-controller behavior. It does not
delegate the human seat's unresolved choices to Forge AI. Original Human code
returns a sole static/replacement option directly; mandatory untargeted triggers
use the original Human spell-play path. Forced cases are written into the
research audit. Multiple candidates are deliberately not treated as forced.

`HeadlessBridgeWorker` checks the native model after every update: life, counters,
types, colors, attachment endpoints in both directions, power/toughness, tapped
state, summoning sickness, and effective known keywords in modifier order. Its
request driver validates exact input types before touching one-shot native
handlers. Stale contexts, duplicate objects, unoffered identities, malformed
partitions, conflicting request-ID replay and integer coercion have separate
negative tests. Accepted replay returns its original receipt without executing
the rules action twice.

Harvest additionally executes the owned Core assembly's pure option translator
and prompt-button workflow selector. It verifies source-bound English strings
and native response IDs without constructing or applying the rendered workflow.
This is narrower evidence than observing those buttons on screen.

## Regression campaign

`run_headless_shared_regression.py` provides bounded `decisions`, `matrix`,
`normal` and `emry` campaigns. Each child game has a fresh rules/native process
and private IPC evidence. Prepared resources and a private research profile are
shared within the selected runtime; retail/install profiles are not used.
Compiled classes, mappings, input fixtures, test sources and native test
binaries have pinned receipts. Failed runs remain beside successful reruns.

The permutation matrix independently specifies initial library objects, selected
inputs, final draws and remaining object order. It never feeds observed
intermediate rules/native state into an expected outcome. Normally shuffled
full matches, actual London mulligans, combat damage assignments, terminal
outcomes and Emry/Brawl regressions cover interaction with existing play.
The native test bot explicitly mulligans unsuitable hands; its casting/outcome
assertions were retained when correcting the old no-mana-hand fixture failure.

Fresh runtime preparation precreates the directories enumerated by the owned
Forge `PROFILE_DIRS` before parallel initialization. Explicit profile paths are
validated inside the private root first. This avoids Forge's non-atomic
first-start directory-creation race; it is not a gameplay rules change.

## Catalogue interpretation and next acceptance gate

The complete static audit covers 16,370 Arena names: 16,331 have one candidate
Forge script and 39 remain unmatched. Scripts for 9,816 names mention one or
more of the audited interface families; 264 have exact source-text modal
bindings. These counts are planning signals, not newly supported cards. A
single card can also require an unimplemented callback, different Arena rules,
a face/token binding, a payment choice, or a combination not yet exercised.

Production admission remains 370 names. Research policies retain the legacy
`verifiedNames` field only as a private fixture allowlist; that field must not be
interpreted as consumer admission or complete fidelity. No catalogue promotion
is performed by these campaigns.

Before deploying these paths: render representative original chooser workflows,
exercise physical input, check concealment, prompts, layers, art and animation,
then run mixed-mechanic scenarios and version-bound release checks. Competing
replacements, optional/targeted or simultaneous trigger ordering, type/card-name
choices, broad payment decisions, copy/face/token semantics and Arena-only
digital rules remain separately tracked gaps. The evidence directory's final
checkpoint report identifies actual successful runs and their exact binaries.

Four cross-family tests additionally resolve Gods Willing on an enchanted
Healer's Hawk: blue/red protection with Frogify, and white/blue protection with
Pacifism. They require Forge's state-based action to remove the matching-color
Aura, preserve the other Aura, retire native attachment/type layers correctly,
and then present the original scry decision. These are specific interaction
proofs, not a substitute for the remaining mixed-mechanic coverage.

## Additional controller-inheritance gap

The final reflection audit deliberately looks beyond the named `choose`, `pay`,
`confirm` and related callbacks checked by the preparation verifier. It finds
inherited AI implementations for `getAbilityToPlay`, `getCostDecisionMaker`,
`helpPayForAssistSpell`, `acceptsDrawOffer`, `sideboard`, `cheatShuffle` and
`isAI`, plus parent convenience/identity methods requiring review. Thus the
named guard is not an exhaustive proof that the human seat can never inherit
AI behavior. `AuditResearchControllerInheritance.java` preserves that finding;
it is an inventory, not a gameplay acceptance test.

Owned bytecode confirms that the inherited cost-decision factory creates an
`AiCostDecision`, and `isAI` returns true. The AI shuffle hook has both a profile
condition and `GameRules.isAllowCheatShuffle()` condition; the owned GameRules
constructor defaults the latter to false. This source evidence does not establish
reachability or absence of other identity-dependent behavior in every card.
Before broad admission, review/guard these entry points, replace the human
identity/cost paths where appropriate, and rerun the affected normal-game and
mixed-mechanic regressions. The existing bounded fixed-payment checks and
scenario results do not close that wider obligation.
