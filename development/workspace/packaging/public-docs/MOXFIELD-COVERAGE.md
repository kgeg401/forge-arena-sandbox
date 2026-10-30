# Moxfield Commander pool: 30 October 2026

This checkpoint sampled the 50 public Commander decks ranked by descending total
views in Moxfield's public search at the time below. This is popularity by views,
not a ranking of deck strength, recent tournament results or Arena legality.
Mainboards, commanders, companions, signature spells and sideboards are included;
maybeboards and token lists are excluded.

The lists contain 1,826 distinct names. **1,188 have matching identities in the
pinned installed Arena catalogue; 638 are excluded.** Catalogue presence does not
establish retail Brawl legality or account ownership. The client does not import
cards missing from that catalogue.

**942 new names are enabled experimentally.** Combined with earlier releases,
this build admits 1,285 experimental names plus the unchanged 370-name verified
baseline. No smoke-test result promotes a name to that verified baseline.

## What the tests establish

- All 1,188 identities match unique pinned Forge scripts and have resolved native
  presentation bindings. Binding success is not gameplay verification.
- 1,173 cards completed a generic cast or land-play walkthrough. The other 15
  require specific board states or choices and are covered by named native
  scenarios. Generic walkthroughs do not exercise every printed ability.
- 284 cards received a first-activation walkthrough attempt: 215 completed;
  69 need a specific fixture. Dedicated suites cover additional ninjutsu,
  cycling, channel, unearth, eternalize, protection and Class scenarios.
- Dedicated native scenarios cover counterspells, redirection, copying,
  conditional targets, gift, divided damage, piles, delve and a Battle.
- Eleven conditional-activation cases cover Wirewood Symbiote, Inventors' Fair,
  Chthonian Nightmare, Shifting Woodland, The Mycosynth Gardens and Bolas's
  Citadel, including real costs, expiration, insufficient resources and decline.
- Fourteen additional cases cover threshold lands, Dinosaur recovery, Haywire
  Mite, temporary protection, nonbasic-land destruction, bottom-library recovery,
  Minas Tirith's actual attack history and regeneration replacing destruction.
- Native-handler tests preserve genuine target/payment/response decisions.
  Rendered checks cover automatic combat triggers, original damage spinners,
  piles and Wizard Class levels with targeted draw triggers.

[Per-card smoke-test and named-scenario coverage](MOXFIELD-CARD-COVERAGE.csv)
separates completed walkthroughs from untested branches. A successful scenario
does not establish every interaction, combo, animation or complete deck.
In particular, partner commander pairs and importing these 50 decks as fully
playable lists are not established by this checkpoint.

## Captured public decks

Captured UTC: 2026-10-30T03:57:35.503862+00:00

