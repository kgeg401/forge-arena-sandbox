# 0.01 alpha client work

Scope: one dedicated Windows launcher; persistent original Arena Home, Decks,
Packs and Play controls; local Practice and Brawl queues with a Forge AI.
No retail account, online queue, game asset redistribution, or general card
support claim. Gameplay admission remains the independently verified 252-card
checkpoint. Existing unfinished Paradox Engine work is excluded from this release.

## Verified during implementation

- Original Home and navigation prefabs render with the installed background,
  fonts, buttons and animations. Advertising/onboarding banners are removed.
- Original Play Blade displays local decks, Practice and Brawl tabs. Native deck
  warnings distinguish invalid decks, and the original Play button follows the
  selected deck's local admission checks.
- Physical mouse input selected Brawl, selected Isamaru, and entered an actual
  Forge Brawl game. Native board: 25 life, both commanders, free first mulligan.
  Original Mulligan/Keep callbacks reached Forge; original Options/Concede and
  Defeat/Continue were exercised separately.
- Two additional Brawl games started and returned to Home in one native process.
  The reference to the prior MatchScene is released; a separate LocalClient
  scene prevents Unity from retaining the last loaded match scene.
- Pack catalog generation now reads installed enum data emitted by the native
  adapter, rather than depending on a private decompiled enum file. It reproduces
  51 sets and 13,326 local printings. These are custom sandbox packs, not retail
  collation or additional verified gameplay support.
- Original Packs carousel renders under the shared navigation after native
  preloading settles. Initial warm-up must be gated before user presentation.
- Existing updater regression: 44 checks. Existing startup/update regression:
  22 checks. New coordinator and installed alpha launcher still require their
  dedicated acceptance pass.

## Remaining release acceptance

1. Finish warm-up/error/settings presentation and coordinated cancellation.
2. Run normal Practice/Brawl games, including source result/Continue, in the
   packaged client; repeat navigation, pack opening, and deck editing afterward.
3. Verify Brawl starter/bot lists and independent validation of invalid decks.
4. Exercise new dedicated launcher, duplicate launch, installed update, profile
   preservation, rollback and restart. Preserve unrelated shortcut/files.
5. Build and scan adapter-only payload; update consumer documentation and public
   source; publish one release titled **0.01 alpha** with verified download.

Private rendered/runtime evidence stays under the alpha-client research folder
on D:. No devlog video is being produced.
