# Forge Arena Sandbox - public test client

An unofficial, unfinished local sandbox adapter using owned Arena files and
Forge rules. Limited admitted cards; no multiplayer. No Arena assets/accounts,
Forge engine, Java, .NET or loader files are redistributed inside this ZIP.
The small Gson JSON library is included with its Apache-2.0 license and source.
Our setup downloads prerequisites directly from their official sources.

## Install

1. Install Arena separately and let it finish downloading its game content.
2. Download the Windows ZIP from test.6 or a newer test release. Extract the
   ENTIRE ZIP, then double-click **Setup.exe** (or Setup.cmd).
3. Setup reuses working 64-bit Python 3.10+ with Tcl/Tk. If missing, it downloads
   and verifies the official Python 3.13.17 installer, installs it for your
   Windows user, and opens the sandbox setup window automatically.
4. Select your Arena folder and a sandbox destination. **Check Arena** checks
   compatibility without installing anything. **Install sandbox** performs that
   check automatically and completes setup. These are the two setup actions.
   No Forge, Java, .NET or loader folders need to be supplied. Setup downloads
   and verifies the fixed official Forge 2.0.15 release, Eclipse Temurin Java 17
   JRE, Microsoft .NET 8 runtime and BepInEx 5.4.23.5, then configures the client.
5. Open **Start Sandbox** in the installed folder. Choose Start practice or Open
   decks. The launcher automatically checks this repository for newer test
   releases at startup. Close the game before updating.

Allow at least 20 GiB free, in addition to Arena's installation. Setup copies
Arena into an independent game folder and keeps Forge and private Java/.NET
runtimes there. Expect about 360 MiB of prerequisite downloads (plus Python if
missing). Installation and card indexing can take several minutes.

An existing launcher-only sandbox can be selected as the destination. Its saved
profile is backed up and retained while setup adds game files. An existing
playable sandbox must use its updater or a new destination. Unrelated existing
folders are rejected. Interrupted work is preserved; never delete saved decks
when troubleshooting an incomplete setup.

## Exact supported files

- Arena Client0.1.14517.1329972 / Unity 6000.3.14f1, including the pinned card
  database. Arena is NOT installed by this setup. A missing database means you
  must finish Arena's content download first. A different build is rejected
  before prerequisite downloads or game copying. Build support is still narrow.
- Automatic setup uses **official Forge 2.0.15** from the fixed `forge-2.0.15`
  release. This replaces the first-install dependency on an unavailable rolling
  snapshot. Existing sandboxes using 2.0.15-SNAPSHOT-08.31 remain supported;
  their engine/resources are not silently replaced during adapter updates.
- Java 17.0.20.1+1 JRE, .NET 8.0.32, BepInEx 5.4.23.5 Windows x64. The pinned
  download URLs, hashes and Forge fingerprints are in dependencies-lock.json
  and requirements.json. Portable runtimes are private to the sandbox; no PATH
  change or global Java/.NET installation is needed.

This is still a developer preview. The sixteen ordinary admitted names are in
release-info.json. Full Emry-deck support and Paradox Engine are not admitted in
these distribution test builds. Full home navigation, general card support,
pack-opening launcher and multiplayer are not implemented. Native gameplay
uses a zero-network-capability Windows AppContainer. The external updater and
prerequisite downloader contact official servers; the game does not.

## Updates, saved files and rollback

The test channel is `kgeg401/forge-arena-sandbox`. A published newer prerelease
with ForgeArenaSandbox-Windows.zip is required; pushing source alone does not
update installed clients. Startup verifies GitHub's asset SHA-256, internal file
hashes, archive paths and existing game/profile compatibility before switching.
The active release is verified again after any update failure. Actions are
serialized, profiles backed up, and older adapter versions kept for rollback.

Saved decks/collection live in `data/native-lab/local-profile`, outside
`versions/<version>`. Updates do not overwrite them. Back them up.
Rollback pauses automatic updates until **Install Update** is used. A fresh
stable-Forge install cannot roll back to an old adapter release that only
accepted the snapshot; compatibility checks stop that downgrade.
No automatic Arena/Forge asset migration or profile-schema migration is included.

## Logs, cache and removal

Python setup logs: `%LOCALAPPDATA%/ForgeArenaSandbox/setup-logs`.
Prerequisite cache and full-setup logs:
`%LOCALAPPDATA%/ForgeArenaSandbox/prerequisites`.
Install/update receipts and game logs are inside your chosen sandbox folder.
Verified download archives are cached for reuse; failed/interrupted work is
preserved for diagnosis. A successful full sandbox does not depend on that cache.

To remove: close the game, back up local-profile, and delete your sandbox folder.
That also removes its private Forge/Java/.NET copies. Python and the download
cache remain separate; original Arena and its account remain unchanged.
The Windows AppContainer registration may remain after removing a full sandbox.

Dependencies retain their licenses. Credits: Card-Forge/Forge, Eclipse Adoptium,
Microsoft .NET, BepInEx, Python Software Foundation and Google Gson. Developed
with OpenAI Codex assistance. Corresponding authored adapter source is included;
no decompiled game source or private account data is distributed. See LICENSE.txt.
