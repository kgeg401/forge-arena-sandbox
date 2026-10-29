# Using the sandbox

## Which download do I need?

Get **ForgeArenaSandbox-Windows.zip** from the current Windows release, extract
everything, then open **Setup.exe**. The repository's source ZIP cannot replace
the Windows release. Setup offers **Check Arena** and **Install sandbox**.

Install Arena separately first. Setup verifies the tested game build before
copying it, then downloads and configures the pinned Forge distribution and
private runtimes. You do not need to install Forge yourself.

## Why does Check Arena reject my installation?

This alpha supports only the Arena files identified in `requirements.json`:
Client0.1.14517.1329972 / Unity 6000.3.14f1 and the matching downloaded card
database. Finish Arena's content download if that database is missing. A newer
or modified build requires a separately tested compatibility update; changing
the version label does not make it compatible.

Keep an existing sandbox and its saved profile intact when reporting a failed
check. The installer does not patch or downgrade the retail game.

## Why can I save a deck but not play it?

Storage and rule support are separate. The editor can store installed Arena
cards that the bridge has not verified. The deck's warning explains the cards
or construction rules blocking a match. [The supported list](SUPPORTED-CARDS.md)
records the current admission policy. A matching Forge script alone does not
prove that the Arena bridge can present every required action correctly.

Practice uses 40–250 main cards. Brawl and Commander use 99 main cards plus one enabled
commander, singleton except basic lands, and the commander's color identity.
Sideboards and companions are not supported. The sandbox does not apply retail
format banlists. Importing an unsupported deck never silently removes its cards.

Fresh profiles include recommended starter decks. Older installations keep
their existing libraries, including older sample names. Deleting a starter does
not cause it to be added again every time the client opens.

## Are these Arena bots or online opponents?

All queues start local games in the native Arena board. Commander Pod is one human and three Forge bots on this PC. Brawl Bot uses 25 life; Commander Bot and Commander Pod use 40 life and 21 commander combat damage. They do
not connect to Arena matchmaking or use its server AI. Multiplayer is unfinished.
Games are not resumable after closing the client.

## How do packs and collection work?

Each fresh profile receives 100 packs for each of the 51 catalogued sets.
Opening uses the installed pack presentation and saves local balances/cards.
Distribution is custom: five commons, two uncommons and one rare/mythic, with a
one-in-eight mythic choice when available. Retail wildcard rewards, bonus sheets,
duplicate protection and account synchronization are absent.

Deck building is unrestricted by collected quantity. Collection is local, and
opening an unverified card does not make it playable in a match.

## How do updates work?

Close the game, then open **ForgeArenaSandbox.exe**. A newer published Windows
release is required; a source-code push alone does not update clients. Startup
checks the download digest and file manifest before switching versions. It
keeps the previous adapter and a profile backup. An offline or rejected update
leaves the verified installed client available.

For test.3/test.6 installations, open the old **Start Sandbox** shortcut once.
If its old hub appears, select **Start practice** once. The update creates the
new **Forge Arena Sandbox** shortcut. Full game-file installation is not repeated.

Rollback pauses automatic updates. The maintenance script can explicitly check,
install or roll back: `Manage-Updates.ps1 -Action Check`, `Install` or `Rollback`.
Close the game first. Older adapters may expose fewer cards/features.

The display name and diagnostic update version are recorded in
`release-info.json`. Updates use that increasing version number.

## Where are my files?

Inside your chosen sandbox folder:

| Location | Contents |
| --- | --- |
| `ForgeArenaSandbox.exe` | Dedicated client launcher |
| `data/native-lab/local-profile` | Decks, packs, collection, menu selection and preferences |
| `profile-backups` | Saved-profile copies made by the updater |
| `logs` | Launcher and local match-service logs |
| `data/native-lab` | Native game diagnostics and current/archived match evidence |
| `versions` | Verified adapter versions retained for update/rollback |

The old `data/native-lab/local-playerprefs.json` is retained during preference
migration. Current preferences live in `local-profile/playerprefs.json`.
The native Graphics screen's window size and fullscreen choice are saved in
`local-profile/display.json` and restored by the dedicated launcher.

If a damaged display file blocks startup, close the client, preserve that file
and restore its `display.json.bak` copy. Removing only the damaged display file
after backing it up uses the default 1280x720 window; it does not remove decks.

## A game or launch failed. What should I report?

Include the sandbox version, Arena build, steps, expected result and actual
result. A short relevant log excerpt or screenshot helps. The local match notice
provides Return Home when the engine stops; reopen the client if its coordinator
is unavailable. Decks and collection are saved separately from matches.

## How do I remove it?

Close the client and back up `local-profile`, then remove the sandbox folder.
Its private game copy, Forge and runtimes are there. Retail Arena remains
separate. Python and the prerequisite download cache are outside that folder.

## Can I save a match and close the game?

Home can park and Resume the same running match. Closing the client ends it; there is no durable match restoration. Decks, packs, collection and settings persist separately.
