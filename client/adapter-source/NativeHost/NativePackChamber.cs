using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections;
using System.Collections.Generic;
using System.Runtime.Serialization;
using AssetLookupTree.Payloads.Prefab;
using Core.Code.AssetLookupTree.AssetLookup;
using Core.Code.Collations;
using Core.Shared.Code.CardFilters;
using HarmonyLib;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using SharedClientCore.SharedClientCore.Meta.MainNavigation;
using SharedClientCore.SharedClientCore.Code.Providers;
using UnityEngine;
using UnityEngine.UI;
using Wotc.Mtga;
using Wizards.Mtga.Inventory;
using Wizards.Mtga;
using Wizards.Mtga.FrontDoorModels;
using Wizards.Models;
using Wizards.Mtga.Assets;
using UnityEngine.SceneManagement;
using Pooling;
using Wotc.Mtga.Loc;
using UnityEngine.Rendering.Universal;
using UnityEngine.EventSystems;

namespace ForgeArenaSandbox;

// All objects come from the owned installation, inside the existing isolated lab.
internal sealed class NativePackChamber
{
    private readonly string _root;
    private readonly PAPA _papa;
    private readonly Action<string> _log;
    private BoosterChamberController? _chamber;
    private NativeMenuSurface? _surface;
    private bool _busy;
    private LocalPackProfile? _profile;
    private InventoryManager? _inventory;
    private ClientPlayerInventory? _nativeInventory;
    private ISetMetadataProvider? _packMetadata;
    private Dictionary<uint,int> _cards = new Dictionary<uint,int>();
    private string? _lastPresentationError;
    private static NativePackChamber? _active;
    public bool Ready=>_chamber!=null && _chamber.IsReadyToShow;
    public NativePackChamber(string root, PAPA papa, Action<string> log, NativeMenuSurface? surface=null) { _root=root; _papa=papa; _log=log; _surface=surface; }
    public void Hide(){if(_busy)throw new InvalidOperationException("Finish revealing this pack before leaving Packs.");_surface?.ClearTransientPresentation();if(_chamber!=null)_chamber.gameObject.SetActive(false);}
    public void Open()
    {
        if (_chamber != null) { _chamber.gameObject.SetActive(true);return; }
        _surface=_surface??new NativeMenuSurface(_papa);
        string path=_papa.AssetLookupSystem.GetPrefabPath<BoosterChamberV2Prefab,BoosterChamberController>();
        _chamber=AssetLoader.Instantiate<BoosterChamberController>(path,_surface.Root);
        _log("Loaded original booster chamber: "+path);
        File.WriteAllText(Path.Combine(_root,"pack-chamber-probe.json"), JsonConvert.SerializeObject(new {
            path,
            objects=_chamber.GetComponentsInChildren<Transform>(true).Select(t=>new {name=t.name,parent=t.parent?.name,position=t.position.ToString(),local=t.localPosition.ToString(),scale=t.localScale.ToString(),components=t.GetComponents<Component>().Select(c=>c?.GetType().FullName).ToArray()}).ToArray(),
            fields=typeof(BoosterChamberController).GetFields(BindingFlags.Instance|BindingFlags.NonPublic).Select(f=>new {name=f.Name,type=f.FieldType.FullName,value=f.GetValue(_chamber)?.ToString()}).ToArray(),
            cameras=UnityEngine.Object.FindObjectsByType<Camera>(FindObjectsSortMode.None).Select(c=>new {c.name,position=c.transform.position.ToString(),rotation=c.transform.eulerAngles.ToString(),c.orthographic,c.orthographicSize,c.fieldOfView,c.cullingMask,c.depth}).ToArray()
        }, Formatting.Indented));
        _profile=new LocalPackProfile(Path.Combine(_root,"local-profile","packs.json"),Path.Combine(_root,"pack-catalog.json"));
        // The official set service is unavailable offline. Provide the narrow
        // set-code/collation mapping needed for the owned pack art, independently
        // of format legality, release dates, store groups or account inventory.
        var metadata=new SetMetadataProvider();
        var collations=new Dictionary<Wotc.Mtga.Wrapper.CollationMapping,ClientSetCollation>();
        foreach(var set in _profile.Sets)
        {
            var id=(Wotc.Mtga.Wrapper.CollationMapping)(int)set["collationId"]!;
            string code=(string)set["set"]!;
            collations[id]=new ClientSetCollation{CollationCode=id,SetCode=code,FlavorId="",Set=new ClientSetMetadata{SetCode=code}};
        }
        AccessTools.Field(typeof(SetMetadataProvider),"_collationsByMapping").SetValue(metadata,collations);
        var storeSets=AccessTools.Field(typeof(SetMetadataProvider),"_storeSets");
        storeSets.SetValue(metadata,Activator.CreateInstance(storeSets.FieldType));
        AccessTools.Field(typeof(SetMetadataProvider),"_relatedSetCodes").SetValue(metadata,new HashSet<string>());
        _packMetadata=metadata;
        _inventory=(InventoryManager)FormatterServices.GetUninitializedObject(typeof(InventoryManager));
        _active=this;
        var harmony=new Harmony("local.codex.forge-arena-packs");
        foreach(string property in new[]{"Inventory","Cards"})
            harmony.Patch(AccessTools.PropertyGetter(typeof(InventoryManagerCore),property),prefix:new HarmonyMethod(typeof(NativePackChamber),property=="Inventory"?nameof(GetInventory):nameof(GetCards)));
        harmony.Patch(AccessTools.Method(typeof(BoosterChamberController),"Coroutine_OpenBoosters"),prefix:new HarmonyMethod(typeof(NativePackChamber),nameof(OpenLocal)));
        harmony.Patch(AccessTools.Method(typeof(Core.Meta.MainNavigation.BoosterChamber.BoosterMetaCardViewPool),"GetCardView"),postfix:new HarmonyMethod(typeof(NativePackChamber),nameof(RestorePooledCardPose)));
        RefreshInventory();
        var rect=(RectTransform)_chamber.transform;rect.anchorMin=Vector2.zero;rect.anchorMax=Vector2.one;rect.offsetMin=Vector2.zero;rect.offsetMax=Vector2.zero;
        var zoom=_surface.Zoom;
        _chamber.Instantiate(zoom,_papa.CardViewBuilder,_papa.AssetLookupSystem,null!,_papa.BILogger,_papa.CardDatabase,null!,_packMetadata,_inventory,value=>{_busy=value;_log("Local pack busy: "+value);},_papa.UnityPool,_chamber.GetComponentInChildren<CustomButton>(true),null!);
        // Custom packs grant cards only. Do not imply retail wildcard-track rewards.
        var track=((Component)AccessTools.Field(typeof(BoosterChamberController),"_wildcardTrack").GetValue(_chamber)).gameObject;
        var trackVisibility=track.GetComponent<CanvasGroup>() ?? track.AddComponent<CanvasGroup>();
        trackVisibility.alpha=0;trackVisibility.blocksRaycasts=false;trackVisibility.interactable=false;
        _chamber.BeginOpen();_chamber.FinishOpen();
        _log("Original pack screen initialized with local profile and original hover zoom.");
    }
    private void RefreshInventory()
    {
        var snapshot=_profile!.Snapshot;
        _cards=((JObject)snapshot["cards"]!).Properties().ToDictionary(p=>uint.Parse(p.Name),p=>(int)p.Value);
        var metadata=_packMetadata!;
        var values=((JObject)snapshot["packs"]!).Properties().Select(p=>new ClientBoosterInfo{collationId=int.Parse(p.Name),count=(int)p.Value})
            .Where(p=>metadata.CollationForMapping((Wotc.Mtga.Wrapper.CollationMapping)p.collationId)!=null).ToList();
        if(_nativeInventory==null)_nativeInventory=new ClientPlayerInventory{boosters=values,vouchers=new List<ClientVoucherDescription>(),CustomTokens=new Dictionary<string,int>()};
        else foreach(var value in values){var existing=_nativeInventory.boosters.FirstOrDefault(x=>x.collationId==value.collationId);if(existing==null)_nativeInventory.boosters.Add(value);else existing.count=value.count;}
    }
    private static bool GetInventory(InventoryManagerCore __instance,ref ClientPlayerInventory __result)
    {if(_active?._inventory!=__instance)return true;__result=_active._nativeInventory!;return false;}
    private static bool GetCards(InventoryManagerCore __instance,ref Dictionary<uint,int> __result)
    {if(_active?._inventory!=__instance)return true;__result=_active._cards;return false;}
    private static bool OpenLocal(BoosterChamberController __instance,int quantityToOpen,SealedBoosterView boosterToOpen,ref IEnumerator __result)
    {if(_active?._chamber!=__instance)return true;__result=_active.OpenRoutine(quantityToOpen,boosterToOpen);return false;}
    private static void RestorePooledCardPose(Core.Meta.MainNavigation.BoosterChamber.BoosterMetaCardViewPool __instance,BoosterMetaCardView __result)
    {
        if(_active?._chamber==null || __result==null)return;
        var owner=AccessTools.Field(typeof(BoosterChamberController),"_boosterMetaCardViewPool").GetValue(_active._chamber);
        if(!ReferenceEquals(owner,__instance))return;
        var prefab=(BoosterMetaCardView)AccessTools.Field(__instance.GetType(),"_cardPrefab").GetValue(__instance);
        // Native warm-up temporarily parents only its first pooled card to the
        // screen and then detaches with worldPositionStays=true. In this local
        // canvas that leaks a world-space pose into the next holder. Restore the
        // original owned prefab pose before the native spawner attaches it.
        if(__result.transform.localPosition!=prefab.transform.localPosition || __result.transform.localScale!=prefab.transform.localScale)
            _active._log("Restored pooled native card pose: "+__result.transform.localPosition+" / "+__result.transform.localScale+" -> "+prefab.transform.localPosition+" / "+prefab.transform.localScale);
        __result.transform.localPosition=prefab.transform.localPosition;
        __result.transform.localRotation=prefab.transform.localRotation;
        __result.transform.localScale=prefab.transform.localScale;
    }
    private IEnumerator OpenRoutine(int quantity,SealedBoosterView booster)
    {
        AccessTools.Field(typeof(BoosterChamberController),"_ignoreInput").SetValue(_chamber,true);
        JObject receipt;
        try {receipt=_profile!.Open(booster.CollationId,quantity,Guid.NewGuid().ToString());}
        catch {AccessTools.Field(typeof(BoosterChamberController),"_ignoreInput").SetValue(_chamber,false);AccessTools.Property(typeof(BoosterChamberController),"ThereIsABoosterOpened").SetValue(_chamber,false);throw;}
        RefreshInventory();
        File.WriteAllText(Path.Combine(_root,"last-pack-receipt.json"),receipt.ToString(Formatting.Indented));
        _log("Local opening committed: "+receipt["set"]+", packs="+quantity+", cards="+((JArray)receipt["cards"]!).Count);
        yield return null;
        AccessTools.Field(typeof(BoosterChamberController),"_ignoreInput").SetValue(_chamber,false);
        Present(receipt);
    }
    private void Present(JObject receipt)
    {
        AccessTools.Property(typeof(BoosterChamberController),"ThereIsABoosterOpened").SetValue(_chamber,true);
        ((SetLogo)AccessTools.Field(typeof(BoosterChamberController),"_setLogo").GetValue(_chamber)).IsVisible=false;
        var setCode=AccessTools.Field(typeof(BoosterChamberController),"_setCode");
        string oldCode=(string)setCode.GetValue(_chamber),newCode=(string)receipt["set"]!;
        if(oldCode!=newCode){AudioManager.SetRTPCValue("booster_packrollover",0);AudioManager.SetRTPCValue("boosterpack_"+oldCode,0);setCode.SetValue(_chamber,newCode);AudioManager.SetRTPCValue("booster_packrollover",100);AudioManager.SetRTPCValue("boosterpack_"+newCode,100);}
        var result=new InventoryInfoShared {cardsOpened=((JArray)receipt["cards"]!).Select(c=>new CrackBoostersCardInfo{grpId=(uint)c["grpId"]!,addedToInventory=true,set=(string)c["set"]!}).ToArray(),Changes=new List<InventoryChangeShared>(),wcTrackPosition=0};
        try{AccessTools.Method(typeof(BoosterChamberController),"VisuallyOpenBooster").Invoke(_chamber,new object[]{(int)receipt["packsBefore"]!,(int)receipt["quantity"]!,result});_lastPresentationError=null;}
        catch(Exception ex){_lastPresentationError=ex.ToString();throw;}
    }
    private IEnumerator ReplayLast()
    {
        if(_chamber!.ThereIsABoosterOpened)throw new InvalidOperationException("Dismiss the current opening before replaying a receipt.");
        var receipt=(JObject)((JArray)_profile!.Snapshot["openings"]!).Last!.DeepClone();
        var views=(List<SealedBoosterView>)AccessTools.Field(typeof(BoosterChamberController),"_boosterViews").GetValue(_chamber);
        var target=views.Single(v=>v.CollationId==(int)receipt["collationId"]!);
        target._presenting=false; // Selecting an already-presented pack would otherwise crack a new one.
        _chamber.ClickedBooster(target);
        yield return new WaitForSeconds(1.5f);
        _log("Replaying committed opening without granting cards: "+receipt["id"]);
        Present(receipt);
    }
    public void Poll()
    {
        if(_chamber==null || _profile==null)return;
        string request=Path.Combine(_root,"pack-action.request.json");
        if(File.Exists(request))
        {
            var action=JObject.Parse(File.ReadAllText(request));File.Delete(request);
            string op=(string)action["op"]!;
            if(op=="inspect_render")
            {
                File.WriteAllText(Path.Combine(_root,"pack-renderers.json"),JsonConvert.SerializeObject(UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None).Where(r=>r.enabled && r.gameObject.activeInHierarchy).Select(r=>new{name=r.name,type=r.GetType().Name,parent=r.transform.parent?.name,layer=r.gameObject.layer,position=r.transform.position.ToString(),bounds=r.bounds.ToString(),screen=_surface!.Camera.WorldToScreenPoint(r.bounds.center).ToString(),visible=r.isVisible,material=r.sharedMaterial?.name}),Formatting.Indented));
            }
            else if(op=="select")
            {
                var views=(List<SealedBoosterView>)AccessTools.Field(typeof(BoosterChamberController),"_boosterViews").GetValue(_chamber);
                var view=views.Single(v=>v.CollationId==(int)action["collationId"]!);
                _chamber.ClickedBooster(view);
            }
            else if(op=="dismiss")AccessTools.Method(typeof(BoosterChamberController),"DismissCards").Invoke(_chamber,null);
            else if(op=="open")
            {
                var view=(SealedBoosterView)AccessTools.Field(typeof(BoosterChamberController),"_selectedBoosterView").GetValue(_chamber);
                if((int?)action["quantity"]==10)_chamber.OpenTen();else _chamber.ClickedBooster(view);
            }
            else if(op=="reference_layout")_chamber.StartCoroutine(ProbeOriginalLayout());
            else if(op=="replay_last")_chamber.StartCoroutine(ReplayLast());
            else if(op=="inspect_cards")
            {
                File.WriteAllText(Path.Combine(_root,"pack-card-render-probe.json"),JsonConvert.SerializeObject(UnityEngine.Object.FindObjectsByType<BoosterMetaCardView>(FindObjectsSortMode.None).Where(v=>v.Card!=null).Select(v=>new{
                    id=v.GetInstanceID(),grpId=v.Card.GrpId,position=v.transform.position.ToString(),scale=v.transform.lossyScale.ToString(),parent=v.transform.parent?.name,
                    renderers=v.GetComponentsInChildren<Renderer>(true).Select(r=>new{r.name,r.enabled,active=r.gameObject.activeInHierarchy,layer=r.gameObject.layer,bounds=r.bounds.ToString(),materials=r.sharedMaterials.Select(m=>new{name=m?.name,shader=m?.shader?.name}).ToArray()}).ToArray()
                }).ToArray(),Formatting.Indented));
            }
            else if(op=="inspect_input")
            {
                var pointer=new PointerEventData(EventSystem.current){position=new Vector2((float)action["x"]!,(float)action["y"]!)};
                var hits=new List<RaycastResult>();EventSystem.current.RaycastAll(pointer,hits);
                var inputSequence=AccessTools.Field(typeof(BoosterChamberController),"_boosterOpenToScrollListController").GetValue(_chamber);
                var list=(RewardScrollList)AccessTools.Field(inputSequence.GetType(),"scrollList").GetValue(inputSequence);
                File.WriteAllText(Path.Combine(_root,"pack-input-probe.json"),JsonConvert.SerializeObject(new{list.ManualScrollDragAllowed,hits=hits.Select(h=>new{name=h.gameObject.name,module=h.module.GetType().FullName,canvas=h.gameObject.GetComponentInParent<Canvas>()?.name,h.depth}).ToArray()},Formatting.Indented));
            }
            else throw new NotSupportedException("Unsupported pack-screen command: "+op);
        }
        var snapshot=_profile.Snapshot;
        var selected=AccessTools.Field(typeof(BoosterChamberController),"_selectedBoosterView").GetValue(_chamber) as SealedBoosterView;
        var sequence=AccessTools.Field(typeof(BoosterChamberController),"_boosterOpenToScrollListController").GetValue(_chamber);
        var revealCards=AccessTools.Field(sequence.GetType(),"_cardsToOpen").GetValue(sequence) as List<Core.Meta.MainNavigation.BoosterChamber.CardDataAndRevealStatus>;
        File.WriteAllText(Path.Combine(_root,"pack-host-status.json"),JsonConvert.SerializeObject(new{utc=DateTime.UtcNow,ready=_chamber.IsReadyToShow,opened=_chamber.ThereIsABoosterOpened,selectedCollation=selected?.CollationId,revision=snapshot["revision"],openingCount=((JArray)snapshot["openings"]!).Count,collectionCopies=((JObject)snapshot["cards"]!).Properties().Sum(p=>(int)p.Value),packs=snapshot["packs"],nativeViews=_chamber.GetComponentsInChildren<SealedBoosterView>().Length,revealCards=revealCards?.Select(c=>new{grpId=c.CardData.GrpId,c.Revealed,c.InFinalPosition,c.AutoReveal}).ToArray(),presentationError=_lastPresentationError,policy="Custom sandbox distribution; no wildcard track or bonus-sheet/duplicate protection."},Formatting.Indented));
    }
    private IEnumerator ProbeOriginalLayout()
    {
        yield return Scenes.LoadSceneAsync("MainNavigation",LoadSceneMode.Additive);
        var scene=SceneManager.GetSceneByName("MainNavigation");
        var roots=scene.GetRootGameObjects();
        File.WriteAllText(Path.Combine(_root,"native-menu-layout-reference.json"),JsonConvert.SerializeObject(new{
            cameras=roots.SelectMany(r=>r.GetComponentsInChildren<Camera>(true)).Select(c=>new{c.name,position=c.transform.position.ToString(),rotation=c.transform.eulerAngles.ToString(),c.orthographic,c.orthographicSize,c.fieldOfView,c.nearClipPlane,c.farClipPlane,c.cullingMask,c.depth,active=c.gameObject.activeInHierarchy,c.enabled,urp=JsonUtility.ToJson(c.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>())}).ToArray(),
            canvases=roots.SelectMany(r=>r.GetComponentsInChildren<Canvas>(true)).Select(c=>new{c.name,c.renderMode,c.planeDistance,c.scaleFactor,position=c.transform.position.ToString(),scale=c.transform.localScale.ToString(),size=(c.transform as RectTransform)?.rect.size.ToString(),scaler=c.GetComponent<CanvasScaler>()?.referenceResolution.ToString()}).ToArray(),
            lights=roots.SelectMany(r=>r.GetComponentsInChildren<Light>(true)).Select(l=>new{l.name,l.type,l.intensity,color=l.color.ToString(),position=l.transform.position.ToString(),rotation=l.transform.eulerAngles.ToString()}).ToArray()
        },Formatting.Indented));
        yield return SceneManager.UnloadSceneAsync(scene);
        _log("Captured original MainNavigation camera/canvas/light reference without initializing official menu services.");
    }
}
