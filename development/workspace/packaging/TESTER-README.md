# Forge Arena Sandbox

An unofficial local Magic sandbox with Arena's installed presentation and Forge
running the rules. **Windows x64. Experimental. Local bots and private two-player Commander.**

Each installation starts with the shared **26 saved decks** and **521 collection
entries / 928 copies**. Updates add missing starters once and preserve your own
decks and progress. See [starter content](docs/STARTER-CONTENT.md).

Arena compatibility: this release supports **0.1.14589.1332174** and the older
**0.1.14517.1329972** asset copies. [Supported builds and limits](docs/ARENA-COMPATIBILITY.md).

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

Exact supported fingerprints are required: **Client0.1.14589.1332174**
(standalone or the pinned Steam executable) and retained **Client0.1.14517.1329972**
standalone assets. Unknown or mixed files are rejected without changing Arena.

## Play

- **Home > Play > Play:** choose Practice Bot, select a valid local deck, then
  click Play. Forge controls the bot and all supported rules.
- **Home > Play > Brawl:** choose Brawl Bot and a Brawl deck. This sandbox uses
  99 main cards plus one commander, singleton except basics, color identity,
  25 life, a free first mulligan, command-zone returns and commander tax.
- **Commander:** on the Brawl tab, choose **Commander Bot (40 Life)** or **Commander Pod (4 Players)**. The pod is one human and three easy Forge bots on this PC, with 40 life, commander tax and 21 commander combat damage. Its shared table and public-zone controls are experimental.
- **Ten-player Commander:** under Brawl choose **Commander Pod (10 Players - Experimental)** for you and nine Forge bots, 40 life, attacks to the nearest living opponent on your left until four remain, then normal legal opponents.
- **Zombie Horde:** under Brawl choose **Zombie Horde (Commander Deck)** for a saved commander deck, or under Play choose **Zombie Horde (Solo)** for a practice deck. You start at 40 life against 200 Zombie/Horror cards with extensive revival. Commander preparation equals mana value (minimum one); practice gets three turns. See [all modes and controls](docs/GAME-MODES.md).
- **Decks:** create, import Arena deck text, edit, duplicate, export or delete
  local decks. Fresh installations receive recommended starters. Choose Practice or Brawl when creating a deck. Click the deck
  header to change its local format. Brawl uses the native commander slot.
  Original search, color/land, type, rarity, mana and card-size controls are connected.
  Local deck changes also save on a normal client exit.
- The original Graphics and Audio screens control local settings. Window size
  and fullscreen choice reopen from the saved profile, along with audio preferences.
- **Packs:** open local sandbox packs using the original carousel, reveal
  animations and card presentation. New installations receive 100 packs for each
  supported catalog set. Pack balances and collected cards persist locally.
- Use the original in-match Options menu to concede. Continue from the result
  screen returns to Home. Another match does not require restarting the client.
- Opening the launcher again focuses the existing client instead of starting
  a second game.

**Profile** changes your local name and avatar. Cosmetic identities share the same decks, collection, packs and settings; creating one does not grant starter content again or create a separate account.

Technical failures can queue an automatic report containing only the release
version and a fixed failure code. Sending requires an existing GitHub CLI
sign-in on this PC, or the host of a connected private match for a guest display
failure. Otherwise reports remain local. No decks, collection, invitations or
detailed logs are attached automatically. [Reporting and recovery limits](docs/FAILURE-REPORTS.md).

**Private Commander (Internet)** under Brawl connects two human players using their saved decks and 40 life. Choose Host room or Join copied invite inside the client after Play; privately share the complete invitation. Both players need the same release. See [setup and limitations](docs/MULTIPLAYER.md). Commander pods remain one human and three or nine bots; Horde remains solo. Public matchmaking queues are not implemented.
The Home menu, navigation, Play panel, deck widgets, pack chamber and game board
reuse installed Arena assets. Local navigation and queue data replace the online
services. Advertising, store/account controls and online reward panels are
omitted. This is not a claim of complete retail UI or behavior parity.

## Current limits

The verified baseline remains **370 main-deck names**. The exact baseline is in [SUPPORTED-CARDS.md](docs/SUPPORTED-CARDS.md); the generated [experimental catalogue notice](docs/EXPERIMENTAL.md) records this release's additional names and blockers. Card admission and play/cast checks do not prove every branch or combination. Actual unmapped actions still report a gap.

Return Home or closing the client ends that match; player-facing durable match saves are not implemented. Decks, packs and settings persist separately.

Packs use custom sandbox collation: five commons, two uncommons and one
rare/mythic, with a one-in-eight mythic choice when available. Retail bonus
sheets, duplicate protection, wildcard rewards and account collection syncing
are not reconstructed. Opening a card does not add unsupported rule behavior.

The game runs in a Windows AppContainer with **zero network capabilities**.
The external installer/updater downloads prerequisites and adapter releases. A separate room worker provides private multiplayer through an authenticated temporary HTTPS tunnel; the host must stay open. See [connection and trust](docs/MULTIPLAYER.md).
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
