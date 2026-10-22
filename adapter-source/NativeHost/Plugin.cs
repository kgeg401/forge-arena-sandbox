using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Collections;
using System.Runtime.InteropServices;
using BepInEx;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.EventSystems;
using Wotc.Mtgo.Gre.External.Messaging;
using Core.Code.AssetBundles.Manifest;
using Core.Shared.Code.ServiceFactories;
using Cysharp.Threading.Tasks;
using Wizards.Mtga;
using Wizards.Mtga.Assets;
using Wizards.Mtga.Platforms;
using Wotc.Mtga.Cards.Database;
using Wotc.Mtga.DuelScene.Interactions;

namespace ForgeArenaSandbox;

[BepInPlugin("local.codex.forge-arena-sandbox", "Forge Arena Local Host", "0.1.0")]
public sealed class Plugin : BaseUnityPlugin
{
    private string _root = "";
    private float _next;
    private LocalGreConnection? _connection;
    private ForgeLandBridge? _forge;
    private NativePackChamber? _packs;
    private NativeDeckScreen? _decks;
    private string _phase = "starting";
    private string? _gap;
    private sealed class NativeQaRejectedException : Exception
    {
        public NativeQaRejectedException(string message) : base(message) { }
    }
    private readonly List<string> _events = new List<string>();
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr value);
    [DllImport("advapi32.dll", SetLastError = true)] static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [DllImport("advapi32.dll", SetLastError = true)] static extern bool GetTokenInformation(IntPtr token, int info, IntPtr buffer, int length, out int needed);

    private void Awake()
    {
        _root = LabBoundary.Validate(Paths.GameRootPath);
        if (!IsNetworkIsolated())
            throw new InvalidOperationException("Local host requires the independent zero-capability AppContainer lab.");
        _phase = "waiting-for-native-services";
        HarmonyLib.Harmony.CreateAndPatchAll(typeof(NativeInputDiagnostics),"local.forge-arena.input-observation");
        Logger.LogInfo("Local host loaded inside isolated Unity process; native scene probe active.");
    }

    private static bool IsNetworkIsolated()
    {
        if (!OpenProcessToken(GetCurrentProcess(), 8, out var token)) return false;
        try
        {
            var memory = Marshal.AllocHGlobal(4);
            try { if (!GetTokenInformation(token, 29, memory, 4, out _) || Marshal.ReadInt32(memory) != 1) return false; }
            finally { Marshal.FreeHGlobal(memory); }
            GetTokenInformation(token, 30, IntPtr.Zero, 0, out var size);
            memory = Marshal.AllocHGlobal(size);
            try { return GetTokenInformation(token, 30, memory, size, out _) && Marshal.ReadInt32(memory) == 0; }
            finally { Marshal.FreeHGlobal(memory); }
        }
        finally { CloseHandle(token); }
    }

    private void Update()
    {
        if(_root=="")return;
        try{_forge?.Poll();}catch(Exception ex){_gap=ex.ToString();Logger.LogError(ex);}
        if (Time.realtimeSinceStartup < _next) return;
        _next = Time.realtimeSinceStartup + 1f;
        try
        {
            _packs?.Poll();
            _decks?.Poll();
            var papa = UnityEngine.Object.FindFirstObjectByType<PAPA>();
            var decksRequest = Path.Combine(_root, "start-decks.request");
            if(File.Exists(decksRequest))
            {
                File.Delete(decksRequest);
                if(papa==null || papa.CardDatabase==null)throw new InvalidOperationException("Prepare owned native assets before opening decks.");
                if(_connection!=null || _packs!=null)throw new InvalidOperationException("Open decks in a fresh lab session; preserve the current screen.");
                if(_decks==null)_decks=new NativeDeckScreen(_root,papa,value=>{_events.Add(value);if(_events.Count>20)_events.RemoveAt(0);});
                _decks.Open();_phase="native-local-deck-editor";
            }
            var packsRequest = Path.Combine(_root, "start-packs.request");
            if (File.Exists(packsRequest))
            {
                File.Delete(packsRequest);
                if (papa == null || papa.CardDatabase == null) throw new InvalidOperationException("Prepare the owned native assets before opening packs.");
                if (_connection != null || _decks != null) throw new InvalidOperationException("Open packs in a fresh lab session; the current screen is preserved.");
                if (_packs == null) _packs = new NativePackChamber(_root, papa, value => { _events.Add(value); if (_events.Count > 20) _events.RemoveAt(0); });
                _packs.Open();
                _phase = "native-pack-chamber-probe";
            }
            var prepare = Path.Combine(_root, "prepare-local-assets.request");
            if (File.Exists(prepare))
            {
                File.Delete(prepare);
                if (papa == null) _gap = "Native application context has not been created.";
                else StartCoroutine(PrepareLocalAssets(papa));
            }
            var command = Path.Combine(_root, "start-board.request");
            if (File.Exists(command))
            {
                File.Delete(command);
                if (_connection != null || _decks != null || _packs != null) throw new InvalidOperationException("A local screen already exists. Start a fresh lab session for a match.");
                if (papa == null || papa.CardDatabase == null || papa.MatchManager == null || papa.Matchmaking == null)
                    _gap = "Native context/card database/match services are not initialized. No substitute database or official connection will be used.";
                else StartBoard(papa);
            }
            var scenes = Enumerable.Range(0, SceneManager.sceneCount).Select(i => SceneManager.GetSceneAt(i).name).ToArray();
            var game = UnityEngine.Object.FindFirstObjectByType<GameManager>();
            NativeInputDiagnostics.Enabled=File.Exists(Path.Combine(_root,"input-diagnostics.flag"));
            var nativeActionPath=Path.Combine(_root,"native-action.request.json");
            if(File.Exists(nativeActionPath))
            {
                var action=JObject.Parse(File.ReadAllText(nativeActionPath));File.Delete(nativeActionPath);
                void QaResult(bool accepted,string? reason=null)=>File.WriteAllText(Path.Combine(_root,"native-action-result.json"),JsonConvert.SerializeObject(new{requestId=(string?)action["requestId"],utc=DateTime.UtcNow,accepted,reason,nativeState=game?.CurrentGameState?.Id,workflow=game?.WorkflowController.CurrentWorkflow?.GetType().Name}));
                try
                {
                  var activeWorkflow=game?.WorkflowController.CurrentWorkflow;
                  var workflow=activeWorkflow as IClickableWorkflow;
                  string ButtonPath(StyledButton button){var names=new List<string>();for(var node=button.transform;node!=null;node=node.parent)names.Add(node.name);names.Reverse();return string.Join("/",names);}
                  var uiButtons=UnityEngine.Object.FindObjectsByType<StyledButton>(FindObjectsSortMode.None).Where(b=>b.gameObject.activeInHierarchy && b.HasInteraction).ToArray();
                  var buttonModel=typeof(StyledButton).GetField("_model",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)!;
                  var uiButtonInfo=uiButtons.Select(b=>{var model=(PromptButtonData)buttonModel.GetValue(b);return new{path=ButtonPath(b),enabled=model.Enabled && b.IsInteractable(),key=model.ButtonText?.Key};}).ToArray();
                  object? mulliganBrowser=null;
                  for(var type=activeWorkflow?.GetType();type!=null;type=type.BaseType){var field=type.GetField("_openedBrowser",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.DeclaredOnly);if(field!=null){mulliganBrowser=field.GetValue(activeWorkflow);break;}}
                  int? HandlerCount(string name)=>mulliganBrowser==null?null:(mulliganBrowser.GetType().GetField(name,System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)?.GetValue(mulliganBrowser) as Delegate)?.GetInvocationList().Length ?? 0;
                  bool? KeepTargetsCurrent()=>mulliganBrowser==null?null:(mulliganBrowser.GetType().GetField("KeepPressed",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)?.GetValue(mulliganBrowser) as Delegate)?.GetInvocationList().All(d=>ReferenceEquals(d.Target,activeWorkflow));
                  GreClient.Rules.BaseUserRequest? observedRequest=null;
                  for(var type=activeWorkflow?.GetType();type!=null;type=type.BaseType){var field=type.GetField("_request",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.DeclaredOnly);if(field!=null){observedRequest=field.GetValue(activeWorkflow) as GreClient.Rules.BaseUserRequest;break;}}
                var clickType=(bool?)action["primary"]==true?SimpleInteractionType.Primary:SimpleInteractionType.DoublePrimary;
                var views=UnityEngine.Object.FindObjectsByType<DuelScene_CDC>(FindObjectsSortMode.None);
                var hits=new List<RaycastResult>();
                var point=new Vector2((float?)action["x"]??0,(float?)action["y"]??0);
                if(EventSystem.current!=null && action["x"]!=null)EventSystem.current.RaycastAll(new PointerEventData(EventSystem.current){position=point},hits);
                  File.WriteAllText(Path.Combine(_root,"native-action-probe.json"),JsonConvert.SerializeObject(new{utc=DateTime.UtcNow,workflow=activeWorkflow?.GetType().Name,applied=activeWorkflow?.AppliedState.ToString(),nativeState=game?.CurrentGameState?.Id,nativeRequest=observedRequest==null?null:new{type=observedRequest.GetType().Name,state=observedRequest.OriginalMessage.GameStateId,message=observedRequest.OriginalMessage.MsgId,submitListeners=observedRequest.OnSubmit?.GetInvocationList().Length ?? 0},uiButtons=uiButtonInfo,mulliganHandlers=new{browser=mulliganBrowser?.GetType().Name,keep=HandlerCount("KeepPressed"),mulligan=HandlerCount("MulliganPressed"),keepTargetsCurrent=KeepTargetsCurrent()},buttons=activeWorkflow?.Buttons?.WorkflowButtons.Select(b=>new{text=b.ButtonText.ToString(),tag=b.Tag.ToString(),enabled=b.Enabled}).ToArray(),screen=new{width=Screen.width,height=Screen.height},focused=Application.isFocused,inputModule=EventSystem.current?.currentInputModule?.GetType().FullName,
                    mouse=UnityEngine.InputSystem.Mouse.current?.position.ReadValue().ToString(),hovered=Wotc.Mtga.CustomInput.CustomUIInputModule.GetHovered().Select(g=>g.name).ToArray(),inputEvents=NativeInputDiagnostics.Events.ToArray(),
                    raycasters=UnityEngine.Object.FindObjectsByType<BaseRaycaster>(FindObjectsSortMode.None).Select(r=>new{name=r.name,type=r.GetType().Name,enabled=r.enabled,camera=r.eventCamera?.name}).ToArray(),
                    raycast=hits.Select(h=>new{name=h.gameObject.name,module=h.module.GetType().Name,card=h.gameObject.GetComponentInParent<DuelScene_CDC>()?.InstanceId,distance=h.distance}).ToArray(),
                    views=views.Select(v=>new{id=v.InstanceId,holder=v.CurrentCardHolder?.CardHolderType.ToString(),click=workflow?.CanClick(v,clickType),visible=v.IsVisible,inputEnabled=v.InputHandler!=null && v.InputHandler.enabled,active=v.gameObject.activeInHierarchy,layer=v.gameObject.layer,position=Camera.main!=null?Camera.main.WorldToScreenPoint(v.transform.position).ToString():null}).ToArray()},Formatting.Indented));
                if((string?)action["op"]=="click")
                {
                    if(workflow==null || activeWorkflow?.AppliedState!=InteractionAppliedState.Applied || activeWorkflow.GetType().Name!=(string?)action["expectedWorkflow"] || game?.CurrentGameState?.Id!=(uint?)action["nativeState"])throw new NativeQaRejectedException("Native card context changed; inspect again.");
                    var matchingViews=views.Where(v=>v.InstanceId==(uint)action["instanceId"]!).ToArray();
                    if(matchingViews.Length!=1)throw new NativeQaRejectedException("Native card view is no longer unique; inspect again.");
                    var view=matchingViews[0];
                    if(!workflow.CanClick(view,clickType))throw new NativeQaRejectedException("Native workflow rejected this card interaction; see native-action-probe.json.");
                    workflow.OnClick(view,clickType);
                }
                  else if((string?)action["op"]=="button")
                  {
                      if(activeWorkflow==null || activeWorkflow.AppliedState!=InteractionAppliedState.Applied || activeWorkflow.GetType().Name!=(string?)action["expectedWorkflow"] || game?.CurrentGameState?.Id!=(uint?)action["nativeState"])throw new NativeQaRejectedException("Native QA button context changed; inspect again.");
                      var matchingButtons=activeWorkflow.Buttons.WorkflowButtons.Where(b=>b.Enabled && b.Tag.ToString()==(string?)action["tag"] && b.ButtonText.ToString()==(string?)action["text"]).ToArray();
                      if(matchingButtons.Length!=1)throw new NativeQaRejectedException("Native workflow button is no longer unique/enabled; inspect again.");
                      matchingButtons[0].ButtonCallback();
                  }
                  else if((string?)action["op"]=="ui_button")
                  {
                      if(activeWorkflow==null || activeWorkflow.AppliedState!=InteractionAppliedState.Applied || activeWorkflow.GetType().Name!=(string?)action["expectedWorkflow"] || game?.CurrentGameState?.Id!=(uint?)action["nativeState"])throw new NativeQaRejectedException("Native QA UI button context changed; inspect again.");
                      var matchingButtons=uiButtons.Where(b=>ButtonPath(b)==(string?)action["path"]).ToArray();
                      if(matchingButtons.Length!=1)throw new NativeQaRejectedException("Native UI button is no longer unique; inspect again.");
                      var button=matchingButtons[0];
                      var model=(PromptButtonData)buttonModel.GetValue(button);
                      if(!model.Enabled || !button.IsInteractable())throw new NativeQaRejectedException("Native UI button is disabled.");
                      button.onClick.Invoke();
                  }
                  else if((string?)action["op"]!="inspect")throw new NativeQaRejectedException("Unknown native QA operation.");
                  if((string?)action["op"]!="inspect")QaResult(true);
                }
                catch(NativeQaRejectedException ex){QaResult(false,ex.Message);Logger.LogWarning(ex.Message);}
            }
            var incoming = Path.Combine(_root, "incoming-messages.request.json");
            if (File.Exists(incoming) && _connection != null)
            {
                if (_forge != null) throw new InvalidOperationException("Raw fixture injection is disabled while Forge controls the board.");
                var batch = JArray.Parse(File.ReadAllText(incoming));
                if (batch.Count > 128) throw new InvalidOperationException("Local message batch exceeds limit.");
                var parsed = batch.Select(value => GREToClientMessage.Parser.ParseJson(value.ToString(Formatting.None))).ToArray();
                File.Delete(incoming);
                foreach (var message in parsed) _connection.Enqueue(message);
                _events.Add("Queued local test messages: " + parsed.Length);
            }
            var capture = Path.Combine(_root, "capture-frame.request");
            if (File.Exists(capture))
            {
                File.Delete(capture);
                var captureType = Type.GetType("UnityEngine.ScreenCapture, UnityEngine.ScreenCaptureModule", true);
                captureType!.GetMethod("CaptureScreenshot", new[] { typeof(string) })!.Invoke(null, new object[] { Path.Combine(_root, "native-board.png") });
            }
            File.WriteAllText(Path.Combine(_root, "native-host-status.json"), JsonConvert.SerializeObject(new
            {
                utc = DateTime.UtcNow, phase = _phase, gap = _gap, scenes,
                papa = papa != null, realDatabase = papa != null && papa.CardDatabase != null,
                matchServices = papa != null && papa.Matchmaking != null,
                nativeGameManager = game != null, nativeState = game != null ? game.CurrentGameState?.Id : null, presentationBusy = game != null && game.UXEventQueue.IsRunning,
                audio = new { initialized = AudioManager.Instance != null && AudioManager.Instance.Initialized, loadError = AudioManager.Instance != null && AudioManager.Instance.HadLoadError, packages = AudioManager.AvailableAudioPackages?.Count ?? 0 },
                players = game != null && game.CurrentGameState != null ? game.CurrentGameState.Players.Select(p => new { seat = p.InstanceId, life = p.LifeTotal }).ToArray() : null,
                forge = _forge == null ? null : new { session = _forge.Session, scenario = _forge.Scenario, gameOver = _forge.GameOver, decision = _forge.DecisionKind, landsPlayed = _forge.LandsPlayed, mana = _forge.ManaTotal, turn = _forge.Turn, phase = _forge.Phase, activeSeat = _forge.ActiveSeat, hand = _forge.HandCount, battlefield = _forge.BattlefieldCount, gap = _forge.Gap },
                persistentPath = Application.persistentDataPath, recentEvents = _events.ToArray()
            }, Formatting.Indented));
        }
        catch (Exception ex) { _gap = ex.ToString(); Logger.LogError(ex); }
    }

    private IEnumerator PrepareLocalAssets(PAPA papa)
    {
        _gap = null;
        _phase = "preparing-installed-local-assets";
        var boot = UnityEngine.Object.FindFirstObjectByType<Bootstrap>();
        if (boot != null) boot.StopAllCoroutines();
        AssetLoader.Initialize(papa.BILogger);
        var provisioner = AssetBundleProvisioner.Create();
        var downloads = Path.Combine(Application.dataPath, "Downloads");
        var seen = new HashSet<string>();
        foreach (var file in Directory.GetFiles(downloads, "Manifest*.mtga"))
        {
            var manifest = JsonConvert.DeserializeObject<AssetFileManifest>(File.ReadAllText(file));
            if (manifest == null) throw new InvalidOperationException("Cannot parse installed manifest: " + file);
            foreach (var asset in manifest.AssetFileInfoByName.Values)
                if (seen.Add(asset.Name)) provisioner.AvailableBundles.Add(asset);
        }
        // Populate only from installed manifests; never call PrepareDownload or a server.
        AssetLoader.PrepareAssets(provisioner, PlatformContext.GetStorageContext().GetEmbeddedBundlePathResolver());
        AudioManager.InitializeAudioManager(papa.AssetLookupSystem, PlatformContext.GetStorageContext());
        _events.Add("Installed manifest assets: " + provisioner.AvailableBundles.Count);
        _phase = "loading-native-localization";
        yield return new LoadLocDatabaseUniTask().Load().ToCoroutine();
        _phase = "loading-native-card-database";
        yield return new LoadCardDatabaseUniTask().Load().ToCoroutine();
        var database = Pantry.Get<CardDatabase>();
        typeof(PAPA).GetProperty("CardDatabase")!.GetSetMethod(true)!.Invoke(papa, new object[] { database });
        _phase = "initializing-native-card-builders";
        papa.CreateFormatManager();
        papa.SetupDeckFormatFactory();
        papa.InitCardBuilders();
        yield return new LoadSetMetadataUniTask().Load().ToCoroutine();
        _phase = "initializing-installed-native-audio";
        AudioManager.InitializeAudio(papa.AssetLookupSystem);
        _events.Add("Native audio initialized; packages=" + AudioManager.AvailableAudioPackages.Count + "; loadError=" + AudioManager.Instance.HadLoadError);
        _phase = "initializing-local-match-services";
        papa.InitializeNpe();
        papa.InitializeMatchMaking();
        _phase = "local-assets-ready-render-unverified";
        _events.Add("Loaded real native database and local services");
    }

    private void StartBoard(PAPA papa)
    {
        var manager = papa.MatchManager;
        _connection = new LocalGreConnection();
        _connection.LocalCommand += command =>
        {
            _events.Add("Native outgoing: " + command.Type);
            if (_events.Count > 20) _events.RemoveAt(0);
            if (_forge == null) _gap = "Native command captured locally. Forge backend is not connected yet.";
        };
        if (File.Exists(Path.Combine(_root, "enable-forge-land-test.flag")))
            _forge = new ForgeLandBridge(_root, _connection, message => { _events.Add(message); if (_events.Count > 20) _events.RemoveAt(0); }, () =>
            {
                var visibleGame=UnityEngine.Object.FindFirstObjectByType<GameManager>();
                return visibleGame != null && !visibleGame.UXEventQueue.IsRunning ? visibleGame.CurrentGameState?.Id : null;
            }, () =>
            {
                var visibleGame=UnityEngine.Object.FindFirstObjectByType<GameManager>();
                var workflow=visibleGame?.WorkflowController.CurrentWorkflow as ActionsAvailableWorkflow;
                if(workflow==null || workflow.AppliedState!=Wotc.Mtga.DuelScene.Interactions.InteractionAppliedState.Applied)return false;
                workflow.OnAutoYieldEnabled();
                return true;
            });
        manager.Initialize(_connection, papa.CardDatabase);
        manager.LocalPlayerInfo.SeatId = 1;
        manager.LocalPlayerInfo.TeamId = 1;
        manager.OpponentInfo.SeatId = 2;
        manager.OpponentInfo.TeamId = 2;
        if(_forge?.Scenario=="brawl-duel")
        {
            manager.LocalPlayerInfo.Commanders=_forge.Commanders(1);
            manager.OpponentInfo.Commanders=_forge.Commanders(2);
        }
        // Installed ProfileUtilities names Ajani as its default-login fallback;
        // Sparky is the installed tutorial opponent constant. Let the original
        // PlayerCreatedMediator resolve portraits through the native asset tree.
        manager.LocalPlayerInfo.AvatarSelection = "Avatar_Basic_AjaniGoldmane";
        manager.OpponentInfo.AvatarSelection = AvatarIdConstants.Sparky;
        var localPortrait=ProfileUtilities.GetAvatarBustImagePath(papa.AssetLookupSystem,manager.LocalPlayerInfo.AvatarSelection);
        var opponentPortrait=ProfileUtilities.GetAvatarBustImagePath(papa.AssetLookupSystem,manager.OpponentInfo.AvatarSelection);
        if(string.IsNullOrEmpty(localPortrait) || string.IsNullOrEmpty(opponentPortrait))throw new NotSupportedException("Installed native avatar portrait mapping is unavailable.");
        _events.Add("Native avatar portraits: "+localPortrait+" | "+opponentPortrait);
        manager.Players.Add(manager.LocalPlayerInfo);
        manager.Players.Add(manager.OpponentInfo);
        var fixture = JObject.Parse(File.ReadAllText(Path.Combine(_root, "board-fixture.json")));
        var full = GREToClientMessage.Parser.ParseJson(fixture["messages"]![0]!.ToString(Formatting.None));
        _phase = "loading-native-match-scene";
        MatchSceneManager.Load(papa, "", () =>
        {
            try
            {
                _connection.Connect(null!);
                _connection.ConnectToGRE(LocalGreConnection.LocalUri, _connection.MatchId);
                if (_forge != null) _forge.Start();
                else _connection.Enqueue(full);
                _phase = "local-state-queued-native-render-unverified";
            }
            catch (Exception ex) { _gap = ex.ToString(); Logger.LogError(ex); }
        });
    }
}
