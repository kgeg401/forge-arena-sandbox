# Four-player Commander pod

The local `SandboxCommanderPod` queue runs one authoritative Forge game with one
human and three bots. It appears under Brawl as **Commander Pod (4 Players)**.
It uses the existing Arena-card sandbox deck policy: 99 main cards and one
admitted commander, singleton and color identity. As in the existing 40-life
queue, this includes admitted Arena planeswalker commanders; it is not a claim
of complete tabletop Commander deck legality or partner support.

## Play

- Start the dedicated local client, open Play, choose Brawl, then Commander Pod.
- Choose a saved deck and Play. The initial opponents use the existing easy
  Emry deck with basic lands and defensive creatures.
- Each player starts at 40 life. Forge enforces 21 combat damage from one
  commander, one free first mulligan, and the multiplayer first-player draw.
- **All players / Tab** shows one shared table: your board below three
  opponents. Player panels sit above their corresponding opponent lanes;
  your own panel stays at the lower left. Each shows life, public zone counts,
  and turn/priority or combat status. Seat colors stay consistent throughout.
- Click a player panel or use **F1–F4** to focus that player's board. Your own
  battlefield remains visible beside the chosen opponent; the other players'
  status panels remain available. Click the same panel or press **Tab** to
  return to the table. Dense battlefields fit their lane and offer focus for
  a closer look.
- Underlined **Graveyard** and **Exile** counts open that player's original
  native public-zone browser. Empty counts are informational. Browsing does
  not switch the focused player or construct a separate card list.
- **Details / F5** opens the original message dialog with all four players'
  life, elimination status and commander damage received, named by source.
  Those records remain available after a player is eliminated.
- To attack another player, select the attacker, click that player's avatar
  or highlighted player panel, and confirm the attacker declaration. A spell
  that targets players uses the same panels. Ineligible panels are disabled
  during selection; targeting returns to the table so other players stay
  visible. Target legality remains Forge-owned.
- When the human is eliminated, this local practice session pauses and offers
  Return Home. The surviving bots are not assigned a fabricated winner.
- Return Home stops the owned rules process; another match can start without
  restarting the client.
- An explicit native turn yield started during a bot's turn carries through
  the remaining opponents until your next turn. Yield-unless-action still
  stops for an opponent's spell or attack; normal response windows remain.
  The native end-turn arrow chooses unless-action normally and full turn yield
  when Shift is held. A normal Next/Pass button remains a single priority pass.

## Implementation

Forge's four original player objects have stable seats for the lifetime of the
match, including after elimination. Each seat has its own life, commander,
hidden hand/library, graveyard and counters. Player targets, attack recipients,
damage, life events and owner/controller identities use those seats.

The installed Arena client selects its existing quadrant camera and avatar
layouts when the match roster has more than two players. The local seat is
configured before scene initialization. The bridge sends a multiplayer GRE game
with four teams and independently owned zones. Eliminated players transition to
the native Removed status and their departed objects are retired.

The installed battlefield has one board. The presentation adapter maps the
four native player layouts onto that shared board instead of copying its mesh
four times. It transforms native card movement goals, colliders, zone origins,
stack badges, paging arrows, avatars and camera positions together. Focus
views retain the local battlefield and one opponent, with the other cards off
camera. Dense battlefield layouts scale to stay inside their ownership lanes.
The mapping is scoped to this four-player GameManager and is inert in duels.

The added screen-space panels use the installed Arena font and panel outline.
They show stable identities, exact life and public counts, turn versus priority,
legal player targets, attack recipients and eliminated seats. Player selection
delegates to the original native workflow and its CanClick check. Native card
browsers, stack, hand, action buttons, animation scheduling and rules keep their
existing paths. The added panels hide while native browsers or Settings are
open; graveyard/library/exile browser headings identify their owner. The old
corner zone-count widgets are suppressed in pods because their two-player
positions and opponent data are ambiguous here. Per-seat public counts take
their place; the original widgets retain their behavior in regular Brawl.

## Verification tools

Build `NativeHost` and `HeadlessBridgeWorker` against the pinned owned assemblies
and compile `ForgeLandEngine.java` against the pinned Forge runtime. Use an
isolated research root: the headless worker rejects a root containing MTGA.exe.
Each verifier accepts `--config`, `--worker`, `--managed`, `--fixture`, and an
unused `--output` directory.

- `ForgeBackend/verify_commander_pod.py`: four 40-life seats, separate commanders,
  free mulligan and turn rotation. `--full-match` additionally checks attacks to
  seats 3, 4 and 2, stable identities after elimination, 21 commander damage at
  positive life, and the final winner through the native parser and handlers.
