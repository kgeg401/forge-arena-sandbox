# Published catalogue alpha

Published on 22 October 2026:
[0.2.0-alpha.5](https://github.com/kgeg401/forge-arena-sandbox/releases/tag/v0.2.0-alpha.5).

The local installed client and published Windows package both enable 370 Arena
main-deck names, an increase of 118 over the previous public release. Paradox
Engine remains disabled research. Full catalogue support is unfinished.

## Shipping checks

- Windows ZIP: 1,099,147 bytes; SHA-256
  `5b922f712b806df7714dec2439460c04617bef97b18c2aa058df787e74d0d388`.
- The public download matches those bytes and its release manifest. The real
  test-channel update feed selects this version and advertises the same digest.
- Original startup code from 0.01 alpha and test.3 automatically downloaded and
  installed this release in separate disposable launcher installations. Saved
  fixture profiles remained byte-identical; previous versions remained available.
- Actual installed-client acceptance separately verified 370 enabled names,
  matching runtime/deck/support metadata, original Home and the zero-network
  native process. Existing decks, collection and preferences were preserved.
- Package equivalence: 17 checks. Actual activation/rollback: 12 checks.
  Installer rejection: 5 checks. All 34 compared runtime artifacts match the
  gameplay-tested build. Installer/updater/coordinator/bootstrap/display checks
  and the source consistency checks pass locally and on GitHub.
- [GitHub CI](https://github.com/kgeg401/forge-arena-sandbox/actions/runs/39855337910)
  passed for release commit `a9ab25ef5fab9dc86c75c9e87dc33b9482fafab0`.
- Package scan: 116 files, zero failures/warnings. Source scan: zero failures,
  three reviewed notices for historical developer paths. Private profiles,
  raw native evidence and owned game assets are excluded.

The first CI run caught inconsistent historical line endings; these were fixed
and checked from a fresh Git export before release. An output collector could
not decode a legacy console character after one older launcher had updated;
its accepted update was recovered from the receipt without repeating it.

This verifies update transport and the local installed client, not successful
installation on another person's PC or all possible Magic interactions. Normally
close and reopen ForgeArenaSandbox.exe to update. Older hub users may need
Start practice once afterward. Setup.exe need not run again for a configured
installation.
