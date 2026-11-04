using System;
using System.Collections.Generic;
using System.Linq;
using TMPro;
using HarmonyLib;
using UnityEngine;
using UnityEngine.UI;
using AssetLookupTree.Payloads.Prefab;
using Core.Code.AssetLookupTree.AssetLookup;
using Core.Code.Input;
using Wizards.Mtga;
using Wizards.Mtga.Assets;

namespace ForgeArenaSandbox;

// Original message view and buttons, above either the menu or match camera.
internal sealed class NativeClientDialogs
{
    private readonly PAPA _papa;
    private readonly Transform _root;
    private SystemMessageView? _view;
    private GameObject? _loading;
    private TMP_InputField? _input;
    public NativeClientDialogs(PAPA papa)
    {
        _papa=papa;
        var obj=new GameObject("Local client notices",typeof(RectTransform),typeof(Canvas),typeof(CanvasScaler),typeof(GraphicRaycaster));
        UnityEngine.Object.DontDestroyOnLoad(obj);_root=obj.transform;
        var canvas=obj.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;canvas.sortingOrder=32760;
        var scaler=obj.GetComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scaler.referenceResolution=new Vector2(1920,1080);scaler.matchWidthOrHeight=.5f;
    }
    public bool IsOpen=>_view!=null && _view.IsOpen;
    public void DismissMatchFailure()
    {
        if(IsOpen && ((TMP_Text)AccessTools.Field(typeof(SystemMessageView),"_titleText").GetValue(_view)).text=="Local match display stopped")_view!.Hide();
    }
    public bool NameInputFocused=>_input!=null && _input.isFocused;
    private IEnumerable<SystemMessageButtonView> ActiveButtons()
    {
        if(!IsOpen)return Array.Empty<SystemMessageButtonView>();
        // The original view retires old controls with end-of-frame Destroy.
        var buttons=(IEnumerable<SystemMessageButtonView>)AccessTools.Field(typeof(SystemMessageView),"_buttons").GetValue(_view);
        return buttons.Where(b=>b.gameObject.activeInHierarchy && ((CustomButton)AccessTools.Field(typeof(SystemMessageButtonView),"_button").GetValue(b)).Interactable);
    }
    public string[] Buttons()=>ActiveButtons().Select(b=>b.GetComponentsInChildren<TMP_Text>(true)[0].text).ToArray();
    public void Click(string label)
    {
        if(!IsOpen)throw new InvalidOperationException("No original client dialog is open.");
        ActiveButtons().Single(b=>b.GetComponentsInChildren<TMP_Text>(true)[0].text==label).Click();
    }
    public void SetInput(string text)
    {
        if(!IsOpen || _input==null)throw new InvalidOperationException("No original profile input is open.");
        _input.text=text;
    }
    public void ShowLoading(string message)
    {
        if(_loading==null)
        {
            _loading=AssetLoader.Instantiate(_papa.AssetLookupSystem.GetPrefabPath<LoadingPanelPrefab,GameObject>(),_root);
            var rect=(RectTransform)_loading.transform;rect.anchorMin=Vector2.zero;rect.anchorMax=Vector2.one;rect.offsetMin=rect.offsetMax=Vector2.zero;
            foreach(var canvas in _loading.GetComponentsInChildren<Canvas>(true))canvas.overrideSorting=false;
        }
        foreach(var text in _loading.GetComponentsInChildren<TMPro.TMP_Text>(true)){foreach(var loc in text.GetComponents<Wotc.Mtga.Loc.Localize>())loc.enabled=false;text.text=message;}
        _loading.SetActive(true);
    }
    public void HideLoading(){_loading?.SetActive(false);}
    private void EnsureView()
    {
        if(_view==null)
        {
            // The original notice is a complete overlay canvas. Nesting it in
            // the loading canvas scales it twice and offsets its message band.
            var prefab=Resources.Load<GameObject>("SystemMessageView_Desktop_16x9");
            if(prefab==null)throw new InvalidOperationException("The installed native message prefab is unavailable.");
            var root=UnityEngine.Object.Instantiate(prefab);UnityEngine.Object.DontDestroyOnLoad(root);
            foreach(var canvas in root.GetComponentsInChildren<Canvas>(true))if(canvas.renderMode==RenderMode.ScreenSpaceOverlay)canvas.sortingOrder=32760;
            _view=root.GetComponentInChildren<SystemMessageView>(true);
            AccessTools.Method(typeof(SystemMessageView),"Initialize").Invoke(_view,new object?[]{_papa.KeyBoardManager,Pantry.Get<IActionSystem>(),null,null});
        }
    }
    public void Input(string title,string initial,TMP_InputField template,Action<string> save,Action cancel)
    {
        EnsureView();if(_input!=null)UnityEngine.Object.Destroy(_input.gameObject);
        _view!.SetTitle(title);_view.SetMessage("Your profiles share decks, packs and collection. Choose a name for this identity.");_view.SetDetails("");
        _input=UnityEngine.Object.Instantiate(template,_view.transform);_input.name="Local profile name";
        for(int i=0;i<_input.onEndEdit.GetPersistentEventCount();i++)_input.onEndEdit.SetPersistentListenerState(i,UnityEngine.Events.UnityEventCallState.Off);
        for(int i=0;i<_input.onValueChanged.GetPersistentEventCount();i++)_input.onValueChanged.SetPersistentListenerState(i,UnityEngine.Events.UnityEventCallState.Off);
        _input.onEndEdit.RemoveAllListeners();_input.onValueChanged.RemoveAllListeners();_input.characterLimit=32;_input.textComponent.richText=false;_input.text=initial;_input.interactable=true;
        var rect=(RectTransform)_input.transform;rect.anchorMin=rect.anchorMax=new Vector2(.5f,.535f);rect.pivot=new Vector2(.5f,.5f);rect.anchoredPosition=Vector2.zero;rect.sizeDelta=new Vector2(600,40);rect.localScale=Vector3.one;_input.gameObject.SetActive(true);
        void Finish(bool accepted){string value=_input!.text;UnityEngine.Object.Destroy(_input.gameObject);_input=null;if(accepted)save(value);else cancel();}
        _view.CreateButtons(new List<SystemMessageManager.SystemMessageButtonData>{new SystemMessageManager.SystemMessageButtonData{Text="Cancel",IsCancel=true,HideOnClick=true,Callback=()=>Finish(false)},new SystemMessageManager.SystemMessageButtonData{Text="Save",IsConfirm=true,HideOnClick=true,Callback=()=>Finish(true)}});
        _view.Show();_input.Select();_input.ActivateInputField();
    }
    public void Show(string title,string message,string button="OK",Action? action=null)
    {
        EnsureView();_view!.SetTitle(title);_view.SetMessage(message);_view.SetDetails("");
        _view.CreateButtons(new List<SystemMessageManager.SystemMessageButtonData>{new SystemMessageManager.SystemMessageButtonData{Text=button,IsConfirm=true,IsCancel=true,HideOnClick=true,Callback=action}});
        _view.Show();
    }
    public void Confirm(string title,string message,string confirm,Action action)
    {
        EnsureView();_view!.SetTitle(title);_view.SetMessage(message);_view.SetDetails("");
        _view.CreateButtons(new List<SystemMessageManager.SystemMessageButtonData>{
            new SystemMessageManager.SystemMessageButtonData{Text="Cancel",IsCancel=true,HideOnClick=true},
            new SystemMessageManager.SystemMessageButtonData{Text=confirm,IsConfirm=true,HideOnClick=true,Callback=action}});
        _view.Show();
    }
    public void Choose(string title,string message,IReadOnlyList<(string Text,Action Action)> options)
    {
        EnsureView();_view!.SetTitle(title);_view.SetMessage(message);_view.SetDetails("");
        var buttons=new List<SystemMessageManager.SystemMessageButtonData>();
        for(int i=0;i<options.Count;i++)buttons.Add(new SystemMessageManager.SystemMessageButtonData{Text=options[i].Text,IsCancel=i==options.Count-1,HideOnClick=true,Callback=options[i].Action});
        _view.CreateButtons(buttons);_view.Show();
    }
    public void ShowPages(string title,IReadOnlyList<string> pages,int page=0)
    {
        if(pages.Count==0)throw new ArgumentException("No detail pages supplied.");
        EnsureView();_view!.SetTitle(title+" ("+(page+1)+"/"+pages.Count+")");_view.SetMessage(pages[page]);_view.SetDetails("");
        var buttons=new List<SystemMessageManager.SystemMessageButtonData>();
        if(pages.Count>1){
            buttons.Add(new SystemMessageManager.SystemMessageButtonData{Text="Previous player",HideOnClick=false,Callback=()=>ShowPages(title,pages,(page+pages.Count-1)%pages.Count)});
            buttons.Add(new SystemMessageManager.SystemMessageButtonData{Text="Next player",HideOnClick=false,Callback=()=>ShowPages(title,pages,(page+1)%pages.Count)});
        }
        buttons.Add(new SystemMessageManager.SystemMessageButtonData{Text="Close",IsCancel=true,HideOnClick=true});
        _view.CreateButtons(buttons);_view.Show();
    }
    public void Choose(string title,string message,string first,Action firstAction,string second,Action secondAction)
    {
        EnsureView();_view!.SetTitle(title);_view.SetMessage(message);_view.SetDetails("");
        _view.CreateButtons(new List<SystemMessageManager.SystemMessageButtonData>{
            new SystemMessageManager.SystemMessageButtonData{Text=first,IsCancel=true,HideOnClick=true,Callback=firstAction},
            new SystemMessageManager.SystemMessageButtonData{Text=second,IsConfirm=true,HideOnClick=true,Callback=secondAction}});
        _view.Show();
    }
}
