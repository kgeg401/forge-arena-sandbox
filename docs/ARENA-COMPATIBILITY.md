# Supported Arena installations

Alpha 15.5 supports both owned Windows Arena builds:

- **Client0.1.14589.1332174**: standalone assets tested in native play. The Steam executable is separately pinned from the supplied recipient report; all eight checked libraries/database files are identical. Steam installation admission is regression-tested, but launching that executable on the recipient PC remains to be confirmed.
- **Client0.1.14517.1329972**: the older assets retained by existing sandbox installs.

Fresh setup recognizes either complete fingerprint. Existing sandbox users keep
their separate game copy and update the authored client normally. Official Arena
updates do not modify that separate copy. Both friends should use the same custom
client release; the two tested Arena asset versions can play together.

This is an adapter port, not an option to skip validation. Unknown builds,
modified files, incomplete downloads and mixed game/database versions remain
blocked. A future Arena patch needs another compatibility check.

The adapter selects the original localization loader for each build, preserves
the exact saved paper printing IDs when Arena adds a real printing, uses the
matching database and reviewed choice bindings, and validates the native pack
collation source. Multiplayer accepts a reviewed ABI family only after matching
the complete game fingerprint and exact supported card/keyword/type mappings.

Verification includes both native Home screens; Decks and the shared library;
an ordinary current-build bot game through turn 7 with casting, combat and damage;
and two native old/current clients through public HTTPS, real saved Commander
decks, keeps, land plays, both commander casts, combat and reciprocal life totals.
Both returned Home. Installer, update/rollback and unknown/mixed-build rejection
checks are recorded with the release. This does not certify every card, every
advanced choice, a complete multiplayer game, or two different households.

For **“Arena build differs from the tested client”**, use this release's complete
Windows ZIP and finish the official Arena content download before checking it.
Do not combine files from different Arena versions. Your saved sandbox decks and
collection remain separate from official Arena accounts and from the game copy.
