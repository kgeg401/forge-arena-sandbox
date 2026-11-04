# Report a beta problem

Start with [known issues](KNOWN-ISSUES.md) and [setup help](FAQ.md), then open
[the matching GitHub issue form](https://github.com/kgeg401/forge-arena-sandbox/issues/new/choose).
Manual issues use the browser; you do not need to install GitHub CLI.

## Include enough to reproduce it

- **Version:** the display/update version from `release-info.json` in the active
  `versions/<version>` folder. Beta 1's update version is `0.2.0-beta.1`.
- **Environment:** Windows version, official Arena store/build, game mode and
  host/guest role for a private match. Give both players' versions for multiplayer.
- **Action:** exact card names and the last few actions. State which player
  controlled each relevant permanent, the turn/phase and any prompt on screen.
- **Result:** what you expected and what actually happened. Say whether it
  repeats or happened once. For performance, give stack size and measured time.
- **Evidence:** a screenshot or short video, plus a small relevant error excerpt
  from the installed `logs` folder if available.

If the game is stalled, record its current prompt before returning Home. Ending
the match does not save a resumable position. Do not deliberately close a useful
match just to assemble a report.

## Keep private data private

Do not attach a whole installation, game files, credentials, account data or a
room invitation. An invitation's fragment after `#` is an access secret. Raw
connection logs and full match exports may expose it or private decks/hands.
Review and redact excerpts before uploading. Screenshots of hidden information
should be shared only if you intend to disclose that information.

The optional automatic reporter sends only a package-pinned version and a fixed
failure code; it does not supply reproduction steps. Reports queued on this PC
are not necessarily delivered to GitHub. [Reporting details](FAILURE-REPORTS.md)

## After submitting

Keep the issue number. Add new evidence to the same issue when it is the same
failure. A maintainer may request a smaller card sequence or a specific bounded
diagnostic. Fix notes distinguish reproducible rules cases, original-client
presentation checks, complete games and recipient-PC testing.
