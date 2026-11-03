# Alpha15.8 - Shared status-file lock repair

A mapped reader of deck-host-status.json could make a diagnostic write abort native card presentation. Periodic status snapshots now publish separately and defer transient locks. Presentation acknowledgements remain pending until publication succeeds. Reproduced the exact1224native error; candidate played cards/combat through turn7with the same mapping held and resumed publishing afterward. Both players should update the native adapter.

# Alpha 15.7 - Legacy automatic-upgrade repair

Retains the exact legacy primary Arena fingerprint needed by Alpha15.2 updaters while preserving all current standalone/Steam variant checks. The actual shipped15.2 updater reproduced the earlier rejection and accepted this package with saved profile bytes preserved. Native/gameplay binaries are unchanged from Alpha15.6. Different Commander decks remain supported.

# Alpha 15.6 - Black-screen startup repair

Select installed asset manifests by the validated card-database identity, preventing old/new manifests from registering the same art path. Preserve installed source files and report unresolved conflicts immediately. Native reproduction and fresh-profile Home/26decks/return-Home validation passed. Existing clients update through the launcher; no Arena/Forge recopy is required. Both friends should update the native adapter.

# Alpha 15.5 - Steam Arena compatibility

Recognizes the exact Steam MTGA.exe reported by the recipient while retaining all eight existing current-build library/database pins. Shared store catalogue selection no longer becomes ambiguous, and unsupported files are identified in the error. Steam launch on the recipient PC remains pending; the adapter/rules binaries are unchanged from the tested Alpha15.4.

# Changelog

## 0.2.0 alpha 15.mp.4 - Current Arena compatibility

- Setup accepts complete tested Arena 0.1.14589.1332174 and retained 0.1.14517.1329972 installations, with matching databases. Unknown/mixed/modified files remain blocked.
- Adapt original localization loaders and retain saved paper printing IDs alongside new native printings. Validate pack-collation metadata against the selected original build.
- Reviewed old/current ABI family supports private Commander between the two asset versions on the same custom-client release. Two real native clients tested through HTTPS with lands, both commander casts, combat, reciprocal life and Return Home. No complete-game, all-card or two-household certification.
- Includes the 26 shared decks/521 collection entries/928 copies from 15.3; saved data and separate game copies remain.

## 0.2.0 alpha 15.mp.3 - Shared starter decks and collection

- Every new profile receives the current 26 saved decks and 521 collection entries/928 copies, with original exact-printing piles. Includes Emry, Jace, Darien, Gamba Gamba, Miirym and Zaxara.
- Existing profiles receive missing starters once; same-name deck edits, higher card counts, unopened packs and opening history are preserved. Safe retry after a partial write and backups before replacement.
- No account/sign-in information, original profile/deck IDs or private history is shared. This does not change an official Arena account.
- Native deck/collection storage checks and all 26 admission checks pass. Gameplay/rules binaries are unchanged from 15.2; exhaustive deck interaction and two-household multiplayer testing remain open.

## 0.2.0 alpha 15.mp.2 - Private internet Commander

- Two human players choose saved Commander decks at 40 life through Brawl > Private Commander (Internet), then Host or Join with a private invitation. No port forwarding.
- One authoritative Forge process, private per-player views, native presentation acknowledgements and exact build/catalogue compatibility. Verified official temporary HTTPS helper; retail game retains zero network capabilities.
- Two real native clients played commander casts and combat, correct opposite results and same-process rematch with reversed host. Completed guest results survive host departure. These tests used public HTTPS on one PC; two-household testing is next.
- Includes existing bot, solo Horde and experimental ten-player bot modes. Saved decks remain separate. No human pods, matchmaking, host migration, crash-resume or all-card claim.

## 0.2.0 alpha 15.mp.1 - Private internet Commander

- Two human players choose saved Commander decks at 40 life through Brawl > Private Commander (Internet), then Host or Join with a private invitation. No port forwarding.
- One authoritative Forge process, private per-player views, native presentation acknowledgements and exact build/catalogue compatibility. Verified official temporary HTTPS helper; retail game retains zero network capabilities.
- Two real native clients played commander casts and combat, correct opposite results and same-process rematch with reversed host. Completed guest results survive host departure. These tests used public HTTPS on one PC; two-household testing is next.
- Includes existing bot, solo Horde and experimental ten-player bot modes. Saved decks remain separate. No human pods, matchmaking, host migration, crash-resume or all-card claim.

## 0.2.0 alpha 14.rail.10 - Interaction-tested efficiency and game-mode guide

- Reuse per-transition chooser-visible cards and token membership sets. Keeps visibility rules, card order and native annotations; avoids repeated full-state rebuilding for each token.
- Six recorded sequences retain 224 exact GRE messages; repeated 36-token projections allocate about 18% fewer temporary bytes. No gameplay fps claim.
- Fresh Forge plus original Arena-handler checks cover token combat, phasing/equipment/counters, Class level/zone reset, mass arrivals, creature/spell copies, poison, Horde revival and commander-sized preparation. Real full-deck ten-player attacks and ordinary 200-card Horde are checked separately; no all-card/full-pod-winner certification.
- Includes both Zombie Horde queues and experimental ten-player Commander. Adds one guide with exact menu locations, 40-life rules, 200-card Horde, preparation and attack-left/final-four rules. Packaged README no longer omits those modes or promises durable Home/resume.
- Saved decks and game assets stay separate from versioned updates; use the normal close/reopen auto-update flow.

## 0.2.0 alpha 14.rail.9 - Client reliability and Commander pods

