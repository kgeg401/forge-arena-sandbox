# Technical reports and recovery

The client can automatically queue a technical report when its rules process
exits unexpectedly, startup times out, an explicit rules gap occurs or the
native match display fails. Reports contain only the installed release version
and a fixed failure code. They exclude your name, decks, collection, invitations,
file paths, detailed logs and sign-in data.

Sending uses an existing GitHub CLI sign-in on this PC. The client does not
install credentials or include a developer's key. Without the CLI, sign-in or
a working connection, reports stay queued; you can still play. This is not an
anonymous central reporting service.

A connected guest's display-failure code can also reach the host through the
authenticated private room. The host supplies its own release and match context
and queues the code locally. Sending to GitHub still requires the host's own
sign-in. A host queue acknowledgment does not mean GitHub received the report.

Repeated failures are deduplicated and rate-limited. An uncertain send is
checked against existing GitHub issues rather than blindly posted again.
An unconfirmed report can remain pending for manual review. Old-version
evidence is retained locally. A local status file distinguishes queued,
unconfirmed and delivered reports; reporting failures do not stop gameplay.
An explicitly closed private room is explained locally and does not create a
bug report. Setup errors keep their diagnostic details on this PC.

Short file-sharing interruptions and temporary guest connection loss have
bounded retry paths that retain the same pending action. They do not replay
spells or skip animations. A dead rules process cannot resume from its display
snapshot: **Return Home** starts a new match. Full match saving and crash
restoration remain unsupported.
