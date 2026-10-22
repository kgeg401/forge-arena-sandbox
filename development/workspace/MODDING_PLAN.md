# Arena local sandbox native host

- Install: `D:\GAMES\MTGA`, standalone, reported client `0.1.14517.1329972`.
- Engine: Unity 6000.3.14f1, Mono managed assemblies, Windows x64.
- Scope: user-owned local experimental client and local Forge backend. Official matchmaking/account state are excluded. This live-service client is treated as protected: tests execute only in a zero-capability Windows AppContainer, never an online injected client.
- Community route: BepInEx Mono plugins exist for Arena. Official loader chosen: BepInEx 5.4.23.5 x64. Archive SHA-256 was checked against GitHub's release digest.
- Loader source: https://github.com/BepInEx/BepInEx/releases/tag/v5.4.23.5
- Arena plugin reference: https://github.com/Mesonimie/mtga-bepinex (reference only; not installed).
- Windows isolation reference: https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer
- Lab: `D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab`, independent file copies, no hard links. Only the lab contains `winhttp.dll`, `doorstop_config.ini` and BepInEx.
- Profile: package `Codex.ForgeArenaSandbox.LocalLab`; preferences redirected to a lab-only JSON store. Native persistent data goes to that package's AC directory, not normal Arena LocalLow.
- Logs: lab `unity-lab.log`, `BepInEx\LogOutput.log`, `native-host-status.json`, `launch-receipt.json`.
- Private extracted/recovered code and evidence stay under D: research; do not publish it.
- Tested: native scene, real card database/art, local full/diff parsing and displayed life change.
- Remaining: Forge rules backend, native settings replies, complete card/action/annotation mapping, audio initialization, full matches and validation across scenarios.
