using System.Collections.Generic;
using System;
using System.Reflection;
using System.Linq;
using Core.Code.Input;
using HarmonyLib;
using MovementSystem;
using UnityEngine;
using Wotc.Mtga.DuelScene;
using Wotc.Mtga.DuelScene.Battlefield;

namespace ForgeArenaSandbox;

// Inert outside this four-player view. No change to rules or selection IDs.
internal static class NativePodLayoutPatches
{
    [ThreadStatic] private static int _endpointDepth;
    internal static void Install()
    {
        var harmony = new Harmony("local.forge-arena.pod-shared-table");
        try
        {
            foreach (var type in typeof(CardHolderBase).Assembly.GetTypes().Where(t => typeof(CardHolderBase).IsAssignableFrom(t)))
                foreach (var method in type.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.DeclaredOnly).Where(m => !m.IsAbstract && m.Name == "GetLayoutEndpoint" && m.ReturnType == typeof(IdealPoint) && m.GetParameters().Length == 1 && m.GetParameters()[0].ParameterType == typeof(CardLayoutData)))
                    harmony.Patch(method, prefix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(EnterEndpoint)), postfix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(Endpoint)), finalizer: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(EndpointFailure)));
            harmony.Patch(AccessTools.Method(typeof(PlayerFocusController_Quadrant), "FocusPlayer_Internal"), prefix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(KeepCamera)));
            harmony.Patch(AccessTools.Method(typeof(PlayerFocusController_Quadrant), "OnUpdate"), prefix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(KeepCamera)));
            harmony.Patch(AccessTools.Method(typeof(BattlefieldCardHolder), "GetCurrentlyHoveredRegion"), prefix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(HoverRegion)));
            harmony.Patch(AccessTools.Method(typeof(BattlefieldCardHolder.BattlefieldLayout), "GenerateData"), postfix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(RegionDetails)));
            harmony.Patch(AccessTools.Method(typeof(ZoneLayoutMediator), "PositionCardHolder"), postfix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(ZoneCreated)));
            harmony.Patch(AccessTools.Method(typeof(LibraryCardHolder), "AdjustCollider"), postfix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(LibraryCollider)));
            harmony.Patch(AccessTools.Method(typeof(GraveyardCardHolder), "UpdateEffectVFX"), postfix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(GraveyardEffect)));
            // A real card click calls ViewGraveyard/ViewLibrary directly;
            // patching only the holder's pointer handler misses that route.
            foreach (var method in new[] { AccessTools.Method(typeof(LibraryCardHolder), "ViewLibrary"), AccessTools.Method(typeof(GraveyardCardHolder), "ViewGraveyard"), typeof(PlayerExileCardHolder).GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly).Single(m => m.Name.EndsWith(".OnPointerClick", StringComparison.Ordinal)) })
                harmony.Patch(method, prefix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(ZoneBrowserStarting)), postfix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(ZoneBrowser)));
            harmony.Patch(AccessTools.Method(typeof(ZoneCountView), "SetVisibility"), prefix: new HarmonyMethod(typeof(NativePodLayoutPatches), nameof(HideDuelZoneCounts)));
        }
        catch
        {
            // A different owned client build must not leave half a layout
            // installed when one of its expected native methods is absent.
            harmony.UnpatchSelf();
            throw;
        }
    }
    private static void EnterEndpoint() => _endpointDepth++;
    private static void Endpoint(CardHolderBase __instance, CardLayoutData data, ref IdealPoint __result)
    {
        _endpointDepth--; if (_endpointDepth == 0) NativeCommanderPodView.Active?.MapEndpoint(__instance, data, ref __result);
    }
    private static Exception? EndpointFailure(Exception? __exception) { if (__exception != null) _endpointDepth = Math.Max(0, _endpointDepth - 1); return __exception; }
    private static bool KeepCamera(PlayerFocusController_Quadrant __instance) { var view = NativeCommanderPodView.Active; return view?.IsReady != true || !view.Owns(__instance); }
    private static void ZoneCreated(CardHolderBase cardHolderBase, uint ownerId) => NativeCommanderPodView.Active?.PositionZone(cardHolderBase, ownerId, true);
    private static void LibraryCollider(LibraryCardHolder __instance) => NativeCommanderPodView.Active?.LibraryCollider(__instance);
    private static void GraveyardEffect(GraveyardCardHolder __instance) => NativeCommanderPodView.Active?.GraveyardEffect(__instance);
    private static void ZoneBrowserStarting(out BrowserBase? __state) => __state = NativeCommanderPodView.Active?.CurrentBrowser;
    private static void HideDuelZoneCounts(ref bool visible) { if (NativeCommanderPodView.Active?.IsReady == true) visible = false; }
    private static void ZoneBrowser(ZoneCardHolderBase __instance, BrowserBase? __state)
    {
        var view = NativeCommanderPodView.Active; if (view != null && !ReferenceEquals(view.CurrentBrowser, __state)) view.LabelZoneBrowser(__instance);
    }
    private static bool HoverRegion(BattlefieldCardHolder __instance, ref BattlefieldRegion? __result)
    {
        var view = NativeCommanderPodView.Active; if (view?.IsReady != true || !view.Owns(__instance) || __instance.Layout is not BattlefieldCardHolder.BattlefieldLayout layout) return true;
        __result = null; var camera = Camera.main; if (camera == null) return false;
        if (Physics.Raycast(camera.ScreenPointToRay(InputHelper.GetPointerPosition()), out var hit)) __result = layout.Regions.FirstOrDefault(r => r.AllCards.Any(c => c.Collider == hit.collider)); return false;
    }
    private static void RegionDetails(BattlefieldCardHolder.BattlefieldLayout __instance, List<CardLayoutData> allData)
    {
        var view = NativeCommanderPodView.Active; if (view?.IsReady != true || !view.Owns((BattlefieldCardHolder)AccessTools.Field(typeof(BattlefieldCardHolder.BattlefieldLayout), "_battlefield").GetValue(__instance))) return;
        view.FitBattlefields(allData);
        // Paging arrows and stack badges are not children of card roots.
        var pending = (List<BattlefieldCardHolder.StackCounterData>)AccessTools.Field(typeof(BattlefieldCardHolder.BattlefieldLayout), "_pendingStackCounters").GetValue(__instance);
        for (int i = 0; i < pending.Count && i < __instance.ActiveStackCounters.Count; i++)
        {
            uint seat = allData.FirstOrDefault(d => d.Card.InstanceId == pending[i].parentInstanceId)?.Card.Model.Instance.Controller?.InstanceId ?? 0;
            if (seat < 1 || seat > 4) continue; var badge = __instance.ActiveStackCounters[i]; badge.transform.position = view.MapPoint(pending[i].positon, seat, true); badge.transform.localScale = Vector3.one * view.Scale(seat, true);
        }
        foreach (var entry in __instance.RegionsByCardTypeAndOwnerId.Values.SelectMany(d => d).GroupBy(p => p.Value))
        {
            uint seat = entry.First().Key; var region = entry.Key;
            foreach (var arrow in new[] { region.LeftPagingButton, region.RightPagingButton }) if (arrow != null && arrow.gameObject.activeInHierarchy) { arrow.transform.position = view.MapPoint(arrow.transform.position, seat, true); arrow.transform.localScale = Vector3.one * view.Scale(seat, true); }
        }
    }
}
