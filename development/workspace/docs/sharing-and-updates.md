## Managed Forge setup (test.5, 2026-10-21)

The public test.5 installer now handles fixed official Forge 2.0.15, Java 17
JRE, .NET 8 and BepInEx automatically. Arena stays a separately installed,
owned prerequisite. The unavailable snapshot is no longer needed for a new
install; existing snapshot-based clients remain an accepted update variant.
Setup accepts an existing launcher-only destination, backs up its profile,
and retains its decks while adding independent game files and private runtimes.

Local verification completed an automatic full setup from the existing public
launcher, reached the original native board/audio with a zero-capability
AppContainer, accepted Keep and played a land through original UI callbacks.
The private Java background process stopped through its recorded IPC. The full
installation then fetched public test.5 through GitHub's normal startup update;
the existing deck and backup hashes were unchanged. 386 stable-Forge rules
checks, 39 prerequisite safety checks, 44 updater and 22 startup checks passed.
This remains one-PC validation, not recipient-PC installation or a complete
manual-match claim. The exact supported Arena build/content is still required.

Release: https://github.com/kgeg401/forge-arena-sandbox/releases/tag/v0.1.0-test.5
Private evidence is under research/packaging/github-live-test in the D: asset
root, including automatic-setup-receipt.json, installer-native-smoke.json,
last-startup-update.json and the game/launcher receipts. Historical notes below
describe the earlier candidates and their now-resolved Forge download blocker.

## Public update test (2026-10-21)

The public test channel is live at https://github.com/kgeg401/forge-arena-sandbox.
The new installer can install just the launcher when the tester has no games.
This permits testing a genuine GitHub download and automatic version update
without claiming game setup has succeeded. Starting with test.3, Setup.exe
checks Python independently using Windows' .NET Framework. Missing 64-bit
Python/Tk is installed from the pinned official Python 3.13.17 installer after
checking its published SHA-256. The bootstrap requests per-user installation,
Tcl/Tk and a per-user launcher without altering PATH, then reprobes before
opening the sandbox setup window. Existing working Python is reused.
Logs go to LOCALAPPDATA/ForgeArenaSandbox/setup-logs. Python is a separately
installed prerequisite and is not removed when deleting a sandbox folder.

The original machine's working Python/Tk and actual official installer download
were verified. Fifteen authored flow checks cover the missing runtime,
download/hash rejection, installer cancellation/errors and post-install checks.
A real clean-PC missing-Python installation remains unverified.

Startup checks the explicitly selected test prerelease channel, verifies the
asset digest and complete manifest, preserves profiles, and switches versions.
The stable bootstrap verifies the selected release before running its entry
point. Actions are serialized. Failed downloads/compatibility checks retain a
verified installed release. Rollback pauses automatic checks until resumed.

Full setup still requires the exact supported local Arena/Forge/loader files.
Forge's rolling public snapshot has moved beyond 2.0.15-SNAPSHOT-08.31; accepting
a fresh upstream build requires compatibility work. Do not call this a complete
fresh-PC playable installer. First test releases use the c14dc62 gameplay policy
and exclude the in-progress Paradox Engine admission.

See packaging/TESTER-README.md for current recipient instructions. The earlier
sections below describe the previous private candidate and historical tests.

Live result: the anonymous GitHub test.1 download installed into a fresh folder.
After publishing test.2, reopening its installed Start Sandbox shortcut fetched
the new release automatically. The window, active-version receipt and archive
digest agreed. An existing local deck file and its profile backup retained the
same hash. Both release publication scans passed with no warnings. This is a
one-PC launcher/update test, not gameplay installation on the brother's PC.
Public evidence summary: the repository's VERIFICATION.md. Private receipts are
under D:/GAMES/CodexAssets/ForgeArenaSandbox/research/packaging/github-live-test.

# Sharing the sandbox with a family tester

The intended GitHub release contains our adapter, installer/launcher, source and
small compatibility policies. Arena's executable, assemblies, card database,
art/audio, Forge's engine/resources, the loader and private accounts/profiles
stay out of the download. Each recipient supplies their own installed files.
The small unmodified Gson JSON dependency is bundled separately with its
Apache-2.0 license and source provenance.

This is an independent local sandbox against AI. Giving another person a copy
does not add multiplayer or share either person's account/collection. Local
sandbox collections and decks stay on that person's machine.

## First install

