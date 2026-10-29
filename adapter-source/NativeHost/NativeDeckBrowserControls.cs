using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using HarmonyLib;
using Newtonsoft.Json.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.Events;
using Core.Shared.Code.CardFilters;
using Wizards.Arena.DeckValidation.Client;
using Wizards.Mtga;
using Wizards.Mtga.Decks;
using Wotc.Mtga.Loc;
using ManaColor=Wotc.Mtgo.Gre.External.Messaging.ManaColor;

namespace ForgeArenaSandbox;

// The original library widgets and comparator, bound to local deck data.
// Sandbox admission is deliberately distinct from retail format legality.
public sealed class NativeDeckBrowserControls
{
    public const string LibraryFormat="SandboxLibrary";
    private readonly DeckFilterBar _filter;
    private readonly TMP_Dropdown _sortDropdown,_formatDropdown;
    private readonly CustomButton _favorite;
    private readonly CustomButton[] _selectionButtons;
    private readonly Action _refresh;
    private readonly Func<string?> _selected;
    private readonly Func<string,JObject> _deck;
    private readonly Action<string,bool> _setFavorite;
    private string _query="";
    private int _format;
    private DeckViewSortType _sort=DeckViewSortType.LastModified;
    public string Query=>_query;
    public int FormatIndex=>_format;
    public int SortIndex=>_sortDropdown.value;
    public IReadOnlyList<ManaColor> Colors=>_filter.GetFilterColors();
    public int VisibleCount{get;private set;}
    public int TotalCount{get;private set;}
    private static object Field(object o,string name)=>AccessTools.Field(o.GetType(),name).GetValue(o);
    private static void Clear(UnityEventBase events){for(int i=0;i<events.GetPersistentEventCount();i++)events.SetPersistentListenerState(i,UnityEventCallState.Off);events.RemoveAllListeners();}
    private static void Bind(CustomButton button,Action action){Clear(button.OnClick);button.Interactable=true;button.OnClick.AddListener(()=>action());}
    private static string Loc(string key)=>Languages.ActiveLocProvider.GetLocalizedText(key);
    public NativeDeckBrowserControls(DeckManagerController manager,Action refresh,Func<string?> selected,Func<string,JObject> deck,Action<string,bool> setFavorite)
    {
        _refresh=refresh;_selected=selected;_deck=deck;_setFavorite=setFavorite;
        ((Transform)Field(manager,"_deckFilterBarPrefab")).gameObject.SetActive(true);
        _filter=(DeckFilterBar)Field(manager,"_deckColorFilterPrefab");_filter.gameObject.SetActive(true);
        // The account-backed manager lifecycle is skipped by the caller. Retain
        // the filter widget's own audio, search editing and clear callbacks.
        AccessTools.Field(typeof(DeckFilterBar),"FilterValueChanged").SetValue(_filter,null);
        AccessTools.Field(typeof(DeckFilterBar),"SearchTextChanged").SetValue(_filter,null);
        _filter.FilterValueChanged+=(type,value)=>_refresh();
        _filter.SearchTextChanged+=text=>{_query=text??"";_refresh();};
        _filter.SearchInput.interactable=true;
        foreach(var view in _filter.GetComponentsInChildren<CardFilterView>(true))view.FilterToggle.interactable=true;
        _sortDropdown=(TMP_Dropdown)Field(manager,"_deckOrderDropdown");
        Clear(_sortDropdown.onValueChanged);
        _sortDropdown.options=new List<TMP_Dropdown.OptionData>{new TMP_Dropdown.OptionData(Loc("MainNav/DeckManager/DeckManager_SortBy_LastModified")),new TMP_Dropdown.OptionData(Loc("MainNav/DeckManager/DeckManager_SortBy_LastPlayed")),new TMP_Dropdown.OptionData(Loc("MainNav/DeckManager/DeckManager_SortBy_Alphabetical"))};
        _sortDropdown.SetValueWithoutNotify(0);_sortDropdown.interactable=true;
        _sortDropdown.onValueChanged.AddListener(index=>{_sort=index==1?DeckViewSortType.LastPlayed:index==2?DeckViewSortType.Alphabetical:DeckViewSortType.LastModified;_refresh();});
        var order=(CustomButton)Field(manager,"_deckOrderButton");order.gameObject.SetActive(true);Bind(order,()=>_sortDropdown.Show());
        _formatDropdown=(TMP_Dropdown)Field(manager,"_deckBucketDropdown");Clear(_formatDropdown.onValueChanged);
        _formatDropdown.options=new List<TMP_Dropdown.OptionData>{new TMP_Dropdown.OptionData("All Decks"),new TMP_Dropdown.OptionData("Practice"),new TMP_Dropdown.OptionData("Brawl / Commander")};
        _formatDropdown.SetValueWithoutNotify(0);_formatDropdown.interactable=true;
        _formatDropdown.onValueChanged.AddListener(index=>{_format=index;_refresh();});
        var bucket=(CustomButton)Field(manager,"_deckBucketButton");bucket.gameObject.SetActive(true);Bind(bucket,()=>_formatDropdown.Show());
        _favorite=(CustomButton)Field(manager,"_favoriteDeckButton");_favorite.gameObject.SetActive(true);
        _selectionButtons=new[]{"_editDeckButton","_exportDeckButton","_cloneDeckButton","_deleteDeckButton","_deckDetailsButton"}.Select(name=>(CustomButton)Field(manager,name)).ToArray();
        Bind(_favorite,()=>{var id=_selected();if(id==null)return;_setFavorite(id,!((bool?)_deck(id)["favorite"]??false));_refresh();});
        SelectionChanged();
    }
    public void SelectionChanged()
    {
        var id=_selected();_favorite.Interactable=id!=null;foreach(var button in _selectionButtons)button.Interactable=id!=null;
        string key=id!=null && (bool?)_deck(id)["favorite"]==true?"MainNav/DeckManager/DeckManager_Top_Unfavorite":"MainNav/DeckManager/DeckManager_Top_Favorite";
        _favorite.SetText(Loc(key),warnOnMissingTextComponent:false);
    }
    public List<DeckViewInfo> Apply(List<DeckViewInfo> infos)
    {
        TotalCount=infos.Count;var colors=_filter.GetFilterColors();
        var visible=infos.Where(info=>colors.All(c=>info.manaColors.Contains(c)) && info.deckName.IndexOf(_query,StringComparison.OrdinalIgnoreCase)>=0);
        if(_format!=0)visible=visible.Where(info=>((JObject)_deck(info.deckId.ToString())["commander"]!).HasValues || (string?)_deck(info.deckId.ToString())["format"]=="arena-brawl" ? _format==2 : _format==1);
        var sorted=DeckViewUtilities.SortDeckViewInfo(visible.ToList(),LibraryFormat,_sort).ToList();VisibleCount=sorted.Count;return sorted;
    }
    public void QueryText(string text){_filter.SearchInput.text=text;_filter.SearchInput.onEndEdit.Invoke(text);}
    public void SetSort(int index){if(index<0||index>2)throw new ArgumentOutOfRangeException(nameof(index));_sortDropdown.value=index;}
    public void SetFormat(int index){if(index<0||index>2)throw new ArgumentOutOfRangeException(nameof(index));_formatDropdown.value=index;}
    public static void CompleteInfo(DeckViewInfo info,JObject deck,PAPA papa,bool matchAdmitted)
    {
        var contents=new Client_DeckContents();
        foreach(var pair in new[]{("main",EDeckPile.Main),("sideboard",EDeckPile.Sideboard),("commander",EDeckPile.CommandZone),("companion",EDeckPile.Companions)})
            contents.Piles[pair.Item2]=((JObject)deck[pair.Item1]!).Properties().Select(p=>new Client_DeckCard(uint.Parse(p.Name),(uint)p.Value)).ToList();
        info.deck.UpdateWith(contents);info.manaColors=info.deck.GetDeckColors(papa.CardDatabase.CardDataProvider,false).ToList();
        info.isFavorite=(bool?)deck["favorite"]??false;
        info.LastUpdated=ReadTime(deck,"updatedUtc");info.LastPlayed=ReadTime(deck,"lastPlayedUtc");info.DeckFormat=LibraryFormat;
        var validation=new DeckDisplayInfo(info.deck,matchAdmitted?DeckDisplayInfo.DeckDisplayState.Valid:DeckDisplayInfo.DeckDisplayState.Invalid,new ClientSideDeckValidationResult(),"");
        var cache=(Dictionary<string,DeckDisplayInfo>)Field(info,"_deckValidationStateByFormat");
        foreach(string format in new[]{LibraryFormat,"SandboxPractice","SandboxBrawl","SandboxCommander"})cache[format]=validation;
    }
    private static DateTime ReadTime(JObject deck,string key)=>DateTime.TryParse((string?)deck[key],CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind,out var value)?value.ToUniversalTime():DateTime.MinValue;
}
