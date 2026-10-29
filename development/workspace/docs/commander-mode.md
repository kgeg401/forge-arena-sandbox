# Commander Bot (40 Life)

Use **Play > Brawl > Commander Bot (40 Life)**, select an enabled 100-card
commander deck such as Jace Superfriends Brawl, and press Play. The same saved
deck can be used in Brawl Bot; choosing the queue controls the match rules.

Commander uses Forge's Commander variant: 40 life for each player, one commander
plus 99 main cards, singleton except basics, commander color identity, command
zone/tax/return choices, and loss at 21 combat damage from one commander. It is
a two-player local bot match using the existing enabled Arena card pool. It
does not add cards or claim a retail banlist. Two-player Commander uses the
ordinary London mulligan; Brawl retains its free first mulligan and 25 life.

The native game metadata uses GameVariant_Commander and the authoritative
starting-life totals supplied by Forge. It does not change Brawl or Practice
starting life. Commander damage remains authoritative in Forge; a complete
Commander-specific statistics UI is not part of this change.

`ForgeBackend/verify_commander_modes.py` runs original-handler start, mulligan
and casting checks for both modes. `--damage-match` additionally runs a normal
shuffled Commander match to a positive-life CommanderDamage loss.

This feature is packaged as a local preview after public alpha.8.

The default Brawl/Commander bot uses a defensive setup-practice deck:
Emry, 94 Islands and five zero-power creatures (Aegis Turtle, Kraken Hatchling,
Murmuring Phantasm, Riptide Turtle and Wall of Mist). It has no removal,
counterspells, combat boosts or damaging creatures apart from its 1-power
commander. It is deliberately very weak so slower decks such as Jace can
practice setup. The normal rules, starting life and AI's legal actions remain.
The legacy `Brawl-Isamaru-Bot.txt` filename is retained for coordinator
compatibility; its actual commander is Emry.
The coordinator reads this deck when starting each match; an existing match
keeps the deck it started with.
