# Reduce repeated visible-card work

`AdoptState` previously rebuilt the complete chooser-visible card list once per
token when detecting creations and disappearances. Each rebuild snapshots all
physical cards, creates an identity dictionary and may clone temporary chooser
views. That repeats work as the token army grows.

The adapter now derives current/prior views once per adopted transition and uses
ID sets for token membership. It reuses the same views for concealment and Class
retirement. Visibility validation, card order, token annotations, identity
changes and actual rules remain intact. The cache is local to one adoption;
no list survives a later state or choice. No shared helper or dependency added.

## Verification

`BridgeReplayProbe` replays recorded, genuine rules states through either compiled
adapter and its real GRE serializer/transport. Pass an owned managed-assembly
folder, a private root with the existing research-only manifest/board fixture,
a JSON array of recorded states, and a new output path. It refuses overwriting
a report; the bridge retains its existing research-path restrictions. Reports
contain full messages so before/after arrays can be compared without filtering.

Six recorded native-handler sequences produced **224 exactly equal GRE messages
across 106 transitions**: 36-token army growth/combat, phasing with equipment,
hidden search, triggered copies, reveal/replacement and draw/token triggers.
The selected historical scenarios had passing checks; they were not executed
again by this replay. Both builds compiled cleanly.

Three independent paired runs of the 36-token sequence retained identical output
and allocated **17.55–17.59% fewer temporary bytes** in the measured adoption
calls. Allocation dropped from approximately 115.7 MB to 95.4 MB over its 39
transitions. Elapsed times were lower in these bounded runs but include cold
runtime/JIT and file I/O; they do not establish gameplay frame-rate gains.

Source, pinned binaries, exact input/provenance, full outputs and repeated
measurements are retained in the private `ForgeArenaEfficiency-20261102` evidence
folder. No installed client, saved profile, published package or update channel
was changed. New live gameplay, exhaustive interactions, Class-specific replay
and rendering parity were not verified in this pass.

This is work reduction, not code golfing. The production change adds two net
source lines including its comment; removing tests or safeguards to reduce the
repository line count would not improve gameplay.


## Fresh interaction acceptance

The follow-up pass runs actual Forge plus original Arena handlers with the exact
optimized NativeHost assembly, rather than replaying saved results. Thirty-seven
bounded scenarios pass 308 checks: token-army growth/combat, three phasing cases,
Wizard Class levels/bounce/recast, fifteen mass-arrival/copy/poison cases, ten Horde
revival cases, four commander preparation/cast boundaries, pod spectating and two
Horde flow cases. The ordinary Horde case uses the real 200-card pool; its passive
survivor loses naturally. Small mechanic pools remain explicitly labelled fixtures.

A separate ten-player run with full Isamaru/Emry/Selvala bot lists reaches turn61,
with six real attacks respecting nearest-left and combat damage from three bot
seats. Seed7274 again develops boards but makes no attacks, so its combat assertion
fails and is preserved. This known native AI behavior was previously diagnosed
with legal attacks; seed13 is the previously verified combat case, not a new sweep
or an AI rewrite. No full-pod winner or natural ten-to-four elimination is claimed.

The mode guide and packaged README now explicitly include both Horde queues and
ten-player Commander. Coordinator fixtures add six saved-deck/Horde-route checks
(51 total). Installation/publication receipts remain in the private
ForgeArenaInteractionRelease-20261102 evidence folder.
