# Developer notes

The Windows release is intended for players. A source checkout is not an
installable release and contains no Arena assemblies, assets or private profiles.

## Repository layout

- `client/`: authored Python installer, updater, coordinator and catalogue helpers.
- `client/adapter-source/`: corresponding C# native adapter, launcher, boundary
  helpers and Java Forge bridge source.
- `client/decks/` and `client/starter-decks.json`: deck inputs and the recommended
  starter list. Internal regression decks are not all seeded into new profiles.
- `docs/`: player guide, supported-name policy and validation boundaries.
- `development/workspace/`: matching authored development sources, batch
  generators, QA tools and historical notes. Disabled research is marked
  separately; raw evidence and game assets are excluded.
- `.github/`: issue forms and headless Windows source checks.

The native game uses an isolated copy of owned files in a zero-network-capability
AppContainer. The external coordinator owns one Forge process per match. Requests
carry a client session and match identity; saved decks are independently validated
before Forge starts. Native menus survive match-scene unloading.

## Building authored components

Use the exact owned Arena/Forge builds pinned in `client/requirements.json`.
The consumer installer needs runtimes; compiling requires the .NET SDK and Java
17 JDK. Set `ArenaManagedDir` to your owned `MTGA_Data/Managed` directory and
`BepInExRoot` to the supported loader directory when building the C# projects.
The supplied MSBuild properties write outputs under `adapter-source/build` by
default, or under an explicit `SandboxBuildRoot`.

For example, from this repository on Windows:

```powershell
dotnet build client/adapter-source/NativeHost/NativeHost.csproj `
  -p:ArenaManagedDir='D:/YourArena/MTGA_Data/Managed' `
  -p:BepInExRoot='D:/YourBepInEx' `
  -p:SandboxBuildRoot='D:/YourAdapterBuild/'
```

The Java bridge source is `client/adapter-source/ForgeLandEngine.java`; compile
against the pinned Forge jar and Gson with Java 17. The small Windows entry points
are `ClientLauncher.cs` and `SetupBootstrap.cs`, built with Windows' .NET Framework
compiler and its WinForms/Drawing/Web.Extensions assemblies.

## Validation and releases

The headless workflow runs authored installer/updater/coordinator fixtures. It
does not contain game assets and cannot establish rendered gameplay, native
input parity, card-rule support or a successful recipient-PC installation.
See [verification](VERIFICATION.md) for the separate native evidence.

A release needs a Windows package with a valid `release-manifest.json`, pinned
prerequisites, corresponding authored source and the exact admission policy used
by its compiled bridge. Preserve profiles outside `versions`. Test a real package
activation, rollback, native startup and match cycle before publishing.

Publish a newer semantic-version prerelease containing the asset named
**ForgeArenaSandbox-Windows.zip**. The test-channel updater reads that release's
SHA-256 digest. The display title can differ from its update version; never reuse
an already published version with different bytes.

Do not commit owned game binaries, extracted assets, decompiled game source,
private profiles, captures containing account data or credentials. Adding a
Forge script match must not automatically promote a card to verified support.