| Rank | Public deck | Views at capture |
| --- | --- | ---: |
| 1 | [Winota: Snowball Stax](https://moxfield.com/decks/j-0aJlxuOUm9FnKRvJcfZw) | 569,153 |
| 2 | [ 🌸 Warrior Queen \[cEDH Najeela\] 🌸](https://moxfield.com/decks/jT8Y9X4tlUmeNZ2AjkD1Vg) | 477,454 |
| 3 | [\[Cabal\] A Faster K'rrik Storm 😈⚡️ (cEDH w/ Primer)](https://moxfield.com/decks/HYT9YcG0bEK1UMvmEEXtTA) | 424,871 |
| 4 | [Collaborative Gitrog Primer](https://moxfield.com/decks/4fbiNVFpr0edHL5Y3IKecg) | 353,342 |
| 5 | [Krark Sakashima Storm \[TOODEEP\]](https://moxfield.com/decks/G-RUVy_CMUWzXlhJknIzZg) | 351,062 |
| 6 | [🐕 Pako and Haldan cEDH 🐕](https://moxfield.com/decks/SBCYdcdc4EmteUIw7Ql0Jg) | 343,027 |
| 7 | [\[cEDH\] Urza Poly Kraken \[Primer\]](https://moxfield.com/decks/kes83-onUU6X_H-RyM8HPw) | 304,102 |
| 8 | [Waiting for Godo - cEDH Primer](https://moxfield.com/decks/URpEcoe6e0GBp3GzsstyBg) | 260,357 |
| 9 | [\[CABLE\] Clockside Outlawed](https://moxfield.com/decks/xmH0i1HMHUi2iCd279RYPA) | 258,627 |
| 10 | [Selvala Brostorm](https://moxfield.com/decks/PQPz_KSrV0S5_Huk1zh_tg) | 255,818 |
| 11 | [Yuriko Tempo (OUTDATED PLEASE DO NOT USE)](https://moxfield.com/decks/RM9tBCjdsEOUQQpleGI4Gw) | 253,268 |
| 12 | [💧 Blue Farm💧 ](https://moxfield.com/decks/2zSXC86KokyKs6vAS9-_sw) | 250,777 |
| 13 | [Winota Ultra Budget ($15 - Turn 3/(2) win possible)](https://moxfield.com/decks/FQ2llEVF2k6oMUoXVA16XA) | 247,154 |
| 14 | [K’rriko cEDH (AUG26 UPDATE)](https://moxfield.com/decks/6NkrPdOXGkeIM0KSyNborw) | 241,767 |
| 15 | [Blue Farm \[Primer\]](https://moxfield.com/decks/7O1sCuIti0igU6Us_Jhadg) | 241,696 |
| 16 | [How to Train Ur-Dragon \[Primer!\]](https://moxfield.com/decks/oTndvxb8bkqLPK_kANUrkA) | 238,782 |
| 17 | [Hail, Caesar Commander Precon Decklist](https://moxfield.com/decks/hvwCjVVsAEOBXY5fP57jzQ) | 235,297 |
| 18 | [🌽Sneaky Farm🚜](https://moxfield.com/decks/Bv8Jo8vkCUmHo-If-g6hug) | 235,263 |
| 19 | [\[cEDH\] Urza Power Scepter \[Primer\]](https://moxfield.com/decks/UCZpPdZhHESE1BgFVge3OA) | 227,514 |
| 20 | [Black Hole Son](https://moxfield.com/decks/ksOWqeElwUaNmAeybXoEjw) | 224,190 |
| 21 | [ \[CEDH\] 🤘 B.A.D. Kaalia 😈](https://moxfield.com/decks/3Nb5DWbEDUWcZOA4bzbr_Q) | 217,656 |
| 22 | [\[$25 Budget\] My Dog and I (Voltron)](https://moxfield.com/decks/AZKbE6E6kUWW2zMfHR41sQ) | 217,183 |
| 23 | [Veloci-Ramp-Tor Commander Precon Decklist](https://moxfield.com/decks/JYmnf92gJkac_I7WCBBTVA) | 210,392 |
| 24 | [Henzie - High Power (NonCedh) ](https://moxfield.com/decks/GnqlEhG3IUysVv3ub5EEEQ) | 206,036 |
| 25 | [Medium Midrange](https://moxfield.com/decks/EwS7lyEQN0mLtomfKlwoMQ) | 199,095 |
| 26 | [Blood Rites Commander Precon Decklist](https://moxfield.com/decks/x6yL8aKmrE-e8J27vhYyNw) | 197,591 |
| 27 | [Mutant Menace Commander Precon Decklist](https://moxfield.com/decks/pCvY-119rESrwMOO6goxjg) | 196,425 |
| 28 | [Peace Offering Commander Precon Decklist](https://moxfield.com/decks/ogBtbQTPTU-9Cy9Bqc8Dlw) | 195,151 |
| 29 | [\[cEDH\] Rograkh Silas Storm Combo](https://moxfield.com/decks/79hYZQUBdUaA9xD8zLX4vQ) | 193,717 |
| 30 | [Squirreled Away Commander Precon Decklist](https://moxfield.com/decks/2pL-5jxvI0uWutqLRv87Jg) | 189,927 |
| 31 | [Korvold, the MAD King👑 Storm 🌩 ](https://moxfield.com/decks/MNRi-mtvb02tMF3KqmF60g) | 184,205 |
| 32 | [\[cEDH\] To Infinity & Beyond](https://moxfield.com/decks/tj910qUf9Uq-Iibp40QfKw) | 180,716 |
| 33 | [Yuriko Pivot](https://moxfield.com/decks/N1VNylbgskmYWa09r26ygQ) | 179,660 |
| 34 | [Korvold's Treasure Storm](https://moxfield.com/decks/-MV1EWXwH0u-K4j7KYTpvA) | 179,148 |
| 35 | [The Magdanomicon - Magda CEDH Primer](https://moxfield.com/decks/8Y4qOAcLN0O_HHYhOboV3Q) | 178,528 |
| 36 | [Niv-Mizzet, Parun](https://moxfield.com/decks/HmRJ5ju54USIf9UVsl5kwQ) | 173,030 |
| 37 | [Tayam, The Luminous GrindStone (cEDH)](https://moxfield.com/decks/uiwJwQmCT0KoJJMAp3tbVA) | 171,923 |
| 38 | [Edgar Markov Aggro](https://moxfield.com/decks/Vv7rGWqkHkaAa8U5o0H1qQ) | 170,216 |
| 39 | [Oath of Sisay](https://moxfield.com/decks/GMft59MvVkq0po8hUB2Ccg) | 167,503 |
| 40 | [🍌 Golden Evolution 🍌](https://moxfield.com/decks/LcNaaKov-kGLxjUvclpDdg) | 165,120 |
| 41 | [🌊 Urza Poly Lobster 🌊"Turning Karn into a Kraken"🦞   (META SWAPS IN CONSIDERING / PRIMER)](https://moxfield.com/decks/mNapLrgSiUaA17cl9XNCpw) | 165,009 |
| 42 | [\[cEDH\] Kinnan NBC (No Bad Cards)](https://moxfield.com/decks/Mi4yPy0jFUGPx6pI5x3OVw) | 164,461 |
| 43 | [Sauron, the Dark Lord](https://moxfield.com/decks/OYWg_0g7AkuzUapuc2DPpw) | 164,039 |
| 44 | [Honorless Meren cEDH](https://moxfield.com/decks/mXvFQ7yKz0OFrsbWAv2bkQ) | 163,506 |
| 45 | [\[cEDH\] - Twitch Control {Primer} 🐙🎯](https://moxfield.com/decks/Y2cdFYZw_0-isKafmKXgNw) | 163,335 |
| 46 | [Family Matters Commander Precon Decklist](https://moxfield.com/decks/rGIZ2-7DKkif9hODOVK5jw) | 159,145 |
| 47 | [👑-Marchesa d'Amati, First of her Name: Queens Gambit♟️ (Aikido & Political Control) \| Budget EDH💸](https://moxfield.com/decks/zJ0qPOnI2UqykOwmeIUixg) | 157,806 |
| 48 | [🧜‍♂️ Kinnan's House of Mirrors \[Yappers & Clappers\] 👾](https://moxfield.com/decks/O7RMsRcwN0uyxGp9et_L2g) | 157,517 |
| 49 | [cEDH Inalla - Wizard's Chess](https://moxfield.com/decks/shj-af8AiUWaoFVbNORQig) | 152,545 |
| 50 | [Quick Draw Commander Precon Decklist](https://moxfield.com/decks/UbO_Mq2RREaIUQhbCr3lOw) | 152,408 |

Capture SHA-256: `8b91afa6d9a08a1046b64b81218dddbc338bf55170afd15567845bc4c383a404`
