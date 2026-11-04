# Castable-card outlines

The original Arena renderer now shows its normal blue outline for spells Forge currently allows you to cast. Ordinary creature, artifact, enchantment, sorcery and planeswalker spells use normal main-phase timing. Instants and flash spells can remain highlighted in other priority windows. Available mana, costs, legal targets and other permissions still come from Forge.

The UI previously required a retail GRE auto-tap plan before considering paid spells affordable. The local bridge supplies Forge-validated actions rather than retail auto-tap plans. A narrow native UI hook recognizes only the current bridge's exact offered cast instance and printing, after the corresponding state is presented. It adds no mana, changes no costs, submits no action and does not manufacture an auto-tap plan. Native warning and selection outlines remain in control of the original renderer.

Highlights stop matching a cast after its resources or targets disappear. Stale instances, different printings, non-cast actions, pending decisions, completed games and inactive multiplayer input seats do not receive the override. The lookup is cached when offers change rather than rebuilding card data each frame.

Validation includes seeded native-handler checks for main-phase casting, combat, the opponent's turn, flash, target availability and spent mana. Original-renderer checks separately verify the actual UI hook and existing card callbacks. These checks do not certify every card or a full remote multiplayer match.
