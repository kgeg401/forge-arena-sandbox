using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using Core.Meta.MainNavigation.PopUps;
using TMPro;
using AssetLookupTree.Payloads.Prefab;
using Wizards.Mtga;
using Wizards.Mtga.Assets;
using Wizards.Mtga.Decks;
using Wotc.Mtga;

namespace ForgeArenaSandbox;

// Original deck statistics and presentation, bound to local data.
public sealed class NativeDeckDetailsView
{
    private static readonly Dictionary<DeckDetailsPopup,NativeDeckDetailsView> Owners=new Dictionary<DeckDetailsPopup,NativeDeckDetailsView>();
    private static bool _patched;
    private readonly DeckDetailsPopup _popup;
    private readonly PAPA _papa;
    private readonly Action<string,string> _rename;
    private readonly Action<string,string>? _changeFormat;
    private readonly Action<Exception>? _onError;
    private readonly NativeDeckCosmeticsView? _cosmetics;
    private string? _deckId;
    private string _name="";
    private int _formatIndex;
    public DeckDetailsPopup Popup=>_popup;
    private static void Clear(UnityEventBase value){for(int i=0;i<value.GetPersistentEventCount();i++)value.SetPersistentListenerState(i,UnityEventCallState.Off);value.RemoveAllListeners();}
    public NativeDeckDetailsView(PAPA papa,Transform parent,Action<string,string> rename,Action<string,string>? changeFormat=null,Action<Exception>? onError=null,ICardRolloverZoom? zoom=null)
    {
        _papa=papa;_rename=rename;_changeFormat=changeFormat;_onError=onError;
        if(!_patched)
        {
            var h=new Harmony("local.forge-arena.deck-details");
            h.Patch(AccessTools.Method(typeof(DeckDetailsPopup),"Show"),prefix:new HarmonyMethod(typeof(NativeDeckDetailsView),nameof(ShowLocal)));
            h.Patch(AccessTools.Method(typeof(DeckDetailsPopup),"OnDestroy"),prefix:new HarmonyMethod(typeof(NativeDeckDetailsView),nameof(DestroyLocal)));
            _patched=true;
        }
        _popup=AssetLoader.Instantiate<DeckDetailsPopup>(papa.AssetLookupSystem.GetPrefabPath<DeckDetailsPrefab,DeckDetailsPopup>(),parent);
        Owners.Add(_popup,this);_popup.gameObject.SetActive(false);
        foreach(var button in _popup.CloseButtons){Clear(button.OnClick);button.OnClick.AddListener(Hide);button.Interactable=true;}
        Clear(_popup._deckNameInput.onEndEdit);_popup._deckNameInput.characterLimit=80;
        _popup._deckNameInput.onEndEdit.AddListener(value=>{
            if(_deckId==null)return;
            value=value.Trim();if(value.Length==0){_popup.SetDeckName(_name);return;}
            if(value!=_name)try{_rename(_deckId,value);_name=value;}catch(Exception error){_popup.SetDeckName(_name);Report(error);}
        });
        if(zoom!=null)_cosmetics=new NativeDeckCosmeticsView(_popup,papa,zoom);
        else{_popup.DisplayItemGridTransform.gameObject.SetActive(false);_popup.SelectorTransform.gameObject.SetActive(false);}
        _popup.DisableSleeveSelection();
        ((EventTrigger)AccessTools.Field(typeof(DeckDetailsPopup),"_deckBoxHitbox").GetValue(_popup)).enabled=false;
        Clear(_popup.FormatDropdown.onValueChanged);_popup.FormatDropdown.interactable=_changeFormat!=null;_popup.FormatButton.Interactable=_changeFormat!=null;
        _popup.FormatDropdown.onValueChanged.AddListener(index=>{
            if(_deckId==null || index==_formatIndex)return;
            try{_changeFormat!(_deckId,index==1?"arena-brawl":"practice");_formatIndex=index;}
            catch(Exception error){_popup.FormatDropdown.SetValueWithoutNotify(_formatIndex);Report(error);}
        });
    }
    private static bool ShowLocal(DeckDetailsPopup __instance)
    {
        if(!Owners.ContainsKey(__instance))return true;
        __instance.gameObject.SetActive(true);AccessTools.PropertySetter(typeof(PopupBase),"IsShowing").Invoke(__instance,new object[]{true});
        // Retain PopupBase.Show's focus/keyboard registration. Skipping only
        // the account model binding must not bypass the native modal manager.
        ((PopupManager?)AccessTools.Field(typeof(PopupBase),"_popupManager").GetValue(__instance))?.RegisterPopup(__instance);
        return false;
    }
    private static bool DestroyLocal(DeckDetailsPopup __instance)
    {
        if(!Owners.Remove(__instance))return true;
        NativeDeckCosmeticsView.Release(__instance);
        var loaders=AccessTools.Field(typeof(DeckDetailsPopup),"_meshRendererReferenceLoaders");
        if(loaders.GetValue(__instance) is Array values)foreach(var value in values)if(value!=null)AccessTools.Method(value.GetType(),"Cleanup").Invoke(value,null);
        loaders.SetValue(__instance,null);return false;
    }
    public void Open(JObject deck,DeckViewInfo info)
    {
        _deckId=(string)deck["id"]!;_name=(string)deck["name"]!;
        var cards=((JObject)deck["main"]!).Properties().Select(p=>new CardPrintingQuantity{Printing=_papa.CardDatabase.CardDataProvider.GetCardPrintingById(uint.Parse(p.Name)),Quantity=(uint)p.Value}).ToList();
        _popup.SetDeck(cards,_papa.CardDatabase.GreLocProvider);_popup.SetDeckName(_name);
        _popup.SetDeckBoxTexture(info.deckImageAssetPath,info.crop);_popup.SetDeckBoxSleeve("CardBack_Default",_papa.CardDatabase,_papa.CardViewBuilder);
        _cosmetics?.SetData(info);
        _formatIndex=((JObject)deck["commander"]!).HasValues || (string?)deck["format"]=="arena-brawl"?1:0;
        _popup.FormatContainer.SetActive(true);_popup.FormatDropdown.options=new List<TMP_Dropdown.OptionData>{new TMP_Dropdown.OptionData("Practice"),new TMP_Dropdown.OptionData("Brawl / Commander")};
        _popup.FormatDropdown.SetValueWithoutNotify(_formatIndex);_popup.FormatDropdown.RefreshShownValue();_popup.Activate(true);
    }
    private void Report(Exception error){if(_onError!=null)_onError(error);else throw error;}
    public void Hide(){if(_popup!=null){_cosmetics?.Hide();_popup.Activate(false);}}
}
