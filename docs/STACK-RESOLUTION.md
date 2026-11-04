# Resolve a large stack

Use Arena's normal **Resolve**/yield controls. After an explicit local yield on
a sufficiently large stack, the bridge can defer unused action forecasts and
overlap bounded rules/presentation work. Forge still executes every actual cost,
priority pass, replacement, trigger and effect in order.

The blue **Cancel** button stops further automatic submissions. Already completed
effects remain, and up to four queued native states can finish presenting. The
client restores current legal actions before accepting a new choice. Use the
normal Resolve control again to continue. Full Control and required choices keep
their normal meaning.

**The sandbox does not change Unity's global time scale.** Arena's native
repeated-resolution pacing remains in use; the whole board, avatars and unrelated
animations are not accelerated. This corrects the earlier local Alpha 15.10
demo's global-clock shortcut. The fast local path is disabled for network matches.

A 304-trigger seeded reproduction completed with the same final rules state
and normal clock, including zero remaining triggers and 344 life. The 40.31-second
board-ready observation began with 294 triggers still remaining, so it is not a
total 304-trigger benchmark. Exact retail timing and a universal 30-second limit
are not claimed. Required human decisions, opponent responses and nonterminating
loops cannot have an unconditional completion deadline.

To generate repeated activations, use [Repeat combo](LOOP-REPEAT.md); that is
separate from resolving objects already on the stack.
