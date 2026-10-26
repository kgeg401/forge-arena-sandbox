# Pinned Forge dependency

The installer downloads the unchanged official Card-Forge 2.0.16 snapshot
from 25 October 2026. Its SHA-256 is
`a9062e49e180655a68d473688436ced1c1f1fd39d3674398b756f2a4c98afdf2`.
The package lock also checks the engine JAR and card scripts after extraction.

This release mirrors the original distribution as a separate prerequisite
asset so the moving upstream daily-snapshots release cannot silently change
the installed engine. Forge is GPL-3.0-or-later; its LICENSE.txt is retained.
The corresponding source archive is supplied beside that dependency at
[the release](https://github.com/kgeg401/forge-arena-sandbox/releases/tag/v0.2.0-alpha.7).
Upstream snapshot source commit:
[434b1ef](https://github.com/Card-Forge/forge/tree/434b1efef2ec697becf801132e3a34fa54dd69de).

Existing clients accept the adapter update using their old dependency first.
On their next isolated launch, the new launcher verifies and stages Forge,
retains the previous runtime, and refreshes derived card metadata. Profiles
and decks are independent of the rules runtime. Rollback restores the retained
compatible engine. Owned Arena assets and assemblies are never included.
