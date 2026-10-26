# Forge Arena Sandbox

An unofficial local Magic sandbox with Arena's installed presentation and Forge
running the rules. **Windows x64. Experimental. No multiplayer.**

## Install once

1. Install MTG Arena separately and let it finish downloading its game content.
2. Download **ForgeArenaSandbox-Windows.zip** from the current Windows GitHub
   release. Extract the entire ZIP and run **Setup.exe**.
3. Choose the Arena folder and a separate sandbox destination. **Check Arena**
   checks compatibility. **Install sandbox** checks and completes installation.
4. Open **Forge Arena Sandbox** in the installed folder, or run
   **ForgeArenaSandbox.exe**. This is the client launcher.

Setup installs the pinned Forge 2.0.16 snapshot from 25 October 2026, private Java 17 and .NET 8
runtimes, and the loader. If suitable Python is missing, Setup.exe installs the
pinned official Python build first. You do not need to install Forge yourself.
Arena files stay on your computer and are copied into an independent sandbox.
Setup reports the space required before installation.

Only the tested Arena build is accepted: **Client0.1.14517.1329972 / Unity
6000.3.14f1**, including its matching downloaded card database and assemblies.
A different build is rejected rather than changing your retail installation.

## Play

- **Home > Play > Play:** choose Practice Bot, select a valid local deck, then
  click Play. Forge controls the bot and all supported rules.
- **Home > Play > Brawl:** choose Brawl Bot and a Brawl deck. This sandbox uses
  99 main cards plus one commander, singleton except basics, color identity,
  25 life, a free first mulligan, command-zone returns and commander tax.
- **Decks:** create, import Arena deck text, edit, duplicate, export or delete
  local decks. Fresh profiles receive recommended starters. Choose Practice or Brawl when creating a deck. Click the deck
  header to change its local format. Brawl uses the native commander slot.
  Original search, color/land, type, rarity, mana and card-size controls are connected.
  Local deck changes also save on a normal client exit.
- The original Graphics and Audio screens control local settings. Window size
  and fullscreen choice reopen from the saved profile, along with audio preferences.
- **Packs:** open local sandbox packs using the original carousel, reveal
  animations and card presentation. New profiles receive 100 packs for each
  supported catalog set. Pack balances and collected cards persist locally.
- Use the original in-match Options menu to concede. Continue from the result
  screen returns to Home. Another match does not require restarting the client.
- Opening the launcher again focuses the existing client instead of starting
  a second game.

There is no online matchmaking: both queues create a **local Forge bot match**.
The Home menu, navigation, Play panel, deck widgets, pack chamber and game board
reuse installed Arena assets. Local navigation and queue data replace the online
services. Advertising, store/account controls and online reward panels are
omitted. This is not a claim of complete retail UI or behavior parity.

## Current limits

**Only explicitly verified main-deck names are admitted**, plus separately verified commanders
and tokens. The current count and exact names are generated in
[SUPPORTED-CARDS.md](docs/SUPPORTED-CARDS.md) and `release-info.json`. Most Arena cards are still
unverified for this bridge and cannot enter a match, even though they can be
browsed, opened or saved in a deck. A warning explains what blocks each deck.

Verified Brawl commanders: **Isamaru, Hound of Konda** and **Emry, Lurker of the
Loch**. Included starter lists use admitted cards. This does not enable every
Emry deck, Paradox Engine, every commander, or retail format banlists.

Packs use custom sandbox collation: five commons, two uncommons and one
rare/mythic, with a one-in-eight mythic choice when available. Retail bonus
sheets, duplicate protection, wildcard rewards and account collection syncing
are not reconstructed. Opening a card does not add unsupported rule behavior.

The game runs in a Windows AppContainer with **zero network capabilities**.
The external installer/updater downloads prerequisites and adapter releases.
Your retail account, collection and saved settings are not used by the sandbox.

## Updates and saved files

Close the client, then open **ForgeArenaSandbox.exe**. It checks the configured
GitHub test channel, verifies a newer release and applies it before opening Home.
You normally do **not** run Setup.exe again. Failed or offline update checks keep
using the verified installed version.

Updating an older test.3/test.6 install: open **Start Sandbox** once. If the old
test hub still appears after the update, choose **Start practice** once to enter
the new Home menu and create the dedicated launcher. Subsequent launches use
**Forge Arena Sandbox**. Game files do not need to be installed again.

Saved decks, packs, collection, menu selection and preferences live under
`data/native-lab/local-profile`, outside the version folders. The updater backs
up that profile before changing versions and keeps the previous adapter for
rollback. Rollback pauses automatic updates until an explicit update is applied.
Use the documented maintenance scripts for update/rollback diagnostics; do not
remove the data folder when troubleshooting.

The exact display and update versions are recorded in `release-info.json`.
Newer releases use increasing update versions; a display title does not change
which update is newer.

See [the player guide](docs/FAQ.md) and [exact supported names](docs/SUPPORTED-CARDS.md) for details.

## Troubleshooting and project source

- Installation or client launch failed: inspect `logs` in the installed folder.
- A match cannot start: check the deck warning and the local bot startup message.
- Copied Arena files are incompatible: keep this sandbox intact and use a tested
  build; automatic migration to another Arena asset build is not implemented.
- Report reproducible sandbox issues at
  https://github.com/kgeg401/forge-arena-sandbox/issues.

The public repository contains authored adapter/launcher source and documentation.
This ZIP contains no Arena assets, Forge engine, Java, .NET or loader binaries.
The included Gson library carries its Apache-2.0 license and source. Dependencies
are fetched from their pinned official sources; exact hashes are recorded in
requirements.json and dependencies-lock.json. Development is AI assisted.
