# Planeswalker and Battle combat checkpoint

Local development only; no installed-client update or release.

## Recovered contracts

The pinned Forge jar is SHA-256 `82083a2e52ff04f22e518f705b1a1fcac877a1ee0fa25db4e4fb208bf6a7295a`.
Its combat controller callback supplies the effective defender. A null key in
the returned card/damage map assigns damage to that defender, which can be a
player, planeswalker, or Battle. Re-querying the original attack target is
incorrect when Forge substitutes a player for trample over planeswalkers.
Use Forge's own excess-damage calculation for recipient lethal values.

The pinned `CardDamaged` event is emitted only for creatures. Loyalty/defense
loss therefore did not provide an actual damage event to Arena's animation
parser. Counter loss cannot reconstruct the exact amount: six damage can remove
only four existing loyalty counters, and paying loyalty is not damage.

`PresentedGame` observes the original post-prevention damage-history callback,
after calling its base implementation. It adds presentation events only for
noncreature cards; Forge continues to own prevention, damage, counters, triggers,
history, and state-based actions. The original Match factory creates exactly the
same Game constructor. No Forge jar patch or alternate rules implementation is
used. Noncreature damage sets Arena's `markDamage` flag to false: the impact
animates without adding creature-style marked damage to a planeswalker or Battle.

## Verified sequences

- Original-handler unblocked six damage to a four-loyalty Jace: one exact
  six-damage event, four loyalty removed, no player damage.
- Blocked trampler: two damage to Bear and four to Jace; both die, attacker
  survives. Manual three/three leaves Jace at one loyalty; six/zero leaves Jace
  at four. Original parser events have exact amounts, no duplicate impacts and
  no creature-style marked damage on Jace.
- Real Lightning Bolt to Jace gives one direct three-damage event and one
  remaining loyalty. An actual shield prevents it and consumes the shield;
  no damage event is fabricated. A real Jace loyalty activation likewise does
  not fabricate an impact.
- A normally cast Invasion of Ikoria receives its real protector, searches a
  creature, is attacked by a blocked eight-power trampler, receives six damage,
  and casts its actual Zilortha back face. Thirteen checks pass through original
  Arena handlers; the protecting player's life remains unchanged.
- Winota/Historian combat, Bowmasters damage, simultaneous tax triggers, and a
  normal shuffled Commander K'rrik cast/cancel pass against the integrated build.
- Existing ordinary and real Phyresis infect combat controls already matched
  Forge's native model. No speculative infect repair was made.

Actual original Unity before/after uses the same scene and original attacker,
target, damage-allocation and Done callbacks. A private read-only observer finds
only the blocker hit in the old CombatFrame; the corrected frame contains the
blocker hit and the exact four-damage planeswalker hit. Original manual spinners
also assign all six to the Bear with no planeswalker hit. Native clip timing was
not changed. Measured p95 was about 6.95 ms in these bounded scenes; this is not
a performance repair or a large-board performance claim.

## Evidence and limits

Private evidence: `C:\Users\loula\Documents\Codex\ForgeArenaEightHour-20261102`.
Rules `java-build-06`, native `native-combat-candidate-07`, `quarries-observed1-A`,
`noncreature-observed1-B`, `noncreature-loyalty2-B`, `battle-blocked1-A.json`,
`animation-card-regressions1-A`, `pw-baseline-current.json`,
`pw-candidate-current.json`, and `pw-candidate-manual6-current.json`.
All borrowed original-renderer sessions restore 35 mutable groups and four
immutable asset hashes and are independently checked.

Trample-over-planeswalker special variants, all Battle cards, all prevention
combinations, simultaneous attackers with shared recipients, large late-game
queues, complete games, and full animation parity are not certified here.
Initial zones are test fixtures; resolution and original callbacks are real.
One early renderer assertion expected marked damage to persist past cleanup;
its raw evidence instead shows correct two damage followed by cleanup. That test
expectation was corrected, and the original failure is preserved.
