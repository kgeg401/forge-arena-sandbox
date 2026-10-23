# Changes

## 0.2.0-alpha.6 — smoother turn flow

- Advances empty rules steps without the repeated pause at each substep.
- Restores original turn banners, phase indicators and contextual Next / To Combat / End Turn controls.
- Keeps playable actions, combat decisions, full control and explicit stops interactive.
- Corrects supported End Turn yield expiry and Resolve All clearing.
- Retains the same rules engine and 370 supported main-deck names as alpha.5.

Verified with eight Forge/native scenarios, twelve rendered checks and local
user play. Complete server smart-stop behavior, complex phase lookahead and
all-card support remain unfinished. This release does not include separate
shared-card-mechanics research. Close and reopen the dedicated launcher to update;
Setup.exe is only needed for a new installation. Decks and collection are preserved.


## 0.2 alpha — 370 supported cards

Update version: `0.2.0-alpha.5`.

- Expands the previous public252-name policy to370 supported Arena card names:
  118 additional names. See [the full additions](docs/ADDED-CARDS-0.2.0-alpha.5.md).
- Adds reviewed trample creatures, removal, fixed creature damage, temporary
  stat modifiers and draw/life effects, with exact native target prompts.
- Fixes damage event classification for supported resolving spells; unexpected
  contexts still report a gap rather than guessing combat/noncombat behavior.
- Adds Fire and Growth / Trample and Growth practice decks. Existing libraries,
  collection and preferences are preserved; update and rollback retain profiles.
- Refreshes support diagnostics and consumer help to match the admitted list.
- Includes matching development sources, batch generators and QA/evidence tools.
  Paradox Engine is preserved as disabled research and is not supported.
- Existing dedicated launcher, native menus, pack openings and Brawl bot queues
  remain. Full catalogue coverage, multiplayer and complete retail parity are
  unfinished. Arena is still required separately.


## 0.01 alpha

Internal update version: `0.2.0-alpha.1`.

- One dedicated Windows launcher opens the native Home menu and focuses an
  existing client when opened again.
- Home, Decks, Packs and Play remain available between matches.
- Practice Bot and Brawl Bot queues create local Forge AI games from saved decks.
- Brawl supports the verified Emry/Isamaru commanders, command-zone play,
  25 life, the free first mulligan, commander tax and return choices.
- The native deck editor includes its commander slot, local format selection,
  original search/filter/sort routines, advanced filters, zoom and card sizes.
- Local pack openings, collected cards, decks, menu selection and preferences
  persist. Normal exit saves pending local deck edits.
- Native Graphics resolution and fullscreen choices survive launcher restarts;
  the launcher no longer forces 720p every time.
- Fresh profiles receive eight recommended starter decks. Existing libraries
  are preserved, and deleted starters are not repeatedly restored.
- Native notices handle local match failure and return to Home. Queue
  cancellation and result-screen Continue no longer require a client restart.
- The release admits 252 main-deck names. Full Arena card coverage and
  multiplayer remain unfinished.

Earlier installer/update test releases are retained in
[Releases](https://github.com/kgeg401/forge-arena-sandbox/releases). Their dated
verification record is [archived here](docs/archive/verification-test-builds.md).
