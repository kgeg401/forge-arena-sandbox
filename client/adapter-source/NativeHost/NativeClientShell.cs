using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Collections;
using HarmonyLib;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;
using TMPro;
using Wotc.Mtga.Loc;
using MTGA.Loc;
using AssetLookupTree.Payloads.Prefab;
using Core.Code.AssetLookupTree.AssetLookup;
using Wizards.Mtga;
using Wizards.Mtga.Assets;

namespace ForgeArenaSandbox;

// Original owned screen prefabs; this adapter supplies only offline navigation/data.
internal sealed class NativeClientShell
{
    private static NativeClientShell? _active;
    private readonly string _root;
    private readonly PAPA _papa;
    private readonly Action<string> _log;
    private bool _constructing;
    private HomePageContentController? _home;
    private NavBarController? _nav;
    private NativeDeckScreen? _decks;
    private NativePlayMenu? _play;
    private NativePackChamber? _packs;
    private NativeClientDialogs? _dialogs;
    private NativeDisplayProfile? _display;
    private readonly MonoBehaviour _runner;
    private readonly Action _startMatch;
    private readonly Func<IEnumerator> _endMatch;
    private string _session="";
    private string? _matchRequest;
    private bool _matchActive;
    private bool _returning;
    private bool _awaitingReturn;
    private float _returnDeadline;
    private bool _cancelRequested;
    private string? _reportedServiceError;
    private DateTime _queuedAt;
    private bool _warmingPacks;
    private float _packsDeadline;
    private GameObject? _loading;
    private CustomButton? _cancel;
    private TMP_Text? _progress;
    private string _queueMessage="";
    private string _screen="starting";
    private string? _error;
    public NativeMenuSurface Surface {get;private set;}=null!;
    public NativeClientShell(string root,PAPA papa,Action<string> log,MonoBehaviour runner,Action startMatch,Func<IEnumerator> endMatch){_root=root;_papa=papa;_log=log;_runner=runner;_startMatch=startMatch;_endMatch=endMatch;}
    private static bool Owned(Component obj)=>_active!=null && (_active._constructing || (_active.Surface!=null && obj.transform.IsChildOf(_active.Surface.Root)));
    private static bool SkipOnline(Component __instance)=>!Owned(__instance);
    private static void Clear(UnityEventBase value){for(int i=0;i<value.GetPersistentEventCount();i++)value.SetPersistentListenerState(i,UnityEventCallState.Off);value.RemoveAllListeners();}
    private void Bind(CustomButton button,Action action){Clear(button.OnClick);button.Interactable=true;button.OnClick.AddListener(()=>Act(action));}
    private void Act(Action action){_error=null;try{action();}catch(Exception ex){_error=ex.ToString();_log(_error);_dialogs?.Show("Sandbox could not complete that action",ex.Message);}WriteStatus();}
    public void Open()
    {
        if(_home!=null){Home();return;}
        _active=this;
        var harmony=new Harmony("local.forge-arena.client-shell");
        harmony.Patch(AccessTools.Method(typeof(MatchSceneManager),"ExitMatchScene"),prefix:new HarmonyMethod(typeof(NativeClientShell),nameof(ExitLocalMatch)));
        var sessionPath=Path.Combine(_root,"client-session.json");
        if(File.Exists(sessionPath))
        {
            var session=JObject.Parse(File.ReadAllText(sessionPath));_session=(string)session["session"]!;
            if(!NativeClientWindow.SetTitle((string?)session["displayVersion"]??""))_log("The sandbox window title could not be applied.");
        }
        foreach(var spec in new[]{(typeof(NavBarController),new[]{"Awake","Start","OnEnable","OnDestroy"}),(typeof(HomePageContentController),new[]{"OnDestroy"}),(typeof(HomeCarouselController),new[]{"Awake","OnDestroy"})})
            foreach(string method in spec.Item2){var original=AccessTools.Method(spec.Item1,method);if(original!=null)harmony.Patch(original,prefix:new HarmonyMethod(typeof(NativeClientShell),nameof(SkipOnline)));}
        Surface=new NativeMenuSurface(_papa);
        _display=new NativeDisplayProfile(_root);
        _dialogs=new NativeClientDialogs(_papa);
        _constructing=true;
        try
        {
            _home=AssetLoader.Instantiate<HomePageContentController>(_papa.AssetLookupSystem.GetPrefabPath<HomePrefab,HomePageContentController>(),Surface.Root);
            Stretch(_home.transform);_home.enabled=false;
            foreach(var field in new[]{"_billboardController","CarouselController"})
            {var value=AccessTools.Field(typeof(HomePageContentController),field)?.GetValue(_home) as Behaviour;if(value!=null)value.enabled=false;}
            _home.transform.Find("SafeZone/Banners")?.gameObject.SetActive(false);
            _home.MainButton.UpdateState(PlayBladeState.Ready);
            var main=_home.MainButton.GetComponent<CustomButton>();
            if(main!=null)Bind(main,Play);
            else {var button=_home.MainButton.GetComponent<Button>();Clear(button.onClick);button.onClick.AddListener(()=>Act(Play));}
            _nav=AssetLoader.Instantiate<NavBarController>(_papa.AssetLookupSystem.GetPrefabPath<NavBarPrefab,NavBarController>(),Surface.Root);
            _nav.enabled=false;
            foreach(var button in new[]{_nav.ProfileButton,_nav.StoreButton,_nav.MasteryButton,_nav.AchievementsButton,_nav.LearnButton,_nav.MailboxButton,_nav.VaultButton})if(button!=null)button.gameObject.SetActive(false);
            _nav.CurrenciesContainer.SetActive(false);
            _nav.DeckViewToggle.gameObject.SetActive(false);
            foreach(string field in new[]{"_wildcardButton","_navBarTokenView","_vaultContainer","_mailboxContainer","_learnContainer"})
            {
                var value=AccessTools.Field(typeof(NavBarController),field)?.GetValue(_nav);
                if(value is GameObject obj)obj.SetActive(false);else if(value is Component component && component.gameObject!=_nav.gameObject)component.gameObject.SetActive(false);
            }
            foreach(var field in typeof(NavBarController).GetFields())
                if(field.FieldType==typeof(GameObject) && (field.Name.EndsWith("Overlay") || field.Name.EndsWith("Lock") || field.Name.EndsWith("Indicator")))
                    (field.GetValue(_nav) as GameObject)?.SetActive(false);
            Bind(_nav.HomeButton,Home);Bind(_nav.DecksButton,Decks);Bind(_nav.PacksButton,Packs);
            _nav.OptionsButton.gameObject.SetActive(true);Bind(_nav.OptionsButton,()=>_runner.StartCoroutine(OpenSettings()));
            Home();
            _log("Original Home and navigation prefabs opened with offline routes.");
        }
        finally{_constructing=false;WriteStatus();}
    }
    private static void Stretch(Transform value){if(value is RectTransform rect){rect.anchorMin=Vector2.zero;rect.anchorMax=Vector2.one;rect.offsetMin=Vector2.zero;rect.offsetMax=Vector2.zero;}}
    private void RequireMenu(){if(_matchActive || _matchRequest!=null || _returning || _awaitingReturn)throw new InvalidOperationException("Finish or cancel the current match before changing screens.");if(_warmingPacks)throw new InvalidOperationException("The original Packs screen is still loading.");}
    public void FlushProfile(){_decks?.FlushProfile();_display?.Flush();}
    public void Home(){if(_matchRequest!=null && !_matchActive && !_returning && !_awaitingReturn){CancelQueue();return;}RequireMenu();_packs?.Hide();_play?.Hide();_decks?.Hide();_home!.gameObject.SetActive(true);_screen="home";Select(_nav?.HomeButton);WriteStatus();}
    private void Decks(){RequireMenu();_packs?.Hide();_play?.Hide();_home!.gameObject.SetActive(false);if(_decks==null)_decks=new NativeDeckScreen(_root,_papa,_log,Surface,_dialogs);_decks.Open();_screen="decks";Select(_nav!.DecksButton);}
    private void Packs(){RequireMenu();_play?.Hide();_decks?.Hide();if(_packs==null)_packs=new NativePackChamber(_root,_papa,_log,Surface);_packs.Open();_home!.gameObject.SetActive(false);_screen="packs";Select(_nav!.PacksButton);if(!_packs.Ready){_warmingPacks=true;_packsDeadline=Time.realtimeSinceStartup+60;_screen="loading-packs";Surface.Camera.enabled=false;_nav!.gameObject.SetActive(false);_dialogs!.ShowLoading("Preparing packs…");}}
    private void Play(){RequireMenu();_packs?.Hide();if(_decks==null){_decks=new NativeDeckScreen(_root,_papa,_log,Surface,_dialogs);_decks.Open();}_decks.Hide();_home!.gameObject.SetActive(true);if(_play==null)_play=new NativePlayMenu(_root,_papa,Surface,_decks,_runner,(q,id)=>Act(()=>Join(q,id)),id=>Act(()=>{_play?.Hide();Decks();_decks.EditDeck(id);}));_play.Open();_screen="play";}
    private void Send(string action,JObject? extra=null)
    {
        var value=extra??new JObject();value["schema"]=1;value["session"]=_session;value["id"]=Guid.NewGuid().ToString();value["action"]=action;
        string target=Path.Combine(_root,"client-service.request.json");
        if(File.Exists(target))throw new InvalidOperationException("A local client request is still being processed.");
        File.WriteAllText(target+".pending",value.ToString(Formatting.Indented));File.Move(target+".pending",target);
    }
    private void Join(string queue,Guid id)
    {
        if(_matchActive || _matchRequest!=null)return; // Ignore a repeated native Play click.
        if(!Guid.TryParse(_session,out _))throw new InvalidOperationException("Start this client with the dedicated launcher before starting a bot match.");
        var deck=_decks!.DeckById(id);var gaps=_decks.Library.MatchGaps(deck,queue);if(gaps.Length>0)throw new InvalidDataException(string.Join("\n",gaps));
        string target=Path.Combine(_root,"client-service-status.json");
        var service=JObject.Parse(File.ReadAllText(target));if((string?)service["session"]!=_session || !new[]{"idle","cancelled","error"}.Contains((string?)service["phase"]) || !DateTimeOffset.TryParse((string?)service["utc"],out var heartbeat) || DateTimeOffset.UtcNow-heartbeat>TimeSpan.FromSeconds(15))throw new InvalidOperationException("The local match service is not ready. Close and reopen the client.");
        _matchRequest=Guid.NewGuid().ToString();
        _cancelRequested=false;_reportedServiceError=null;_queuedAt=DateTime.UtcNow;
        var request=new JObject{["schema"]=1,["session"]=_session,["id"]=_matchRequest,["action"]="start",["queue"]=queue,["deckId"]=id.ToString()};
        string path=Path.Combine(_root,"client-service.request.json");if(File.Exists(path)){_matchRequest=null;throw new InvalidOperationException("A local match request is still pending.");}
        File.WriteAllText(path+".pending",request.ToString());File.Move(path+".pending",path);
        _play?.Hide();ShowQueue("Starting the local Forge bot…");_screen="queue";_log("Queued "+queue+" with saved deck "+id);
    }
    private void ShowQueue(string message)
    {
        if(_loading==null)
        {
            _loading=AssetLoader.Instantiate(_papa.AssetLookupSystem.GetPrefabPath<LoadingPanelPrefab,GameObject>(),Surface.Root);Stretch(_loading.transform);
            _progress=_loading.GetComponentsInChildren<TMP_Text>(true).FirstOrDefault();
            if(_progress==null)throw new NotSupportedException("Installed native loading panel has no text control.");
            foreach(var loc in _progress.GetComponents<Localize>())loc.enabled=false;
            _cancel=UnityEngine.Object.Instantiate(_home!.MainButton.GetComponent<CustomButton>(),_loading.transform);_cancel.name="Cancel local matchmaking";
            Bind(_cancel,CancelQueue);_cancel.SetText("Cancel");
            var rect=(RectTransform)_cancel.transform;rect.anchorMin=rect.anchorMax=new Vector2(.5f,.25f);rect.pivot=new Vector2(.5f,.5f);rect.anchoredPosition=Vector2.zero;rect.sizeDelta=new Vector2(300,75);rect.localScale=Vector3.one;
        }
        _queueMessage=message;_loading.SetActive(true);_cancel!.gameObject.SetActive(true);_progress!.gameObject.SetActive(true);_progress.text=message;
        _home!.MainButton.gameObject.SetActive(false);
        _nav!.gameObject.SetActive(false);
    }
    private void HideQueue(){_loading?.SetActive(false);_cancel?.gameObject.SetActive(false);_nav!.gameObject.SetActive(true);_home!.MainButton.gameObject.SetActive(true);}
    private void CancelQueue(){if(_matchRequest==null || _cancelRequested)return;Send("cancel",new JObject{["matchRequestId"]=_matchRequest});_cancelRequested=true;_queueMessage="Cancelling the local match…";if(_progress!=null)_progress.text=_queueMessage;}
    private static bool ExitLocalMatch(MatchSceneManager __instance){if(_active==null || !_active._matchActive)return true;_active.RequestReturn();return false;}
    public void RequestReturn(){if(!_matchActive || _returning)return;_returning=true;_screen="returning-home";_runner.StartCoroutine(ReturnHome());}
    private IEnumerator ReturnHome()
    {
        yield return _endMatch();
        _matchActive=false;_returning=false;_awaitingReturn=true;_returnDeadline=Time.realtimeSinceStartup+25;Surface.SetVisible(true);_nav!.gameObject.SetActive(true);
        Send("match-ended",new JObject{["matchRequestId"]=_matchRequest});_screen="queue";ShowQueue("Returning Home…");
    }
    private void PollService()
    {
        if(_matchRequest==null || _returning)return;
        string path=Path.Combine(_root,"client-service-status.json");if(!File.Exists(path))return;
        JObject service;using(var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete))using(var reader=new StreamReader(stream))service=JObject.Parse(reader.ReadToEnd());
        if((string?)service["session"]!=_session)return;
        if(!DateTimeOffset.TryParse((string?)service["utc"],out var heartbeat) || DateTimeOffset.UtcNow-heartbeat>TimeSpan.FromSeconds(15))
        {
            if(_reportedServiceError!="heartbeat")
            {
                _reportedServiceError="heartbeat";_error="The local match service stopped responding. Close and reopen the client.";
                _dialogs!.Show("Local match service unavailable",_error,"Close client",()=>Application.Quit());
            }
            return;
        }
        if((string?)service["requestId"]!=_matchRequest)return;
        string? phase=(string?)service["phase"];
        if(_awaitingReturn)
        {
            // A failed engine may still report its old error in the frame that
            // Return Home sends match-ended. Wait for that operation's outcome.
            if(phase=="idle")
            {
                _awaitingReturn=false;_error=null;_matchRequest=null;HideQueue();Home();
            }
            else if(Time.realtimeSinceStartup>_returnDeadline && _reportedServiceError!="return-timeout")
            {
                _reportedServiceError="return-timeout";
                _dialogs!.Show("Local match did not close","The local match service did not finish closing. Reopen the client to recover; your saved decks and collection are preserved.","Close client",()=>Application.Quit());
            }
            return;
        }
        if(_matchActive)
        {
            if(phase=="error" && _reportedServiceError!=(string?)service["message"])
            {
                _error=_reportedServiceError=(string?)service["message"]??"The local rules engine stopped.";
                _dialogs!.Show("Local match stopped",_error,"Return Home",RequestReturn);
            }
            return;
        }
        if(phase=="ready" && !_cancelRequested)
        {
            var engine=JObject.Parse(File.ReadAllText(Path.Combine(_root,"forge-ipc","state.json")));
            if((string?)engine["session"]!=(string?)service["engineSession"])throw new InvalidDataException("The local match session changed before the board opened.");
            HideQueue();Surface.SetVisible(false);_matchActive=true;_screen="match";
            try{_startMatch();Send("match-started",new JObject{["matchRequestId"]=_matchRequest});}
            catch{_matchActive=false;Surface.SetVisible(true);throw;}
        }
        else if(new[]{"idle","cancelled","error"}.Contains(phase))
        {
            _error=phase=="error"?(string?)service["message"]:null;_matchRequest=null;HideQueue();Home();
            if(_error!=null)_dialogs!.Show("Bot match could not start",_error);
        }
        else if(_progress!=null)_progress.text=_queueMessage=(string?)service["message"]??"Starting local match…";
    }
    private void Select(CustomButton? selected){if(_nav==null)return;foreach(var b in new[]{_nav.HomeButton,_nav.DecksButton,_nav.PacksButton})b.GetComponent<Animator>()?.SetBool("Selected",b==selected);_nav.transform.SetAsLastSibling();}
    private IEnumerator OpenSettings()
    {
        var task=Pantry.Get<SettingsMenuHost>().Open();while(!task.IsCompleted)yield return null;
        if(task.IsFaulted)Act(()=>throw task.Exception!.GetBaseException());
    }
    public void Poll()
    {
        _display?.Poll();
        _decks?.Poll();
        _packs?.Poll();
        if(_screen=="play" && _play!=null && !_play.IsOpen){_screen="home";Select(_nav?.HomeButton);}
        if(_warmingPacks && _packs!.Ready){_warmingPacks=false;Surface.Camera.enabled=true;_nav!.gameObject.SetActive(true);_dialogs!.HideLoading();_screen="packs";Select(_nav.PacksButton);}
        if(_warmingPacks && Time.realtimeSinceStartup>_packsDeadline)
        {
            _warmingPacks=false;Surface.Camera.enabled=true;_nav!.gameObject.SetActive(true);_dialogs!.HideLoading();
            _packs?.Hide();_screen="home";_home!.gameObject.SetActive(true);Select(_nav.HomeButton);
            _dialogs.Show("Packs did not finish loading","The installed Packs screen could not become ready. Your local collection was preserved. Return Home and try again.");
        }
        PollService();
        var request=Path.Combine(_root,"client-ui.request.json");
        if(File.Exists(request))
        {
            var value=JObject.Parse(File.ReadAllText(request));File.Delete(request);
            bool accepted=false;
            Act(()=>
            {
                if(value["expectedScreen"]!=null && (string?)value["expectedScreen"]!=_screen)throw new InvalidOperationException("The native screen changed; inspect again.");
                switch((string?)value["op"])
                {
                    case "home":Home();break;case "decks":Decks();break;case "play":Play();break;case "packs":Packs();break;case "inspect":Dump();break;
                    case "select-deck":_play!.SelectDeck(Guid.Parse((string)value["id"]!));break;
                    case "return-home":RequestReturn();break;
                    case "click":
                        var button=Surface.Root.GetComponentsInChildren<CustomButton>(false).Single(b=>PathOf(b.transform)==(string?)value["path"]);
                        if(!button.Interactable)throw new InvalidOperationException("The original native button is disabled.");button.OnClick.Invoke();break;
                    case "tab":
                        var tab=Surface.Root.GetComponentsInChildren<CustomTab>(false).Single(t=>t.name==(string?)value["name"]);
                        if(tab.Locked)throw new InvalidOperationException("The original native tab is locked.");tab.OnClicked();break;
                    default:throw new InvalidDataException("Unknown local client action.");
                }
                accepted=true;
            });
            File.WriteAllText(Path.Combine(_root,"client-ui-result.json"),JsonConvert.SerializeObject(new{requestId=(string?)value["requestId"],utc=DateTime.UtcNow,accepted,error=accepted?null:_error,screen=_screen}));
        }
        WriteStatus();
    }
    private void Dump()=>File.WriteAllText(Path.Combine(_root,"client-ui-tree.json"),JsonConvert.SerializeObject(Surface.Root.GetComponentsInChildren<Transform>(true).Select(t=>new{path=PathOf(t),active=t.gameObject.activeSelf,components=t.GetComponents<Component>().Select(c=>c?.GetType().FullName),rect=t is RectTransform r?new{anchors=r.anchorMin.ToString()+" "+r.anchorMax.ToString(),pivot=r.pivot.ToString(),position=r.anchoredPosition.ToString(),size=r.sizeDelta.ToString(),scale=r.localScale.ToString()}:null,group=t.GetComponent<CanvasGroup>()?.alpha,image=t.GetComponent<Image>()?.color.ToString()}),Formatting.Indented));
    private void WriteStatus()=>File.WriteAllText(Path.Combine(_root,"client-ui-status.json"),JsonConvert.SerializeObject(new{utc=DateTime.UtcNow,screen=_screen,error=_error,nativeHome=_home!=null,nativeNavigation=_nav!=null,persistent=true,matchRequest=_matchRequest,matchActive=_matchActive,cancelRequested=_cancelRequested,queueMessage=_queueMessage,dialogOpen=_dialogs?.IsOpen,selection=_play?.Snapshot(),buttons=Surface==null?null:Surface.Root.GetComponentsInChildren<CustomButton>(false).Select(b=>new{name=b.name,enabled=b.Interactable,path=PathOf(b.transform)}).ToArray()},Formatting.Indented));
    private static string PathOf(Transform node){var names=new List<string>();for(;node!=null;node=node.parent)names.Add(node.name);names.Reverse();return string.Join("/",names);}
}
