# Internet multiplayer: playable two-human integration

The later alpha 15.mp.1 integration adds the normal saved-deck Play queue,
private Host/Join lobby, pinned official cloudflared download, authoritative
two-human Java controller, paired per-player native views and display ACK fences.
All 107 inherited human callbacks execute with their actual player context;
per-player mulligans, turn preferences and explicit payment ownership persist.
Only this queue enables human-duel behavior; existing solo/bot modes keep their
normal controllers.

Two separate original native clients on one PC played through public HTTPS,
cast Isamaru and Emry, dealt combat damage, displayed opposite native results and
returned Home. A same-process second room reversed hosting roles and verified
the guest's completed result survives host departure. The first terminal-close
failure remains archived. The native waiting-seat Intermission failure was
reproduced and fixed; legitimate automatic `rules_` inputs are accepted alongside
clicked `arena_` inputs. Network-specific labels replace bot labels in this queue.
Source/runtime/catalogue compatibility is checked before joining. Invites contain
secrets and are not included in public evidence.

The final rules build passes separate room/rules/view/presentation/coordinator,
Horde preparation, ten-player bot spectating and token-combat checks. These do
not establish every card combination. Two physical households, long-duration
disconnect behavior, host migration, crash-resume and human pods remain unverified
or unimplemented. See [consumer instructions](../packaging/public-docs/MULTIPLAYER.md).

## Historical foundation checkpoint (before native integration)

This is an **unreleased two-player Commander foundation**, not a multiplayer
option in the installed client. The normal Alpha 14.10 download still runs
local games. No installer, updater channel, installed client or saved deck was
changed by this pass.

## Implemented source

| Part | Behavior | Verification |
| --- | --- | --- |
| `packaging/multiplayer_room.py` | Private invitation, separate player credentials, exact compatibility check, own-view-only reads, command deduplication and reconnect with retained credentials. HTTPS is required outside loopback. | 41 real loopback HTTP/contract checks. |
| `packaging/multiplayer_rules.py` | One host coordinator publishes paired stable Forge views and submits each authenticated command once. Wait for actual matching acknowledgement, hold on disconnect, retain rejection, refuse hidden/unoffered priority actions. | 18 IPC/offer checks. Earlier adapter revision also drove a real HTTPS game. |
| `packaging/multiplayer_view.py` | Present either global rules seat as Arena's local seat one; reverse attack/choice player references. Preserve card/ability/stack/decision identities and existing visibility. | 18 projection checks; both recorded real-human perspectives passed the existing bridge and original Arena GRE parser. |

These files are deliberately **absent from the release's `OWN_SCRIPTS`
allowlist**. There are no misleading Host/Join buttons pointing at an
unfinished engine or local bot queue. Product Java and native source remain
unchanged.

The two-human Java controller is currently a private research prototype. It
binds authored human callbacks to the actual player on Forge's sole owner
thread and writes distinct private views at stable boundaries. Its broader
callback/global-state behavior still needs auditing before product promotion.

## Actual proof and its limits

Two separate scripted Python processes on this PC connected through a real
public HTTPS tunnel to a real two-human Forge Commander game. Both kept their
opening hands, played three lands, cast their commanders and passed priority;
combat and a genuine concession ended the game at turn seven. All 123
submitted rules actions were acknowledged by Forge. Neither player received
the other's unrevealed hand identities. A later revision also removes deck
lists, deterministic seed and internal diagnostic metadata from network views.

This establishes an internet transport/rules slice. It does **not** establish
two physical PCs, two household networks, rendered guest controls, useful
latency under real network loss, or arbitrary Commander interaction parity.
The scripted basic test decks are legal-size Commander control decks, not a
deck-strength or complete card-catalogue test.

The final local HTTP two-process case passed 423 actual Forge commands over
20 turns, including a targeted Winds of Rebuke, the other human's commander
return, subsequent play and a genuine concession. It uses the latest
room/rules adapter and does not claim this larger case ran over public HTTPS.
The two decks were deliberately simple singleton control inputs; four distinct
bounce spells replaced four Islands in the guest deck, with Orvar as commander.

All **424 actually published views per player** from that case passed seat
projection, the unchanged native bridge and the original GRE parser: 848 GRE
messages for each player, with exactly one terminal result and opposite
win/loss perspectives. This is still recorded message projection, not Unity
rendering or live native input. An earlier approximate response-derived replay
had two terminal events for the host because it included both an acknowledgement
and final paired snapshot. That evidence is retained; the final check uses
the actual published stream without deduplication or smoothing.

An additional opening-game diagnostic exercised a human blocker and a human
commander-return choice. The targeted-spell coverage assertion correctly failed
when the chosen spell reached the graveyard through Emry's mill rather than a
cast. That attempt is **not a passed targeted-spell sequence**. A later
public-HTTPS attempt reached a real target choice, but the scripted player
could not answer its own overly restrictive targeting policy; it remains a
failed test. The final local case corrected the policy without changing game
rules. An earlier duplicate-card fixture was rejected by the existing singleton
validator before startup. Do not describe any of those failures as engine fixes.

The host owns the complete rules state and therefore can see all cards. The
guest only receives their own rules-produced view. A host-authoritative private
friend match is the chosen trust model; this is not a cheating-resistant public
service. The HTTPS test relay terminates TLS; it is not end-to-end encryption
against the relay operator. Access tokens are not placed in command lines or
request logs. All test tunnels and processes are bounded and closed afterward.

## Next acceptance gates

1. Replace the research-only context prototype with an audited product
   two-human controller. Separate remaining per-player preferences and startup
   state; keep unsupported callbacks explicit. Preserve solo/pod/Horde behavior.
2. Connect host/join, saved-deck exchange, authoritative deck validation,
   complete runtime/catalogue compatibility pins and host-owned lifecycle to
   the existing coordinator and original menu controls.
3. Apply guest seat projection and receive unsolicited opponent updates without
   discarding native pending requests or resolving animations out of order.
   Validate exact published views through the original parser and actual Unity
   controls for both players, including targeted effects, response priority,
   commander replacement, elimination and correct single end-of-game result.
4. Test dropped replies, disconnect/rejoin and host closure without invented
   passes, duplicate payment/casts, secret-card leakage or silent AI takeover.
   A retained token in one running test process is not restart recovery.
5. Complete a two-PC internet game before including multiplayer in the normal
   package. Four-/ten-player human pods and cooperative Horde are later gates.

## Reproduce source checks

From the repository root with Python 3.10 or newer:

```powershell
python packaging/verify_multiplayer_room.py
python packaging/verify_multiplayer_rules.py
python packaging/verify_multiplayer_view.py
```

These three scripts create only temporary/local fixtures. They do not launch
Arena, install a service, open a public room, change firewall/DNS settings, or
establish native multiplayer readiness.

Private evidence and prototype source:
`C:\Users\loula\Documents\Codex\ForgeArenaMultiplayer-20261102`.
Use the per-attempt reports and process/cleanup receipts, not a stale aggregate
result left by an earlier passed case.

## Upstream references

Forge already has [network play](https://github.com/Card-Forge/forge/blob/master/docs/Network-Play.md)
and [network testing documentation](https://github.com/Card-Forge/forge/blob/master/docs/Development/Network-Testing.md).
The Arena adapter's one-human assumptions still require reconstruction;
upstream network support alone does not make this frontend multiplayer.
The first connectivity experiments used an ephemeral
[Cloudflare Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/),
not a deployed match service or a permanent friend invite.
