# Forge Arena Sandbox — public test client

This download tests installation and automatic updates. It is an unfinished,
unofficial personal sandbox adapter. Multiplayer and full card support are not
implemented. No Arena executable, art, audio, card database, Forge engine,
loader, accounts or profiles are included. Gson 2.13.2 is included with its
Apache-2.0 license and source link. Adapter testing permission: LICENSE.txt.

## No games installed? Test the launcher and updates now

1. Download `ForgeArenaSandbox-Windows.zip` from test.3 or a newer test release.
   Extract the complete ZIP, then double-click **Setup.exe** (or Setup.cmd).
2. Setup checks for working 64-bit Python 3.10+ with Tcl/Tk. If missing, it
   downloads the official Python 3.13.17 Windows installer from python.org,
   verifies its published SHA-256, and installs Python with Tcl/Tk and its
   launcher for the current user. Installation progress is visible. It does not
   add Python to PATH or replace a working interpreter. After rechecking Python,
   it opens the sandbox setup window automatically. Internet is needed for a
   missing Python download; failed/cancelled installs do not continue.
3. Choose a NEW install folder outside the extracted download. Click
   **Install launcher only**. This needs no Arena, Forge, account, Java or .NET.
4. Open **Start Sandbox** in the installed folder. It checks the public test
   channel and automatically downloads newer adapter versions at startup.
   The window displays the installed version and release message.

To demonstrate an update with Python setup included, install **0.1.0-test.3**,
then open Start Sandbox after a later test release is published. Keep the
launcher closed while publishing for a clear before/after. Updates are checked
at startup, not continuously during a match. No telemetry is uploaded.

Setup.exe uses the .NET Framework included with supported Windows 10/11 PCs.
This is separate from .NET 8, which is still required for full game setup.
Python setup logs are in `%LOCALAPPDATA%/ForgeArenaSandbox/setup-logs`.
Python remains a separate installed prerequisite if you remove the sandbox.

Launcher-only means the updater/UI is installed; it is NOT a playable game.
The game buttons stay disabled until a separate full setup is completed.

## Playing: additional prerequisites and a current blocker

Full setup needs Windows x64, Python 3.10+ with Tk, .NET 8 x64, Java 17,
your own complete Arena installation, Forge and extracted BepInEx 5.4.23.5.
Use the setup window's prerequisite links and folder selectors. **Check game
files** is read-only; **Install with game files** copies into a NEW separate
folder. Allow about 15 GiB plus Forge files and a 2 GiB reserve, in addition to
the source game installation. Original installs are never patched.

Only the exact pinned files in requirements.json are accepted:
- Arena Client0.1.14517.1329972 / Unity 6000.3.14f1, including its card database.
- Forge 2.0.15-SNAPSHOT-08.31. The rolling upstream snapshot is newer;
  this old snapshot is not currently offered by that download. We still need
  a supported fresh-PC Forge distribution/build before full game setup is
  suitable for a tester with neither game installed. Installing latest Forge
  alone does NOT satisfy these checks. Do not bypass the checks.
- BepInEx 5.4.23.5 Windows x64, Java 17 and .NET 8.

After compatible full setup, Start Sandbox offers practice and the native deck
browser. All Arena game execution uses a zero-network-capability AppContainer;
the external updater alone contacts GitHub. Other Arena clients must be closed.
The package's release-info.json lists its sixteen ordinary admitted names.
Other cards may be saved in decks but cannot start an unsupported match.
Emry mechanics have local development evidence, but the full Emry list and
Paradox Engine are not admitted by these first distribution test releases.
Native readiness is not proof of a complete manual game on another PC.

## Updates, failures and rollback

The test channel is `kgeg401/forge-arena-sandbox` on GitHub. Test releases are
explicitly marked prereleases; stable releases use a separate channel.
The updater downloads only the named Windows ZIP from that repository, checks
GitHub's SHA-256 digest, all internal file hashes, archive paths, and any existing
game/profile compatibility. It backs up profiles before switching versions.
Concurrent launcher/update actions are blocked. Close the game for updates.
A failed update preserves the installed release; the launcher verifies it again.

Saved decks and collection live in `data/native-lab/local-profile`, outside
`versions/<version>`. Update/rollback does not overwrite them. Back them up.
**Rollback Sandbox** selects the retained previous adapter. Automatic updates
are paused on rollback until **Install Update** is used, so the previous version
can actually be tested. Diagnostic receipts/logs stay in the installation folder.
There is no automatic game-asset upgrade or profile-schema migration.

Uninstall: close the client, back up local-profile, then delete only your chosen
install folder. Original games/accounts remain. The network-restricted
AppContainer registration may remain after a full-game uninstall.

Developed with OpenAI Codex assistance. Dependencies: Card-Forge/Forge,
BepInEx, Python, Eclipse Temurin Java, Microsoft .NET, Google Gson.
Corresponding authored adapter source is included; no decompiled game source.
