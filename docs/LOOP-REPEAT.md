# Repeat a combo

Perform the same complete mana or life-gain ability cycle twice. If the client
recognizes an unchanged, repeatable position, use **Repeat combo** beside the stack.
The original Arena X selector chooses **1–1000 additional repeats**; confirm its
**X =** button. Entering `100`
performs 100 more cycles; it does not include the cycles you already demonstrated.

Each activation uses the real rules engine. Costs are paid, targets are checked,
effects resolve, and other players retain their response windows. Mana abilities
follow their normal rules and do not gain artificial stack entries. Animations
continue normally, so a large batch can take time.

**Life loop** also checks the exact life gain and mana change for each cycle.
For example, repeatedly gaining one life and untapping Staff of Domination costs
three mana per full cycle. Generate enough mana first; Repeat never grants free
resources.

Detection can survive the untap ability leaving the stack. When an eligible
sequence is available, the collapsed **Repeat combo** button opens its selector.
The active batch shows progress and a blue **Cancel** button. Cancelling closes
the selector; the launcher returns only when a valid sequence is available.
A new match starts fresh.

For **Stack repeats**, activate a repeatable ability while retaining priority.
Each repeat pays the current cost and adds another actual activation to the
stack. Use the normal Resolve/Pass controls when you are ready to resolve it.

The blue **Cancel** prevents further submissions. Completed actions and paid costs remain.
Finish any choice already opened by the current action normally. An opponent's
response, changed position, unavailable ability, unexpected random result or
uncertain submission stops repetition safely. No opponent decisions are made
on their behalf.

The detector covers deterministic activated-ability sequences, including recorded
color and target choices. It does not discover arbitrary spell, sacrifice,
random, library-changing or growing-battlefield loops. If no panel appears, play
the combo normally. Re-demonstrate a cycle after changing its position.

Solo native presentation and two-human native-handler tests have bounded
coverage. Host and guest ownership passed over loopback; a host-owned public
HTTPS run also completed ten cycles, cancellation and a real opposing bounce.
Earlier timeout/DNS failures remain recorded. Two-PC presentation and general
internet reliability remain experimental.

For large local stacks, see [stack resolution](STACK-RESOLUTION.md). Repeating
a combo and resolving an existing stack are separate operations.
