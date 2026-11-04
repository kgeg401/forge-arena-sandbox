# Five absurd Commander engines

Five real-card, 100-card Commander brews for the sandbox. Each has 99 cards plus its commander, 36 lands, singleton nonbasics, and matching color identity. All cards were checked against Scryfall's Commander legalities on November 4, 2026. These are experimental high-power brews; no measured cEDH or numerical bracket rating is claimed. The internal deck-storage label `arena-brawl` does not imply official Arena Brawl legality.

## Rebel Printer Go Brrr — Otharri, Suns' Glory

The army deck. Attacking with Otharri earns experience counters, then creates an increasingly large Rebel army. Anointed Procession, Mondrak and Ojer Taq multiply it; Impact Tremors and Purphoros turn arrivals into damage.

The absurd line is **Otharri + Breath of Fury + army-wide haste**. Put Breath on a creature that can connect. Combat damage sacrifices it, moves the Aura to another creature and grants another combat with your creatures untapped. Every Otharri attack increases experience and creates more bodies than the loop consumes. Fervor, Anger or another haste source lets new Rebels join later combats. Blockers, removal and preventing damage can break this line; an Aura on a creature that cannot connect does not start it.

## One Damage Is Enough — Ob Nixilis, Captive Kingpin

Every event in which an opponent loses exactly one life grows Ob and exiles your next card for temporary access. Pingers, tiny death triggers and one-damage attacks feed the engine.

**Ob + All Will Be One + a one-damage seed**, such as Gut Shot, repeatedly adds a counter and deals one damage. Choose an opponent for each damage trigger. Ob's exile instruction can continue with an empty library because it is not a draw. Protect Ob: removing either permanent stops the engine. Larger damage events do not satisfy his exact-one condition. Quest for Pure Flame supplies a separate counter-based route into All Will Be One.

## Snake Oil Factory — Hapatra, Vizier of Poisons

Turn -1/-1 counters into deathtouch Snakes with Hapatra and Insects with Nest of Scarabs. Yawgmoth and Fume Spitter start the counter engine; Young Wolf supplies a renewable body.

**Hapatra + Nest of Scarabs + Blowfly Infestation + Blood Artist** can turn one dying countered creature into a chain of token deaths, replacement bodies and drain triggers. Keep legal targets and enough bodies available. When paying Yawgmoth's sacrifice cost, do not sacrifice the creature you selected as his target: that can leave the ability without a legal target. Blowfly can also force you to put counters on your own support creatures when no disposable bodies remain.

## Definitely Not Rigged — Tivit, Seller of Secrets

Vote for evidence or bribery, then turn the results into Clues and Treasures. Tivit gives you an additional vote. Academy Manufactor converts each resulting token into a Clue, Food and Treasure.

In a four-player pod, one Tivit election with the extra vote produces five artifacts even without Manufactor. **Time Sieve** sacrifices five artifacts for an extra turn. Attack with Tivit in that turn, connect, hold another election and repeat. In a duel there are fewer voters: use Manufactor, extra-vote effects or other artifact production rather than assuming five tokens. Tivit must connect, Sieve must remain available, and actual votes are player choices. Opponents can answer the abilities normally.

## Worst Gift Ever — The Beamtown Bullies

Give the active opponent a nonlegendary creature from your graveyard. **Leveler** exiles their library; **Eater of Days** makes them skip their next two turns; **Soulgorger Orgg** temporarily takes their life total down to one. Gifts are goaded and have a delayed exile instruction.

Use Entomb-style setup to put the bad gifts in your graveyard. Activate Bullies during the recipient's turn, not yours. Do not use ordinary Reanimate on Leveler or Eater under your own control. Despotic Scepter can destroy a permanent you own even when an opponent controls it.

A reusable drain line is **Bullies + Thornbite Staff + Hangarback Walker in the graveyard + Blood Artist**. Return the zero-counter Walker under the active opponent; it dies, returns to its owner's graveyard, triggers drain and untaps the Staff-equipped Bullies. Repeat while the activation remains legal. This is a real paid/triggered rules interaction, not a promise that the loop shortcut recognizes every part automatically.

## What was checked

The original native request handlers and Forge rules ran these seeded scenarios on both supported Arena builds: an Otharri extra-combat win; Ob/All Will Be One win after exhausting the exile library; Hapatra token/drain win; Tivit votes, real artifact sacrifices and successive extra turns; Bullies donating Leveler followed by an empty-library loss; and three Walker/Staff recycling cycles. Both red modal blasts also exercised the native mode picker. Paper-art loading and saved-deck readiness are checked separately in the native client.

Seeded mechanic tests do not prove every interaction in all five shuffled decks or remote multiplayer compatibility. New admissions remain experimental; the independently verified catalogue is unchanged. No custom invented cards are used.

References: [Commander format](https://magic.wizards.com/en/formats/commander), [banned and restricted list](https://magic.wizards.com/en/banned-restricted-list).
