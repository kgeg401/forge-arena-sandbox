# Historical developer README

Preserved verbatim from the earlier development checkpoint. Counts and status
below are historical, not the current release. Original links were relative to
the workspace root. See the current README and catalogue delivery record.

## Latest playable checkpoint (2026-10-21)

The new [Emry mechanics test](docs/emry.md) connects Emry's artifact discount,
four-card entry mill and targeted graveyard casting to Forge and the original
Arena controls. Use **Forge Emry Mechanics Test** for the repeatable artifact
practice deck, or **Forge Emry Brawl Test** for a deliberately land-heavy
100-card, 25-life commander fixture. The full saved Emry deck is still blocked
by its other unsupported cards. The earlier tester ZIP is unchanged.

The [Brawl foundation](docs/brawl.md) also retains the Isamaru test through
**Forge Arena Brawl Test** or `Open-Brawl.ps1`. Commander tax, affinity, death
return choices and both choices on a commander bounced toward hand have
input-driven rules evidence. Broader commander support remains unfinished.

The [card support audit](docs/card-support-audit.md) now covers all 16,140 installed
names. There are 15,840 Forge script candidates, 300 unmatched names, one
construction failure and two constructor diagnostics. The audit maps missing
bridge capabilities per card; sixteen ordinary names are now admitted.
Candidate construction never promotes playable support.

[Sharing and updates](docs/sharing-and-updates.md) describes the unpublished
tester installer and versioned updater. A separate local install has reached
the original board/deck browser using its own copied assets. Saved profiles stay
outside application versions. This remains a developer preview: no GitHub upload,
second-PC validation or multiplayer is implied.

Use **Forge Arena Decks** to browse, duplicate, edit, name, save, import and export local decks through Arena's original deck components. See [local deck lists](docs/local-decks.md) for controls and current limitations. The main-section editor is connected; full Home navigation, format/crafting controls and other-section editing remain unfinished.

Use **Forge Arena Practice** on the desktop for a ready-to-play shuffled white/blue match. Use **Forge Arena Custom Decks** to choose your deck and the opponent deck, then play through Arena's original mulligan, Play/Draw and match controls. Samples are in `decks/`; exports from the deck browser appear in the custom match picker's starting folder.

Sixteen ordinary card names are admitted: Plains, Island, Savannah Lions, Yoked Ox, Oreskos Swiftclaw, Impassioned Orator, Divine Arrow, Unsummon, Essence Scatter, Quick Study, Hare Apparent, Emry, Lurker of the Loch, Ornithopter, Aether Spellbomb, Seat of the Synod and Tormod's Crypt. Isamaru is separately admitted as a Brawl commander; Hare's existing Arena Rabbit token is mapped. Forge owns costs, colored mana, targets, stack/trigger/counter resolution, spell draws and empty-library loss, normal turns, combat, discards and outcomes; original Arena supplies the board, cards, controls, effects and audio. Ajani and Sparky use original match-local default portraits.

The [earlier card-coverage checkpoint](docs/card-coverage.md) records the initial catalogue mapping. The latest normalization finds 15,840 of 16,140 Arena names with a unique Forge script candidate; this is source/name coverage, not playable-card coverage. Hare's three-cast native slice renders three Rabbit tokens; a separate normal headless Hare game reaches a turn-14 win. `decks/Hare-Apparent-Practice.txt` is a 60-card sample for the custom-deck launcher.

Imported main decks contain 40–250 cards with unrestricted copies. Unsupported cards/sideboards fail before closing a running game; canceling either picker also preserves it. Export printing labels are accepted but art uses pinned verified printings. This is a personal sandbox policy, not sanctioned-format deck validation.

The optional `decks/White-Blue-Study.txt` sample adds Quick Study to a normal 60-card deck. Run `Open-Playable.ps1 -ChooseDecks`, or `-DeckPath <file> -OpponentDeckPath <file>`. Omitting the opponent file mirrors yours. Restart by launching again; prior evidence is archived. For admitted vanilla creatures, multi-block damage uses Arena's original assignment screen: uncheck Auto Allocate Damage, change the split, then Done. Forge applies the chosen allocation. Legacy damage ordering, trample/deathtouch, general cards/abilities, original home/Continue flow, avatar selection and complete presentation parity remain gaps.

Headless tests cover complete normally started games and each supported decision. Native observations include London mulligan/Play-Draw, targeted damage/cancel, Orator triggers, blue returns, imports, avatars, counters, manual multi-block damage, spell draws, cleanup and empty-library loss. A complete rendered nine-card practice match reached natural defeat on turn 14; all 20 life states, 49 damage and winner agree with the installed parser across 170 states. Full engine runs do not imply a full rendered match for every deck. Original yield behavior and trigger source-link placement still have presentation/usability gaps. Earlier checkpoints are preserved in [the history](docs/checkpoint-history.md).

