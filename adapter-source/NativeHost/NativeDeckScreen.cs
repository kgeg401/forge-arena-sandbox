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
    private string? _deletePending;
    private LocalDeckLibrary? _library;
    private JObject? _deck;
    private string _message="";
    private string _query="";
    private bool _dirty;
    private static NativeDeckScreen? _active;
    private bool _constructing;
    public NativeDeckScreen(string root,PAPA papa,Action<string> log){_root=root;_papa=papa;_log=log;}
    private static object Field(object obj,string name)=>AccessTools.Field(obj.GetType(),name).GetValue(obj);
    private static bool Owned(Component obj)=>_active!=null && (_active._constructing || (_active._surface!=null && obj.transform.IsChildOf(_active._surface.Root)));
    private static bool SkipOnlineLifecycle(Component __instance)=>!Owned(__instance);
    public void Open()
    {
        if(_wrapper!=null)return;
        _library=new LocalDeckLibrary(Path.Combine(_root,"local-profile","decks.json"),Path.Combine(_root,"deck-catalog.json"));
        _surface=new NativeMenuSurface(_papa);_active=this;
        var harmony=new Harmony("local.codex.forge-arena-decks");
        foreach(var spec in new[]{(typeof(WrapperDeckBuilder),new[]{"Awake","OnEnable","OnDestroy","Update"}),(typeof(DeckBuilderWidget),new[]{"OnEnable","OnDisable","OnDestroy"}),(typeof(DeckListView),new[]{"OnEnable","OnDisable","OnDestroy"}),(typeof(DeckMainTitlePanel),new[]{"OnEnable","OnDisable"}),(typeof(SearchAndFilterBar),new[]{"Awake","OnEnable","OnDisable","OnDestroy"}),(typeof(CardPoolHolder),new[]{"OnEnable","OnDisable","OnDestroy"})})
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
            holder.CanSingleClickCards=v=>false;holder.CanDragCards=v=>false;
            holder.ClearCommanderCards();holder.ClearPartnerCards();holder.ClearCompanionCards();
            _list.SideboardCardHolder.gameObject.SetActive(false);_list.SideboardTitlePanel.gameObject.SetActive(false);_list.ShowSideboardToggle.gameObject.SetActive(false);
            _list.SleevesButton.gameObject.SetActive(false);
            Clear(_list.DeckNameInput.onEndEdit);_list.DeckNameInput.characterLimit=80;
            _list.DeckNameInput.onEndEdit.AddListener(name=>Act(()=>{if(string.IsNullOrWhiteSpace(name))throw new InvalidDataException("Enter a deck name.");_deck!["name"]=name;_dirty=true;Refresh();}));
            _list.MainDeckTitlePanel.SetDeckFormatSelector(null!,false,false);
            _list.SetSleeve("CardBack_Default",_papa.CardViewBuilder,_papa.CardDatabase);
            _pool=UnityEngine.Object.Instantiate((CardPoolHolder)Field(_widget,"_poolHolderPrefab"),(Transform)Field(_widget,"_poolParent"));
            ((RectTransform)_pool.transform).StretchToParent();_pool.EnsureInit(_papa.CardDatabase,_papa.CardViewBuilder);
            _pool.DirectlySetZoomHandler=_surface.Zoom;_pool.RolloverZoomView=_surface.Zoom;
            _pool.OnCardClicked=v=>Act(()=>Adjust(v.Card.GrpId,1));_pool.OnCardRightClicked=null;
            _pool.CanSingleClickCards=v=>true;_pool.CanDragCards=v=>false;_pool.CanDropCards=v=>false;
            _pool.ShowHighlight=v=>true;
            _header=UnityEngine.Object.Instantiate((SearchAndFilterBar)Field(_widget,"_headerPrefab"),(Transform)Field(_widget,"_headerParent"));
            ((RectTransform)_header.transform).StretchToParent();
            Clear(_header.SearchInput.onEndEdit);
            _header.SearchInput.onEndEdit.AddListener(query=>Act(()=>{_query=query.Trim();RefreshPool();}));
            Clear(_header.ClearSearchButton.onClick);_header.ClearSearchButton.onClick.AddListener(()=>Act(()=>{_query="";_header.SearchInput.text="";RefreshPool();}));
            Bind(_header.NewDeckButton,NewDeck);
            foreach(var toggle in _header.GetComponentsInChildren<Toggle>(true))toggle.interactable=false;
            _header.AdvancedFiltersButton.interactable=false;
            Bind((CustomButton)Field(_widget,"_doneButton"),()=>{Save();ShowLibrary();});
            Bind((CustomButton)Field(_widget,"_backButton"),()=>{Save();ShowLibrary();});
            ((CustomButton)Field(_widget,"_batchCraftingButton")).gameObject.SetActive(false);
            ((CustomButton)Field(_widget,"_applySkinsButton")).gameObject.SetActive(false);
            if(_library.Decks.Count==0)
            {
                string seeds=Path.Combine(_root,"local-deck-seeds");
                foreach(string file in Directory.GetFiles(seeds,"*.txt"))_library.Save(_library.Import(File.ReadAllText(file),Path.GetFileNameWithoutExtension(file)));
            }
            _deck=_library.Decks.OfType<JObject>().FirstOrDefault()??_library.New("New sandbox deck");
            Refresh();BuildLibrary();ShowLibrary();_log("Original native deck list, card pool and deck browser connected to local library.");
        }
        finally{_constructing=false;}
    }
    private static bool PoolRows(CardPoolHolder __instance,ref int __result){if(!Owned(__instance))return true;__result=2;return false;}
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
    private void Act(Action action){try{action();_message="";}catch(Exception ex){_message=ex.Message;_log(ex.ToString());}ShowMessage();WriteStatus();}
    private void Adjust(uint id,int change)
    {
        var cards=(JObject)_deck!["main"]!;string key=id.ToString();int count=checked(((int?)cards[key]??0)+change);
        if(count>999)throw new InvalidDataException("Maximum 999 copies per printing.");
        if(count<=0)cards.Remove(key);else cards[key]=count;
        _dirty=true;Refresh();
    }
    private void Save(){_library!.Save(_deck!);_dirty=false;_selected=(string)_deck!["id"]!;_log("Saved local deck "+_deck["id"]+" / "+_deck["name"]);Refresh();}
    private void NewDeck(){if(_dirty)Save();_deck=_library!.New("New sandbox deck");_dirty=true;ShowEditor();Refresh();}
    private void Refresh()
    {
        var values=((JObject)_deck!["main"]!).Properties().Select(p=>new{Id=uint.Parse(p.Name),Count=(uint)p.Value});
        var display=values.Select(p=>new ListMetaCardViewDisplayInformation{Card=_papa.CardDatabase.CardDataProvider.GetCardPrintingById(p.Id),Quantity=p.Count,Invalid=!(bool)_library!.Cards[p.Id]["matchSupported"]!}).ToList();
        display=display.OrderBy(x=>(int)_library!.Cards[x.Card.GrpId]["sort"]![0]!).ThenBy(x=>(int)_library!.Cards[x.Card.GrpId]["sort"]![1]!).ThenBy(x=>(int)_library!.Cards[x.Card.GrpId]["sort"]![2]!).ThenBy(x=>(string)_library!.Cards[x.Card.GrpId]["sort"]![3]!,StringComparer.Ordinal).ToList();
        _list!.MainDeckCardHolder.SetCards(display);_list.DeckNameInput.SetTextWithoutNotify((string)_deck["name"]!);
        _list.MainDeckTitlePanel.SetCardCount(display.Sum(c=>(int)c.Quantity),null!,0,true);
        var text=(TMP_Text)Field(_list.MainDeckTitlePanel,"_detailsText");
        var gaps=_library!.MatchGaps(_deck);text.text=gaps.Length==0?(_dirty?"Unsaved local deck":"Saved local deck"):("Sandbox • "+gaps.Length+" match limitation(s)");
        RefreshPool();WriteStatus();
    }
    private void RefreshPool()
    {
        var ids=_library!.Cards.Values.Where(c=>(bool)c["preferred"]! || (_query.Length>0 && ((string)c["name"]!).IndexOf(_query,StringComparison.OrdinalIgnoreCase)>=0)).Where(c=>_query.Length==0 || ((string)c["name"]!).IndexOf(_query,StringComparison.OrdinalIgnoreCase)>=0).GroupBy(c=>(string)c["name"]!).Select(g=>g.OrderByDescending(c=>(bool)c["preferred"]!).ThenByDescending(c=>(uint)c["grpId"]!).First()).OrderBy(c=>(string)c["name"]!).Take(500);
        var display=ids.Select(c=>new PagesMetaCardViewDisplayInformation{Card=_papa.CardDatabase.CardDataProvider.GetCardPrintingById((uint)c["grpId"]!),Max=999,AvailablePrintingCount=999,AvailableTitleCount=999,RemainingTitleCount=999,QuantityStyle=PagesMetaCardView.QuantityDisplayStyle.Infinity}).ToList();
        _pool!.SetCards(display,false);_pool.ScrollToTop();
        if(_header!=null)_header.EventCardPoolTitleText.text="Sandbox collection";
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
        Bind((CustomButton)Field(_manager,"_cloneDeckButton"),()=>{var deck=Find(Selected());deck["id"]=Guid.NewGuid().ToString();deck["name"]=((string)deck["name"]!).Substring(0,Math.Min(73,((string)deck["name"]!).Length))+" (copy)";_library!.Save(deck);_selected=(string)deck["id"]!;ShowLibrary();});
        Bind((CustomButton)Field(_manager,"_deleteDeckButton"),()=>{var id=Selected();if(_deletePending!=id){_deletePending=id;((TMP_Text)Field(_manager,"_deckCountText")).text="Click Delete again to remove the selected local deck";return;}_library!.Delete(id);_selected=null;_deletePending=null;ShowLibrary();});
        foreach(string field in new[]{"_deckDetailsButton","_favoriteDeckButton","_craftAllButton","_collectionButton"})((CustomButton)Field(_manager,field)).gameObject.SetActive(false);
        foreach(var dropdown in _manager.GetComponentsInChildren<TMP_Dropdown>(true))dropdown.interactable=false;
        // Manager filter bars require server format data; unsupported controls stay inactive.
        ((Transform)Field(_manager,"_deckFilterBarPrefab")).gameObject.SetActive(false);
        ((DeckFilterBar)Field(_manager,"_deckColorFilterPrefab")).gameObject.SetActive(false);
    }
    private JObject Find(string id)=>_library!.Decks.OfType<JObject>().First(d=>(string)d["id"]! ==id);
    private string Selected()=>_selected??throw new InvalidOperationException("Select a local deck first.");
    private void Select(string id){_selected=id;_deletePending=null;_folder!.SelectDeck(_folder.GetDeckViewInfo(id));UpdateLibraryText();}
    private void Edit(string id){if(_dirty)throw new InvalidOperationException("Save the current deck before switching.");_deck=Find(id);_selected=id;ShowEditor();Refresh();}
    private void ShowEditor(){_browsing=false;_manager?.gameObject.SetActive(false);_wrapper!.gameObject.SetActive(true);}
    private void ShowLibrary()
    {
        _browsing=true;_wrapper!.gameObject.SetActive(false);_manager!.gameObject.SetActive(true);
        var infos=_library!.Decks.OfType<JObject>().Select(GetInfo).ToList();_folder!.SetDecks(infos,true);_folder.SetFolderOpenState(true);
        ((Localize)Field(_folder,"_invalidGridDescription")).gameObject.SetActive(false);
        ((Transform)Field(_folder,"_invalidGridParent")).gameObject.SetActive(false);
        foreach(var view in _folder.GetComponentsInChildren<DeckView>(true))
        {
            var gaps=_library.MatchGaps(Find(view.GetDeckId().ToString()));view.ClearValidationIcons();
            if(gaps.Length>0)
            {
                AccessTools.Field(typeof(DeckView),"_invalidCardCount").SetValue(view,gaps.Length);
                AccessTools.Field(typeof(DeckView),"_animateInvalid").SetValue(view,true);
                AccessTools.Method(typeof(DeckView),"SetToolTipText").Invoke(view,new object[]{string.Join("\n",gaps)});
                AccessTools.Method(typeof(DeckView),"ApplyVisualUpdates").Invoke(view,null);
            }
        }
        if(_selected!=null){var info=infos.FirstOrDefault(i=>i.deckId.ToString()==_selected);if(info!=null)_folder.SelectDeck(info);}
        UpdateLibraryText();
    }
    private void UpdateLibraryText(){if(_manager!=null)((TMP_Text)Field(_manager,"_deckCountText")).text=_library!.Decks.Count+" / ∞";}
    private DeckViewInfo GetInfo(JObject deck)
    {
        var first=((JObject)deck["main"]!).Properties().OrderBy(p=>(int)_library!.Cards[uint.Parse(p.Name)]["sort"]![0]!).ThenByDescending(p=>(int)p.Value).FirstOrDefault();
        var printing=first==null?null:_papa.CardDatabase.CardDataProvider.GetCardPrintingById(uint.Parse(first.Name));
        string art=printing?.ImageAssetPath??"";
        return new DeckViewInfo{deckId=Guid.Parse((string)deck["id"]!),deckName=(string)deck["name"]!,deck=new Client_Deck(new Client_DeckSummary{DeckId=Guid.Parse((string)deck["id"]!),Name=(string)deck["name"]!,Avatar="Avatar_Basic_AjaniGoldmane",CardBack="CardBack_Default"}),accountCosmeticDefaults=new ClientVanitySelectionsV3{avatarSelection="Avatar_Basic_AjaniGoldmane",cardBackSelection="CardBack_Default"},sleeveData=CardDataExtensions.CreateSkinCard(0,_papa.CardDatabase,"","CardBack_Default",true),crop=_papa.CardViewBuilder.CardMaterialBuilder.CropDatabase.GetCrop(art,"Normal")??ArtCrop.DEFAULT,deckImageAssetPath=_papa.CardViewBuilder.CardMaterialBuilder.TextureLoader.GetCardArtPath(art)};
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
                case "new":NewDeck();break;
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
        File.WriteAllText(Path.Combine(_root,"deck-host-status.json"),JsonConvert.SerializeObject(new{utc=DateTime.UtcNow,ready=_list!=null && _pool!=null,browsing=_browsing,selected=_selected,dirty=_dirty,message=_message,deck=_deck,decks=_library!.Decks,matchGaps=_library.MatchGaps(_deck),rows=_list?.MainDeckCardHolder.CardViews.Select(v=>new{id=v.Card.GrpId,count=v.Quantity}).ToArray(),query=_query,policy="Original Arena presentation with local sandbox data. Saving a deck does not establish match support or retail format legality."},Formatting.Indented));
    }
}
