using System;
using System.IO;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using AssetLookupTree.Payloads.Prefab;
using Core.Code.AssetLookupTree.AssetLookup;
using Wizards.Mtga;
using Wizards.Mtga.Assets;
using Wotc.Mtga;
using Wotc.Mtga.Extensions;
using Wizards.Mtga.Decks;
using Wizards.Mtga.Inventory;
using Pooling;
using Wotc.Mtga.Cards.ArtCrops;
using Wotc.Mtga.Cards.Database;
using GreClient.CardData;
using Wotc.Mtga.Loc;
using UnityEngine.Events;
using Core.Shared.Code.CardFilters;
using Wotc.Mtga.Cards;

namespace ForgeArenaSandbox;

// Owned prefab presentation, local deck data. No account deck service is invoked.
internal sealed class NativeDeckScreen
{
    private readonly string _root;
    private readonly PAPA _papa;
    private readonly Action<string> _log;
    private NativeMenuSurface? _surface;
    private WrapperDeckBuilder? _wrapper;
    private DeckBuilderWidget? _widget;
    private DeckListView? _list;
    private CardPoolHolder? _pool;
    private SearchAndFilterBar? _header;
    private DeckManagerController? _manager;
    private DeckFolderView? _folder;
    private string? _selected;
    private bool _browsing;
    private NativeDeckBrowserControls? _browser;
    private NativeDeckDetailsView? _details;
    private NativeCatalogueView? _catalogue;
    private NativeClientDialogs? _dialogs;
    private LocalDeckLibrary? _library;
    private JObject? _deck;
    private string _message="";
    private string _query="";
    private bool _dirty;
    private bool _choosingCommander;
    private NativeCatalogueFilters? _filters;
    private AdvancedFiltersView? _advanced;
    private bool _syncingFilters;
    private bool _largeCards;
    private int _poolResultCount;
    private uint[] _poolIds=Array.Empty<uint>();
    private static NativeDeckScreen? _active;
    private bool _constructing;
    private Coroutine? _pendingDrop;
    public NativeDeckScreen(string root,PAPA papa,Action<string> log,NativeMenuSurface? surface=null,NativeClientDialogs? dialogs=null){_root=root;_papa=papa;_log=log;_surface=surface;_dialogs=dialogs;}
    public void Hide(){CancelDrag();if(_dirty)Save();_details?.Hide();_advanced?.gameObject.SetActive(false);_surface?.ClearTransientPresentation();if(_wrapper!=null)_wrapper.gameObject.SetActive(false);if(_manager!=null)_manager.gameObject.SetActive(false);}
    public void FlushProfile(){if(_dirty && _deck!=null){_library!.Save(_deck);_dirty=false;_log("Saved pending local deck changes on client exit.");}}
    public LocalDeckLibrary Library=>_library!;
    public List<DeckViewInfo> DeckInfos()=>_library!.Decks.OfType<JObject>().Select(GetInfo).ToList();
    public JObject DeckById(Guid id)=>Find(id.ToString());
    public void EditDeck(Guid id)=>Edit(id.ToString());
    private static object Field(object obj,string name)=>AccessTools.Field(obj.GetType(),name).GetValue(obj);
    private static bool Owned(Component obj)=>_active!=null && (_active._constructing || (_active._surface!=null && obj.transform.IsChildOf(_active._surface.Root)));
    private static bool SkipOnlineLifecycle(Component __instance)=>!Owned(__instance);
    public void Open()
    {
        if(_wrapper!=null){ShowLibrary();return;}
        _library=new LocalDeckLibrary(Path.Combine(_root,"local-profile","decks.json"),Path.Combine(_root,"deck-catalog.json"));
        _filters=new NativeCatalogueFilters(_papa.CardDatabase,_library.Cards.Keys);
        _surface=_surface??new NativeMenuSurface(_papa);_active=this;
        NativeDeckDragAdapter.Initialize(card=>card.Holder!=null && (ReferenceEquals(card.Holder,_pool) || (_list!=null && ReferenceEquals(card.Holder,_list.MainDeckCardHolder))));
        var harmony=new Harmony("local.codex.forge-arena-decks");
        foreach(var spec in new[]{(typeof(WrapperDeckBuilder),new[]{"Awake","OnEnable","OnDestroy","Update"}),(typeof(DeckBuilderWidget),new[]{"OnEnable","OnDisable","OnDestroy"}),(typeof(DeckListView),new[]{"OnEnable","OnDisable","OnDestroy"}),(typeof(DeckMainTitlePanel),new[]{"OnEnable","OnDisable"}),(typeof(SearchAndFilterBar),new[]{"Awake","OnEnable","OnDisable","OnDestroy"}),(typeof(CardPoolHolder),new[]{"OnEnable","OnDisable","OnDestroy"}),(typeof(AdvancedFiltersView),new[]{"Awake","OnEnable","OnDisable"})})
            foreach(string method in spec.Item2)harmony.Patch(AccessTools.Method(spec.Item1,method),prefix:new HarmonyMethod(typeof(NativeDeckScreen),nameof(SkipOnlineLifecycle)));
        harmony.Patch(AccessTools.Method(typeof(CardPoolHolder),"Awake"),prefix:new HarmonyMethod(typeof(NativeDeckScreen),nameof(PoolAwake)));
        harmony.Patch(AccessTools.Method(typeof(CardPoolHolder),"Init"),prefix:new HarmonyMethod(typeof(NativeDeckScreen),nameof(PoolInit)));
        harmony.Patch(AccessTools.Method(typeof(CardPoolHolder),"ExpectedPoolRows"),prefix:new HarmonyMethod(typeof(NativeDeckScreen),nameof(PoolRows)));
        foreach(string method in new[]{"Awake","OnEnable","OnDestroy"})harmony.Patch(AccessTools.Method(typeof(DeckManagerController),method),prefix:new HarmonyMethod(typeof(NativeDeckScreen),nameof(SkipOnlineLifecycle)));
        foreach(string method in new[]{"Awake","OnDestroy"})harmony.Patch(AccessTools.Method(typeof(DeckViewSelector),method),prefix:new HarmonyMethod(typeof(NativeDeckScreen),nameof(SkipOnlineLifecycle)));
        harmony.Patch(AccessTools.Method(typeof(DeckFolderView),"OnFolderToggleChanged"),prefix:new HarmonyMethod(typeof(NativeDeckScreen),nameof(LocalFolderToggle)));
        _constructing=true;
        try
        {
            var path=_papa.AssetLookupSystem.GetPrefabPath<WrapperDeckBuilderPrefab,WrapperDeckBuilder>();
            _wrapper=AssetLoader.Instantiate<WrapperDeckBuilder>(path,_surface.Root);_wrapper.enabled=false;
            _widget=(DeckBuilderWidget)Field(_wrapper,"_deckbuilder");
            var listParent=(Transform)Field(_widget,"_deckListParent");
            ((Transform)Field(_widget,"_deckColumnParent")).gameObject.SetActive(false);listParent.gameObject.SetActive(true);
            _list=AssetLoader.Instantiate<DeckListView>(_papa.AssetLookupSystem.GetPrefabPath<DeckListViewPrefab,DeckListView>(),listParent);
            ((RectTransform)_list.transform).StretchToParent();
            var holder=_list.MainDeckCardHolder;holder.EnsureInit(_papa.CardDatabase,_papa.CardViewBuilder);holder.RolloverZoomView=_surface.Zoom;
            holder.OnCardAddClicked=v=>Act(()=>Adjust(v.Card.GrpId,1));holder.OnCardRemoveClicked=v=>Act(()=>Adjust(v.Card.GrpId,-1));
            holder.CanSingleClickCards=v=>false;holder.CanDragCards=v=>!_choosingCommander;
            holder.CanDropCards=v=>!_choosingCommander && ReferenceEquals(v.Holder,_pool);
            holder.OnCardDropped=(view,destination)=>QueueDrop(view,1);
            holder.ClearCommanderCards();holder.ClearPartnerCards();holder.ClearCompanionCards();
            var commander=holder._commanderHolder;commander.EnsureInit(_papa.CardDatabase,_papa.CardViewBuilder);commander.RolloverZoomView=_surface.Zoom;
            commander.CanSingleClickCards=v=>true;commander.CanDoubleClickCards=v=>false;commander.CanDragCards=v=>false;
            commander.OnCardClicked=v=>Act(()=>{_deck!["commander"]=new JObject();_deck["format"]="arena-brawl";_dirty=true;Refresh();});
            Bind(commander.AddButton,()=>{BeginCommanderChoice();RefreshPool();});
            _list.SideboardCardHolder.gameObject.SetActive(false);_list.SideboardTitlePanel.gameObject.SetActive(false);_list.ShowSideboardToggle.gameObject.SetActive(false);
            _list.SleevesButton.gameObject.SetActive(false);
            Clear(_list.DeckNameInput.onEndEdit);_list.DeckNameInput.characterLimit=80;
            _list.DeckNameInput.onEndEdit.AddListener(name=>Act(()=>{if(string.IsNullOrWhiteSpace(name))throw new InvalidDataException("Enter a deck name.");_deck!["name"]=name;_dirty=true;Refresh();}));
            _list.MainDeckTitlePanel.SetDeckFormatSelector(null!,false,false);
            Bind(_list.MainDeckTitlePanel.Button,()=>ShowDetails(_deck!));
            _list.SetSleeve("CardBack_Default",_papa.CardViewBuilder,_papa.CardDatabase);
            _pool=UnityEngine.Object.Instantiate((CardPoolHolder)Field(_widget,"_poolHolderPrefab"),(Transform)Field(_widget,"_poolParent"));
            ((RectTransform)_pool.transform).StretchToParent();_pool.EnsureInit(_papa.CardDatabase,_papa.CardViewBuilder);
            _pool.DirectlySetZoomHandler=_surface.Zoom;_pool.RolloverZoomView=_surface.Zoom;
            _pool.OnCardClicked=v=>Act(()=>{if(_choosingCommander){if(!_library!.IsVerifiedCommander(v.Card.GrpId))throw new InvalidDataException("This commander is not verified for Brawl.");_deck!["commander"]=new JObject{[v.Card.GrpId.ToString()]=1};_deck["format"]="arena-brawl";_choosingCommander=false;_dirty=true;Refresh();}else Adjust(v.Card.GrpId,1);});_pool.OnCardRightClicked=null;
            _pool.CanSingleClickCards=v=>true;_pool.CanDragCards=v=>!_choosingCommander;
            _pool.CanDropCards=v=>!_choosingCommander && ReferenceEquals(v.Holder,holder);
            _pool.OnCardDropped=(view,destination)=>QueueDrop(view,-1);
            _pool.ShowHighlight=v=>true;
            _header=UnityEngine.Object.Instantiate((SearchAndFilterBar)Field(_widget,"_headerPrefab"),(Transform)Field(_widget,"_headerParent"));
            ((RectTransform)_header.transform).StretchToParent();
            Clear(_header.SearchInput.onEndEdit);
            _header.SearchInput.onEndEdit.AddListener(query=>Act(()=>{_query=query.Trim();RefreshPool();}));
            Clear(_header.ClearSearchButton.onClick);_header.ClearSearchButton.onClick.AddListener(()=>Act(()=>{_query="";_header.SearchInput.text="";RefreshPool();}));
            Bind(_header.NewDeckButton,NewDeck);
            foreach(var toggle in _header.GetComponentsInChildren<Toggle>(true))toggle.interactable=false;
            _header.SearchInput.characterLimit=256;
            var nativeColors=new HashSet<CardFilterType>{CardFilterType.White,CardFilterType.Blue,CardFilterType.Black,CardFilterType.Red,CardFilterType.Green,CardFilterType.Color_Colorless,CardFilterType.Multicolor};
            foreach(var view in _header.GetComponentsInChildren<CardFilterView>(true).Where(v=>nativeColors.Contains(v.FilterType)))
            {
                var local=view;view.FilterToggle.SetIsOnWithoutNotify(false);view.FilterToggle.interactable=true;
                view.FilterToggle.onValueChanged.AddListener(value=>{if(!_syncingFilters)Act(()=>SetFilter(local.FilterType,value));});
            }
            _header.LandsToggle.SetIsOnWithoutNotify(false);_header.LandsToggle.interactable=true;
            _header.LandsToggle.onValueChanged.AddListener(value=>{if(!_syncingFilters)Act(()=>SetFilter(CardFilterType.Type_Land,value));});
            _header.LargeCardsToggle.SetIsOnWithoutNotify(false);_header.LargeCardsToggle.interactable=true;
            _header.LargeCardsToggle.onValueChanged.AddListener(value=>Act(()=>{_largeCards=value;RefreshPool();}));
            _header.CraftingModeToggle.gameObject.SetActive(false);_header.CompanionFilterToggle.gameObject.SetActive(false);_header.DeckFilterToggle.gameObject.SetActive(false);_header.FiltersUsedToggle.gameObject.SetActive(false);
            BuildAdvancedFilters();
            _header.SearchInput.ShowSearchTips+=visible=>((GameObject)Field(_header,"_advancedSearchTips")).SetActive(visible);
            Bind((CustomButton)Field(_widget,"_doneButton"),()=>{Save();ShowLibrary();});
            Bind((CustomButton)Field(_widget,"_backButton"),()=>{Save();ShowLibrary();});
            ((CustomButton)Field(_widget,"_backButton")).gameObject.SetActive(false);
            ((CustomButton)Field(_widget,"_batchCraftingButton")).gameObject.SetActive(false);
            ((CustomButton)Field(_widget,"_applySkinsButton")).gameObject.SetActive(false);
            _library.Seed(Path.Combine(_root,"local-deck-seeds"));
            _deck=_library.Decks.OfType<JObject>().FirstOrDefault()??_library.New("New sandbox deck");
            Refresh();BuildLibrary();ShowLibrary();_log("Original native deck list, card pool and deck browser connected to local library.");
        }
        finally{_constructing=false;}
    }
    private static bool PoolRows(CardPoolHolder __instance,ref int __result){if(!Owned(__instance))return true;__result=_active!._largeCards?1:2;return false;}
    private static bool LocalFolderToggle(DeckFolderView __instance){if(!Owned(__instance))return true;((Animator)Field(__instance,"_animator")).SetBool("Open",((Toggle)Field(__instance,"_folderToggle")).isOn);return false;}
    private static bool PoolAwake(CardPoolHolder __instance)
    {
        if(!Owned(__instance))return true;
        var field=AccessTools.Field(typeof(CardPoolHolder),"_pages");var pages=(IList)Activator.CreateInstance(field.FieldType)!;
        var pageType=field.FieldType.GetGenericArguments()[0];var parent=(Transform)Field(__instance,"_pageParent");
        for(int i=0;i<3;i++)
        {
            var trans=new GameObject("Local native card page "+i,typeof(RectTransform)).GetComponent<RectTransform>();trans.SetParent(parent,false);
            var page=Activator.CreateInstance(pageType,true)!;AccessTools.Field(pageType,"Trans").SetValue(page,trans);pages.Add(page);
        }
        field.SetValue(__instance,pages);AccessTools.Field(typeof(CardPoolHolder),"_cardDisplayInfos").SetValue(__instance,new List<PagesMetaCardViewDisplayInformation>());
        return false;
    }
    private static bool PoolInit(CardPoolHolder __instance,Wotc.Mtga.Cards.Database.CardDatabase cardDatabase,CardViewBuilder cardViewBuilder)
    {
        if(!Owned(__instance))return true;
        AccessTools.Property(typeof(MetaCardHolder),"CardDatabase").SetValue(__instance,cardDatabase);
        AccessTools.Property(typeof(MetaCardHolder),"CardViewBuilder").SetValue(__instance,cardViewBuilder);
        foreach(var pair in new[]{("_previousButton","ScrollPrevious"),("_nextButton","ScrollNext")})
        {var button=(CustomButton)Field(__instance,pair.Item1);button.OnClick.AddListener(()=>AccessTools.Method(typeof(CardPoolHolder),pair.Item2).Invoke(__instance,null));}
        return false;
    }
    private static void Clear(UnityEventBase events){for(int i=0;i<events.GetPersistentEventCount();i++)events.SetPersistentListenerState(i,UnityEventCallState.Off);events.RemoveAllListeners();}
    private void Bind(CustomButton button,Action action){button.Interactable=true;Clear(button.OnClick);button.OnClick.RemoveAllListeners();button.OnClick.AddListener(()=>Act(action));}
    private void Act(Action action)
    {
        try{action();_message="";}
        catch(Exception ex)
        {
            _message=ex.Message;_log(ex.ToString());
            // A details/filter modal can cover the deck header. Use Arena's
            // original notice above it so a rejected edit is still explained.
            _dialogs=_dialogs??new NativeClientDialogs(_papa);
            _dialogs.Show("Deck could not be changed",ex.Message);
        }
        ShowMessage();WriteStatus();
    }
    private void Adjust(uint id,int change)
    {
        var cards=(JObject)_deck!["main"]!;string key=id.ToString();int count=checked(((int?)cards[key]??0)+change);
        if(count>999)throw new InvalidDataException("Maximum 999 copies per printing.");
        int total=new[]{"main","sideboard","commander","companion"}.Sum(pile=>((JObject)_deck[pile]!).Properties().Sum(p=>(int)p.Value));
        if(change>0 && checked(total+change)>1000)throw new InvalidDataException("Local editing is limited to 1000 total cards.");
        if(count<=0)cards.Remove(key);else cards[key]=count;
        _dirty=true;Refresh(true);
    }
    private void QueueDrop(MetaCardView card,int change)
    {
        if(_pendingDrop!=null || _deck==null)return;
        _pendingDrop=_widget!.StartCoroutine(ApplyDrop(card.Card.GrpId,change,(string)_deck["id"]!));
    }
    private IEnumerator ApplyDrop(uint id,int change,string deckId)
    {
        // Let the original OnEndDrag restore/release its visual before a
        // quantity change can destroy the last list row or rebuild a pool page.
        yield return null;_pendingDrop=null;
        if(_browsing || _wrapper==null || !_wrapper.gameObject.activeInHierarchy || (string?)_deck?["id"]!=deckId)yield break;
        Act(()=>Adjust(id,change));
    }
    private void CancelDrag()
    {
        if(_pendingDrop!=null && _widget!=null){_widget.StopCoroutine(_pendingDrop);_pendingDrop=null;}
        _pool?.ReleaseAllDraggingCards();_list?.MainDeckCardHolder.ReleaseAllDraggingCards();
    }
    private void Save(){_library!.Save(_deck!);_dirty=false;_selected=(string)_deck!["id"]!;_log("Saved local deck "+_deck["id"]+" / "+_deck["name"]);Refresh();}
    private void NewDeck(){if(_dirty)Save();_deck=_library!.New("New sandbox deck");_dirty=true;_choosingCommander=false;ShowEditor();_pool!.ScrollToTop();Refresh();ChooseFormat();}
    private void BeginCommanderChoice()
    {
        _choosingCommander=true;_query="";_header!.SearchInput.text="";_filters!.Reset();SyncFilterControls();_pool!.ScrollToTop();
    }
    private void ChooseFormat()
    {
        var panel=_list!.MainDeckTitlePanel;
        panel.SetDeckFormatSelector(new List<DeckFormat>{new DeckFormat(null!,Languages.ActiveLocProvider){FormatName="SandboxPractice"},new DeckFormat(null!,Languages.ActiveLocProvider){FormatName="SandboxBrawl"}},true,true);
        var dropdown=(TMP_Dropdown)Field(panel,"_formatDropdown");Clear(dropdown.onValueChanged);dropdown.ClearOptions();dropdown.AddOptions(new List<string>{"Practice Bot","Brawl Bot",""});dropdown.SetValueWithoutNotify(2);dropdown.options.RemoveAt(2);
        dropdown.onValueChanged.AddListener(index=>Act(()=>{if(index<0 || index>1)throw new InvalidDataException("Choose Practice or Brawl.");if(index==0 && ((JObject)_deck!["commander"]!).HasValues){dropdown.SetValueWithoutNotify(1);throw new InvalidOperationException("Remove the commander before switching this deck to Practice.");}_deck!["format"]=index==1?"arena-brawl":"practice";_dirty=true;panel.SetDeckFormatSelector(null!,false,false);_choosingCommander=index==1 && !((JObject)_deck["commander"]!).HasValues;if(_choosingCommander)BeginCommanderChoice();else{_query="";_header!.SearchInput.text="";}Refresh();}));
    }
    private void Refresh(bool quantitiesOnly=false)
    {
        var values=((JObject)_deck!["main"]!).Properties().Select(p=>new{Id=uint.Parse(p.Name),Count=(uint)p.Value});
        var display=values.Select(p=>new ListMetaCardViewDisplayInformation{Card=_papa.CardDatabase.CardDataProvider.GetCardPrintingById(p.Id),Quantity=p.Count,Invalid=!(bool)_library!.Cards[p.Id]["matchSupported"]!}).ToList();
        display=CardSorter.Sort(display,_papa.CardDatabase,SortType.LandLast,SortType.CMCWithXLast,SortType.ColorOrder,SortType.Title).ToList();
        _list!.MainDeckCardHolder.SetCards(display);_list.DeckNameInput.SetTextWithoutNotify((string)_deck["name"]!);
        _list.CostWidget.SetDeck(display.Select(c=>new CardPrintingQuantity{Printing=c.Card,Quantity=c.Quantity}).ToList());
        var commanders=((JObject)_deck["commander"]!).Properties().ToArray();
        bool brawl=commanders.Length>0 || (string?)_deck["format"]=="arena-brawl";
        if(brawl)
        {
            _deck["format"]="arena-brawl";
            _list.MainDeckCardHolder.SetCommanderCards(new ListMetaCardViewDisplayInformation{Card=commanders.Length==1?_papa.CardDatabase.CardDataProvider.GetCardPrintingById(uint.Parse(commanders[0].Name)):null!,Quantity=1,Invalid=commanders.Length!=1 || !_library!.IsVerifiedCommander(uint.Parse(commanders[0].Name))});
            _list.MainDeckCardHolder._commanderHolder.SetAddButtonActive(commanders.Length==0);
        }
        else _list.MainDeckCardHolder.ClearCommanderCards();
        int total=display.Sum(c=>(int)c.Quantity)+(brawl?commanders.Sum(c=>(int)c.Value):0);
        var countFormat=new DeckFormat(null!,Languages.ActiveLocProvider){MinMainDeckCards=brawl?100:40,MaxMainDeckCards=brawl?100:250};
        _list.MainDeckTitlePanel.SetCardCount(total,countFormat,brawl?100:40,false);
        var text=(TMP_Text)Field(_list.MainDeckTitlePanel,"_detailsText");
        var gaps=_library!.MatchGaps(_deck);text.text=(brawl?"Brawl / Commander":"Practice")+(gaps.Length>0?" • "+gaps.Length+" issue(s)":"");
        if(quantitiesOnly && _catalogue!=null)_catalogue.RefreshQuantities();else RefreshPool(false);
        WriteStatus();
    }
    private void RefreshPool(bool resetPage=true)
    {
        _catalogue=_catalogue??new NativeCatalogueView(Path.Combine(_root,"local-profile","preferred-printings.json"),_papa,_pool!,_library!.Cards.Keys,id=>(bool)_library.Cards[id]["preferred"]!,()=>_deck!);
        var candidates=_library!.Cards.Values.Where(c=>!_choosingCommander || _library.IsVerifiedCommander((uint)c["grpId"]!))
            .ToArray();
        var criteria=_filters!.Selected.Contains(CardFilterType.Type_Land)?new[]{SortType.BasicLandsFirst,SortType.ColorOrder,SortType.CMCWithXLast,SortType.Title}:CardSorter.CardPoolNewCardsFirstSort;
        var matched=CardSorter.Sort(_filters.Apply(candidates.Select(c=>(uint)c["grpId"]!),_query),_papa.CardDatabase,false,criteria).ToArray();
        _catalogue.SetCards(matched,resetPage);_poolResultCount=_catalogue.TitleCount;_poolIds=_catalogue.DisplayIds.ToArray();
        if(_header!=null)_header.EventCardPoolTitleText.text=(_choosingCommander?"Choose a Brawl commander":"All Cards")+" ("+_poolResultCount+")";
    }
    private void SetFilter(CardFilterType type,bool value)
    {
        _filters!.Set(type,value);SyncFilterControls();
        if(_advanced==null || !_advanced.gameObject.activeSelf)RefreshPool();
    }
    private void SyncFilterControls()
    {
        _syncingFilters=true;
        try
        {
            var selected=_filters!.Selected;
            foreach(var view in _header!.GetComponentsInChildren<CardFilterView>(true).Concat(_advanced==null?Array.Empty<CardFilterView>():_advanced.GetComponentsInChildren<CardFilterView>(true)))
                if(view.FilterToggle!=null && view.FilterToggle.interactable)view.FilterToggle.isOn=selected.Contains(view.FilterType);
            _header.LandsToggle.isOn=selected.Contains(CardFilterType.Type_Land);
            _header.FiltersUsedToggle.SetIsOnWithoutNotify(selected.Count>0);
            if(_advanced!=null)foreach(var group in (IEnumerable)Field(_advanced,"_filterGroupsOfMTGSets"))
            {
                var views=(List<CardFilterView>)Field(group!,"AllFilterViews");
                ((Toggle)Field(group!,"Toggle")).SetIsOnWithoutNotify(views.Count>0 && views.All(view=>selected.Contains(view.FilterType)));
            }
        }
        finally{_syncingFilters=false;}
    }
    private void BuildAdvancedFilters()
    {
        _advanced=UnityEngine.Object.Instantiate((AdvancedFiltersView)Field(_widget!,"_advancedFiltersPrefab"),(Transform)Field(_widget!,"_popupRoot"));
        _advanced.gameObject.SetActive(true);
        foreach(string field in new[]{"FormatContainer","_formatInfoContainer","_formatDropdownSpacer1","_formatDropdownSpacer2","_formatSelectionAccordian","_formatNotLegalAccordian","_collectedCardsGroup"})
            ((GameObject)Field(_advanced,field)).SetActive(false);
        ((TMP_Dropdown)Field(_advanced,"_formatDropdown")).gameObject.SetActive(false);
        ((GameObject)Field(_advanced,"_collectedCardsGroup")).transform.parent.gameObject.SetActive(false);
        var onlineColumn=_advanced.transform.Find("Content/Scroll/Viewport/ContentCONTAINER/Column_2");
        if(onlineColumn==null)throw new InvalidDataException("The installed advanced filter layout changed.");
        onlineColumn.gameObject.SetActive(true);
        // Keep the original left-column graphics in a separate native UI batch.
        // Without this canvas the persistent popup drops their clipped meshes.
        // Inherit sorting and the outer viewport mask; retain normal scrolling.
        var filterColumn=_advanced.transform.Find("Content/Scroll/Viewport/ContentCONTAINER/Column_1");
        var columnCanvas=filterColumn.gameObject.AddComponent<Canvas>();columnCanvas.overrideSorting=false;
        filterColumn.gameObject.AddComponent<GraphicRaycaster>();
        var groups=((IEnumerable)Field(_advanced,"_filterGroupsOfMTGSets")).Cast<AdvancedFiltersView.FilterGroupView>().ToArray();
        foreach(var group in groups)
        {
            group.Container.SetActive(false);group.Toggle.gameObject.SetActive(false);
        }
        var setGroup=groups[0];var prefab=(CardFilterView)Field(_advanced,"_setFilterViewPrefab");
        foreach(var set in _filters!.SetFilters.OrderByDescending(s=>(int)s.Key))
        {
            var view=UnityEngine.Object.Instantiate(prefab,setGroup.Container.transform);view.Initialize(set.Key,set.Value);setGroup.AllFilterViews.Add(view);
        }
        for(var node=setGroup.Container.transform;node!=null && node!=_advanced.transform;node=node.parent)node.gameObject.SetActive(true);
        ((TMP_Text)Field(_advanced,"_formatLegalText")).text=Languages.ActiveLocProvider.GetLocalizedText("MainNav/Collection/AllSets");
        Clear(setGroup.Toggle.onValueChanged);setGroup.Toggle.gameObject.SetActive(true);setGroup.Toggle.interactable=true;
        setGroup.Toggle.onValueChanged.AddListener(value=>Act(()=>{foreach(var view in setGroup.AllFilterViews)view.FilterToggle.isOn=value;}));
        foreach(var view in _advanced.GetComponentsInChildren<CardFilterView>(true))
        {
            var local=view;bool available=!view.FilterType.ToString().StartsWith("Collection_");
            view.FilterToggle.interactable=available;
            if(available)view.FilterToggle.onValueChanged.AddListener(value=>{if(!_syncingFilters)Act(()=>SetFilter(local.FilterType,value));});
        }
        Bind((CustomButton)Field(_advanced,"_doneButton"),()=>{_advanced.Hide(false);RefreshPool();});
        var reset=(Button)Field(_advanced,"_resetButton");Clear(reset.onClick);
        reset.onClick.AddListener(()=>Act(()=>{_filters!.Reset();_query="";_header!.SearchInput.text="";SyncFilterControls();}));
        Clear(_header!.AdvancedFiltersButton.onClick);_header.AdvancedFiltersButton.interactable=true;
        _header.AdvancedFiltersButton.onClick.AddListener(()=>Act(()=>{
            _surface!.ClearTransientPresentation();SyncFilterControls();_advanced.Show();
        }));
        _header.FiltersUsedToggle.gameObject.SetActive(true);_header.FiltersUsedToggle.interactable=false;
        SyncFilterControls();_advanced.gameObject.SetActive(false);
    }
    private void BuildLibrary()
    {
        _manager=AssetLoader.Instantiate<DeckManagerController>(_papa.AssetLookupSystem.GetPrefabPath<DeckManagerPrefab,DeckManagerController>(),_surface!.Root);
        _manager.enabled=false;
        var parent=(Transform)Field(_manager,"_deckSelectorParent");
        var selector=AssetLoader.Instantiate<DeckViewSelector>(_papa.AssetLookupSystem.GetPrefabPath<DeckViewSelectorPrefab,DeckViewSelector>(),parent);
        ((RectTransform)selector.transform).StretchToParent();
        _folder=UnityEngine.Object.Instantiate(selector._deckFolderViewNoFolderPrefab,(Transform)Field(selector,"_folderParent"));
        _folder.Initialize(info=>Act(()=>Select(info.deckId.ToString())),info=>Act(()=>Edit(info.deckId.ToString())),null!,()=>DeckManagerMode.SingleSelectMode,(info,name)=>Act(()=>{var deck=Find(info.deckId.ToString());deck["name"]=name;_library!.Save(deck);ShowLibrary();}),_=>{});
        // The native builder only needs local presentation dependencies here.
        var builder=new DeckViewBuilder();
        foreach(var pair in new (string,object)[]{("_unityObjectPool",_papa.UnityPool),("_assetLookupSystem",_papa.AssetLookupSystem),("_cardViewBuilder",_papa.CardViewBuilder),("_cardDatabase",_papa.CardDatabase),("_metaCardViewBuilder",new MetaCardBuilder(_papa.CardViewBuilder))})AccessTools.Field(typeof(DeckViewBuilder),pair.Item1).SetValue(builder,pair.Item2);
        AccessTools.Field(typeof(DeckFolderView),"_deckViewBuilder").SetValue(_folder,builder);
        _folder.ShowCreateDeckButton(()=>Act(NewDeck));_folder.SetFolderOpenState(true);
        Bind((CustomButton)Field(_manager,"_editDeckButton"),()=>Edit(Selected()));
        ((CustomButton)Field(_manager,"_editDeckButton")).SetText(Languages.ActiveLocProvider.GetLocalizedText("MainNav/DeckManager/Button_Edit"));
        Bind((CustomButton)Field(_manager,"_importDeckButton"),()=>{var imported=_library!.Import(GUIUtility.systemCopyBuffer,"Imported deck");_library.Save(imported);_selected=(string)imported["id"]!;ShowLibrary();});
        Bind((CustomButton)Field(_manager,"_exportDeckButton"),()=>{var deck=Find(Selected());var text=_library!.Export(deck);GUIUtility.systemCopyBuffer=text;ExportFile(deck);_log("Exported deck to clipboard and local file: "+deck["id"]);});
        Bind((CustomButton)Field(_manager,"_cloneDeckButton"),()=>{var deck=Find(Selected());deck["id"]=Guid.NewGuid().ToString();deck["name"]=((string)deck["name"]!).Substring(0,Math.Min(73,((string)deck["name"]!).Length))+" (copy)";deck.Remove("favorite");deck.Remove("lastPlayedUtc");_library!.Save(deck);_selected=(string)deck["id"]!;ShowLibrary();});
        Bind((CustomButton)Field(_manager,"_deleteDeckButton"),()=>{
            var id=Selected();var name=(string)Find(id)["name"]!;_dialogs=_dialogs??new NativeClientDialogs(_papa);
            _dialogs.Confirm("Delete local deck?","Delete “"+name+"”? This removes it from this sandbox's deck library.","Delete",()=>Act(()=>{_library!.Delete(id);_selected=null;ShowLibrary();}));
        });
        foreach(string field in new[]{"_craftAllButton","_collectionButton"})((CustomButton)Field(_manager,field)).gameObject.SetActive(false);
        var details=(CustomButton)Field(_manager,"_deckDetailsButton");details.gameObject.SetActive(true);Bind(details,OpenDetails);
        foreach(var dropdown in _manager.GetComponentsInChildren<TMP_Dropdown>(true))dropdown.interactable=false;
        _browser=new NativeDeckBrowserControls(_manager,ShowLibrary,()=>_selected,Find,(id,value)=>_library!.SetFavorite(id,value));
    }
    private JObject Find(string id)=>_library!.Decks.OfType<JObject>().First(d=>string.Equals((string)d["id"]!,id,StringComparison.OrdinalIgnoreCase));
    private string Selected()=>_selected??throw new InvalidOperationException("Select a local deck first.");
    private void OpenDetails()
    {
        ShowDetails(Find(Selected()));
    }
    private void ShowDetails(JObject deck)
    {
        _surface!.ClearTransientPresentation();
        _details=_details??new NativeDeckDetailsView(_papa,(Transform)Field(_browsing?(object)_manager!:_widget!,"_popupRoot"),
            (id,name)=>ChangeDetails(id,value=>value["name"]=name),
            (id,format)=>ChangeDetails(id,value=>{
                if(format=="practice" && ((JObject)value["commander"]!).HasValues)throw new InvalidOperationException("Remove the commander before switching this deck to Practice.");
                value["format"]=format;
            }),error=>Act(()=>throw error),_surface.Zoom);
        // The editor popup must stay active while the library is hidden and vice versa.
        _details.Popup.transform.SetParent((Transform)Field(_browsing?(object)_manager!:_widget!,"_popupRoot"),false);
        _details.Open(deck,GetInfo(deck));
    }
    private void ChangeDetails(string id,Action<JObject> change)
    {
        if(!_browsing && (string?)_deck?["id"]==id){change(_deck!);_dirty=true;Refresh();}
        else{var value=Find(id);change(value);_library!.Save(value);if((string?)_deck?["id"]==id)_deck=value;ShowLibrary();}
    }
    public void RecordPlayed(Guid id)=>_library!.RecordPlayed(id.ToString());
    private void Select(string id){_selected=id;_folder!.SelectDeck(_folder.GetDeckViewInfo(id));_browser?.SelectionChanged();UpdateLibraryText();}
    private void Edit(string id){if(_dirty)throw new InvalidOperationException("Save the current deck before switching.");_choosingCommander=false;_deck=Find(id);_selected=id;ShowEditor();_pool!.ScrollToTop();Refresh();}
    private void ShowEditor(){_browsing=false;_manager?.gameObject.SetActive(false);_wrapper!.gameObject.SetActive(true);}
    private void ShowLibrary()
    {
        CancelDrag();
        _browsing=true;_wrapper!.gameObject.SetActive(false);_manager!.gameObject.SetActive(true);
        var infos=_library!.Decks.OfType<JObject>().Select(GetInfo).ToList();if(_browser!=null)infos=_browser.Apply(infos);
        if(_selected!=null && !infos.Any(info=>info.deckId.ToString()==_selected))_selected=null;
        _folder!.SetDecks(infos,true);_folder.SetFolderOpenState(true);
        ((Localize)Field(_folder,"_invalidGridDescription")).gameObject.SetActive(false);
        ((Transform)Field(_folder,"_invalidGridParent")).gameObject.SetActive(false);
        foreach(var view in _folder.GetComponentsInChildren<DeckView>(true))
        {
            var gaps=_library.MatchGaps(Find(view.GetDeckId().ToString()));view.ClearValidationIcons();
            if(gaps.Length>0)
            {
                AccessTools.Field(typeof(DeckView),"_invalidCardCount").SetValue(view,0);
                AccessTools.Field(typeof(DeckView),"_animateInvalid").SetValue(view,true);
                AccessTools.Method(typeof(DeckView),"SetToolTipText").Invoke(view,new object[]{string.Join("\n",gaps)});
                AccessTools.Method(typeof(DeckView),"ApplyVisualUpdates").Invoke(view,null);
            }
        }
        if(_selected!=null){var info=infos.FirstOrDefault(i=>i.deckId.ToString()==_selected);if(info!=null)_folder.SelectDeck(info);}
        _browser?.SelectionChanged();UpdateLibraryText();
    }
    private void UpdateLibraryText(){if(_manager!=null)((TMP_Text)Field(_manager,"_deckCountText")).text=(_browser!=null && _browser.VisibleCount<_browser.TotalCount?"<color=#5555FF>"+_browser.VisibleCount+"</color>":_library!.Decks.Count.ToString())+" / ∞";}
    internal DeckViewInfo GetInfo(JObject deck)
    {
        var first=((JObject)deck["main"]!).Properties().OrderBy(p=>(int)_library!.Cards[uint.Parse(p.Name)]["sort"]![0]!).ThenByDescending(p=>(int)p.Value).FirstOrDefault();
        first=((JObject)deck["commander"]!).Properties().FirstOrDefault()??first;
        var printing=first==null?null:_papa.CardDatabase.CardDataProvider.GetCardPrintingById(uint.Parse(first.Name));
        string art=printing?.ImageAssetPath??"";
        var info=new DeckViewInfo{deckId=Guid.Parse((string)deck["id"]!),deckName=(string)deck["name"]!,deck=new Client_Deck(new Client_DeckSummary{DeckId=Guid.Parse((string)deck["id"]!),Name=(string)deck["name"]!,Avatar="Avatar_Basic_AjaniGoldmane",CardBack="CardBack_Default"}),accountCosmeticDefaults=new ClientVanitySelectionsV3{avatarSelection="Avatar_Basic_AjaniGoldmane",cardBackSelection="CardBack_Default"},sleeveData=CardDataExtensions.CreateSkinCard(0,_papa.CardDatabase,"","CardBack_Default",true),crop=_papa.CardViewBuilder.CardMaterialBuilder.CropDatabase.GetCrop(art,"Normal")??ArtCrop.DEFAULT,deckImageAssetPath=_papa.CardViewBuilder.CardMaterialBuilder.TextureLoader.GetCardArtPath(art)};
        NativeDeckBrowserControls.CompleteInfo(info,deck,_papa,_library!.MatchGaps(deck).Length==0);return info;
    }
    private void ExportFile(JObject deck){Directory.CreateDirectory(Path.Combine(_root,"local-deck-exports"));File.WriteAllText(Path.Combine(_root,"local-deck-exports",(string)deck["id"]!+".txt"),_library!.Export(deck));}
    private void ShowMessage(){if(_message!=""){if(_browsing && _manager!=null)((TMP_Text)Field(_manager,"_deckCountText")).text=_message;else if(_list!=null)((TMP_Text)Field(_list.MainDeckTitlePanel,"_detailsText")).text=_message;}}
    public void Poll()
    {
        if(_deck==null)return;
        string request=Path.Combine(_root,"deck-action.request.json");
        if(File.Exists(request))
        {
            var action=JObject.Parse(File.ReadAllText(request));File.Delete(request);
            Act(()=>{switch((string?)action["op"]){
                case "save":Save();break;
                case "open":Edit((string)action["id"]!);break;
                case "import":var imported=_library!.Import((string)action["text"]!,(string?)action["name"]??"Imported deck");_library.Save(imported);_deck=imported;_dirty=false;Refresh();break;
                case "export":ExportFile(_deck);break;
                case "browse":if(_dirty)Save();ShowLibrary();break;
                case "clipboard":GUIUtility.systemCopyBuffer=(string)action["text"]!;break;
                case "inspect_input":
                    var point=new Vector2((float)action["x"]!,(float)action["y"]!);var hits=new List<UnityEngine.EventSystems.RaycastResult>();UnityEngine.EventSystems.EventSystem.current.RaycastAll(new UnityEngine.EventSystems.PointerEventData(UnityEngine.EventSystems.EventSystem.current){position=point},hits);
                    File.WriteAllText(Path.Combine(_root,"deck-input-probe.json"),JsonConvert.SerializeObject(new{point=point.ToString(),hits=hits.Select(h=>new{h.gameObject.name,components=h.gameObject.GetComponents<Component>().Select(c=>c.GetType().FullName).ToArray(),h.distance,h.depth,h.sortingOrder,h.sortingLayer}),cameras=UnityEngine.Object.FindObjectsByType<Camera>(FindObjectsSortMode.None).Select(c=>new{c.name,c.cullingMask,components=c.GetComponents<Component>().Select(v=>v.GetType().FullName).ToArray()})},Formatting.Indented));break;
                case "inspect_layout":
                    File.WriteAllText(Path.Combine(_root,"deck-layout-probe.json"),JsonConvert.SerializeObject(new{cameras=UnityEngine.Object.FindObjectsByType<Camera>(FindObjectsSortMode.None).Select(c=>new{c.name,c.enabled,c.cullingMask,c.depth,c.depthTextureMode,urp=JsonUtility.ToJson(c.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>())}),rows=_list!.MainDeckCardHolder.CardViews.Take(3).Select(v=>new{card=v.Card.GrpId,screen=_surface!.Camera.WorldToScreenPoint(v.transform.position).ToString(),world=v.transform.position.ToString(),nodes=v.GetComponentsInChildren<Transform>(true).Select(t=>new{t.name,active=t.gameObject.activeInHierarchy,layer=t.gameObject.layer,rect=(t as RectTransform)?.rect.ToString(),position=t.position.ToString(),color=t.GetComponent<Graphic>()?.color.ToString(),canvas=t.GetComponent<Graphic>()?.canvas?.name,material=t.GetComponent<Graphic>()?.materialForRendering?.name,group=t.GetComponent<CanvasGroup>()?.alpha})}),parents=_list!.MainDeckCardHolder.GetComponentsInChildren<Mask>(true).Select(m=>new{m.name,m.enabled,layer=m.gameObject.layer,screen=_surface!.Camera.WorldToScreenPoint(m.transform.position).ToString(),rect=((RectTransform)m.transform).rect.ToString(),m.showMaskGraphic,canvas=m.graphic.canvas.name,material=m.graphic.materialForRendering?.name})},Formatting.Indented));break;
                case "advanced":_header!.AdvancedFiltersButton.onClick.Invoke();break;
                case "query":_header!.SearchInput.text=(string)action["text"]!;_header.SearchInput.onEndEdit.Invoke(_header.SearchInput.text);break;
                case "filter":
                    var filter=Enum.Parse<CardFilterType>((string)action["type"]!);
                    if(filter==CardFilterType.Type_Land)_header!.LandsToggle.isOn=(bool)action["enabled"]!;
                    else (_advanced!=null && _advanced.gameObject.activeSelf?_advanced.GetComponentsInChildren<CardFilterView>(true):_header!.GetComponentsInChildren<CardFilterView>(true)).Single(v=>v.FilterType==filter && v.FilterToggle.interactable).FilterToggle.isOn=(bool)action["enabled"]!;
                    break;
                case "large_cards":_header!.LargeCardsToggle.isOn=(bool)action["enabled"]!;break;
                case "select_format":
                    ((TMP_Dropdown)Field(_list!.MainDeckTitlePanel,"_formatDropdown")).value=(int)action["index"]!;break;
                case "new":NewDeck();break;
                case "library_query":_browser!.QueryText((string)action["text"]!);break;
                case "library_sort":_browser!.SetSort((int)action["index"]!);break;
                case "library_format":_browser!.SetFormat((int)action["index"]!);break;
                case "rename":_deck["name"]=(string)action["name"]!;_dirty=true;Refresh();break;
                case "adjust":Adjust((uint)action["grpId"]!,(int)action["change"]!);break;
                default:throw new NotSupportedException("Unsupported deck action.");
            }});
        }
        WriteStatus();
    }
    private void WriteStatus()
    {
        if(_deck==null)return;
        File.WriteAllText(Path.Combine(_root,"deck-host-status.json"),JsonConvert.SerializeObject(new{utc=DateTime.UtcNow,ready=_list!=null && _pool!=null,browsing=_browsing,selected=_selected,dirty=_dirty,message=_message,deck=_deck,decks=_library!.Decks,matchGaps=_library.MatchGaps(_deck),rows=_list?.MainDeckCardHolder.CardViews.Select(v=>new{id=v.Card.GrpId,count=v.Quantity}).ToArray(),query=_query,advanced=_advanced!=null && _advanced.gameObject.activeInHierarchy,poolResultCount=_poolResultCount,poolIds=_poolIds,filters=_filters?.Selected.Select(f=>f.ToString()).ToArray(),largeCards=_largeCards,policy="Original Arena presentation with local sandbox data. Saving a deck does not establish match support or retail format legality."},Formatting.Indented));
    }
}