- Repairs nullable update digests, session-qualified native error notices, expensive full-board notice reads and unlimited growth of newly marked match archives. Existing legacy archives/decks remain untouched. Export/full-history options are documented.
- Includes the previously local pod repairs: face-up exile ordering, empty-zone click handling, ten-seat commander-damage pages, original Options navigation, deliberate post-defeat spectating and safe Return Home. Refreshes large-pod rail/portraits and survivor-aware camera controls.
- Includes concurrent native coin flips/Thumb presentation, paper artwork, creature-combo/copy Commander decks, protection/combat fixes and disk-backed completed rules replies with integrity checks. Catalogue: 370 verified-baseline names plus 1,421 experimental names; this does not certify every card or combo.
- Current maintenance checks: 143 focused authored checks, 23 package equivalence checks and original Continue/queued fatal/Return Home/second-match verification. Small notice allocation ~3.6 KB vs prior ~17.5 MB full-file parse; not an fps measurement. Private original files restored independently.
- Known limits: an extra second-match spectator check was blocked by the private observer retaining its first-game queue. No new full-pod winner, all-card, recipient-PC or complete retail UI parity certification. Return Home ends the match; durable player save/restore remains unfinished.

## 0.2.0 alpha 13 - Paper Darien and commander-sized Horde prep

- Commander Horde preparation now matches the commander's printed mana value (minimum one turn). Five-mana commanders get five preparation turns; Darien gets six. Practice decks keep three. Normal land drops and costs remain in force; life stays 40 and the Horde stays 200 cards.
- Adds the exact original 100-card FREAK-OFF Darien paper deck, with no substitutions. Enables 52 new experimental names, including 31 explicit paper-only presentation records using Forge rules. No owned Arena database records are overwritten. Paper-only artwork uses the native missing-art placeholder.
- Fixes incremental presentation overlays so updated token bindings retain existing identities, and distinguishes trigger-execution effects from actual activated abilities. Adds exact generated-copy body binding as an explicit preparation option.
- Tests cover all 52 new cast/land entry points, four on-curve commander openings and 34 named interaction scenarios. Actual native checks load all 31 paper models with matching names, show the saved deck in Play, and open a 40-life/200-card/six-prep Horde match with a successful original land play.
- The verified baseline remains 370; 1,348 names remain experimental, for 1,718 admitted primaries. Exhaustive combinations, partner commanders, network Horde and durable match saves remain outside this checkpoint.

## 0.2.0 alpha 12 - Ghoulraiser reveal fix

- Fixes a stalled reveal box when Ghoulraiser returns a physical Zombie token card. Explicitly revealed cards retain their original identity; other hidden cards stay hidden and temporary visibility ends after acknowledgment.
- Horde and Commander Horde start the survivor at 40 life against the existing 200-card Zombie/Horror deck. This does not reset damage during an ongoing match.
- Exact failing token-return scenario, ordinary revival, opening-life and hidden-pile regressions pass through the original handlers. This is a targeted repair, not certification of every card interaction.

## 0.2.0 alpha 11 - Solo reanimation Horde and combat progression

- Adds Zombie Horde (Solo) and Zombie Horde (Commander Deck). Use existing practice or 99-card-plus-commander decks, 40 survivor life and three preparation turns against a shuffled 200-card Zombie/Horror Horde.
- The Horde has 120 physical Zombie token cards and 80 themed creatures/spells, including 52 revival copies. Actual Forge targets, response windows, graveyard returns, mass reanimation, death triggers, haste attacks and damage-to-mill rules are connected.
- Fixes targeted free casts, Horde-controlled mass-return ordering and Undead Butler's separately linked reflexive trigger. A no-target revival spell is explicitly discarded as a Horde variant rather than stranding an exhausted hand.
- Connects optional human Exert choices and fixes stale priority controls after native combat-damage presentation. Keeps original targets, optional payments and response windows.
- Adds 11 experimental Arena card names. The verified baseline stays 370; the experimental inventory is 1,296 names. Existing identities and 139 additional presentation objects are preserved. No new name is promoted to fully verified support.
- Bounded native-handler revival cases, seven final Horde regressions, original rendered Commander opening, exact package checks, and disposable update/rollback checks pass. A pass-only survivor loses a genuine ordinary 200-card game; broad deck balance and every possible revival chain remain unverified.
- Solo Horde only. Paid Horde activations/flashback, cooperative Horde, network play and durable match saves remain unfinished. Existing Forge/Arena prerequisites and automatic test-channel updates are unchanged.

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

## 0.2.0 alpha 7 â€” Jace Superfriends Brawl

- Adds the exact 100-card Jace Superfriends Brawl starter, led by Jace, Multiverse Architect.
- Pins the official Forge 2.0.16 snapshot containing his rules; automatic private engine upgrade retains rollback copies.
- Connects planeswalker combat recipients, optional mana taxes, copied loyalty abilities, Saga descriptions and Narset rebound.
- Native checks cover 100 card play/cast scenarios, 21 loyalty activations, focused Jace/rebound/proliferate outcomes, 51 regression groups and eight turn-flow modes. One normal full match completed 30 turns / 570 actions.
- Installed native client opened the deck and normal Brawl match; prior deck records were unchanged. Profiles and retail assets stay local.
- The 370-name verified baseline is unchanged. 343 additional card names remain experimental; smoke tests do not verify every branch or combination.

# Changes

## 0.2.0-alpha.6 â€” smoother turn flow

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


## 0.2 alpha â€” 370 supported cards

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
