# Arena card support audit

The totals and constructor diagnostics below describe the earlier Forge snapshot.
The current fixed official Forge 2.0.15 catalogue, rebalanced identity handling and
background validation are documented in [background-card-pipeline.md](background-card-pipeline.md).

The installed catalogue has 16,140 English primary, non-token names across
20,159 printings. This is installed metadata, not proof that every entry is
released, available to an account, legal in a format, or downloaded as art.
Only Arena entries are indexed; Forge-only cards are excluded.

The repeatable audit now checks candidate identity, constructs every matched
Forge card and all its exposed faces, inventories actual engine traits, and
joins those requirements to the implemented bridge boundaries. It never starts
a match or resolves an ability during construction. Static/construction success
cannot change admission.

## Current results

| Gate | Result |
| --- | --- |
| Unique Forge script candidates | 15,840 names |
| No script-name match | 300 names; not proof of missing Forge implementation |
| Construction with no diagnostic | 15,837 candidates; not playtested by this audit |
| Construction diagnostics | 2 candidates |
| Construction failure | 1 candidate |
| No detected structural blocker, still unverified | 6 candidates |
| Admitted for bounded existing play | 16 ordinary names, plus the separately mapped Rabbit token; Isamaru separately commander-only |

Aftermath split titles use `///` in Arena and `//` in Forge. Normalizing that
identity notation recovered 26 candidates without broadening play admission.
The scanner also excludes Oracle text, comments, descriptions and AI hints from
executable feature detection. Compiled keyword-generated traits supplement
explicit script directives.

The actual constructor audit found:

- **Perfected Theory:** installed Forge fails to construct the raw ability.
- **Circadian Struggle:** missing `DBEffect` subability diagnostic.
- **Withering Curse:** missing `DBPutCounter` subability diagnostic.

These are diagnostics of the pinned installed scripts/engine, not claims about
other Forge versions. No installed game/Forge definition was edited.

The controller inventory contains 102 relevant callback signatures; 86 still
resolve to inherited Forge AI methods. Existing admission remains intentionally
narrow. Brawl-specific confirmation overrides do not imply generic human-choice
support. Additional cards requiring those human decisions must get a native
decision adapter before admission; constructor success alone must never enable
them. This checkpoint inventories those paths; it does not implement all inherited
callbacks or assert exhaustive dynamic call coverage.

## Inspect a card

Private outputs are under
`D:\GAMES\CodexAssets\ForgeArenaSandbox\research\card-coverage`:

- `Card-Compatibility.html`: searchable, paginated card/blocker report. Browser
  visual/interaction validation is unverified; local-file navigation was blocked
  by the browser tool's URL policy, and no alternate route was attempted.
- `card-compatibility.json`: every name, printing IDs, candidate script hash,
  construction result, effect APIs, keywords, blocker codes, evidence findings,
  verification gates, and shared source-code anchors/hashes.
- `card-compatibility.csv`: spreadsheet-friendly names and missing features.
- `compatibility-summary.json`, `construction-receipt.json`,
  `controller-callbacks.json`, and `compatibility-checks.json`: totals, exact
  input/output/build identities, decision surface and 58 integrity/boundary checks.

Each missing capability has an implementation file/line/hash showing why the
current bridge cannot represent it. Effect-to-callback hints guide research;
they are not a complete call graph. The report does not infer a card's entire
rules correctness from its name, API list, or successful construction.

Examples caught beyond simple keyword detection: Brainstorm needs hand ordering,
Enlightened Tutor needs a library choice, Omen Hawker needs restricted mana,
and Warlord's Elite has a non-mana additional casting cost. None is admitted.
The manual damage allocator also has an explicit creature-name restriction,
and the installed legend rule uses `chooseSingleEntityForEffect`. That override
now handles the actual internal legend rule through a human native selection;
other non-forced single-entity choices stop with a fidelity gap. Conservative
structural blockers are retained even on admitted cards and do not replace the
bounded per-card sequence evidence. The six
remaining static candidates are draw/life instants; they still require rules,
asset, native-control and sequence verification.

## Repeat and extend

Run `python ForgeBackend/run_card_audit.py` from the repository. The constructor
process has a five-minute bound, captures per-card diagnostics, writes a receipt,
and only replaces the previous inventory after checking complete source hashes.
`verify_compatibility_report.py` checks catalogue completeness, admission
separation, source provenance, three constructor problems, choice/cost/mana
boundary cases, and unsafe spreadsheet prefixes.

The next implementation order is generic mana/cost representation and human
decision safety, then representative vanilla/keyword/choice families. For each
family: review source identity/rules, implement the missing adapter, test real
Forge sequences using inputs, exercise original native controls/rendering, and
retain evidence before changing explicit `bridge_support.json` admission.
Whole combinations and interaction exceptions need regression scenarios too.

The existing native/manual-input, smart-yield, source-link placement, and full
presentation limitations remain. The [Emry checkpoint](emry.md) admits five
additional source-checked ordinary names after sequence and native checks;
construction success alone still cannot promote a card.

## Saved Emry Brawl deck check

The saved Arena export and installed Forge deck agree: one Emry commander,
99 main cards, 75 distinct names. After the Emry checkpoint, current admission
covers 31 copies across six names: 26 Islands and one each of Emry, Ornithopter,
Aether Spellbomb, Seat of the Synod and Tormod's Crypt. The other 69 names/copies
remain unsupported, so the complete deck still fails production admission.
This is a recheck of the same saved export, not a fresh account export. Exact
results are in `research/emry-mechanics/saved-deck-current-admission.json` on D:.

An independent, read-only Forge probe found all 75 exact names and constructed
each without diagnostics, including **A-The One Ring**. It registered Emry with
the installed Brawl variant at 25 starting life. No card was cast or resolved and
no game was started; this does not verify the deck's interactions.

The installed Forge Brawl preset expects 59 main cards, whereas Arena's 100-card
Brawl needs 99 plus the commander. The adapter now registers the actual Brawl
variant and enforces its explicit 99-plus-one sandbox admission separately.
Normally started 25-life commander games, Emry affinity/tax and the targeted
artifact loop have their own evidence; the full deck does not. The primary
catalogue excludes nonprimary rebalanced entries: the installed A-The One Ring
records are present but omitted from this index. Their exact Forge definition
exists; substituting the original Ring would change its activation cost and was
not done. General rebalanced export identities need their own catalogue policy.

Private evidence: `research/emry-brawl-check/compatibility.json`,
`card-checks.csv`, `forge-probe.json` and the probe/log on D:. Current account deck
freshness, format banlists, all color identities, native assets and full gameplay
were not verified by these saved-list checks. Next work should select another
small card family from the actual unsupported list and test its mana, choices,
triggers and interactions before admission.
