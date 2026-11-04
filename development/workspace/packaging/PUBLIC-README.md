<h1 align="center">Forge Arena Sandbox</h1>

<p align="center">
  <img src="docs/images/hero.svg" alt="Your decks. Your table. Play solo or bring a friend to Commander." width="1200">
</p>

<p align="center">
  A personal Magic sandbox with <strong>Arena's original presentation</strong> and <strong>Forge's rules engine</strong>.<br>
  Solo matches, Commander pods, Zombie Horde, and private two-player Commander.
</p>

<p align="center">
  <a href="https://github.com/kgeg401/forge-arena-sandbox/releases/tag/v0.2.0-beta.2"><img src="docs/images/download-windows.svg" alt="Download Beta 2 for Windows" width="296" height="60"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> · <a href="#play-with-a-friend">Play with a friend</a> · <a href="docs/BETA.md">Beta notes</a> · <a href="docs/KNOWN-ISSUES.md">Known issues</a> · <a href="docs/REPORTING-BUGS.md">Report a bug</a>
</p>

<p align="center"><sub>Beta 2 · Windows x64 · Public testing prerelease · MTG Arena installed separately</sub></p>

![An actual sandbox match with Emry on the battlefield](docs/images/emry-match.png)

<p align="center"><sub>Actual sandbox gameplay. Arena artwork and presentation load from your own installation.</sub></p>

## Pick your next game

| Mode | Your table |
| :--- | :--- |
| **Practice & Brawl** | Test a deck against a Forge bot. Brawl uses 99 cards plus a commander and 25 life. |
| **Commander duel** | Play a bot with 40 life, commander tax, and commander damage. |
| **Private Commander** | Invite one friend over the internet. Two humans, your own decks, 40 life. |
| **Commander pods** | Play with three or nine bots. The experimental ten-player mode attacks left until four players remain. |
| **Zombie Horde** | Bring a commander deck against a 500-card Zombie Legion with revival, copy engines and death triggers. Start at 40 life, with preparation turns based on your commander's mana value. Solo for now. |

[See every mode, its rules, and where to find it →](docs/GAME-MODES.md)

**A library to start with.** Installations receive **32 shared starter decks** and a local starter collection. Cosmetic profiles share decks and collection, while keeping their own name and avatar. Import Arena deck text, edit your list, or try an included build. Saved content stays on your PC. [Starter content](docs/STARTER-CONTENT.md)

## Quick start

**Before you begin:** a Windows x64 PC, a fully downloaded installation of MTG Arena, and at least 20 GiB free. Setup checks compatibility and the space needed for its separate game copy.

1. **Get the client.** Open the [Beta 2 Windows release](https://github.com/kgeg401/forge-arena-sandbox/releases/tag/v0.2.0-beta.2) and download **ForgeArenaSandbox-Windows.zip**. GitHub's **Source code** archives are for developers.
2. **Install once.** Extract the entire ZIP, open **Setup.exe**, and choose your Arena folder plus a separate sandbox destination. Select **Check Arena**, then **Install sandbox**. Setup handles Forge, Python if needed, and the private runtimes. The first download and game-file copy can take several minutes.
3. **Play.** Open **Forge Arena Sandbox** from the installed folder. For a first match, choose **Play → Practice Bot → White-Lifegain**.

Using Steam? **Manage → Browse local files** opens the Arena folder to select. [Supported Arena builds and setup help](docs/ARENA-COMPATIBILITY.md)

## Play with a friend

Choose **Brawl → Private Commander (Internet)**, select a saved Commander deck, and choose **Host** or **Join**. The host shares the complete private invitation and keeps their client open.

Both players need the same current client build. **You can use different decks.** [Connection guide and limits →](docs/MULTIPLAYER.md)

## Familiar from the first click

| Choose your match | Open your packs |
| :---: | :---: |
| <img src="docs/images/brawl-queue.png" alt="Arena's original Play panel showing local Brawl decks" width="430"> | <img src="docs/images/packs.png" alt="The original Arena pack-opening presentation in the sandbox" width="430"> |
| Original deck selection and commander controls. | Local packs, original reveal animations, saved balances. |

Home, Decks, Packs, and Options use the installed game's presentation. Pack contents follow custom sandbox collation; retail wildcard rewards and duplicate protection are not reconstructed. [More screenshots](docs/SCREENS.md)

## What is in Beta 2?

The beta brings together the existing modes with the **500-card Zombie Legion**, real-card combo decks and artwork, native castable-card outlines, and the original X selector for supported repeatable combos. Large local stacks retain the backend processing improvements while using the **normal game animation clock**. [Beta release notes](docs/BETA.md) · [All guides](docs/README.md)

**370 card names remain in the verified baseline; another 1,590 are enabled experimentally, for 1,960 primary names.** Verification covers recorded scenarios, not every possible interaction. Experimental cards can still encounter an explicit unsupported-action gap. [Card coverage](docs/MOXFIELD-COVERAGE.md) · [Verification record](docs/VERIFICATION.md)

- Private rooms support **two humans**. Four- and ten-player pods use bots; Horde is solo.
- Closing the client or returning Home **ends the match**. Durable match saves are unfinished; your decks, collection, packs, and settings persist separately.
- Official Arena accounts, collections, rewards, and online matchmaking are not connected to this sandbox.
- Beta is a public testing milestone. Full card coverage, exact retail parity, a universal 30-second stack limit and general two-household multiplayer reliability are not certified. [Known issues and testing priorities](docs/KNOWN-ISSUES.md)

## Updates are in the launcher

Close all sandbox windows, then reopen **ForgeArenaSandbox.exe** or your desktop shortcut. The launcher checks for updates and backs up your saved profile before applying one. Use the launcher for future updates after the first setup.

[Release notes](CHANGELOG.md) · [Troubleshooting](docs/FAQ.md) · [Report a problem](https://github.com/kgeg401/forge-arena-sandbox/issues/new/choose)

## Help test the beta

Start with **Practice Bot → White-Lifegain**. Then try a saved Commander deck, a Horde opening or a private match with a friend. Report the exact version, mode, card/action, steps and expected versus actual result. Screenshots help; please keep invitations and private diagnostics out of public issues. [How to report](docs/REPORTING-BUGS.md)

<details>
<summary><strong>Connection, credits, and project source</strong></summary>

The game process runs in a Windows AppContainer with zero network capabilities. The separate installer/updater downloads prerequisites and client releases. Private Commander uses an external worker and an authenticated temporary HTTPS tunnel. [Connection and trust](docs/MULTIPLAYER.md)

Rules are powered by [Card-Forge/Forge](https://github.com/Card-Forge/forge). Credits also include BepInEx, Eclipse Adoptium, Microsoft .NET, Python, and Google Gson. Development is assisted by OpenAI Codex. Dependencies retain their own licenses; see [testing permission and attribution](LICENSE.txt).

[Developer guide](docs/DEVELOPMENT.md) · [Source and catalogue tools](development/README.md)

</details>

---

<sub>Unofficial, independent project. Not affiliated with Wizards of the Coast. MTG Arena and its assets belong to their respective owners and must be installed separately. Screenshots document gameplay; reusable Arena assets are not included in the download.</sub>
