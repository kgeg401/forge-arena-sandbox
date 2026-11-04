using System;
using HarmonyLib;
using GreAction=Wotc.Mtgo.Gre.External.Messaging.Action;

namespace ForgeArenaSandbox;

[HarmonyPatch(typeof(global::ActionExtensions),nameof(global::ActionExtensions.CanAffordToCast))]
internal static class NativeCastAvailability
{
    internal static Func<GreAction,bool>? AuthoritativeCast;

    // Forge has already checked payment and timing. Its native cast offers do
    // not contain the retail GRE auto-tap plan this UI helper normally requires.
    internal static bool Evaluate(GreAction action,bool nativeAffordable)
        => nativeAffordable || AuthoritativeCast?.Invoke(action)==true;

    private static void Postfix(GreAction action,ref bool __result)
        => __result=Evaluate(action,__result);
}
