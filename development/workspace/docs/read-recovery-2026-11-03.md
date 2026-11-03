# Retain a rules response through a short Windows read lock

A real Windows exclusive-file lock reproduced an exception from the background
response reader. Its faulted task kept failing on subsequent polls; the native
adapter treats that exception as a stopped display. This failure did not require
a bad card or rules-engine exit.

The reader now retries only sharing violations (32/33/1224, including Mono's
message form) and access-denied races, for at most one second. Background
response retries wait only on their worker; cached decision/network snapshots
defer to a later poll. Persistent access errors and malformed payloads still
fail explicitly. No input is resent, no response is skipped, and request/session
validation and original presentation barriers remain unchanged.

`packaging/SharedReadRecoveryProbe` links the actual helpers and passes fourteen
contracts, including real exclusive locks, nonblocking polling, unchanged
response adoption, permanent parse failures and bounded persistent denial.
The existing eleven asynchronous ownership checks also pass. Build these with
an explicit `SandboxBuildRoot`, then run the resulting DLL directly.

A fresh original-client regression with the default full messages casts Raise
the Alarm and three Second Harvests through original controls. It resolves a
288-trigger stack to 108 tokens and 452 life. All 441 persistent native states
and 1,868 annotations match the retained baseline exactly; only independently
verified per-run match IDs are normalized. This is a normal rendered regression,
not an injected-lock test in Unity or a complete crash/save recovery claim.
The fault-injection contracts above run on Windows .NET 8. The private game
root was restored afterward; nothing was installed or published for users.
