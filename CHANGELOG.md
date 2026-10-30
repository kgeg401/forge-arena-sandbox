# Changelog

## 0.2.0 alpha 10 - Arena-only Moxfield pool and combat choices

- Samples the 50 most-viewed public Moxfield Commander lists: 1,188 matching Arena identities; 638 outside that catalogue are excluded. Adds 942 experimental names, bringing the client to 370 verified plus 1,285 experimental names. No smoke result is promoted to verified support.
- Removes redundant mandatory-trigger ordering and forced one-option prompts while retaining manual ordering, optional costs, targets and actual response windows. Connects the original Auto Choose Replacement Effects setting, native divided-damage and pile controls. Automatic replacement ranking uses Forge's chooser; Arena server ranking is not claimed.
- Fixes shared targeting, X-dependent spell/activation availability, delve, gift costs, Battle protection/defeat, Class levels, colorless/type protection, ninjutsu and temporary token keyword provenance. Adds original life, fixed energy and source-return payment questions.
- Adds 25 named native scenarios for conditional/context activations, resource rejection and payment decline. Includes 51 payment/effect regression groups, broad cast/land and first-activation walkthroughs, and separate rendered acceptance, including changing the real replacement-order setting inside one match. See [verification and limits](docs/VERIFICATION.md) and [per-card coverage](docs/MOXFIELD-COVERAGE.md).
- Includes the experimental Commander Pod: one human and three local bots, 40 life, split attacks, commander damage and elimination. Network multiplayer and partner commander pairs remain unfinished.
- Keeps the existing dedicated launcher and automatic test-channel update path. The actual alpha 9-to-alpha 10 package update and rollback preserve saved test profiles. Recipient-PC installation and complete retail parity are not established by this checkpoint.

## 0.2.0 alpha 9 - Human gameplay fixes and local Commander

- Adds 40-life Commander Bot and an experimental four-player Commander Pod: one human and three easy Forge bots on the same PC. Includes a shared table, opponent focus, public-zone controls and commander-damage display.
- Corrects the human controller and cached Forge player identity at construction. Bots remain AI; human deck shuffling does not use AI helpers.
- Fixes prepayment target cancellation being treated as a rejected play and suspending automatic progression. Real cost failures remain rejected.
- Shows numeric printed planeswalker loyalty outside the battlefield and actual counters on the battlefield; includes both Compleated payment branches.
- Restores Jace, Cunning Castaway's combat-loot trigger, Incubator's active Phyrexian face and Seat of the Synod's manual blue mana. Retains Mana Drain's delayed mana fix.
- Checks include 51 payment/effect groups, normal Emry mechanics and Commander return/tax sequences, a complete normal duel, a 713-name static presentation-binding audit, and rendered four-seat cancellation/retry. Static mapping is not gameplay certification of every card.
- The verified baseline remains 370 names; 343 additional names remain experimental. Network multiplayer, complete card coverage, durable match saves and full retail UI parity remain unfinished.
- Update through the existing launcher after closing the client. Profiles stay outside version folders and rollback is retained.

## 0.2.0 alpha 8 - Mana Drain delayed mana fix

- Fixes the stall at Mana Drain's next-main-phase trigger after its counterspell resolved.
- Projects Forge's delayed-trigger SpellDescription exactly as DelayedTriggerEffect does, binding the original hidden native mana ability.
- Only Mana Drain's generated card mapping changes. Gameplay code, other cards, admission and Forge dependency are unchanged.
- Native whole-sequence tests cover mana values 0, 2, 3 and an uncounterable 4-mana spell, exact colorless output, correct following main phase, pool clearing and no repeat on the next turn.
- Existing running matches need the client reopened to load the corrected binding.

## 0.2.0 alpha 7 — Jace Superfriends Brawl

- Adds the exact 100-card Jace Superfriends Brawl starter, led by Jace, Multiverse Architect.
- Pins the official Forge 2.0.16 snapshot containing his rules; automatic private engine upgrade retains rollback copies.
- Connects planeswalker combat recipients, optional mana taxes, copied loyalty abilities, Saga descriptions and Narset rebound.
- Native checks cover 100 card play/cast scenarios, 21 loyalty activations, focused Jace/rebound/proliferate outcomes, 51 regression groups and eight turn-flow modes. One normal full match completed 30 turns / 570 actions.
- Installed native client opened the deck and normal Brawl match; prior deck records were unchanged. Profiles and retail assets stay local.
- The 370-name verified baseline is unchanged. 343 additional card names remain experimental; smoke tests do not verify every branch or combination.

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
