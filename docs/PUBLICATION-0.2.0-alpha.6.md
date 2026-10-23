# Turn-flow release checks — 0.2.0-alpha.6

The user accepted the installed native turn flow and authorized publication.
The Windows package contains the same tested NativeHost binary; the Java rules,
production policy, support index and decks remain identical to public alpha.5.

- ZIP: 1,104,984 bytes, SHA-256 `b9dce360348e23d6861c23b696597a3fb4fb58e4e945198aa3993d27a3cb1603`.
- Native DLL: `1318894da0578f3417debfb297b8670057be38ea582f5a8f16b1fd61858877b0`.
- Eight actual Forge/native-handler scenarios and twelve rendered checks passed.
- Package/backend equivalence passed sixteen checks.
- Real downloaded alpha.5 upgrade/rollback/reapply passed thirteen checks,
  retaining exact saved-data fixture bytes and the previous version.
- Updater, startup, dependency and client coordinator suites passed.
- Windows bootstrap: fifteen checks; saved display settings: eleven checks.
- Package scan: 119 files, zero failures/warnings. Public source scan: zero
  failures; three reviewed historical developer-path warnings.
- Source snapshot check: 357 checks, 314 authored source files, 370 names.

The first startup-fixture attempt encountered restricted temporary-directory
rename permissions. Rerunning in an explicit writable test folder passed; no
installer implementation change was required. Raw native evidence and profiles
remain private. These checks do not prove successful installation on a recipient
PC. Public download and update-feed checks are recorded after upload.

See [behavior and remaining limits](TURN-FLOW-0.2.0-alpha.6.md).
