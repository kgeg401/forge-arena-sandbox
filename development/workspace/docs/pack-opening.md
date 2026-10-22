# Local pack-opening checkpoint

Run `Open-Packs.ps1` (or the Forge Arena Packs desktop shortcut after installation).
The original booster chamber, pack carousel, opening rig, rare reveal particles,
card layout, hover preview, Continue, Open x10 and opening preferences are used.
This opens a fresh isolated lab instead of a match. Local profile files survive
launches. Normal practice remains a separate launcher.

## Local inventory

Each local profile starts with 100 packs for each of 51 source-derived catalog
sets. The catalog contains 13,326 primary draft-content printings from the pinned
owned Arena database. Collection copies, pack balances and request receipts are
committed as one transaction under the private lab's `local-profile/packs.json`.
The previous version is retained as `.bak`. Replaying an accepted opening must
not grant rewards again. These balances never refer to the official account.

The custom distribution is five distinct commons, two distinct uncommons and
one rare/mythic. When mythics exist in a set, that slot chooses mythic one eighth
of the time. This is explicitly **sandbox collation**, not a reconstruction of
retail odds, bonus sheets, wildcard tracks, fifth-copy compensation or duplicate
protection. All collected copies are retained. No ownership restriction has yet
been connected to the deck importer. Match support remains ten card names.

## Source and rendering evidence

Owned `BoosterChamberController.Coroutine_OpenBoosters` calls the inventory service
and then `VisuallyOpenBooster`. A scoped Harmony hook replaces the service-facing
coroutine with a local transaction and retains the native presentation method.
Scoped inventory getter hooks supply its local pack/card views. Other inventory
instances and the normal match bridge are not changed.

The owned MainNavigation scene supplied its 1920x1080 content/popup canvas
settings, orthographic camera planes and main/fill lights. The popup camera must
be a URP overlay in the base camera stack; an ordinary second camera erased the
screen. The original hover prefab is a GameObject with a child view, not a root
View_CardRolloverZoom asset.

Native warm-up parents the first pooled card to the screen, then detaches it
while preserving world pose. In this local host its next use retained local
z=28.33 and scale=0.67 instead of the owned prefab's z=0/scale=1. A scoped pool
postfix restores the original prefab pose before the native spawner attaches the
card. Recorded inspection then shows all eight cards at matching final depth
and scale; the previously incomplete eighth card renders fully.

## Validation and boundaries

`PackProfileProbe` exercises the actual save implementation, idempotence,
restart, invalid requests, open-ten, exhaustion and reward accounting. A native
AppContainer run is necessary as well: Mono's File.Replace failed despite the
desktop checks passing. Saving now uses a flushed same-directory pending file,
retained backup and atomic Windows MoveFileEx replacement without merging ACLs.

`PackBackend/audit_native_packs.py` compares every durable receipt against the
catalog, balances, complete collection and native displayed identities/final
animation state. Pixel appearance and mouse interaction are checked separately.
Private source, screenshots, probes and audits are under
`D:\GAMES\CodexAssets\ForgeArenaSandbox\research\pack-opening`.

All 51 carousel entries are present; individual packs/cards across the entire
catalog have not been visually audited. Narrow local set metadata supplies only
the set-code/collation mapping needed for pack art. Publication/format metadata,
store groups and franchise-badge parity are not reconstructed. The original
home/navigation route, collection browser and deck builder remain unfinished.

Final hour checks: 19 persistence assertions pass. Native audit covers five real
transactions/fourteen packs/112 copies and a full unchanged-profile restart.
The 80-card receipt matches every native revealed ID and final animation flag.
Manual rare reveal, hover and Continue were observed. Automated manual dragging
through the bulk grid did not reliably scroll; native drag is enabled and input
raycasts reach the expected original controls, so human bulk browsing remains
unverified. This is a remaining input-validation gap.

Chapter25 (1:11) and the updated25-chapter compilation (22:49) were accepted
and explicitly acknowledged by Atlas at13:19America/New_York. Both chat files
are under9MB; full-quality masters, source recordings, validation and delivery
receipts remain on D:. Normal practice also passed a fresh native startup smoke
check after these shared-host changes.
