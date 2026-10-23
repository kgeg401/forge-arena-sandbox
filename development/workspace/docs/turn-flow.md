# Turn flow — 0.2.0-alpha.6

Empty rules steps advance after native presentation completes, without a repeated
650 ms delay or a new user-facing action request at every substep. Forge retains
every rules step. Internal automatic rules requests are logged separately from
native player responses. Meaningful actions, choices, combat selection, full
control and explicit stops continue to hold for input.

The adapter now supplies native turn/phase annotations and next-phase metadata.
The original client displays its turn banner, phase indicator and contextual
Next / To Combat / End Turn controls. End-turn yield settings expire at the
appropriate supported boundary; Resolve All clears after the stack empties.
Native presentation readiness, rather than a fixed animation timer, gates progress.

## Evidence and limits

Eight real Forge/native-handler scenarios pass: empty progression, combat,
full control/stops, payable response, no-response progression, yield-unless-action,
yield-turn and Resolve All. Twelve rendered checks pass through original client
callbacks. The user played this installed build and accepted its turn flow.
The released native binary is byte-identical to that accepted local preview.
The rules engine, 370-name policy and catalogue are unchanged from alpha.5.

These checks do not establish complete Arena server smart-stop parity, all
per-phase stop semantics, complex next-phase lookahead (including first-strike,
extra phases and blocker branches), frame-by-frame animation parity or broader
card/payment support. Unknown behavior still reports fidelity gaps.

## Reproduction

Build TurnFlowProbe with owned compatible Arena assemblies and the pinned loader.
ForgeBackend/verify_turn_flow.py takes a prepared runtime config, explicit policy,
probe path, managed directory, empty-board fixture and fresh output directory.
It uses actual Forge games and original native parser/request handlers; headless
presentation readiness is controlled, so rendered/user acceptance is separate.

Private evidence: ForgeArenaTurnFlowParity-20261023/baseline-run-r2/report.json,
rendered-check.json and completion.json in the local Documents/Codex workspace.
Original game captures, decompiled references and private profiles are excluded.
Unreleased shared-card-mechanics work is not included in this release.
