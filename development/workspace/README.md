# Forge Arena Sandbox — development workspace

Internet multiplayer now has a **Private Commander (Internet)** queue, saved-deck
selection and Host/Join flow for two humans at 40 life. See [setup and limitations](packaging/public-docs/MULTIPLAYER.md)
and [the implementation evidence](docs/multiplayer-2026-11-02.md).

The shared starter library adds the current 26 saved decks and 521 collection
printing entries (928 copies) to new and existing profiles without overwriting
personal content. See [merge behavior and validation](packaging/public-docs/STARTER-CONTENT.md).

Local development now includes an **experimental four-player Commander pod**:
one human and three Forge bots. See [the pod implementation and validation
notes](docs/commander-pod.md). This is not a claim that the published download
already contains this checkpoint.

The release catalogue has a **370-name verified baseline** and **1,296 additional
experimental primary names**. Experimental admission permits testing; it does
not certify every card effect or interaction. See the
[latest catalogue evidence](packaging/public-docs/VERIFICATION.md).

The alpha 11 changes also connect optional Exert choices and repair a pause
after combat-damage presentation. The [combat checkpoint](docs/combat-exert-20261101.md)
records the tested sequences and remaining limits. Editing this workspace does
not update the installed client or public download.

Local development also includes **solo Zombie Horde**, including a queue for
your saved 99-card-plus-commander decks. See [the Horde rules and tested
boundaries](packaging/public-docs/ZOMBIE-HORDE.md). Alpha 11 includes this
experimental mode in the regular client.

The public player download and automatic-update channel are maintained at
[forge-arena-sandbox](https://github.com/kgeg401/forge-arena-sandbox). The
available version is identified by that repository's release page. Players install Arena
separately, then run Setup.exe from the Windows release ZIP. The setup includes
Forge and the pinned runtimes; saved data stays outside version folders.

## Source layout

- `NativeHost`, `LocalTransport`, `LabLauncher`, `LabPreferences`,
  `PreferencePatcher`, `Shared`: authored native adapter and isolation helpers.
- `ForgeBackend`: independent Forge bridge, catalogue qualification, targeted
  scenario generation, batch execution, evidence review and native QA tools.
- `DeckBackend`, `PackBackend`: local deck and sandbox pack metadata.
- `packaging`: installer, updater, dependency pins, public documentation and
  explicit release allowlists.
- `decks`: practice inputs selected by `packaging/starter-decks.json`.
  `packaging/starter-content.json` also seeds the shared exact-printing library
  and collection. Existing saved deck objects are retained.
- `ForgeBackend/draft_policies`: disabled research, including Paradox Engine;
  these policies are explicitly research-only and not consumer admission.

The published repository keeps the player runtime under `client/` and a matching
copy of this development workspace under `development/workspace/`. Game assets,
private profiles, native dumps and full research evidence stay local.

## Validation and release boundaries

See [catalogue delivery](docs/catalogue-delivery.md) and the public
[validation record](packaging/public-docs/VERIFICATION.md). Passing constructors,
source scans or generated cases never grants card admission. A release requires
reviewed rules/native evidence, a committed production policy, package checks,
activation/rollback, actual installed-client acceptance and profile preservation.

The earlier 370-name delivery passed 477 targeted effect scenarios, 25 production
regression stages and a complete 31-turn native match. Newer scenario evidence is
recorded in the linked verification notes. These are bounded checks, not proof of
all possible interactions or complete retail UI/animation parity. Multiplayer
remains unfinished.

Developer tools include historical default Windows paths. Use the explicit
portable `FORGE_ARENA_CONFIG`/policy options supported by each tool and review
paths before running research scripts on another machine. The installer uses its
own validated configuration. Build the authored native adapter with the owned
Arena assemblies and pinned loader; those dependencies are not in this source.

The [earlier developer README](docs/history-pre-catalogue-readme.md) and dated
work logs are retained as history. They do not describe the current release.
