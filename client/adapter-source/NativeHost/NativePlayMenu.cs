using System;
using System.IO;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using HarmonyLib;
using Newtonsoft.Json;
using UnityEngine;
using AssetLookupTree.Payloads.Prefab;
using Core.Code.AssetLookupTree.AssetLookup;
using Wizards.Mtga;
using Wizards.Mtga.Assets;
using Wizards.Mtga.Decks;
using Wizards.Mtga.PlayBlade;
using Wotc.Mtga;
using Wotc.Mtga.Loc;
using MTGA.Loc;
using Wizards.Unification.Models.PlayBlade;
using BladeType = Wizards.Mtga.PlayBlade.BladeType;

namespace ForgeArenaSandbox;

// Uses the original Play Blade and deck widgets. No online event/queue services.
internal sealed class NativePlayMenu
{
    private static NativePlayMenu? _active;
    private readonly string _root;
    private readonly PAPA _papa;
    private readonly NativeMenuSurface _surface;
    private readonly NativeDeckScreen _decks;
    private readonly Action<string,Guid> _join;
    private readonly Action<Guid> _edit;
    private readonly MonoBehaviour _runner;
    private PlayBladeV3? _blade;
    private Coroutine? _showRoutine;
    private readonly Dictionary<DeckViewInfo,Newtonsoft.Json.Linq.JObject> _localDecks=new Dictionary<DeckViewInfo,Newtonsoft.Json.Linq.JObject>();
    public NativePlayMenu(string root,PAPA papa,NativeMenuSurface surface,NativeDeckScreen decks,MonoBehaviour runner,Action<string,Guid> join,Action<Guid> edit)
    {_root=root;_papa=papa;_surface=surface;_decks=decks;_runner=runner;_join=join;_edit=edit;}
    private static object Field(object o,string name)=>AccessTools.Field(o.GetType(),name).GetValue(o);
    private static void Set(object o,string name,object value)=>AccessTools.Field(o.GetType(),name).SetValue(o,value);
    private static bool Owned(Component c)=>_active!=null && c.transform.IsChildOf(_active._surface.Root);
    public void Open()
    {
        if(_blade==null)
        {
            _active=this;
            var harmony=new Harmony("local.forge-arena.play-menu");
            foreach(var spec in new[]{(typeof(DeckViewSelector),"Initialize",nameof(InitializeSelector)),(typeof(DeckViewSelector),"SetDecks",nameof(SetDecks)),(typeof(FindMatchBladeContentView),"HydrateDeckSelector",nameof(Hydrate)),(typeof(FindMatchBladeContentView),"UpdateDeckSelector",nameof(UpdateSelector)),(typeof(FindMatchBladeView),"GetActiveNPEQuests",nameof(NoOnlineQuests)),(typeof(DeckViewInfo),"GetValidationForFormat",nameof(ValidateDeck)),(typeof(DeckViewUtilities),"SortDeckViewInfo",nameof(SortDecks))})
                harmony.Patch(AccessTools.Method(spec.Item1,spec.Item2),prefix:new HarmonyMethod(typeof(NativePlayMenu),spec.Item3));
            harmony.Patch(AccessTools.Method(typeof(FindMatchBladeContentView),"UpdateUx"),postfix:new HarmonyMethod(typeof(NativePlayMenu),nameof(LocalCaptions)));
            harmony.Patch(AccessTools.Method(typeof(BladeQueueListItem),"SetModel"),postfix:new HarmonyMethod(typeof(NativePlayMenu),nameof(QueueCaption)));
            harmony.Patch(AccessTools.Method(typeof(DeckView),"UpdateDisplayForFormat"),prefix:new HarmonyMethod(typeof(NativePlayMenu),nameof(DeckPresentation)));
            _blade=AssetLoader.Instantiate<PlayBladeV3>(_papa.AssetLookupSystem.GetPrefabPath<PlayBladeV3Prefab,PlayBladeV3>(),_surface.Root);
            var rect=(RectTransform)_blade.transform;rect.anchorMin=Vector2.zero;rect.anchorMax=Vector2.one;rect.offsetMin=Vector2.zero;rect.offsetMax=Vector2.zero;
            _blade.Initialize(new MetaCardBuilder(_papa.CardViewBuilder),new Selection(Path.Combine(_root,"local-profile","play-selection.json")),_join,(id,_,__,___)=>_edit(id),_=>{},_=>{},_=>{},_papa.UnityPool,_papa.AssetLookupSystem);
            // Events and recent online matches have no local counterparts yet.
            foreach(var context in (IEnumerable)Field(_blade,"_bladeContexts"))
            {
                var view=(BladeView)Field(context,"bladeView");
                if(view.Type!=BladeType.FindMatch)((CustomTab)Field(context,"bladeTabView")).gameObject.SetActive(false);
            }
        }
        _localDecks.Clear();var infos=_decks.DeckInfos();
        foreach(var info in infos){var deck=_decks.DeckById(info.deckId);_localDecks[info]=deck;info.DeckFormat=((Newtonsoft.Json.Linq.JObject)deck["commander"]!).HasValues || (string?)deck["format"]=="arena-brawl"?"SandboxBrawl":"SandboxPractice";}
        _blade.SetData(new Model(infos));
        if(_showRoutine!=null)_runner.StopCoroutine(_showRoutine);
        _showRoutine=_runner.StartCoroutine(_blade.ShowCoroutine());
    }
    public bool IsOpen=>_blade!=null && _blade.gameObject.activeInHierarchy;
    public void Hide(){if(_showRoutine!=null){_runner.StopCoroutine(_showRoutine);_showRoutine=null;}if(_blade!=null && _blade.gameObject.activeSelf)_blade.Hide(true);}
    public void SelectDeck(Guid id){if(_blade==null || !_blade.gameObject.activeInHierarchy)throw new InvalidOperationException("Open Play first.");var view=_blade.GetComponentInChildren<FindMatchBladeContentView>(false);((DeckViewSelector)Field(view,"_deckViewSelector")).SelectDeck(id.ToString());}
    public object? Snapshot(){var selection=_blade==null?null:Field(_blade,"_currentSelectionInfo") as BladeSelectionInfo;return selection==null?null:new{queue=selection.FindMatchInfo?.SelectedEventName,deck=selection.FindMatchInfo?.SelectedDeckId,invalid=selection.FindMatchInfo?.SelectedDeckIsInvalidForFormat};}
    private static void Caption(object component,string field,string text)=>((Localize)Field(component,field)).SetText("Sandbox/LocalCaption",(List<MTGALocalizable.LocParam>?)null,text);
    private static void LocalCaptions(FindMatchBladeContentView __instance,FindMatchSelectionInfo currentSelection)
    {
        if(!Owned(__instance))return;
        Caption(__instance,"_titleText",currentSelection.SelectedEvent.LocTitle);Caption(__instance,"_descriptionText",currentSelection.SelectedEvent.LocDescription);
        Caption(__instance,"_deckSizeText",currentSelection.SelectedQueueType==PlayBladeQueueType.Brawl?"99 + commander":"40–250 cards");Caption(__instance,"_sideBoardSizeText","No sideboard");
    }
    private static void QueueCaption(BladeQueueListItem __instance,BladeQueueInfo bladeQueueInfo){if(Owned(__instance))Caption(__instance,"_text",bladeQueueInfo.LocTitle);}
    private static bool DeckPresentation(DeckView __instance,string format)
    {
        if(!Owned(__instance))return true;
        var info=Field(__instance,"_deckViewInfo") as DeckViewInfo;
        if(info==null || _active==null || !_active._localDecks.ContainsKey(info))return true;
        var validation=info.GetValidationForFormat(format);__instance.ClearValidationIcons();
        Set(__instance,"_invalidCardCount",(int)validation.ValidationResult.NumberOfInvalidCards);Set(__instance,"_animateInvalid",!validation.IsValid);
        AccessTools.Method(typeof(DeckView),"SetToolTipText").Invoke(__instance,new object[]{validation.TooltipText});AccessTools.Method(typeof(DeckView),"ApplyVisualUpdates").Invoke(__instance,null);return false;
    }
    private static bool InitializeSelector(DeckViewSelector __instance,Action<DeckViewInfo> onDeckSelected,Action<DeckViewInfo> onDeckDoubleClicked,Action<DeckViewInfo> onDeckClickAndHold,Func<DeckManagerMode> getCurrentMode,Action<DeckViewInfo,string> onDeckNameEndEdit)
    {
        if(!Owned(__instance))return true;
        Set(__instance,"_onDeckSelected",onDeckSelected);Set(__instance,"_onDeckDoubleClicked",onDeckDoubleClicked);Set(__instance,"_onDeckClickAndHold",onDeckClickAndHold);Set(__instance,"_getCurrentMode",getCurrentMode??(()=>DeckManagerMode.SingleSelectMode));Set(__instance,"_onDeckNameEndEdit",onDeckNameEndEdit);
        var folder=UnityEngine.Object.Instantiate(__instance._deckFolderViewNoFolderPrefab,(Transform)Field(__instance,"_folderParent"));
        folder.Initialize(__instance.SelectDeck,onDeckDoubleClicked,onDeckClickAndHold,getCurrentMode??(()=>DeckManagerMode.SingleSelectMode),onDeckNameEndEdit,_=>{});
        var builder=new DeckViewBuilder();var papa=_active!._papa;
        foreach(var pair in new (string,object)[]{("_unityObjectPool",papa.UnityPool),("_assetLookupSystem",papa.AssetLookupSystem),("_cardViewBuilder",papa.CardViewBuilder),("_cardDatabase",papa.CardDatabase),("_metaCardViewBuilder",new MetaCardBuilder(papa.CardViewBuilder))})Set(builder,pair.Item1,pair.Item2);
        Set(folder,"_deckViewBuilder",builder);folder.FolderId=Guid.Empty;folder.SetFolderOpenState(true);
        Set(__instance,"_myDecksFolderView",folder);((List<DeckFolderView>)Field(__instance,"_deckFolders")).Add(folder);
        return false;
    }
    private static bool SetDecks(DeckViewSelector __instance,IReadOnlyList<DeckViewInfo> decks,bool allowUnownedCards)
    {
        if(!Owned(__instance))return true;
        foreach(var folder in (List<DeckFolderView>)Field(__instance,"_deckFolders")){folder.SetFolderOpenState(true);folder.SetDecks(decks.ToList(),allowUnownedCards);}
        return false;
    }
    private static bool Hydrate(FindMatchBladeContentView __instance,IReadOnlyList<DeckViewInfo> decks,FindMatchSelectionInfo currentSelection)
    {
        if(!Owned(__instance))return true;
        var selector=(DeckViewSelector)Field(__instance,"_deckViewSelector");
        selector.SetDecks(decks,false);selector.SetFormat(currentSelection.SelectedEvent.DeckFormat,false);
        if(currentSelection.SelectedDeckId!=Guid.Empty)selector.SelectDeck(decks.FirstOrDefault(d=>d.deckId==currentSelection.SelectedDeckId));
        return false;
    }
    private static bool UpdateSelector(FindMatchBladeContentView __instance,FindMatchSelectionInfo currentSelection)
    {if(!Owned(__instance))return true;((DeckViewSelector)Field(__instance,"_deckViewSelector")).SetFormat(currentSelection.SelectedEvent.DeckFormat,false);return false;}
    private static bool NoOnlineQuests(FindMatchBladeView __instance,ref List<string> __result){if(!Owned(__instance))return true;__result=new List<string>();return false;}
    private static bool ValidateDeck(DeckViewInfo __instance,string formatName,ref DeckDisplayInfo __result)
    {
        if(_active==null || !_active._localDecks.TryGetValue(__instance,out var deck))return true;
        string format=string.IsNullOrEmpty(formatName)?__instance.DeckFormat:formatName;
        var gaps=_active._decks.Library.MatchGaps(deck,format);
        __result=new DeckDisplayInfo(__instance.deck,gaps.Length==0?DeckDisplayInfo.DeckDisplayState.Valid:DeckDisplayInfo.DeckDisplayState.Invalid,new Wizards.Arena.DeckValidation.Client.ClientSideDeckValidationResult(),string.Join("\n",gaps));return false;
    }
    private static bool SortDecks(IReadOnlyList<DeckViewInfo> deckViewInfos,string formatForSort,ref IReadOnlyList<DeckViewInfo> __result)
    {
        if(_active==null || !deckViewInfos.All(d=>_active._localDecks.ContainsKey(d)))return true;
        __result=deckViewInfos.OrderByDescending(d=>d.GetValidationForFormat(formatForSort).IsValid).ThenBy(d=>d.deckName,StringComparer.OrdinalIgnoreCase).ToList();return false;
    }
    private sealed class Model : IBladeModel
    {
        public IReadOnlyList<DeckViewInfo> Decks{get;}
        public IReadOnlyList<BladeEventInfo> Events{get;}=new List<BladeEventInfo>();
        public IReadOnlyList<RecentlyPlayedInfo> RecentlyPlayed{get;}=new List<RecentlyPlayedInfo>();
        public IReadOnlyList<BladeEventFilter> EventFilters{get;}=new List<BladeEventFilter>();
        public IReadOnlyDictionary<PlayBladeQueueType,List<BladeQueueInfo>> Queues{get;}
        public bool UnviewedEventsExist()=>false;
        public Model(List<DeckViewInfo> decks)
        {
            Decks=decks;Queues=new Dictionary<PlayBladeQueueType,List<BladeQueueInfo>>{{PlayBladeQueueType.Unranked,new List<BladeQueueInfo>{Queue("SandboxPractice","Practice Bot","40–250 cards. Play a local Forge AI with verified cards.",PlayBladeQueueType.Unranked)}},{PlayBladeQueueType.Brawl,new List<BladeQueueInfo>{Queue("SandboxBrawl","Brawl Bot","100 cards including a verified commander. Singleton, color identity, 25 life and a free first mulligan. Local Forge AI.",PlayBladeQueueType.Brawl)}}};
        }
        private static BladeQueueInfo Queue(string id,string title,string description,PlayBladeQueueType type)=>new BladeQueueInfo{QueueId=id,LocTitle=title,PlayBladeQueueType=type,Tags=new List<string>(),EventInfo_BO1=new BladeEventInfo{EventName=id,LocTitle=title,LocShortTitle=title,LocDescription=description,IsBotMatch=true,DeckFormat=id,Format=new DeckFormat(null!,Wotc.Mtga.Loc.Languages.ActiveLocProvider){FormatName=id}},DeckConstraintInfo_B01=new DeckConstraintInfo{MainDeckKey=type==PlayBladeQueueType.Brawl?"99 + commander":"40–250 cards",SideBoardKey="No sideboard"}};
    }
    private sealed class Selection : IPlayBladeSelectionProvider
    {
        private readonly string _path;
        private BladeSelectionData _data;
        public Selection(string path){_path=path;_data=File.Exists(path)?JsonConvert.DeserializeObject<BladeSelectionData>(File.ReadAllText(path)):GetDefaultSelectionData();}
        public BladeSelectionData GetDefaultSelectionData()=>new BladeSelectionData{bladeType=BladeType.FindMatch,findMatch=new FindMatchData{QueueId="SandboxPractice",QueueType=PlayBladeQueueType.Unranked,QueueIdForQueueType=new Dictionary<PlayBladeQueueType,string>{{PlayBladeQueueType.Unranked,"SandboxPractice"},{PlayBladeQueueType.Brawl,"SandboxBrawl"}}}};
        public BladeSelectionData GetSelection()=>_data;
        public void SetSelection(BladeSelectionData data){data.bladeType=BladeType.FindMatch;LocalDeckLibrary.SaveJsonAtomically(_path,JsonConvert.SerializeObject(data,Formatting.Indented));_data=data;}
        public void SetSelectedTab(BladeType type){_data.bladeType=BladeType.FindMatch;}
        public bool IsEventBladeDeckSelected()=>false;
    }
}
