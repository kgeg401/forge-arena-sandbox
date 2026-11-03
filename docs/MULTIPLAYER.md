# Play Commander with a friend over the internet

This experimental mode is two human players, 99 cards plus one commander each,
40 starting life, normal commander tax and commander combat damage. Both players
choose their own saved decks. Forge on the host PC is the single rules authority;
each original Arena board receives only that player's permitted view.

## First test

1. Both players update by closing the game and reopening **ForgeArenaSandbox.exe**.
   New users extract the Windows release ZIP and run **Setup.exe**. Arena must be
   installed separately. Both installations need the same release and catalogue.
2. Save or import a valid Commander deck in **Decks**. Saved Brawl decks work here
   with the mode's 40-life rules and enabled sandbox card catalogue.
3. Open **Home > Play > Brawl > Private Commander (Internet)**, choose the deck
   and click **Play**. The client opens its private-room dialog.
4. One person clicks **Host room**, waits for the invitation, then clicks **Copy
   invitation** and privately sends it to their friend. Keep the entire invitation,
   including everything after `#`. This is the room's access secret.
5. The other person copies the complete invitation and chooses **Join copied
   invite** inside their client. When both
   decks are locked, the original game board opens, including play/draw and
   mulligan choices. Each player controls their own cards and response windows.
6. Finish or concede through the original Options menu, then Continue to Home.
   Create a new room for another match; invitations are not permanent.

No router port forwarding, additional account, or manually installed Forge server
is needed. The host downloads a version-pinned, SHA-256-verified official
Cloudflare connection helper on first use. The download is about 55 MB. A normal
working internet connection is required on both PCs; firewalls that block the
helper or Cloudflare may prevent connection.

## Connection and trust

The game itself retains zero Windows network capabilities. Its external Python
worker handles authenticated HTTPS messages through a temporary Cloudflare
tunnel to a loopback-only room. Only the room protocol is exposed; it does not
serve local files or accept arbitrary engine commands. The host runs both decks
and therefore must be trusted with the complete match and deck information.
Cloudflare terminates the public TLS connection; this is not end-to-end encryption
against the relay provider. Never post an invitation publicly.

Keep both clients and the host PC awake and open. Brief connection interruptions
retry while holding the match. Closing either client or leaving the room ends
the connection; there is no host migration or crash-resume. A completed result
remains usable if the host leaves first. Unfinished matches are not saved.

## Test status and limits

Two independent native clients on one PC have played through the public HTTPS
route, with separate decks, hidden hands, mulligans, real casts and combat, and
opposite native win/loss results. This is preparation for the first two-household
test, not a claim that your particular networks or every card combination have
been verified. Human four-/ten-player pods, Horde co-op, public matchmaking and public
rooms are not included. Existing bot and solo modes remain available.

If stuck, record the turn, card/action, both players' visible prompts and which
player hosted. Do not share invitations or raw connection logs publicly. Finish
the room, return both clients Home and create a fresh invitation. A compatibility
error means both players should update; it must not be bypassed.

Connection helper: [official Quick Tunnel documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/),
[cloudflared source and Apache-2.0 license](https://github.com/cloudflare/cloudflared/blob/master/LICENSE).
