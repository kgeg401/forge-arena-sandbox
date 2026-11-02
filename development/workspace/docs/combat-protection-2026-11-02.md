# Compound protection and temporary combat abilities

Akroma's Will could resolve correctly in Forge and then stop the client with `Unmapped literal native keyword: Protection from each color`. Forge represents this as one keyword; the original native parser accepts the five color protection identities together in a single ability annotation.

The adapter now expands this exact compound for presentation. It retains the actual source, affected card, timestamp, layer, and single persistent annotation identity. Cleanup retires the whole annotation. Removal expands the same identities. Other unsupported compounds still fail explicitly; the implementation does not alter Forge rules, targeting, blocking, damage, or randomness.

Validation includes:

- The old native-handler failure is preserved for the protection-only and commander-both modes.
- All three real modes now pass 17 native-handler assertions: first mode without a commander, second mode without a commander, and both with a real commander. Protection excludes the green reach blockers, lifelink and double strike follow the selected modes, vigilance affects tapping, and temporary native grants expire at actual cleanup.
- The original rendered modal browser accepts both actual card choices. The creature makes two original combat clips with two damage each, gains four life, and returns at the next real turn with the temporary grants expired. No generic confirmation was inserted.
- Heroic Intervention's independent native case verifies indestructible through five marked combat damage, two deathtouch kills, lifelink, and actual cleanup. The original rendered damage browser, combat clip, survivor, 22/20 life totals, and next-turn expiry also pass. This separates temporary grants from printed Nighthawk keywords.
- Ten small `KeywordProbe` contracts cover literal compatibility, five-color grouping, unchanged source/layer identity, expiry/removal, incomplete mappings, unknown compounds, and invalid layers. The integrated 24 focused effect cases still pass all 128 assertions.

The unit contracts and seeded sequences do not certify every protection variant, all catalogue interactions, or complete-match reliability. The user installation, deck profiles, and update channel remain unchanged.
