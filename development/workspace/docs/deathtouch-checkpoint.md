# Deathtouch catalogue checkpoint

The audited development policy admits **278 main-deck names**, up from 252.
It adds 26 source-qualified, keyword-only deathtouch creatures. The published
**0.01 alpha remains at 252** until a consolidated update is released. The
separate unfinished Paradox Engine draft is excluded from this checkpoint.

The installed Arena catalogue has 16,370 indexed names. **16,092 remain outside
this development admission policy.** Construction, searchable catalogue entries,
artwork and basic casts alone do not establish playable support. These are
bounded verified scenarios, not exhaustive interactions or animation parity.

## What changed

The human controller now allows deathtouch in unordered creature combat damage
assignment. The player chooses the exact distribution between offered blockers;
every point must be assigned once. The lethal-damage hint is one for deathtouch.
Forge still performs actual damage, lifelink, state-based actions and deaths.
Trample, banding and legacy ordered assignment remain explicit gaps.

Source qualification is opt-in and reads owned Arena ability identities/text,
mana cost, stats and types alongside the exact Forge script. Hidden/additional
abilities, unusual costs, linked faces and digital/rebalanced variants do not
silently enter this family. The compatibility report no longer treats plain
deathtouch allocation as an unimplemented capability.

## Evidence

- All 26 candidates cast, pay and resolve in both supported Forge distributions:
  208 assertions per distribution.
- Each candidate performs actual multi-block combat: 290 assertions per
  distribution, including one damage killing a blocker and zero damage sparing
  it. Lifelink, flying/reach and vigilance combinations are included.
- Five cross-keyword scenarios pass 29 assertions per distribution: Ambush
  Viper's flash timing, Nightveil Predator's owner-specific hexproof, first
  strike preventing deathtouch retaliation, deathtouch blocking a large attacker,
  and reach/deathtouch intercepting a flyer.
- All 26 original native models resolve to the exact owned source artwork.
  All 26 also cast and resolve through original native card/button callbacks:
  130 assertions. Rendered boards were captured and inspected separately.
- The original damage browser displays Vampire Nighthawk and two reach
  blockers. Its original Done button emits exactly one native damage response,
  assigning one to each. Both blockers and Nighthawk die; the native board and
  Forge agree on life 22 versus 20. Twelve retained outcome/wire assertions pass.
- Two normally shuffled games complete, with the family controlled by the human
  adapter and by Forge's AI respectively. Fourteen outcome/phase-loop assertions
  pass. This is separate from seeded combat fixtures and original-client QA.
- The unchanged 252-name baseline passes all 25 regression stages and 272 engine
  assertions with the new controller code. Source identity/mapping checks cover
  the independent 278-name research policy and separate commander mappings.

The family evidence totals **1,210 assertions**, excluding artwork counts and
the existing baseline regression. Counts include both explicitly tested Forge
distributions; they do not represent that many unique card mechanics.

The promotion tool requires all of these gates and writes a new policy and a
hash-linked receipt. It does not publish, deploy, modify profiles, or grant
support based on a source scan. The exact verified policy is separate from the
unrelated working-tree draft.

The expanded 278-name policy separately passes the same 25 regression stages
and 272 engine assertions. A normally shuffled original-client game also
completes on turn 14 with 145 original control actions, life -9 versus 13 and
Forge's AI winning. The bounded driver was resumed in the same session after
its first time limit; accepted inputs were not repeated. This is separate from
the two headless normal games and the seeded native damage-browser scenario.

## Local client and update preparation

Private candidate `0.2.0-alpha.2` includes the verified 278-name policy and the
practice sample. The package builder now compiles the rules from current source
instead of copying a potentially stale build cache. Sixteen checks establish
source/dependency identities and exact equality to both independently tested
sets of engine classes. The actual ZIP passes 12 update/rollback checks in a
disposable client and five installer rejection checks. Six negative promotion
checks reject incomplete or changed evidence without creating a policy.

The private candidate is installed locally with a profile backup and the prior
version retained for rollback. The new sample imports through the actual native
deck library, has no match-support gaps, and starts a Practice Bot match through
the original Play controls. All 14 existing deck records remain identical. The
only intended profile changes are the added deck, its automatic backup and the
last Play selection; eight other profile files remain byte-identical.

The public GitHub download remains `0.01 alpha` / `0.2.0-alpha.1`, with 252 names.
No new public release or recipient-PC update is claimed.

Package builds now require an explicit committed gameplay checkpoint. A working
admission draft cannot silently become the release policy. Two boundary checks
confirm rejection before output creation and preservation of existing packages.

Installed acceptance also completes a naturally shuffled Practice Bot game on
turn 12, with 36 original gameplay-control actions and life -8 versus 15. The
production game does not expose a fixed replay seed; none is invented. Physical
result Continue returns Home, and a physical Decks click works afterward in
the same native process. Running the installed root launcher returns success
and focuses that same process. The client is left at Home with the sample saved.

Native QA reads Forge again after observing the original screen and waits when
their workflows disagree during automatic yields. Only errors explicitly raised
before an action was published allow a fresh observation. An accepted action
followed by a presentation timeout is never automatically resent.

Private evidence, game assets and decompiled research remain under:
`D:/GAMES/CodexAssets/ForgeArenaSandbox/research/catalogue-hour-20261022`.
The receipt is `promotion-278.json`; the policy is `verified-policy-278.json`.
No original game files or decompiled code are included in project source.

## Added names

Ambush Viper; Ankle Biter; Daggerback Basilisk; Dragon Sniper; Feral Abomination;
Gifted Aetherborn; Gilacorn; Hired Poisoner; Hullcarver; Kraul Stinger; Midnight
Assassin; Moss Viper; Needlethorn Drake; Nightveil Predator; Noxious Groodion;
Pharika's Chosen; Sedge Scorpion; Squirrelanoids; Tajuru Blightblade; Thornweald
Archer; Typhoid Rats; Ukud Cobra; Underdark Basilisk; Vampire Champion; Vampire
Nighthawk; Vampire of the Dire Moon.

The 60-card `decks/Black-Green-Deathtouch.txt` is a practice sample, not a claim
about retail format legality or the user's owned collection.

## Next broader capabilities

Trample needs both blocker allocation and player-damage routing through the
original damage browser. General spell/ability identity bindings, human modal
and zone choices, counters, replacements, additional costs and face lifecycles
remain the larger barriers to full-catalogue play. Inherited AI choices do not
count as support for the human player.
