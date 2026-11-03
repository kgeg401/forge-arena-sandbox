# Cosmetic profiles and an in-client private lobby (work in progress)

Local identities share the existing saved decks, collection, pack receipts and
settings. The original Profile navigation button opens original Arena dialogs.
Create/rename uses a cloned original deck-name input, with three source-backed
avatar choices: Ajani Goldmane, Sparky and the tutorial planeswalker. Cosmetic
data is saved separately in local-profile/identities.json. No collection grants
or deck migrations happen when an identity is created or selected.

The current maximum is 32 identities with names up to 32 UTF-16 code units.
Malformed, duplicate, read-only and stale writes are rejected while preserving
the existing file. Profile changes are unavailable during a queued/live match.
The first stored identity is the legacy Local Player. These are local display
identities, not authenticated Arena accounts.
The authored update/rollback suite now includes identities.json alongside the
shared decks and packs; all 44 checks preserve the entire profile and its backup.
This is disposable-fixture coverage, not a recipient-PC installation.

Private Commander now chooses Host, Join copied invite or Cancel inside the
original client dialogs. A hosted room offers an original-styled Copy Invitation
button. The external Tk connection window has been removed. Current client and
match request IDs qualify room status, preventing stale room status from opening
another request's controls. Existing authenticated roles, presentation barriers,
compatibility validation and sole rules owner remain.

Room peers exchange only the selected name/avatar. The authenticated profile
endpoint locks each role's identity for that room; the guest view maps identities
to native local/opponent seats. Local profile IDs, collection and other saved
identities are not included. Different saved decks remain permitted.

## Current acceptance boundary

20 cosmetic storage contracts, 27 lobby-boundary contracts and 24 cosmetic-file,
real local HTTP and peer-seat projection checks pass. Existing coordinator and
room/view suites pass. One private original client completed profile/name/Sparky
selection, preserved all shared saved JSON bytes and opened/cancelled the original
in-client Private Commander dialog back to Home. Screenshots were inspected;
an initially overlapping name input was corrected.

Further native checks cover switching identities, renaming while preserving the
same ID/avatar, duplicate-name rejection without file changes, and refusing
profile edits while a hosted room waits. Original Cancel closes the hosted
connection and returns Home. Name entry now receives native input focus, and a
duplicate name gives a specific correction. The final profiles-only native case
passed nine checks. Dialog QA reads the original registered, interactable button
list, excluding retired controls awaiting end-of-frame destruction; original
button callbacks and animations remain in use. No physical typing test is claimed.

Two additional original clients subsequently used native profile creation,
Host, Copy invitation and Join copied invite through a genuine public HTTPS
tunnel. Both native boards displayed the correct opposing names and Ajani/
Sparky portraits. Original play/draw, keep, land, commander-cast and attack
controls completed 16 callbacks through turn six, with both commanders on the
battlefield. This verifies two local clients through the internet endpoint;
two-household testing, interruption recovery and complete games remain separate.

The borrowed native copy's 36 mutable groups and four immutable assets were
restored; the groups were independently rehashed. Raw evidence, source-backed
API research and earlier failed test-driver attempts remain private under
ForgeArenaProfilesRecovery-20261103. No installed-client or public release update
has been made. The two additional borrowed copies were also restored and
independently checked: 38 mutable groups and four immutable hashes per copy.
Public-queue matchmaking is not implemented; this is the existing
private internet room flow inside the client.

## Transient connection input safety

A fault-after-acceptance test reproduced an input identity bug: if the room
queued an action but its HTTP reply was lost, the coordinator could generate a
new command for the same native input on the next board revision. It now retains
the exact command before network I/O, reuses its identity on retry, and consumes
the native request only after the known result. Gateway 502/503/504 errors remain
uncertain connection failures rather than false gameplay rejections. Existing
authentication, ownership, board and presentation gates remain.

50 fault/contract checks pass, covering failures before and after
acceptance, actual rejection results, duplicate prevention and presentation
acknowledgements. Startup also retains the same invitation/join identity through
lost join, profile and deck receipts. Repeating an already locked identical deck
remains valid after rules start; replacements and new post-start decks are
refused. Startup retries have a 90-second limit, cancellation and immediate
authentication rejection. These include real HTTP tests and simulated timer/
cancel bounds. A separate real Forge two-human sequence completed 100 distinct
commands through turn six with one cast reply deliberately lost after HTTP
acceptance. That cast reached Forge once and both commanders resolved once.
That test supplied presentation acknowledgements and does not establish a
durable save or recovery after the coordinator exits.

A subsequent rendered test used two original local clients through public
HTTPS, with their actual native presentation acknowledgements. It blocked guest
I/O for 35 seconds after the room accepted a commander cast, deliberately losing
the receipt. The same command envelope reconciled after reconnection, and play
continued in the original session through turn eight. Seven additional original
UI callbacks succeeded after reconnection. Both restored boards were captured;
11 checks passed. This covers a bounded guest I/O outage with the host/tunnel
still running, not two-household testing or recovery after a host/engine restart.

## Separate performance experiment

A private flag tests native diffs containing only exactly changed game objects.
Every state, annotation and interaction is retained. In the same real seeded
288-trigger sequence, full object updates fell from 93,181 to 587 while all 441
captured original parser states/events and all rules states matched. Headless
action timing was essentially unchanged (52.86 versus 52.26 seconds), so this is
data-reduction evidence, not a demonstrated rendering/frame-rate improvement.
Six actual native payment/effect groups and three phasing scenarios pass with
the experiment enabled.

One rendered baseline and two independent candidate runs also matched all 441
persistent native states and 1,868 annotations through the final life gain,
including exact card identities.
Only the separately verified per-run match ID was qualified for comparison.
Original client screenshots show the 288-trigger stack and final 108-token army
with 452 life. The baseline completed the sequence in 66.58 seconds versus 62.38
and 62.48 seconds for the candidates; bounded 20-second samples measured p99 frames at
41.68 versus 20.84 ms, with the same 6.95 ms median. These are one-scene results,
not a general speedup or complete animation timing equivalence. The same windows
used 39.84 CPU seconds for the baseline and 48.72/45.75 for the candidates while
rendering more frames; this does not demonstrate lower CPU use. Wider event
fidelity and load measurements remain; ordinary clients do not enable it.
