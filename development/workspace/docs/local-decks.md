# Local deck lists

`Open-Decks.ps1 -Build` opens the separate, network-isolated Arena lab. The
`Forge Arena Decks` desktop shortcut opens the already-built version.

The browser uses the installed DeckManager, DeckViewSelector, DeckFolderView and
DeckView prefabs. Double-click a deck, or select it and click **Edit Deck**. The
original editor shell, list rows, card grid, search field, name field, hover zoom,
art, mana symbols and buttons display local data. Click a grid card to add it;
click a list row to remove one copy; its quantity tag adds a copy. **Done** and
**Back** save and return to the browser. The plus button creates a deck. Duplicate,
clipboard import and clipboard export use the original browser buttons. Deletion
requires a second click and retains the previous library file as a backup.

Export also writes a text file under `native-lab/local-deck-exports/`. The existing
**Forge Arena Custom Decks** launcher opens that directory when exports exist.
Its match preflight still rejects unverified cards and unsupported deck sections
before stopping the current client. A saved deck is not a claim of match support.

## Storage and source boundaries

All private data remains under `D:\GAMES\CodexAssets\ForgeArenaSandbox`:

- `native-lab/local-profile/decks.json`: local deck IDs, names, exact printing
  IDs and counts in main, sideboard, commander and companion sections.
- `native-lab/deck-catalog.json`: 20,159 primary, non-token English printings
  from the pinned owned card database; generated read-only by
  `DeckBackend/build_deck_catalog.py`. No ownership or legality claim.
- `research/deck-ui/`: private source inspection and verification evidence.

Saves flush a pending file, preserve a backup and atomically replace the primary
file. Invalid imports save nothing. Uncommitted pending files do not replace a
saved library at startup. Invalid schema, duplicate IDs and unknown printings
fail without resetting the library. Storage checks operate on separate temporary
profiles and do not mutate the player's library or pack collection.

Import accepts English Arena `Deck`, `Sideboard`, `Commander`, `Companion`
sections and count/name lines, optionally with exact `(SET) collector` labels.
Labels resolve exact source printings; unlabeled verified practice names prefer
the bridge's pinned printings. Other unlabeled names prefer the highest source
printing ID. Export retains exact IDs through set/collector labels. Unknown
names/printings and malformed rows reject the entire import. Local editing is
bounded to 999 copies per printing and 1000 cards across all sections.

Seven source label combinations identify multiple printing IDs. Exact-label
imports and exports involving those combinations fail explicitly rather than
silently substitute a printing. The saved JSON still preserves the exact ID;
name-only imports can deliberately choose the documented preferred version.

## Deliberate limitations

- The match bridge remains limited to its eleven admitted names, a 40–250-card
  main deck, and pinned presentation IDs. Retail formats/copy limits are not
  enforced in sandbox deck storage. Other printings of supported names retain
  their identity in storage/export; the current match importer deliberately uses
  the pinned practice presentation.
- The default grid shows the eleven admitted names. Searching also searches the
  larger installed catalog, shows one preferred printing per name, and caps the
  grid at 500 results. General-card rendering and mechanics are not all verified.
  Exact alternate printings can be imported but have no printing-selector UI yet.
- The editor currently edits the main section. Other imported sections survive
  save/export unchanged and produce match limitations; their editor UI is hidden.
- Crafting, color/advanced filters, format selectors, cosmetics and whole-app
  Home navigation are not connected. Their unsupported controls are disabled or
  hidden. Sandbox quantities are unrestricted; pack ownership remains separate.
- This is original presentation with local adapters, not the full retail deck
  workflow. Scoped hooks bypass the account-backed screen lifecycle and replace
  the bound buttons' serialized online callbacks. The normal installed client
  and its services are not patched.

`NativeMenuSurface` follows the camera/canvas values recovered from the owned
MainNavigation scene, with both UI and 3D card input paths. Native asset loading,
hover zoom, card layout and card-row behavior remain in the original components.
Decompiled source and owned assets are private evidence on D:, not repository
content. The repository contains the adapters and catalog generator only.
