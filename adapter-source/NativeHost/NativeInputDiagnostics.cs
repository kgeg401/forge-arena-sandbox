using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.EventSystems;

namespace ForgeArenaSandbox;

// Optional observation only. Never invokes handlers or changes input/rules.
[HarmonyPatch]
internal static class NativeInputDiagnostics
{
    internal static bool Enabled;
    internal static readonly Queue<JObject> Events=new Queue<JObject>();
    static IEnumerable<MethodBase> TargetMethods()
    {
        foreach(string name in new[]{"OnPointerEnter","OnPointerClick","HandleClick","OnBeginDrag","OnEndDrag"})
            yield return typeof(CardInput).GetMethod(name)!;
    }
    static void Prefix(CardInput __instance,MethodBase __originalMethod,PointerEventData eventData)
    {
        if(!Enabled)return;
        var view=__instance.GetComponent<DuelScene_CDC>();
        Events.Enqueue(new JObject{["utc"]=DateTime.UtcNow,["method"]=__originalMethod.Name,["card"]=view?.InstanceId,
            ["position"]=eventData.position.ToString(),["clickCount"]=eventData.clickCount,["dragging"]=eventData.dragging,["visible"]=__instance.IsVisible,["enabled"]=__instance.enabled});
        while(Events.Count>100)Events.Dequeue();
    }
}
