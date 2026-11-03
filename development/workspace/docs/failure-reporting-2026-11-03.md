# Bounded automatic technical reports

The coordinator queues fixed codes for rules-owner exits, startup timeouts and
explicit rules-fidelity gaps. The original native error dialog also emits a
code-only local packet qualified by the current client and match request.
Stale packets, extra fields, arbitrary error text and ordinary cancellations
cannot create reports. An unavailable reporting service never ends a match.

Only the package-pinned release version and an allowlisted failure code enter
the fixed GitHub issue template. Names, local profile IDs, decks, collection,
paths, invitations, tokens and detailed logs are excluded. Each version/code
has a stable deduplication marker. Local events and delivery receipts remain
separate from game actions and presentation acknowledgments.

The publisher runs on a background thread and uses the player's existing
GitHub CLI authentication to the fixed project repository on github.com. It
does not install credentials or include a maintainer key. Without the CLI,
sign-in or a working connection, reports stay queued locally. This does not
provide an anonymous public reporting service for other players. A connected
guest can relay the single fixed display-failure code through its authenticated
room to the host's outbox; the host supplies its own version and match context.
No guest credentials or private fields travel. The host must have reporting
enabled and its own authentication for GitHub delivery. A code queued on the
host is not a GitHub delivery receipt. Source
checkouts without pinned release metadata do not start automatic reporting.

Each version has its own bounded outbox, three creations per day and at least
ten minutes between creations. Older-version evidence is retained. Public
cross-installation deduplication is a bounded lookup, not an atomic global
reservation; simultaneous first reports from separate PCs can race.

The attempted state is committed before sending. If a POST receipt is lost,
the publisher reconciles the existing issue and never automatically replays an
uncertain creation. A send that never reached GitHub can therefore remain
unconfirmed and need manual review. Delivered issues are not posted again.
Queued, sent and unconfirmed counts have a local status file. This is technical
reporting, not game saving or automatic reconstruction of a dead rules engine.

`verify_failure_reports.py` passes 26 contracts, including actual local HTTP
receipt loss and reconciliation. `verify_failure_reporting_integration.py`
passes 22 coordinator, ownership, privacy and worker-isolation contracts.
These fixtures do not count as native gameplay.

Twenty-one actual local HTTP relay contracts additionally check guest-only
authentication, fixed fields, idempotence, host write failure, stale contexts,
solo-mode rejection and unchanged game actor/revision. Two initial fixture
setups were rejected by the existing UUID/private-view guards before testing
the relay; the successful fixture meets those original guards. This is not a
rendered two-PC reporting test.

An actual original-client case opens a rules match, deliberately stops only its
owned engine, queues the fixed exit code locally with the publisher held
offline, uses the original Return Home button and opens a different genuine
match in the same client. Both original error and replacement-board captures
were inspected. This verifies the failure/re-entry path, not restoration of
the stopped match. A separate attempted response-lock fixture did not trigger
a native read exception and earns no read-recovery acceptance.

A bounded actual background-publisher self-test sent exactly one issue with
version `0.2.0-profiles.2` and code `REPORTER_SELF_TEST`. A fresh GitHub read
verified its exact body and receipt; a second flush sent nothing. The test
[issue](https://github.com/kgeg401/forge-arena-sandbox/issues/1) was then closed,
and its closed state independently fetched. No real player failure data was
published. This establishes delivery with this PC's existing authentication,
not an installer, another PC's authentication or a public release.

Setup failures are now covered by the same local diagnostic boundary as a
running network session. Two before-fix checks reproduced a missing constructor
error receipt and an ordinary authenticated HTTP 410 closure being classified
as a rules-engine bug. Thirteen focused contracts now preserve the original
setup error locally, retain validated session context, survive a failed
diagnostic write and distinguish a closed room from `NETWORK_SESSION_FAILED`.
An explicitly closed room gets a useful local explanation without a GitHub
bug report. These are HTTP/ownership fixtures, not another native game claim.