The prototype accepts exact supported Arena/Forge/loader builds, checks local
dependencies, and offers read-only preflight before creating an independent
client copy. A different build or existing destination is rejected before
modifying it. Source installs are never patched. The runtime preserves the
zero-capability AppContainer and private Forge preferences.

The first tester candidate requires Windows x64, Python 3.10+, .NET 8 x64,
Java 17, Arena, Forge and the pinned loader. Dependency setup and a graphical
installer are still future work. Setup creates Start Practice, Start Hares,
Open Decks, Check Updates, Install Update and Rollback Sandbox Windows shortcuts.
Initial prerequisite selection remains a command-line step in this developer
candidate; normal launch/update actions do not require changing execution policy.

Current first-package modes are Practice, Hares and the native local deck
browser. Full card support, multiplayer, integrated Home navigation and a pack
launcher are not part of this first package. The broader developer pack-opening
work is preserved separately. Native readiness is not proof of a manual full
game on the recipient's PC.

## Updating without losing decks

Application files are versioned separately from persistent data:

```text
Chosen sandbox directory/
  active-version.json
  versions/0.1.0-preview.2/       adapter program and corresponding source
  versions/next-version/        staged, verified update
  data/native-lab/              recipient's independent Arena copy
  data/native-lab/local-profile/ decks and collection
  data/forge-runtime/           recipient's independent Forge resources/cache
  profile-backups/              backups made before version switches
```

The updater checks a configured GitHub repository's latest stable release and
asset digest. It downloads to staging, verifies hashes and safe archive paths,
checks game/engine/loader/profile compatibility, backs up the local profile,
and atomically switches the active version. It does not overwrite that profile.
The previous application version remains available for rollback. Updating and
rollback require the sandbox to be closed.

Derived card indexes refresh when their generator code or explicit admission
policy changes. This is separate from the saved decks and collection; a new
name match cannot automatically admit a card for gameplay.

Unsupported client builds or profile migrations stop without switching versions.
Automatic Arena/Forge asset upgrades and schema migration are not implemented.
The copied client can retain its supported version independently of a later
retail update; new adapters must explicitly support that copied build.

For private repositories, the current prototype supports manually downloaded
archives. Private GitHub authentication is not implemented. No token is embedded
or requested. Public stable release checks can use the repository configured
during setup. No repository is configured or published by this work.

## Release procedure

Build locally against the owned pinned files, run engine/native checks, and use
`packaging/build_tester_package.py` to create an allowlisted adapter-only ZIP.
It includes no game libraries and rejects payloads byte-identical to the pinned
prerequisite files. Keep the original assets/private evidence outside Git.
Run the mod publication lint too. Publish only a concrete tested package after
the owner authorizes the repository/release; no upload is implied here.

GitHub Releases provide versioned downloads and release notes. The prototype's
future stable asset name is `ForgeArenaSandbox-Windows.zip`. Use a tested version
tag and preserve hashes; immutable releases can prevent replacement of a
published asset. The updater's source is `packaging/update_tester.py`.

Sources: [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases),
[release API and asset digests](https://docs.github.com/en/rest/releases/releases),
[immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases).

This documentation describes the packaging design and prototype. A passing
fixture test or local installation does not prove delivery to another person.

## Local verification and remaining work

A fresh, independent install on this PC copied 14.9 GB of owned Arena files,
plus Forge resources, and reached the original match and deck browser with
working native audio initialization. The OS launch receipt confirms an
AppContainer token with zero capabilities. The early preloader also refuses an
ordinary process token before game assemblies load.

An actual update/rollback/update sequence retained the five sample decks and
their backup byte for byte. Separate authored-fixture checks cover invalid
checksums, unsupported builds/schema, archive traversal/aliases, staging and
profile preservation. These are local tests, not a successful install on a
second person's PC or a tested internet release channel.

Original Play First and Keep controls responded to automated input during the
fresh install test. Automated hand-card input was unreliable; no full manual
game is claimed for this new install. Observation-only diagnostics were added,
without replacing native handlers. The existing developer lab's earlier
rendered-game evidence remains separate. Before calling this brother-ready,
verify manual play on the new install, then a complete install and match on his
PC. The first installer still needs a friendly prerequisite/setup screen.

The local smoke install is retained at
`D:\GAMES\CodexAssets\ForgeArenaSandbox\tester-smoke\Brother Sandbox`.
It is a working extra copy, not space reclaimed or a delivered download.
