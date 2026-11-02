# Four-player Commander opponents

Commander Pod uses three distinct complete decks:

| Commander | Plan | Main-deck lands | Main-deck creatures |
| --- | --- | ---: | ---: |
| Isamaru, Hound of Konda | White creatures, flying and lifegain | 38 | 44 |
| Emry, Lurker of the Loch | Artifact value, recursion and blue creatures | 39 | 47 |
| Selvala, Heart of the Wilds | Green ramp, large creatures and trample | 38 | 43 |

Each list has 99 main cards plus one commander, respects singleton and color
identity, and uses the client's existing admitted card pool. These are casual
creature-focused opponents, not competitive Commander lists. Forge makes their
decisions normally; it may play another spell instead of its commander.

The gentle one-on-one training opponent is unchanged. Its old 94-land list is no
longer copied into the three pod seats. Start a new pod match after updating;
an already running match retains the decks it was created with.

The table now packs surviving opponents into adjacent positions and brings the
camera closer after eliminations. Seat identities, targets and ownership remain
unchanged. Click an opponent's panel to focus on a crowded board; Tab returns to
the overview.

The experimental ten-player queue starts you and nine bots at 40 life. It repeats
the three complete lists above across the nine bot seats. With five or more
players alive, Forge's native Pramikon direction rule allows attacks only against
the nearest living opponent on your left (including their planeswalkers). At four
players, attacks are unrestricted. Spells retain their usual targeting rules.
The source rule exempts Battles; these bot lists contain none. This is a local
one-human mode, not ten-person network multiplayer.
