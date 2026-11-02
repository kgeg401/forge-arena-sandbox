# Strike timing and token-army verification

These are bounded compatibility and presentation checks, not additional gameplay
repairs or complete-game/animation-parity certification. Product code remains the
tested non-player damage build from `e33bc26`.

## Strike steps

Original-handler Youthful Knight first strike kills Savannah Lions before it can
retaliate. Fencing Ace deals its two hits in distinct Forge damage steps.

A three-power Fencing Ace receives trample through an actual Charge Through
cast. Against a 0/4 Yoked Ox, original damage-allocation controls show lethal four
in the first step, then lethal one in the second. Actual damage is three to Ox,
then one to Ox and two to the player. Original Unity produces two separate combat
clips with exactly those hit branches. The next automatic rules pass occurs
8.2626 ms after the first clip completes; it does not overtake that animation.
The original Done controls remain real human damage-allocation decisions.

`native_strike_timeline.py` reviews this specific sequence. It preserves native
seven-digit UTC fractions as 100 ns ticks and rejects early passes, overlapping
clips, missing hits and missing completions. Eleven synthetic reader checks pass;
they are separate from the real native evidence.

The first reader failed because Python 3.10 does not parse seven-digit native
fractions. The original game sequence succeeded. Its failed report remains
unchanged; `strike-rendered-review-r3.json` separately reviews the same immutable
native rows. An initial Rancor fixture was rejected by the admission policy and
was replaced with already-admitted Charge Through. No card was silently added.

## A real growing army

Starting with one Doubling Season, actual Raise the Alarm creates four Soldiers.
Two actual Second Harvest casts grow the army to twelve, then thirty-six. Original
token identities and one-one characteristics remain intact. The tokens wait for
their next natural turn; no readiness, resources or intermediate states are
injected. All thirty-six attack and deal one actual damage each, winning from
twenty life with the opponent at minus sixteen.

Both original-handler and original rendered UI sequences pass. The rendered
sequence uses original card casts, Next/End Turn, a real next-turn land drop,
All Attack and the thirty-six-attacker submission. No manual mandatory-trigger
confirmation or Resolve shortcut was used. The existing initial-fixture limit
was preserved: the larger army was built through actual spells.

This private 1280x720 run measured p95 about 6.95 ms and p99 about 13.89 ms. These
numbers describe that scene and measurement window; no performance repair or
larger-army scaling guarantee follows from them.

Private evidence is under
`C:\Users\loula\Documents\Codex\ForgeArenaEightHour-20261102`:
`strike-sequences-baseline1-A`, `strike-sequences-trample2-A`,
`strike-rendered-review-r3.json`, `token-army-36-baseline1-B.json`, and
`army-rendered-current.json`. Original raw reports, failures, screenshots,
native wire and build hashes are retained in the per-session folders.
Each borrowed renderer session restores and independently checks 35 mutable
groups plus four immutable assets. No user installation, release or updater
promotion is included.
