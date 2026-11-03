# Alpha 15.9 — profiles and recovery

- Create, rename and switch local names/avatars. Decks, collection, packs and preferences remain shared on this installation.
- Host or join private two-player Commander through native client dialogs. Keep the host client open; both players must update.
- Reconnect a briefly interrupted guest connection without duplicating an uncertain action. This does not recover a crashed rules engine or migrate the host.
- Retry short Windows read locks; distinguish a normally closed room from a technical failure. A failed match can return Home and start another match.
- Queue only the pinned client version and a fixed failure code for reporting. Optional automatic GitHub delivery requires the player's own authenticated GitHub CLI, or a configured host for a relayed guest display failure. No private decklists, names, invitations, raw logs or maintainer credentials are sent.

Public matchmaking is planned and is not included. The measured sparse-object performance experiment remains disabled by default. No complete-card, full-game, two-household or crash-save restoration claim is made.

Validation: original native profile controls, actual HTTPS two-client room/reconnection, native failure-to-Home/new-match, native guest failure relay, one received/closed sanitized report, and the actual packaged Keep/land play. Detailed limits are in FAILURE-REPORTS.md and the development notes. Existing supported Arena variants and card admission policy are retained.
