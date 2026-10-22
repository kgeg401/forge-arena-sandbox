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

namespace ForgeArenaSandbox;

// Camera/canvas values recovered from the owned MainNavigation scene.
internal sealed class NativeMenuSurface
{
    public readonly Transform Root;
    public readonly ICardRolloverZoom Zoom;
    public NativeMenuSurface(PAPA papa)
    {
        foreach(var startup in Object.FindObjectsByType<Canvas>(FindObjectsSortMode.None))startup.gameObject.SetActive(false);
        var camera=Camera.main;
        camera.transform.position=Vector3.zero;camera.transform.rotation=Quaternion.identity;
        camera.orthographic=true;camera.orthographicSize=5;camera.nearClipPlane=-50;camera.farClipPlane=180;camera.cullingMask=12648481;camera.depth=50;
        var main=new GameObject("Local native menu light").AddComponent<Light>();main.type=LightType.Directional;main.intensity=.75f;main.transform.rotation=Quaternion.Euler(30,330,0);
        var fill=new GameObject("Local native menu fill").AddComponent<Light>();fill.type=LightType.Directional;fill.intensity=.5f;fill.transform.rotation=Quaternion.Euler(345,15,0);
        if(camera.GetComponent<CurrentCamera>()==null)camera.gameObject.AddComponent<CurrentCamera>();
        // Card art is a 3D CDC with colliders, while toolbar/list controls use UI
        // graphics. Both native input paths must reach the same EventSystem.
        if(camera.GetComponent<PhysicsRaycaster>()==null)camera.gameObject.AddComponent<PhysicsRaycaster>();
        Root=Canvas("Local deck screen canvas",camera,95).transform;
        var popup=new GameObject("Local native deck popup camera").AddComponent<Camera>();popup.CopyFrom(camera);
        popup.transform.position=new Vector3(0,0,-240);popup.cullingMask=281083937;popup.depth=51;popup.clearFlags=CameraClearFlags.Depth;
        camera.GetUniversalAdditionalCameraData().renderType=CameraRenderType.Base;
        popup.GetUniversalAdditionalCameraData().renderType=CameraRenderType.Overlay;
        camera.GetUniversalAdditionalCameraData().cameraStack.Add(popup);
        var zoomCanvas=Canvas("Local native deck popup canvas",popup,40);
        var path=papa.AssetLookupSystem.GetPrefabPath<CardRolloverZoomPrefab,GameObject>();
        var obj=AssetLoader.Instantiate(path,zoomCanvas.transform);
        var view=obj.GetComponentInChildren<View_CardRolloverZoom>(true);
        view.Initialize(papa.CardViewBuilder,papa.CardDatabase,Languages.ActiveLocProvider,papa.UnityPool,Pantry.Get<IObjectPool>(),papa.KeyBoardManager,null!);
        Zoom=new CardRolloverZoomDelegator(view,null!);
    }
    private static Canvas Canvas(string name,Camera camera,float plane)
    {
        var obj=new GameObject(name,typeof(RectTransform),typeof(Canvas),typeof(CanvasScaler),typeof(GraphicRaycaster));
        var canvas=obj.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceCamera;canvas.worldCamera=camera;canvas.planeDistance=plane;
        var scaler=obj.GetComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scaler.referenceResolution=new Vector2(1920,1080);scaler.matchWidthOrHeight=.5f;
        return canvas;
    }
}
