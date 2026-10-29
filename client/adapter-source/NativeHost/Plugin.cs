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

[BepInPlugin("local.codex.forge-arena-sandbox", "Forge Arena Local Host", "0.2.0")]
public sealed class Plugin : BaseUnityPlugin
{
    private string _root = "";
    private float _next;
    private LocalGreConnection? _connection;
    private ForgeLandBridge? _forge;
    private NativePackChamber? _packs;
    private NativeDeckScreen? _decks;
    private NativeClientShell? _shell;
    private string _phase = "starting";
    private string? _gap;
    private bool _cardAssetProbeRunning;
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

    private void OnApplicationQuit()
    {
        try{_shell?.FlushProfile();_decks?.FlushProfile();}
        catch(Exception ex){Logger.LogError("Pending deck changes could not be saved; the last committed library was preserved: "+ex);}
    }

    private void OnGUI()
    {
        if(_forge?.RulesCalculationSlow!=true)return;
        float width=Math.Min(440,Screen.width-20);
        GUI.Box(new Rect((Screen.width-width)/2,12,width,32),"Still calculating this turn… ("+(int)_forge.RulesWaitSeconds+"s)");
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
            _shell?.Poll();
            var papa = UnityEngine.Object.FindFirstObjectByType<PAPA>();
            var clientRequest=Path.Combine(_root,"start-client.request");
            if(File.Exists(clientRequest))
            {
                File.Delete(clientRequest);
                if(papa?.CardDatabase==null)throw new InvalidOperationException("Prepare native assets before opening the client.");
                if(_shell==null)_shell=new NativeClientShell(_root,papa,value=>{_events.Add(value);if(_events.Count>20)_events.RemoveAt(0);},this,()=>StartBoard(papa),()=>EndClientMatch(papa));
                _shell.Open();_phase="native-local-client";
            }
            if(!_cardAssetProbeRunning && papa?.CardDatabase!=null && File.Exists(Path.Combine(_root,"card-assets.request.json")))
            {
                _cardAssetProbeRunning=true;
                StartCoroutine(NativeCardAssetProbe.Run(_root,papa,()=>_cardAssetProbeRunning=false));
            }
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
            if(game!=null && papa!=null && _forge?.IsCommanderPod==true)NativeCommanderPodView.Ensure(game,papa,()=>{if(_forge?.IsCommanderPod==true)_shell?.ShowPodDetails(_forge.PodDetails());});
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
                  var orderCardIds=(mulliganBrowser as Wotc.Mtga.DuelScene.Browsers.OrderCardsBrowser)?.GetCardViews().Select(v=>v.InstanceId).ToArray();
                  var damageRows=activeWorkflow?.GetType().GetMethod("GetOrderedDamageAssignments",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)?.Invoke(activeWorkflow,null) as IEnumerable<Wotc.Mtga.DuelScene.Interactions.AssignDamage.MtgDamageAssignment>;
                  var damageAssignments=damageRows?.Select(v=>new{instanceId=v.InstanceId,assignedDamage=v.AssignedDamage,lethalDamage=v.LethalDamage,isPlayer=v.IsPlayerInstance,isAttackQuarry=v.IsAttackQuarry}).ToArray();
                  var damageBrowser=activeWorkflow?.GetType().GetField("_assignDamageBrowser",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)?.GetValue(activeWorkflow) as Wotc.Mtga.DuelScene.Browsers.AssignDamageBrowser;
                  var damageToggle=damageBrowser?.GetType().GetField("_autoAssignLethalToggle",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)?.GetValue(damageBrowser) as UnityEngine.UI.Toggle;
                  var damageSpinners=damageBrowser?.GetType().GetField("_idToSpinnerMap",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)?.GetValue(damageBrowser) as Dictionary<uint,SpinnerAnimated>;
                  UnityEngine.UI.Button? SpinnerButton(SpinnerAnimated spinner,bool up)=>typeof(SpinnerAnimated).GetField(up?"_upButton":"_downButton",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)?.GetValue(spinner) as UnityEngine.UI.Button;
                  bool Available(UnityEngine.UI.Selectable? control)=>control!=null && control.gameObject.activeInHierarchy && control.IsInteractable();
                  var damageControls=new{autoAssign=damageToggle==null?null:new{value=damageToggle.isOn,enabled=Available(damageToggle)},spinners=damageSpinners?.Select(v=>new{instanceId=v.Key,value=v.Value.Value,increase=Available(SpinnerButton(v.Value,true)),decrease=Available(SpinnerButton(v.Value,false))}).ToArray()};
                  int? HandlerCount(string name)=>mulliganBrowser==null?null:(mulliganBrowser.GetType().GetField(name,System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)?.GetValue(mulliganBrowser) as Delegate)?.GetInvocationList().Length ?? 0;
                  bool? KeepTargetsCurrent()=>mulliganBrowser==null?null:(mulliganBrowser.GetType().GetField("KeepPressed",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)?.GetValue(mulliganBrowser) as Delegate)?.GetInvocationList().All(d=>ReferenceEquals(d.Target,activeWorkflow));
                  GreClient.Rules.BaseUserRequest? observedRequest=null;
                  for(var type=activeWorkflow?.GetType();type!=null;type=type.BaseType){var field=type.GetField("_request",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.DeclaredOnly);if(field!=null){observedRequest=field.GetValue(activeWorkflow) as GreClient.Rules.BaseUserRequest;break;}}
                var clickType=(bool?)action["primary"]==true?SimpleInteractionType.Primary:SimpleInteractionType.DoublePrimary;
                var views=UnityEngine.Object.FindObjectsByType<DuelScene_CDC>(FindObjectsSortMode.None);
                var hits=new List<RaycastResult>();
                var point=new Vector2((float?)action["x"]??0,(float?)action["y"]??0);
                if(EventSystem.current!=null && action["x"]!=null)EventSystem.current.RaycastAll(new PointerEventData(EventSystem.current){position=point},hits);
                  File.WriteAllText(Path.Combine(_root,"native-action-probe.json"),JsonConvert.SerializeObject(new{utc=DateTime.UtcNow,workflow=activeWorkflow?.GetType().Name,applied=activeWorkflow?.AppliedState.ToString(),nativeState=game?.CurrentGameState?.Id,orderCardIds,damageAssignments,damageControls,nativeRequest=observedRequest==null?null:new{type=observedRequest.GetType().Name,state=observedRequest.OriginalMessage.GameStateId,message=observedRequest.OriginalMessage.MsgId,submitListeners=observedRequest.OnSubmit?.GetInvocationList().Length ?? 0},uiButtons=uiButtonInfo,mulliganHandlers=new{browser=mulliganBrowser?.GetType().Name,keep=HandlerCount("KeepPressed"),mulligan=HandlerCount("MulliganPressed"),keepTargetsCurrent=KeepTargetsCurrent()},buttons=activeWorkflow?.Buttons?.WorkflowButtons.Select(b=>new{text=b.ButtonText.ToString(),tag=b.Tag.ToString(),enabled=b.Enabled}).ToArray(),screen=new{width=Screen.width,height=Screen.height},focused=Application.isFocused,inputModule=EventSystem.current?.currentInputModule?.GetType().FullName,
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
                  else if((string?)action["op"]=="damage_toggle" || (string?)action["op"]=="damage_spinner")
                  {
                      if(activeWorkflow?.GetType().Name!="AssignDamageWorkflow" || activeWorkflow.AppliedState!=InteractionAppliedState.Applied || game?.CurrentGameState?.Id!=(uint?)action["nativeState"] || damageBrowser==null)throw new NativeQaRejectedException("Native damage context changed; inspect again.");
                      if((string?)action["op"]=="damage_toggle")
                      {
                          if(!Available(damageToggle) || damageToggle!.isOn!=(bool?)action["expectedValue"])throw new NativeQaRejectedException("Original damage toggle changed or is unavailable.");
                          damageToggle.isOn=!damageToggle.isOn;
                      }
                      else
                      {
                          uint instance=(uint)action["instanceId"]!;
                          if(damageSpinners==null || !damageSpinners.TryGetValue(instance,out var spinner) || spinner.Value!=(int?)action["expectedValue"])throw new NativeQaRejectedException("Original damage spinner changed or is unavailable.");
                          string? direction=(string?)action["direction"];
                          if(direction!="increase" && direction!="decrease")throw new NativeQaRejectedException("Unknown spinner direction.");
                          var button=SpinnerButton(spinner,direction=="increase");
                          if(!Available(button))throw new NativeQaRejectedException("Original damage spinner button is disabled.");
                          button!.onClick.Invoke();
                      }
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
                forge = _forge == null ? null : new { session = _forge.Session, scenario = _forge.Scenario, gameOver = _forge.GameOver, decision = _forge.DecisionKind, landsPlayed = _forge.LandsPlayed, mana = _forge.ManaTotal, turn = _forge.Turn, phase = _forge.Phase, activeSeat = _forge.ActiveSeat, hand = _forge.HandCount, battlefield = _forge.BattlefieldCount, rulesWaitSeconds = _forge.RulesWaitSeconds, rulesCalculationSlow = _forge.RulesCalculationSlow, gap = _forge.Gap },
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
        var collationType=typeof(Wotc.Mtga.Wrapper.CollationMapping);
        string collationDigest;
        using(var algorithm=System.Security.Cryptography.SHA256.Create())
        using(var source=File.OpenRead(collationType.Assembly.Location))collationDigest=BitConverter.ToString(algorithm.ComputeHash(source)).Replace("-","").ToLowerInvariant();
        var collations=Enum.GetNames(collationType).Where(n=>System.Text.RegularExpressions.Regex.IsMatch(n,"^[A-Z][A-Z0-9]+$")).Select(n=>new{name=n,id=Convert.ToInt32(Enum.Parse(collationType,n))}).Where(v=>v.id>60000 && v.id<200000).ToDictionary(v=>v.name,v=>v.id);
        File.WriteAllText(Path.Combine(_root,"pack-collation-map.json"),JsonConvert.SerializeObject(new{schema=1,sourceAssemblySha256=collationDigest,mappings=collations},Formatting.Indented));
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
        // Multiplayer layout captures the local seat during scene initialization.
        HarmonyLib.AccessTools.Property(typeof(MatchManager),"LocalPlayerSeatId").SetValue(manager,1u,null);
        manager.LocalPlayerInfo.SeatId = 1;
        manager.LocalPlayerInfo.TeamId = 1;
        manager.OpponentInfo.SeatId = 2;
        manager.OpponentInfo.TeamId = 2;
        if(_forge?.Scenario=="brawl-duel" || _forge?.Scenario=="commander-duel" || _forge?.IsCommanderPod==true)
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
        if(_forge?.IsCommanderPod==true)
        {
            manager.LocalPlayerInfo.ScreenName=_forge.PlayerName(1);
            manager.OpponentInfo.ScreenName=_forge.PlayerName(2);
            for(int seat=3;seat<=_forge.PlayerCount;seat++)
                manager.Players.Add(new MatchManager.PlayerInfo(_forge.PlayerName(seat))
                {SeatId=(uint)seat,TeamId=(uint)seat,AvatarSelection=AvatarIdConstants.Sparky,Commanders=_forge.Commanders(seat)});
            _events.Add("Four-player Commander roster configured before native match scene load.");
        }
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
    private IEnumerator EndClientMatch(PAPA papa)
    {
        _phase="returning-local-client-home";
        _forge?.Detach();_forge=null;
        var manager=UnityEngine.Object.FindFirstObjectByType<MatchSceneManager>();
        if(manager!=null){manager.StopAllCoroutines();manager.enabled=false;}
        AudioManager.Instance?.UnLoadBattleField();
        var home=SceneManager.GetSceneByName("LocalClient");if(!home.IsValid())home=SceneManager.CreateScene("LocalClient");SceneManager.SetActiveScene(home);
        var scenes=Enumerable.Range(0,SceneManager.sceneCount).Select(i=>SceneManager.GetSceneAt(i)).Where(s=>s.isLoaded).ToArray();
        foreach(var scene in scenes.Where(s=>s.name!="MatchScene" && s.name!="AssetPrep" && s.name!="LocalClient"))yield return SceneManager.UnloadSceneAsync(scene);
        var match=SceneManager.GetSceneByName("MatchScene");if(match.IsValid() && match.isLoaded)yield return SceneManager.UnloadSceneAsync(match);
        papa.MatchManager.Reset();_connection=null;_gap=null;_phase="native-local-client";
    }
}
