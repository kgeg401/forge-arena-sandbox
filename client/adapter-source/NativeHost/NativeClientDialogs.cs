using System;
using System.Collections.Generic;
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
    public NativeClientDialogs(PAPA papa)
    {
        _papa=papa;
        var obj=new GameObject("Local client notices",typeof(RectTransform),typeof(Canvas),typeof(CanvasScaler),typeof(GraphicRaycaster));
        UnityEngine.Object.DontDestroyOnLoad(obj);_root=obj.transform;
        var canvas=obj.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;canvas.sortingOrder=32760;
        var scaler=obj.GetComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scaler.referenceResolution=new Vector2(1920,1080);scaler.matchWidthOrHeight=.5f;
    }
    public bool IsOpen=>_view!=null && _view.IsOpen;
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
