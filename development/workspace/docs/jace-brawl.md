# Jace Superfriends Brawl

The saved Arena Brawl list is `decks/Brawl-Jace-Superfriends.txt`: one Jace,
Multiverse Architect commander plus 99 cards. The starter menu labels it
**Jace Superfriends Brawl**. The sandbox starts at 25 life and uses Forge's
Brawl variant, native command zone and normal commander costs.

Forge 2.0.15 predates the upstream Jace script. The release lock pins the
25 October 2026 2.0.16 snapshot and checks its archive, JAR and card scripts.
The upstream source commit and corresponding source archive are documented
in `packaging/public-docs/FORGE-DEPENDENCY.md`.

## Verification

`verify_jace_brawl.py` accepts `--config`, `--worker`, `--managed`, `--fixture`,
and a fresh `--output` directory. It exercises actual owned Arena handlers
against the isolated research-only Forge runtime. Outcomes cover draw/bottom,
creature/planeswalker/no-hit reveal, tax pay/decline with planeswalker combat,
Narset rebound through next upkeep, and Ichormoon granted proliferate.

`verify_deck_smoke.py` additionally accepts `--deck`; it plays or casts each
card and resolves its stack, then uses one available loyalty ability for each
planeswalker. These are valid artificial fixtures, not exhaustive rules tests.
`verify_brawl_deck_match.py` starts the exact shuffled 100-card list normally
and runs a bounded explicit test policy. It does not rate deck strength.
`verify_turn_flow.py` separately protects automatic pacing and response windows.

The source projector and native binding builder retain source identities and
fail on ambiguous mappings. The public release includes authored integration
metadata, not a card database dump, projection dump, assets or game assemblies.
Experimental admission remains distinct from the 370-name verified baseline.

## Updating

Existing users reopen the installed dedicated launcher. The old updater accepts
the adapter package before any dependency change. The new launcher stages and
verifies the preferred Forge runtime, retains the old tree, and refreshes only
derived metadata. Profiles and saved decks are retained. Fresh installations
use the same pinned dependency. Compatible owned Arena files remain necessary.
