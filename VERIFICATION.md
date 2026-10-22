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


## Python bootstrap - test.3

Fifteen authored flow checks passed for runtime reuse, missing runtime, rejected downloads, installer cancellation/errors and post-install probing. The actual official Python installer was downloaded and matched the published SHA-256; it was not executed on this machine because a working runtime exists. The packaged Setup.exe reused that runtime and opened the real setup window. A full missing-Python installation on a clean Windows PC remains unverified.

## Managed Forge setup - test.5

A launcher-only installation was completed on this Windows PC using separately
installed, owned Arena files. Setup downloaded and verified official Forge
2.0.15, Eclipse Temurin Java 17 JRE, Microsoft .NET 8 and BepInEx archives,
then configured a full independent sandbox and private runtimes. The existing
saved deck file and its backup retained their original hashes.

The installed client reached the original Arena board, rendered its cards and
audio, accepted the original Keep control, and played a land through the
original native card callback. Its OS launch receipt confirmed an AppContainer
with zero network capabilities. The actual private Forge background process
was also stopped through identity-checked IPC after the game closed.

Additional evidence: a complete normal rules match (7 checks), Hare tokens
(22), Emry mechanics (251), and Emry Brawl (106) passed against official Forge
2.0.15 using the downloaded Java JRE. Adapter bytecode compiled against the
snapshot and stable release was identical. The 39 prerequisite checks include
safe downloads/extraction, wrong-build rejection, launcher completion with
profile retention, and private Java cleanup. The 44 updater and 22 startup
checks still pass. Publication scans report no failures or warnings.

This is one-PC validation, not a successful installation on the recipient's PC.
Arena remains separate and must match the explicitly supported build. Full card
support, a complete manual game and multiplayer are not claimed. Test.4 was an
unpublished installation candidate; test.5 contains the final updater handling
for private Java. No Arena files or Forge binaries are included in the release
ZIP: Forge and runtimes are fetched from pinned official downloads by setup.
