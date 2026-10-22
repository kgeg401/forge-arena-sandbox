using Pooling;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.Rendering.Universal;
using Wizards.Mtga;
using Wizards.Mtga.Assets;
using Wotc.Mtga;
using Wotc.Mtga.Loc;
using AssetLookupTree.Payloads.Prefab;
using Core.Code.AssetLookupTree.AssetLookup;
using UnityEngine.EventSystems;
using HarmonyLib;
using Wotc.Mtga.CustomInput;

namespace ForgeArenaSandbox;

// Camera/canvas values recovered from the owned MainNavigation scene.
internal sealed class NativeMenuSurface
{
    public readonly Transform Root;
    public readonly ICardRolloverZoom Zoom;
    public readonly GameObject Lifetime;
    public readonly Camera Camera;
    private readonly EventSystem _input;
    public void SetVisible(bool visible)
    {
        // Match scenes own their EventSystem and destroy it on unload. Keep the
        // menu's native input module with its persistent presentation instead.
        if(visible)foreach(var input in Object.FindObjectsByType<EventSystem>(FindObjectsSortMode.None))if(input!=_input)input.enabled=false;
        Lifetime.SetActive(visible);
        if(visible){_input.enabled=true;EventSystem.current=_input;_input.SetSelectedGameObject(null);}
    }
    public void ClearTransientPresentation(){Zoom.Close();}
    public NativeMenuSurface(PAPA papa)
    {
        foreach(var startup in Object.FindObjectsByType<Canvas>(FindObjectsSortMode.None))startup.gameObject.SetActive(false);
        Lifetime=new GameObject("Forge Arena persistent menu");
        Object.DontDestroyOnLoad(Lifetime);
        foreach(var input in Object.FindObjectsByType<EventSystem>(FindObjectsSortMode.None))input.enabled=false;
        var inputObject=new GameObject("Persistent native menu input",typeof(EventSystem),typeof(CustomUIInputModule));
        inputObject.transform.SetParent(Lifetime.transform,false);_input=inputObject.GetComponent<EventSystem>();EventSystem.current=_input;
        var previous=UnityEngine.Camera.main;
        var camera=new GameObject("Local native menu camera").AddComponent<Camera>();
        if(previous!=null){camera.CopyFrom(previous);previous.gameObject.SetActive(false);}
        // Camera.CopyFrom does not copy the URP extension. Keep the installed
        // renderer/depth configuration when giving the menu its own lifetime.
        var cameraData=camera.GetUniversalAdditionalCameraData();
        if(previous!=null)
        {
            var original=previous.GetUniversalAdditionalCameraData();
            cameraData.SetRenderer((int)AccessTools.Field(typeof(UniversalAdditionalCameraData),"m_RendererIndex").GetValue(original));
            cameraData.requiresDepthTexture=original.requiresDepthTexture;cameraData.requiresColorTexture=original.requiresColorTexture;
            cameraData.renderPostProcessing=original.renderPostProcessing;cameraData.antialiasing=original.antialiasing;cameraData.antialiasingQuality=original.antialiasingQuality;
        }
        camera.gameObject.tag="MainCamera";camera.transform.SetParent(Lifetime.transform,false);Camera=camera;
        camera.transform.position=Vector3.zero;camera.transform.rotation=Quaternion.identity;
        camera.orthographic=true;camera.orthographicSize=5;camera.nearClipPlane=-50;camera.farClipPlane=180;camera.cullingMask=12648481;camera.depth=50;
        var main=new GameObject("Local native menu light").AddComponent<Light>();main.type=LightType.Directional;main.intensity=.75f;main.transform.rotation=Quaternion.Euler(30,330,0);
        var fill=new GameObject("Local native menu fill").AddComponent<Light>();fill.type=LightType.Directional;fill.intensity=.5f;fill.transform.rotation=Quaternion.Euler(345,15,0);
        main.transform.SetParent(Lifetime.transform,false);fill.transform.SetParent(Lifetime.transform,false);
        if(camera.GetComponent<CurrentCamera>()==null)camera.gameObject.AddComponent<CurrentCamera>();
        // Card art is a 3D CDC with colliders, while toolbar/list controls use UI
        // graphics. Both native input paths must reach the same EventSystem.
        if(camera.GetComponent<PhysicsRaycaster>()==null)camera.gameObject.AddComponent<PhysicsRaycaster>();
        Root=Canvas("Local deck screen canvas",camera,95).transform;
        Root.SetParent(Lifetime.transform,false);
        var popup=new GameObject("Local native deck popup camera").AddComponent<Camera>();popup.CopyFrom(camera);
        popup.transform.position=new Vector3(0,0,-240);popup.cullingMask=281083937;popup.depth=51;popup.clearFlags=CameraClearFlags.Depth;
        camera.GetUniversalAdditionalCameraData().renderType=CameraRenderType.Base;
        var popupData=popup.GetUniversalAdditionalCameraData();popupData.renderType=CameraRenderType.Overlay;
        // This persistent surface shares nested native canvases across screens.
        // Retain their stencil between the base and rollover cameras; clearing
        // it here hides every masked row in the original deck-list prefab.
        AccessTools.Field(typeof(UniversalAdditionalCameraData),"m_ClearDepth").SetValue(popupData,false);
        camera.GetUniversalAdditionalCameraData().cameraStack.Add(popup);
        var zoomCanvas=Canvas("Local native deck popup canvas",popup,40);
        popup.transform.SetParent(Lifetime.transform,true);zoomCanvas.transform.SetParent(Lifetime.transform,false);
        var path=papa.AssetLookupSystem.GetPrefabPath<CardRolloverZoomPrefab,GameObject>();
        var obj=AssetLoader.Instantiate(path,zoomCanvas.transform);
        var view=obj.GetComponentInChildren<View_CardRolloverZoom>(true);
        view.Initialize(papa.CardViewBuilder,papa.CardDatabase,Languages.ActiveLocProvider,papa.UnityPool,Pantry.Get<IObjectPool>(),papa.KeyBoardManager,null!);
        Zoom=new CardRolloverZoomDelegator(view,null!);
        Zoom.Close();
    }
    private static Canvas Canvas(string name,Camera camera,float plane)
    {
        var obj=new GameObject(name,typeof(RectTransform),typeof(Canvas),typeof(CanvasScaler),typeof(GraphicRaycaster));
        var canvas=obj.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceCamera;canvas.worldCamera=camera;canvas.planeDistance=plane;
        var scaler=obj.GetComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scaler.referenceResolution=new Vector2(1920,1080);scaler.matchWidthOrHeight=.5f;
        return canvas;
    }
}
