# Verified card-family expansion

The local checkpoint admits **252 main-deck names**, up from the public test.6
baseline of 16. This adds **236 names**: 90 plain creatures, three basic lands,
139 keyword-only creatures and four fixed draw spells. Commanders and tokens
are counted separately. The unfinished Paradox Engine draft remains separate.
The remaining **16,118 catalogue names are not admitted**; the catalogue covers
16,370 source-indexed names, not release/format legality or account ownership.

This is bounded support evidence, not exhaustive card interactions or complete
Arena animation parity. No constructor, script scan or artwork check by itself
grants admission. GitHub test.6 remains unchanged until one consolidated release.

## Shared changes

- Source color ordinals and engine color masks are separate. Five-color mana,
  repeated colored costs and mixed printed costs are mapped and source-checked.
- Combat damage uses a capability instead of a creature-name whitelist. Special
  trample/deathtouch/banding and legacy ordered allocations remain explicit gaps.
- Existing Forge decisions, phase loop and original Arena card views provide
  keyword behavior and icons. No duplicate keyword rules engine was added.
- Fixed, untargeted draw spells reuse actual Forge draws and original native
  controls. Sorcery timing is enforced by Forge, including direct invalid inputs.
- Research fixtures remain separate from normal shuffled matches and cannot be
  packaged as supported gameplay. Opponent/combat setup is bounded, initial-only
  and requires a research manifest. It does not feed intermediate game state.
- The original-native asset probe reads effective renderer property blocks.
  Showcase frames can use different renderer names; all material properties are
  inspected, while an exact source artwork texture is still required.
- Independent mapping checks now cover every admitted color, cost, source
  ability and presentation type, including sorceries, in the selected runtime.

## Evidence

Plain creatures/basic lands: 656 cast/payment/resolution checks, 53 combat checks,
five full shuffled matches, 271 original model/art checks for 90 printings,
five native creature casts and original mana activation callbacks. See
[the first family](plain-creature-family.md) for its exact scope.

Keyword-only creatures: 1,112 per-card cast/payment/resolution checks for all
139 candidates. Fifty representative semantic checks cover flying, reach,
vigilance, haste, defender, flash, lifelink, first strike, double strike, menace
and hexproof. This includes illegal one-blocker menace rejection, owner-specific
hexproof targeting, fresh haste eligibility and timing/phase-order outcomes.
All 139 original native models resolve to exact source artwork. Six native casts
show the original keyword icons. Original controls performed a three-damage
fresh haste attack, then a six-creature attack on the next local turn: life24,
opponent2, distinct first/normal damage steps, vigilance untapped. The native
capture is a seeded research scenario, not a complete normal match.

Five complete shuffled keyword matches use seeds8200-8204 and five different
decks against the existing White-Lifegain opponent. Four draw spells
(Concentrate, Divination, Harmonize, Weave Fate) have exact source text, 43
draw/payment/timing checks, four native cast/resolutions with exact art, and two
complete shuffled games, seeds8300-8301. The existing Quick Study remains tested.

The prior 109-name checkpoint passed all24 broad stages and272 engine assertions.
The final252 checkpoint passed all25 broad stages and272 engine assertions,
including the new source-mapping stage and three complete-match regression seeds.
Both supported Forge runtimes pass the50 keyword and43 draw checks. The original
parser replays50 keyword states and9 draw states. All12 additional sample decks
pass native library imports and exact-printing round trips (47 total storage
checks). The actual package passes12 update/rollback checks and5 installer
preflight checks in disposable installations; user profiles are unchanged.
All252 primary Forge scripts are byte-identical in supported legacy/stable
distributions; engine compatibility is tested separately.

Private raw evidence, owned assets and decompiled research stay on D: under
`GAMES/CodexAssets/ForgeArenaSandbox/research/broad-card-support`. The
`promotion-252.json` receipt links the verified policy. Keyword evidence lives in
`keywords-source-3`; earlier qualification attempts are retained, including the
rejected hybrid-cost and type-mismatch cases. Draw evidence is in `fixed-draw`.
Native snapshots and wire journals distinguish original callbacks from physical
mouse input. No account data or original game assets are packaged.

## Remaining work

Next broad families need data-driven ability/target identity bindings, generic
human choices, additional cost forms, triggered/static/replacement effects,
counters, tokens and face/extra-zone lifecycles. AI-inherited controller choices
are not evidence that a human can play those cards. Source mismatches and the39
unmatched names remain individual blockers. Whole-catalogue gameplay, multiplayer,
alternate-printing rendering, complete presentation fidelity and recipient-PC
verification are not complete.