## Play and restart

Pack-opening development is separate from matches: see [local packs](docs/pack-opening.md).
Run `Open-Packs.ps1` for the original booster chamber backed by a persistent local collection.

- Double-click **Forge Arena Practice** for a shuffled white/blue match.
- Double-click **Forge Arena Hares** for the 60-card Hare Apparent sample against the white practice opponent.
- Double-click **Forge Emry Mechanics Test** for artifact discount, mill and sacrifice/recast practice. **Forge Emry Brawl Test** uses Emry in command; both are development fixtures, not your full saved deck.
- Double-click **Forge Arena Decks** for the original deck browser with local saves. Double-click a deck to edit; Done saves it. Export copies Arena text and writes a private file for the custom-match launcher.
- Double-click **Forge Arena Custom Decks** to choose supported deck files. Cancel leaves the current game open.
- Choose Play/Draw if offered, Keep/Mulligan, then return cards with the original London drag interface when required.
- Double-click a land or creature in hand. Instants use the native target selector when required. Use Pass/Resolve and confirm attack/block choices.
- For manual multi-block damage, disable Auto Allocate Damage, adjust the split and press Done.
- Start again by running a launcher. It archives the previous session. The result screen's Continue/home route is still unfinished.

The older **Forge Arena Sandbox** and **Forge Arena Mixed Duel** shortcuts retain fixed-hand diagnostic scenarios.

## Source and runtime boundaries

Retail Arena remains unchanged. The private native lab runs in a Windows AppContainer with zero network capabilities; Forge runs separately with private preferences/cache. Assets, builds, captured wire messages, source evidence and recordings live under `D:\GAMES\CodexAssets\ForgeArenaSandbox`.

`ForgeBackend/verify_card_manifest.py` compares seventeen unique source mappings (sixteen ordinary names and the additional Isamaru commander) against the pinned owned Arena database and Forge definitions. It checks identities, types, creature subtypes, mana costs/colors and mapped abilities. Startup also checks explicit color identities against Forge. This previously caught and fixed Swiftclaw's incorrect Soldier subtype: both sources say Cat Warrior. The audit runs before backend compilation.

`behavior-ledger.md` distinguishes recovered source, implementation, rendered observations and remaining gaps. `MODLOG.md` preserves development evidence and failed attempts. [Historical checkpoints](docs/checkpoint-history.md) retain the original limitations; they do not override this current feature list.

## Evidence and checks

- Complete normal rendered practice match: `research/custom-deck-protocol/full-practice-*` on D:, 170 native states, natural turn 14 defeat, all 20 life states, 49 damage and winner match in 12 audit checks.
- Draw/cleanup/empty-library fixture: `research/draw-protocol/native-draw-*`, 29 states, no damage, natural draw-loss at 20/20, 12 audit checks.
- Manual damage allocation: `research/combat-protocol/native-manual-damage-*`, original 0/3 choice and actual Forge outcome.
- Source mapping audit: `research/card-manifest-audit.json` and `research/subtype-correction-native.json`.

Targeted checks are under `ForgeBackend/verify_*.py`. `verify_normal_duel.py` drives complete actual Forge matches using inputs, without feeding intermediate state. ParserProbe replays captured messages through the installed Arena parser; `ForgeBackend/audit_recorded_match.py` compares them with Forge's journal. Parser tests alone do not prove rendering; the native observations above were recorded separately.

## Dev logs

The four-hour checkpoint adds chapters 13–24. The new-work edit is 11:29; all 24 chapters together are 21:38. Both full-quality masters and separate full-duration chat copies are under `D:\GAMES\CodexAssets\ForgeArenaSandbox\devlogs\2026-10-21-combat`. Filenames are `Forge-Arena-Devlog-This-Checkpoint-2026-10-21.mp4` and `Forge-Arena-Devlog-Combined-2026-10-21-Four-Hour-Checkpoint.mp4`. All 12 new chapters and both compilations were accepted and acknowledged in the existing Atlas chat; delivery receipts are preserved privately. Earlier footage retains its historical limitations and corrected subtype bug.

The current Practice shortcut includes the Study deck. Current readiness and evidence summary: `research/four-hour-playable-readiness.json` and `research/four-hour-checkpoint.json` on D:.

The isolated native client still attempts some background startup requests, which fail name resolution. A final live snapshot shows an ancillary listening socket but no established connection; Forge has no TCP socket. The listener's exact component is unconfirmed. The zero-capability AppContainer remains in place. This is not a claim that every native background subsystem has been removed.
