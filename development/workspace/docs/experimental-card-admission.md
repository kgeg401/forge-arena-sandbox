# Local experimental deck admission

The user explicitly authorizes trying the eight requested decks without their
verified-card admission requirement. The verified 370-name policy stays byte-
identical. An optional, package-bound experimental inventory enables additional
native/rules identities and commanders, each marked experimental=true and
verified=false. Admission means permission to try, not verified gameplay.

prepare_experimental_admission.py consumes an explicit deck inventory and the
owned read-only Arena database/installed Forge scripts. The current inventory
contains 342 additional names and four commanders. Jace, Multiverse Architect
is excluded because the pinned Forge lacks its script. Forty-five names lack
an installed Arena primary presentation and remain explicit hard blockers.
No stand-in cards, generated game identities or silent omissions are used.

The same inventory feeds native metadata, deck storage/selection, Python deck
validation, match coordinator and Forge admission. Singleton, deck size, colour
identity, exact object identities and runtime fidelity-gap checks remain active.
Experimental games use the existing explicit shared-controller research paths;
those paths still have incomplete choices, payments, inheritance auditing and
rendered acceptance. The shared-card research is included in this local build
as unverified development work, not promoted support.

The inventory is disabled by default when absent. Its source database, Forge
scripts and baseline policy hashes must match before use. The installer package
includes it only through the explicit --experimental-admission argument. Public
alpha.6 is unchanged. Automatic metadata invalidation includes both the helper
and inventory. Roll back to alpha.6 to remove experimental admission.

Headless evidence: three real Brawl decks reach the initial starting-player
choice on the exact installed stable Forge distribution. Python parsing preserves
all 99 main cards and the commander, blocks Jace, and continues to reject wrong
colour, duplicate nonbasic and wrong-size decks. Native selection and rendered
installed-client acceptance are checked separately; engine startup alone does
not demonstrate card effects, complete games or combos.

Private evidence: ../ForgeArenaExperimental-20261023. No GitHub publication is
requested or performed for this local experiment.

## Reported Bojuka Bog crash

The installed experimental.1 match exited after playing Bojuka Bog on turn 2.
Forge requested its mandatory targeted ETB trigger; the strict human controller
rejected all targeted triggers. This was an actual bridge gap, not a missing
Forge rule or an invalid deck. Original logs are preserved privately.

The fix admits a single mandatory targeted trigger only with a native ability
binding, lets Forge's original PlaySpellAbility/setupTargets call the explicit
human target adapter, and rejects cancellation of mandatory target choices.
Bojuka Bog's Forge trigger, Arena ability 90052, player prompt 1019 and fixed
black mana ability 1003 are checked against both pinned sources. Zero-mana
payments no longer inspect unrelated mana sources. Other optional, multiple or
unbound triggers still report a gap; this does not establish whole-deck support.

Regression evidence covers targeting either player, empty/nonempty graveyards,
illegal/canceled target rejection, exact exile destinations, tapped arrival,
subsequent spell payment, manual black mana, and the normal Match.startGame loop.
Five scenarios also pass through the original Arena target/action handlers in
one persistent headless native model per match. Rendered acceptance remains a
separate check. Fatal owner-thread failures now write engine-error.json and the
client coordinator displays its reason rather than only an unexplained exit.

Private evidence: ../ForgeArenaBogFix-20261023. Verified admission remains 370;
experimental admission remains 342. This is a local fix, not a public release.

## Chord of Calling availability crash

The next reported failure occurred in experimental.2 after Chatterfang resolved.
Snapshot enumeration called canPayCost for Chord of Calling, which called the
human convoke-payment controller. That unsupported callback escaped while
building an acknowledgment, before the player attempted to cast Chord.

Experimental action probes now isolate UnsupportedOperationException per action,
preserve the existing match-level fidelity gap, and report unavailableActions
with source identity/action/reason. They cannot open a player decision while
enumerating offers. A rejected direct cast cannot poison the match-level gap.
Real effect execution retains strict failure handling. Unknown failures are not
swallowed. Cost probes do not use the AI to answer human payment choices.

X mana requires an explicit picker; the original CostPartMana.countX is checked
because SpellAbility.isAnnouncing("X") alone misses Chord. These actions remain
unavailable until their controls exist. The native shell reports a newly seen
unavailable action once per match through the original dialog, at a priority
boundary rather than over another choice. The card's experimental admission is
unchanged; this repair does not implement convoke, improvise, waterbend or X.

Headless scenarios compare repeated snapshots for unchanged events, tapped
state and mana; reject an unsupported cast without a fatal gap; cast another
creature; and reach Chatterfang plus Chord in the normal Match.startGame loop.
The same three scenarios pass through the persistent original Arena handlers.
Private evidence: ../ForgeArenaConvokeFix-20261023. Rendered notice acceptance
and complete experimental deck games remain separate from these checks.
