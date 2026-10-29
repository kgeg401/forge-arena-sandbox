using System;
using Core.Meta.Cards.Views;
using HarmonyLib;

namespace ForgeArenaSandbox;

// DraggingCard's setter still raises the native OnDragStateChange event. Only
// its account-backed companion preview callback is excluded for local views.
public static class NativeDeckDragAdapter
{
    private static Func<MetaCardView,bool>? _owns;
    private static bool _patched,_localDrag;
    public static void Initialize(Func<MetaCardView,bool> owns)
    {
        _owns=owns;if(_patched)return;
        new Harmony("local.forge-arena.deck-drag-context").Patch(AccessTools.Method(typeof(MetaCardViewDragState),"OnDraggedCardChange"),prefix:new HarmonyMethod(typeof(NativeDeckDragAdapter),nameof(CompanionPreview)));
        _patched=true;
    }
    private static bool CompanionPreview(MetaCardView? draggingCard)
    {
        if(draggingCard!=null && _owns?.Invoke(draggingCard)==true){_localDrag=true;return false;}
        if(draggingCard==null && _localDrag){_localDrag=false;return false;}
        return true;
    }
}
