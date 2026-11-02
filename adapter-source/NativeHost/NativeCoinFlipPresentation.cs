using System.Collections.Generic;
using System;
using System.Reflection;
using UnityEngine;
using System.Linq;
using AssetLookupTree;
using GreClient.Rules;
using HarmonyLib;
using Pooling;
using Wotc.Mtga.DuelScene.UXEvents;

namespace ForgeArenaSandbox;

[HarmonyPatch(typeof(CoinFlipEventTranslator),nameof(CoinFlipEventTranslator.Translate))]
internal static class NativeCoinFlipPresentation
{
    // The shipped translator indexes events[-1] when a flip is the first UX event.
    [HarmonyPrefix]
    private static bool FirstEvent(IReadOnlyList<GameRulesEvent> allChanges,int changeIndex,List<UXEvent> events,
        IUnityObjectPool ____unityObjectPool,AssetLookupSystem ____assetLookupSystem)
    {
        if(events.Count!=0 || allChanges[changeIndex] is not CoinFlipEvent flip)return true;
        events.Add(new ChooseRandomUXEvent_CoinFlip(flip.AffectorId,flip.AffectedId,flip.Results,____unityObjectPool,____assetLookupSystem));
        return false;
    }
}

[HarmonyPatch(typeof(DefaultEventTranslation),nameof(DefaultEventTranslation.GenerateEvents))]
internal static class NativeCoinFlipOrder
{
    // Reveal randomness before this snapshot changes cards, counters or displayed life.
    [HarmonyPostfix]
    internal static void RevealBeforeConsequences(List<UXEvent> __result)
    {
        var flips=__result.OfType<ChooseRandomUXEvent_CoinFlip>().Cast<UXEvent>().ToArray();
        if(flips.Length==0)return;
        __result.RemoveAll(e=>e is ChooseRandomUXEvent_CoinFlip);
        __result.InsertRange(0,flips);
    }
}

[HarmonyPatch(typeof(ChooseRandomUXEvent_CoinFlip),nameof(ChooseRandomUXEvent_CoinFlip.Execute))]
internal static class NativeCoinFlipTogether
{
    private static readonly MethodInfo Flip=AccessTools.Method(typeof(ChooseRandomUXEvent_CoinFlip),"FlipCoin");

    [HarmonyPostfix]
    private static void StartTogether(ChooseRandomUXEvent_CoinFlip __instance,List<bool> ____flipResults,
        ref IUnityObjectPool ____unityObjectPool,ref int ____nextCoinToFlip,ref float ____duration,
        ChooseRandomUXEvent_CoinFlip_Data ____data)
    {
        if(____flipResults.Count<2)return;
        var camera=Camera.main ?? throw new InvalidOperationException("Coin reveal camera is unavailable");
        var original=____unityObjectPool;var pool=new CoinPool(original);____unityObjectPool=pool;
        try
        {
            for(;____nextCoinToFlip<____flipResults.Count;____nextCoinToFlip++)
            {
                Flip.Invoke(__instance,new object[]{0f,____flipResults[____nextCoinToFlip]});
                var coin=pool.Last ?? throw new InvalidOperationException("The native coin prefab was not produced");
                var point=CoinBurstLayout.Point(____nextCoinToFlip,____flipResults.Count);
                float depth=camera.WorldToViewportPoint(coin.transform.position).z;
                if(depth<=0)throw new InvalidOperationException("Coin reveal lies behind its camera");
                coin.transform.position=camera.ViewportToWorldPoint(new Vector3(point.X,point.Y,depth));
                coin.transform.localScale*=point.Scale;
            }
            ____duration=Math.Max(____data.FlipDuration,Math.Max(____data.HeadsAnimation.length,____data.TailsAnimation.length));
        }
        finally{____unityObjectPool=original;}
    }

    // Capture the object from the original native spawn without duplicating its effects.
    private sealed class CoinPool:IUnityObjectPool
    {
        private readonly IUnityObjectPool _inner;
        internal GameObject? Last;
        internal CoinPool(IUnityObjectPool inner)=>_inner=inner;
        public GameObject PopObject(GameObject prefab)=>Last=_inner.PopObject(prefab);
        public GameObject PopObject(GameObject prefab,Transform parent)=>_inner.PopObject(prefab,parent);
        public GameObject PopObject(string path)=>_inner.PopObject(path);
        public GameObject PopObject(string path,Transform parent)=>_inner.PopObject(path,parent);
        public void PushObject(GameObject value)=>_inner.PushObject(value);
        public void PushObject(GameObject value,bool worldPositionStays)=>_inner.PushObject(value,worldPositionStays);
        public void DeferredPushObject(GameObject value)=>_inner.DeferredPushObject(value);
        public void Clear()=>_inner.Clear();
        public void Destroy()=>_inner.Destroy();
    }
}
