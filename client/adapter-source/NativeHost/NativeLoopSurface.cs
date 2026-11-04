using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using AssetLookupTree.Payloads.Prefab;
using AssetLookupTree.Payloads.UI.DuelScene;
using Newtonsoft.Json.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;
using Wotc.Mtga.DuelScene;
using Wotc.Mtga.DuelScene.Interactions;
using Wotc.Mtga.Loc;

namespace ForgeArenaSandbox;

// The same prefab and controls used by Arena's NumericInputWorkflow.
internal sealed class NativeLoopSurface
{
    private readonly Func<JObject> _state;
    private readonly GameManager _game;
    private readonly Action<int> _run;
    private readonly Action _stop;
    private LoopPanelVisibility _visibility=new LoopPanelVisibility();
    private readonly GameObject _hud,_nativeHud;
    private readonly View_ChooseXInterface _selector;
    private readonly Button _submit;
    private readonly StyledButton _cancel,_launcher;
    private readonly TMP_Text _caption;
    private int _count=100;
    private bool _repeatEnabled,_stopEnabled,_playing,_expanded;
    private string? _error;
    private const BindingFlags Fields=BindingFlags.Instance|BindingFlags.NonPublic;
    internal NativeLoopSurface(Transform parent,Func<JObject> state,Action<int> run,Action stop)
    {
        _state=state;_run=run;_stop=stop;_game=parent.GetComponent<GameManager>();
        var papa=UnityEngine.Object.FindFirstObjectByType<PAPA>()??throw new InvalidOperationException("Arena UI is not ready.");
        _hud=new GameObject("Arena repeat controls",typeof(RectTransform),typeof(Canvas),typeof(CanvasScaler),typeof(GraphicRaycaster));_hud.transform.SetParent(parent,false);_hud.SetActive(false);
        try
        {
            var canvas=_hud.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;canvas.sortingOrder=31020;
            var scale=_hud.GetComponent<CanvasScaler>();scale.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scale.referenceResolution=new Vector2(1920,1080);scale.matchWidthOrHeight=.5f;
            _nativeHud=new GameObject("Native repeat X root",typeof(RectTransform));_nativeHud.transform.SetParent(_game.Context.Get<ICanvasRootProvider>().GetCanvasRoot(CanvasLayer.ScreenSpace_Default),false);
            var nativeRect=(RectTransform)_nativeHud.transform;nativeRect.anchorMin=Vector2.zero;nativeRect.anchorMax=Vector2.one;nativeRect.offsetMin=nativeRect.offsetMax=Vector2.zero;_nativeHud.SetActive(false);
            _selector=AssetLoader.Instantiate<View_ChooseXInterface>(papa.AssetLookupSystem.GetPrefabPath<ChooseXInterfacePrefab,View_ChooseXInterface>(),_nativeHud.transform);
            _selector.name="Repeat X selector";_selector.ValueModified+=Modify;_selector.Submit+=Repeat;_selector.SetButtonStyle(ButtonStyle.StyleType.Main);_selector.Open();
            _submit=(Button)typeof(View_ChooseXInterface).GetField("_confirmationButton",Fields)!.GetValue(_selector);
            var payload=papa.AssetLookupSystem.TreeLoader.LoadTree<DuelSceneButtonPrefabs>().GetPayload(papa.AssetLookupSystem.Blackboard);
            _cancel=AssetLoader.Instantiate<StyledButton>(payload.SecondaryButtonRef.RelativePath,_hud.transform);_cancel.name="Repeat Cancel";_cancel.Init(papa.AssetLookupSystem);
            _cancel.SetModel(new PromptButtonData{ButtonText="DuelScene/ClientPrompt/ClientPrompt_Button_Cancel",Style=ButtonStyle.StyleType.Secondary,ClearsInteractions=false,ButtonCallback=Cancel});
            Place((RectTransform)_cancel.transform,new Vector2(-340,126));
            _launcher=AssetLoader.Instantiate<StyledButton>(payload.SecondaryButtonRef.RelativePath,_hud.transform);_launcher.name="Repeat combo";_launcher.Init(papa.AssetLookupSystem);
            _launcher.SetModel(new PromptButtonData{ButtonText=new MTGALocalizedString(new RepeatLabel()){Key="Repeat combo"},Style=ButtonStyle.StyleType.Secondary,ClearsInteractions=false,ButtonCallback=Open});
            Place((RectTransform)_launcher.transform,new Vector2(-340,126));
            var caption=new GameObject("Repeat count label",typeof(RectTransform),typeof(TextMeshProUGUI));caption.transform.SetParent(_hud.transform,false);Place((RectTransform)caption.transform,new Vector2(-24,354));((RectTransform)caption.transform).sizeDelta=new Vector2(320,35);
            _caption=caption.GetComponent<TextMeshProUGUI>();_caption.font=_submit.GetComponentInChildren<TMP_Text>(true).font;_caption.fontSize=21;_caption.alignment=TextAlignmentOptions.Right;_caption.raycastTarget=false;
        }
        catch{if(_nativeHud!=null)UnityEngine.Object.Destroy(_nativeHud);UnityEngine.Object.Destroy(_hud);throw;}
    }
    private static void Place(RectTransform rect,Vector2 position){rect.anchorMin=rect.anchorMax=rect.pivot=new Vector2(1,0);rect.anchoredPosition=position;rect.localScale=Vector3.one;}
    private void Modify(int delta){if(_stopEnabled)return;_count=Math.Max(1,Math.Min(1000,_count+delta));_error=null;Refresh(_playing);}
    internal void SetCount(string value)
    {
        if(!int.TryParse(value,NumberStyles.None,CultureInfo.InvariantCulture,out int count) || count<1 || count>1000)throw new ArgumentOutOfRangeException(nameof(value),"Choose 1 to 1000 repetitions.");
        if(_stopEnabled)throw new InvalidOperationException("Cancel the current batch before changing its count.");_count=count;Refresh(_playing);
    }
    internal void Open(){_visibility.Open();Refresh(_playing);}
    internal void Close(){if(_stopEnabled)return;_visibility.Close();Refresh(_playing);}
    private void Cancel(){if(_stopEnabled)Stop();else Close();}
    internal void Repeat()
    {
        if(!_repeatEnabled || _stopEnabled)return;
        try{_run(_count);_error=null;}
        catch(Exception e) when(e is InvalidOperationException || e is ArgumentOutOfRangeException){_error=e.Message;}
        Refresh(_playing);
    }
    internal void Stop(){if(_stopEnabled)_stop();_error=null;_visibility.Close();Refresh(_playing);}
    internal void Reset(){_visibility=new LoopPanelVisibility();_error=null;}
    internal void Refresh(bool playing)
    {
        _playing=playing;var state=_state();bool fast=(bool?)state["fastResolving"]==true;bool running=(bool)state["running"]! || fast;_visibility.Observe(running,(int)state["requested"]!);
        _repeatEnabled=(bool)state["available"]! && !running;_stopEnabled=running;
        var workflow=_game.WorkflowController.CurrentWorkflow;
        bool nativeNumberChoice=workflow is NumericInputWorkflow || workflow is IParentWorkflow parent && parent.ChildWorkflows.Any(w=>w is NumericInputWorkflow);
        _expanded=playing && (bool)state["visible"]! && !_visibility.Collapsed && !running && !nativeNumberChoice;
        bool launcher=playing && _visibility.Collapsed && _repeatEnabled && !nativeNumberChoice;
        _hud.SetActive(_expanded || launcher || playing && running);_nativeHud.SetActive(_expanded);_cancel.gameObject.SetActive(_expanded || playing && running);_launcher.gameObject.SetActive(launcher);_caption.gameObject.SetActive(_expanded || playing && running);
        _selector.SetButtonText("X = "+_count.ToString(CultureInfo.InvariantCulture));
        var flags=NumericInputVisualState.None;
        if(!running && _count<1000)flags|=NumericInputVisualState.IncrementEnabled|NumericInputVisualState.IncrementManyEnabled;
        if(!running && _count>1)flags|=NumericInputVisualState.DecrementEnabled|NumericInputVisualState.DecrementManyEnabled;
        if(_repeatEnabled)flags|=NumericInputVisualState.CanSubmit;
        _selector.SetVisualState(flags);_submit.interactable=_repeatEnabled;
        _caption.text=_error??(fast?"Resolving stack: "+state["remainingStack"]:running?"Repeating "+state["completed"]+" / "+state["requested"]:"Repeat combo");
    }
    internal JObject Snapshot()=>new JObject{["count"]=_count.ToString(CultureInfo.InvariantCulture),["visible"]=_expanded,["collapsed"]=_visibility.Collapsed,["launcherVisible"]=_launcher.gameObject.activeInHierarchy,["repeatEnabled"]=_repeatEnabled,["stopEnabled"]=_stopEnabled,["cancelVisible"]=_cancel.gameObject.activeInHierarchy,["error"]=_error,["nativeSelector"]=_selector.GetType().Name,["cancelStyle"]=_cancel.Style.ToString(),["loop"]=_state()};
    internal void Dispose(){if(_selector!=null){_selector.Submit-=Repeat;_selector.ValueModified-=Modify;}if(_nativeHud!=null)UnityEngine.Object.Destroy(_nativeHud);if(_hud!=null)UnityEngine.Object.Destroy(_hud);}
    private sealed class RepeatLabel:IClientLocProvider
    {
        public string GetLocalizedText(string key,params (string,string)[] args)=>key;
        public string GetLocalizedTextForLanguage(string key,string language,params (string,string)[] args)=>key;
        public bool TryGetLocalizedTextForLanguage(string key,string language,(string,string)[] args,out string value){value=key;return true;}
        public bool DoesContainTranslation(string key)=>key=="Repeat combo";
        public bool IsDisposed()=>false;
        public IEnumerable<string> GetKeys()=>new[]{"Repeat combo"};
        public void OpenConnection(){}
        public void CloseConnection(){}
    }
}
