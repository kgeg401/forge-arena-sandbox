# Phase-specific stops

The bridge previously treated the presence of any permanent or temporary stop
as a global pause. A future upkeep stop could therefore prevent an unrelated
spell from resolving in a main phase. Protobuf's generic merge also appended
Set/Clear commands, leaving old active records behind after a toggle.

The adapter now maintains one stop state per phase and side. Only an active
stop for the current phase and side holds progression. Clearing a stop replaces
its previous state; future temporary stops survive until their requested phase,
then clear when that phase is left. Full control, valid response windows and
explicit attack/target/payment/damage choices remain player decisions.

The phase/side/status contract was checked against the installed client's
original phase-ladder controls and protobuf types. This is a local bridge
policy; it does not reconstruct Arena's server-side smart-stop engine.

The old original-handler case reproduces an unrelated spell pause. The corrected
17-case matrix passes, including counterspell responses, full control, yields,
Resolve All, combat presentation, active/future/wrong-side stops, clearing,
clear-all, and actual permanent/temporary upkeep cycles. Contract checks also
reject invalid settings before mutation and preserve unrelated controls.

Private original-renderer comparison uses the same rules, scene and native
phase icon. The old bridge pauses at the current main phase with no actions.
The corrected bridge reaches the next requested upkeep, accepts the original
Draw and Main buttons, and clears the original icon while leaving a real land
playable. The Beginning icon groups upkeep and draw; its local-player scope
remains Team even when its original status is Clear.

These are bounded private sequences, not full-match or complete UI-parity
certification. Per-session fresh backups and independent hash restoration are
recorded under `ForgeArenaEightHour-20261102`. No live install or publication.
