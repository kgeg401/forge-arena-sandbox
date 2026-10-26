# Published alpha.7 acceptance

Public release: [v0.2.0-alpha.7](https://github.com/kgeg401/forge-arena-sandbox/releases/tag/v0.2.0-alpha.7).
The Windows adapter is 1,552,843 bytes; SHA-256:
`0126ea4e5c5609535f68d80ca7842a43dab6b89023b1fe33d71c16f1cd71e049`.
GitHub reported the same digest after publication. The Forge dependency and
corresponding source archive are attached separately; their hashes are pinned.

The existing dedicated launcher checked the public test channel, downloaded
the published Windows archive, verified its digest and applied alpha.7. The
active-version and startup receipts confirmed the upgrade, then the native
persistent Home menu rendered successfully. The preferred private Forge engine
was the pinned 25 October 2026 snapshot. All pre-existing deck records were
unchanged and the new Jace starter remained a 99-card main deck plus commander.

Before publication the installed candidate opened the normal Brawl queue,
selected Jace Superfriends Brawl and rendered the normal mulligan and match.
A land was played through the original native interaction. The private runtime
upgrade retained the previous engine and backed up the profile.

Headless evidence covers 100 per-card smoke checks, 21 loyalty activations,
focused Jace/rebound/proliferate outcomes, 51 regression groups, eight pacing
modes, eight dependency-switch fixtures and 44 updater fixtures. One normally
started full match completed 30 turns / 570 commands. These are bounded checks,
not proof of every card branch or combination.

The Windows payload scan had zero failures and warnings. The public source scan
had zero failures and four deliberate warnings for historical local-path
examples in development notes/tools. No profiles, assets or game assemblies
were included. The 420-check source snapshot verification passed.
