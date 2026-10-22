# First broad supported card family

The first verified family checkpoint admitted **109 main-deck card names**: the prior
16 plus **90 plain creatures and three additional basic lands**. Public GitHub
test.6 remains unchanged at 16 until the consolidated update is published. The
full Arena catalogue remains unfinished; this change does not enable all cards.
The separate unfinished Paradox Engine working-tree entry is preserved and is
excluded from the verified release checkpoint. The subsequent252-name checkpoint
is documented in [card-family-expansion.md](card-family-expansion.md).

## Shared implementation

- Arena database color enum ordinals and Forge color bit masks are kept separate.
  All five colors, repeated colored symbols and mixed colored printed costs are
  represented. Native printed costs are compared with Forge definitions. Hybrid,
  snow and variable printed costs retain explicit fidelity gaps.
- Intrinsic mana ability IDs 1001-1005 are checked in the owned Abilities table
  against formatted W/U/B/R/G source text. Native offers and floating mana use the
  source card's actual ability ID. Multiple mana abilities still require a choice
  adapter and are rejected explicitly.
- Plain combat damage allocation no longer depends on creature names. Special
  keyword/legacy ordered allocations remain gaps. Original native unordered
  damage controls allow zero allocation to a recipient and require the engine's
  complete total to be assigned.
- Main-deck/Brawl basic-land exceptions include all five supported basics. Color
  identity and commander restrictions remain enforced.

## Family eligibility and evidence

Candidates require matching source name/types/printed cost/P/T, no native printed
abilities, no supertypes, no digital-only flag or linked faces, and no executable
Forge directives, keywords or Oracle text. This excludes future placeholders with
missing Forge effects and native cards whose rules are not actually vanilla.
`prepare_plain_family.py` reproduces the proposal from the baseline policy and
owned source data. Research policy admission is marked explicitly and cannot be
packaged as supported gameplay.

Completed checks for the proposed family:

- All 90 creatures: actual Forge cast offers, color masks, complete printed mana
  costs, source payment, stack insertion, resolution, P/T and summoning sickness.
  Wrong-color requests and all five basic activations are included: **656 checks**.
- Five representative new multi-block combat cases: free distribution, surviving
  recipients, marked damage, attacker deaths and no player damage: **53 checks**.
- Five normally shuffled complete matches: green, black, red, blue and five-color
  decks against the existing opponent; seeds 8100-8104; **35 outcome checks**.
- Every new creature's original native model and effective renderer art texture
  matches its exact owned printing and art ID: **271 checks for 90 printings**.
  The probe reads renderer material property blocks: the shared material retains
  MissingArt even while the effective per-renderer texture is correct.
- Original native callbacks cast/resolve Gigantosaurus, Fusion Elemental, Fire
  Elemental, Dune Beetle and Aegis Turtle. Their art, frames, costs and actual
  stats were visually inspected on the board. **23 checks**, an 11-state original
  parser replay, and original native activation checks for Swamp/Mountain/Forest.
- A real DPI-correct mouse double-click activated an Island, reached the original
  pointer handlers and produced actual blue mana. The stock automation driver
  used virtualized coordinates and lost foreground ownership; the existing
  per-monitor-aware driver worked. Native callback tests are distinguished from
  this physical-input evidence.

This supports a bounded primitive family. It is not exhaustive interaction,
complete native-match, animation-parity or per-card manual-game verification.
Per-family gates in the policy/report state the evidence precisely.

## Private evidence and backups

Evidence is on D: under `CodexAssets/ForgeArenaSandbox/research/broad-card-support`.
The promotion receipt links per-card, combat, full-match, native-art and new-mana
reports. Original callback footage is represented by inspected stills and wire
journals, not a devlog video. Native rendering remains the owned original client.
No Arena assets, account data or decompiled source belongs in the repository.

The original local-profile backup is
`C:/Users/loula/.universal-modder/backups/arena-broad-card-support/20261021-233644.zip`.
Pre-change policy, deployed adapter/manifest files and prior native IPC are
retained. All verified 109 Forge scripts are byte-identical between the supported
legacy snapshot and official 2.0.15; engine/build compatibility is checked separately.

## Remaining catalogue work

Remaining families include generic ability identity bindings, human choices,
keywords and counters, targeted/player/stack interactions, triggered and static
effects, replacements, tokens, alternate faces, extra zones and digital mechanics.
Successful construction alone never grants admission. Further work remains local
and is grouped into a single larger public update rather than per-step releases.