- `ForgeBackend/verify_commander_pod_targets.py`: a normally shuffled Emry deck
  containing Jace, Wielder of Mysteries; target seats 3 and 4, independently mill
  their libraries and draw for the human. Seed 14 places Jace in the opening
  hand; no intermediate rules state is supplied to the reconstruction.
- `ForgeBackend/verify_commander_pod_combat.py`: two creatures attack seats 3
  and 4 in the same combat, both players take the correct damage, seat 2 stays
  untouched, and only the commander recipient records commander damage.
- `ForgeBackend/verify_commander_pod_tax.py`: cast Emry, Unsummon it, accept
  the native command-zone return, inspect the two generic tax and recast it
  using five Islands, without injecting mana or intermediate state.
- `ForgeBackend/verify_commander_pod_boundaries.py`: two London mulligans, the
  multiplayer first-player draw, and quick concession during both opening-hand
  and main-phase workflows without inventing a winner. A normally shuffled
  Necropotence deck also pays 40 real life, reaches zero and leaves the other
  three players alive; no life total or intermediate state is injected.
- `ForgeBackend/verify_commander_pod_yield.py`: a payable instant remains in
  hand while native turn yield crosses all three opponents, then returns
  control. The unless-opponent-action variant stops at the first bot spell.
  It uses `TurnFlowProbe` in place of the normal headless worker.
- `ForgeBackend/verify_commander_modes.py`: existing two-player Brawl and
  40-life Commander regressions.
- `packaging/verify_client_service.py`: queue validation, process ownership,
  duplicate/stale requests, cancellation and preservation of the saved library.

Rendered acceptance is separate. Check a clean native launch, all four players,
close-up/table controls, land and commander plays, library searches, attacks to
different avatars, bot responses, elimination notice, Home return and a second
match. Parser checks alone do not establish those outcomes.

The 2026-10-26 shared-table checkpoint exercised native land and commander
casts, attacks to seat 4, Jace player targets at seats 3 and 4, automatic table
return for targeting, a populated owned graveyard browser, four focus views,
35-permanent mixed boards and a 49-permanent normal match. A normally shuffled
passive fixture reached 22 commander damage at positive life: the eliminated
panel showed OUT, was disabled, and retained its seat while the other players
continued. Pod-to-Brawl-to-pod scene changes retained normal two-player land
play and recreated the four-player panels. Rendered panel bounds were checked
at 1280x720, 1600x900, 1920x1080, 2560x1080 and 1280x960. These checks do not
establish complete Arena parity, every card interaction, or every native
screen's behavior at every aspect ratio.

Real mouse input additionally exercised focus, automatic table return on
entering combat, the mapped attacker collider and a seat-4 defender panel,
including the native attack line. It caught a browser-heading path missed by
direct holder-pointer tests: real graveyard/library card input calls the
holder's View method directly. Those View methods now supply the owner heading;
all three native graveyard lists were checked against their own card owners.
The new panel controls also opened a five-card local graveyard and a four-card
opponent exile after a real Tormod's Crypt activation. Both lists retained
their actual owners, empty-zone controls were disabled, and public browsing
left the rules-state hash unchanged. Real mouse clicks exercised both controls.

The native worker also checks that a planeswalker attack retains the blocker
destination in the turn UI. A departed planeswalker is represented by Forge's
synthetic defender `Card(-1, "<Nothing>")`; it is retired from the presentation
link rather than treated as a real card or redirected to its controller.

## Checkpoint limits

- One human plus three local bots; no network connections or four-human lobby.
- The initial bots share the easy opponent list; opponent deck selection is
  not exposed in the native menu yet.
- The queue inherits the existing experimental card and choice limitations.
  Four seats do not establish support for every card or multiplayer interaction.
- The added four-player layout is local presentation, rather than an original
  Arena four-player UI. Cards in a crowded overview become smaller; use focus
  or the native card viewer to read them.
- Synthetic Tab input did not verify the keyboard shortcut. Physical keyboard
  acceptance remains pending; the clickable view controls were exercised.
- The Details dialog is an added local inspection control using the installed
  native prefab. It is not an assertion that Arena ships a four-player queue.
- The deterministic full-match fixture intentionally gives the bots only Plains
  for a multicolor commander. It checks rules, targeting and elimination, not AI
  strength. Very late impossible-mana AI searches can be expensive; use the
  bounded fixture and keep failures as evidence.

Private game assets, profiles, native decompilation and raw research evidence
stay outside the repository. A public release still requires packaging and
installed-client acceptance; this document does not establish publication.

For a private checkpoint, `packaging/launch_local_preview.py --spec <private.json>`
verifies a pinned release and owned native build, launches a separate prepared
AppContainer lab, and reuses only that lab's existing preview. It does not
replace the installed client or close another lab's parked match. The private
spec and prepared owned assets are not distributable installer inputs.
