using System;
using System.Collections.Generic;
using HarmonyLib;
using UnityEngine;
using Wizards.Mtga;
using Wizards.Mtga.Decks;
using Wotc.Mtga;
using Wotc.Mtga.Providers;

namespace ForgeArenaSandbox;

// Native deck cosmetic summary. Selection remains read-only until its local
// persistence and match presentation are connected; no account writes occur.
internal sealed class NativeDeckCosmeticsView
{
    private static readonly Dictionary<DeckDetailsPopup,NativeDeckCosmeticsView> Owners=new Dictionary<DeckDetailsPopup,NativeDeckCosmeticsView>();
    private static bool _patched;
    private readonly DeckDetailsPopup _popup;
    private readonly PAPA _papa;
    private readonly ICardRolloverZoom _zoom;
    public NativeDeckCosmeticsView(DeckDetailsPopup popup,PAPA papa,ICardRolloverZoom zoom)
    {
        _popup=popup;_papa=papa;_zoom=zoom;Owners.Add(popup,this);
        if(!_patched)
        {
            new Harmony("local.forge-arena.deck-cosmetic-context").Patch(AccessTools.Method(typeof(CardBackSelectorPopup),"Init"),prefix:new HarmonyMethod(typeof(NativeDeckCosmeticsView),nameof(InitSleeve)));
            _patched=true;
        }
        popup.DisplayItemGridTransform.gameObject.SetActive(true);
        popup.SelectorTransform.gameObject.SetActive(true);
        popup.CosmeticSelector.Init(popup.DisplayItemGridTransform,popup.SelectorTransform,true);
        popup.CosmeticSelector.CloseAllCosmeticSelectors();
    }
    private static bool InitSleeve(CardBackSelectorPopup __instance)
    {
        foreach(var owner in Owners.Values)
        {
            if(!__instance.transform.IsChildOf(owner._popup.transform))continue;
            // The original Init requests the account scene's zoom service and
            // passes an uninitialized database to the holder. Supply this
            // persistent menu's existing database, builder and zoom instead.
            AccessTools.Field(typeof(CardBackSelectorPopup),"_cosmeticsProvider").SetValue(__instance,Pantry.Get<CosmeticsProvider>());
            AccessTools.Field(typeof(CardBackSelectorPopup),"_cardDatabase").SetValue(__instance,owner._papa.CardDatabase);
            var holder=(MetaCardHolder)AccessTools.Field(typeof(CardBackSelectorPopup),"_cardHolder").GetValue(__instance);
            holder.EnsureInit(owner._papa.CardDatabase,owner._papa.CardViewBuilder);holder.RolloverZoomView=owner._zoom;
            return false;
        }
        return true;
    }
    public void SetData(DeckViewInfo info)
    {
        _popup.CosmeticSelector.SetData(info.deck,info.accountCosmeticDefaults,true);
        _popup.CosmeticSelector.CloseAllCosmeticSelectors();
    }
    public void Hide()=>_popup.CosmeticSelector.CloseAllCosmeticSelectors();
    public static void Release(DeckDetailsPopup popup)=>Owners.Remove(popup);
}
