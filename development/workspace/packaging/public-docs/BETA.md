# Beta 2 — public testing release

Update version: **`0.2.0-beta.2`**. Windows x64; MTG Arena must be installed
separately. Download **ForgeArenaSandbox-Windows.zip** from the
[Beta 2 release](https://github.com/kgeg401/forge-arena-sandbox/releases/tag/v0.2.0-beta.2).
The **Source code** archives are developer checkouts, not the Windows installer.

Beta marks a consolidated public test build. Experimental modes, card mappings
and incomplete capabilities retain the limits listed below.

## New in Beta 2

**Settings → Report a bug** saves a private-data-free technical session timeline,
opens a prefilled GitHub form and its report folder, and leaves the match open.
Add screenshots/details and drag the log into the form before submitting. A
GitHub browser sign-in is needed; GitHub CLI is not needed for this button.

## Included

- Practice and Brawl bots; 40-life Commander duel and four-/ten-player bot pods.
- Private internet Commander for two humans, with saved decks, Host/Join and
  cosmetic names/avatars. Pods and Horde remain local; public matchmaking is absent.
- A fixed 500-card Zombie Legion: 300 physical Zombie token cards and 200 support
  cards, real revival/copy/death-trigger effects, and a public-state sequencing
  policy. Commander preparation follows original mana value, minimum one turn.
- 32 shared starter decks, real-card combo decks and private cached paper-card
  illustrations. Invented custom-rule cards are disabled.
- Native castable-card outlines and the original Arena X selector for supported
  deterministic repeats, with a blue Cancel button.
- Faster local large-stack processing, preserving real effects, costs and choices.
  **The sandbox does not speed up the global game clock or normal animations.**
- Existing saved-data backups, version rollback, short read-lock retries and
  sanitized technical failure reporting.

## Supported and experimental cards

The package contains **370 verified baseline names and 1,590 experimental names**,
for **1,960 primary names**. Experimental means enabled for testing, not proven
in every interaction. Separate token, face and emblem presentation records are
not extra playable primary cards. This is not the full Arena or paper catalogue,
nor a retail banlist/format-legality guarantee.

## Install or update

New users: install and fully download official Arena, extract the Windows ZIP,
run **Setup.exe**, select **Check Arena**, then **Install sandbox** into a separate
folder. Setup downloads pinned Forge and private runtimes. Reserve at least
20 GiB; the actual preflight checks the required space.

Existing users: close all sandbox windows and reopen **ForgeArenaSandbox.exe**
or its dedicated shortcut. The existing test channel accepts this newer beta
prerelease. Decks and collection stay outside version folders and are backed up
before updates. No manual game-file replacement is needed. Both friends must
use the same custom-client release and matching catalogue.

If an older launcher cannot update, preserve the entire installed folder and
report its exact version/error. Do not overwrite the data folder or bypass an
Arena fingerprint mismatch. [Setup help](FAQ.md) · [Compatible builds](ARENA-COMPATIBILITY.md)

## What to test first

1. Complete setup and a **Practice Bot → White-Lifegain** opening.
2. Import/select a Commander deck; cast the commander and play through combat.
3. Try a Horde preparation/wave or a four-player pod before the ten-player mode.
4. With a friend, test private Host/Join, mulligans, both players casting and a
   normal finish/concession. Report each PC's release and Arena build.
5. For an interaction failure, record the exact cards, last action, visible prompt
   and expected result. [Report a bug](REPORTING-BUGS.md)

## Validation and limits

The gameplay binaries derive from the locally tested Alpha 15.11 checkpoint.
The normal-clock 304-trigger reproduction completed with the same final rules
state as the previous demo, with Unity time scale 1 in every recorded sample.
Both supported Arena assembly variants compile. This is a seeded workload,
not the original unseeded user match or a retail timing benchmark.

The 500-card Horde has bounded original-handler mechanic cases and two scripted
full games won by the Horde. A survivor win, optimal AI and broad balance are not
established. Native two-client HTTPS tests and dependency/update fixtures have
separate recorded scopes. [Verification](VERIFICATION.md)

Durable match saves, host migration, human multiplayer pods, co-op Horde,
general internet reliability, complete catalogue support, exact retail parity
and a universal 30-second stack cap remain open. [Known issues](KNOWN-ISSUES.md)
