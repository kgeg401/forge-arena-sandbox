# Live verification - 2026-10-21

Tested on one Windows PC, not the recipient's PC:

- Downloaded test.1 anonymously from this GitHub repository, verified its asset
  digest and internal manifest, and installed into a fresh folder.
- Opened the installed Start Sandbox shortcut and observed test.1 in its window.
- Published test.2, closed the first launcher, and reopened the same shortcut.
- Startup fetched test.2 from GitHub automatically. The window displayed test.2
  and its new banner. The active version and update receipt agreed.
- An existing local deck-library file retained the same SHA-256.
- 66 authored updater/startup checks and 5 negative installer checks passed.
- Both release packages passed publication scans with 0 failures/0 warnings.

These releases change only launcher release information, not gameplay support.
A source commit alone does not update clients: a newer prerelease containing
ForgeArenaSandbox-Windows.zip must be published.

Launcher-only setup tests installation and updates without Arena or Forge.
It does not make gameplay available. Full setup still requires compatible local
Arena files and a supported Forge distribution. The old pinned Forge snapshot
is not offered by the rolling upstream download. No successful brother-PC
install, gameplay or multiplayer test is claimed.
