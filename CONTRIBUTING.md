# Help test Forge Arena Sandbox

Start with the [Beta 1 guide](docs/BETA.md) and [known issues](docs/KNOWN-ISSUES.md).
This is a public testing prerelease with explicit card and multiplayer limits.

## Report a problem

Use [the issue chooser](https://github.com/kgeg401/forge-arena-sandbox/issues/new/choose)
for client/setup, card rules, private multiplayer or performance problems.
Search for an existing issue first; add new evidence there when it is the same
failure. Give exact versions, mode, card names, actions and expected/actual result.
[Evidence and privacy guidance](docs/REPORTING-BUGS.md)

Feature and card-support requests are welcome through the separate request form.
Link a concrete real-card interaction or describe the player experience you want.
Requests do not automatically change the card admission policy.

## Working with the source

Read [the developer guide](docs/DEVELOPMENT.md) and the repository
[license](LICENSE.txt) before reusing or changing source. The license grants
personal noncommercial testing permission; it is not an unrestricted open-source
license. This cleanup does not change those terms or third-party licenses.

Build/test in an isolated sandbox. Keep existing user decks, collection, matches
and official Arena installations intact. Use pinned dependency fingerprints.
Do not contribute game binaries/assets, decompiled game source, credentials,
private profiles or raw personal captures.

For proposed code changes, explain the trigger, resulting behavior and the checks
performed. Separate fixture/headless results, original-handler tests, rendered
gameplay and recipient-PC testing. Preserve real costs, response windows and
hidden information. A Forge script match or constructor test does not justify
promoting a card to verified support.
