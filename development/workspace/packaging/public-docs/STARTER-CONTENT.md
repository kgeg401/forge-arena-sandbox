# Shared starter library

Beta 1 includes **32 shared starter decks**
and **907 collection printing entries, totaling 1,338 copies**. Every new client
installation receives the same starter content, including Emry, Jace Superfriends,
Darien, Gamba Gamba, Miirym Mass Arrival and Zaxara Copy Army. Cosmetic name/avatar
profiles share this library and do not repeat starter grants.

Existing players receive missing starter decks at the next normal client launch.
A saved deck with the same name is retained, including your edits. Collection
counts are brought up to the starter minimum once; larger existing counts stay.
Your profile identity, unopened packs, opening history and other saved data are
kept. Starter grants are recorded separately from pack-opening rewards. Reopening
the client does not grant them again. Deleting a starter deck after the grant
does not silently recreate it on every launch.

To share a game, both players close and reopen the dedicated launcher, then
choose **Brawl > Private Commander (Internet)** and select a saved commander deck.
Both need the same version. This release is still a private two-player test;
it does not add human multiplayer pods or certify every card interaction.

The shared snapshot contains only deck names, formats and exact printing counts,
plus collection counts. Account details, sign-in data, original profile/deck IDs,
favorites, play timestamps and pack-opening history are not distributed. This is
content for the custom client; it does not modify an official Arena account.

Validation includes the original 26-deck snapshot comparison and later
starter extensions, actual native storage classes,
all deck-admission checks, once-only native pack rewards, existing-profile merge,
idempotence, malformed-input preservation, partial-I/O retry and update/rollback.
The beta's runtime and catalogue are checked against the tested source
checkpoint. These merge checks are not a complete-match test of every deck or
a two-household network test. The original 26-deck/521-printing/928-copy figures
describe the Alpha 15.3 snapshot, not the current package.
