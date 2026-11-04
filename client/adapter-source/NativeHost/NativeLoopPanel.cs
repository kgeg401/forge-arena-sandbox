using Newtonsoft.Json.Linq;
using UnityEngine;
using GameStage=Wotc.Mtgo.Gre.External.Messaging.GameStage;

namespace ForgeArenaSandbox;

internal sealed class NativeLoopPanel:MonoBehaviour
{
    internal static NativeLoopPanel? Active;
    private ForgeLandBridge _bridge=null!;
    private GameManager _game=null!;
    private NativeLoopSurface _surface=null!;
    private float _next;
    internal static void Ensure(GameManager game,ForgeLandBridge bridge)
    {
        var view=game.GetComponent<NativeLoopPanel>();
        if(view!=null){if(!ReferenceEquals(view._bridge,bridge)){view._bridge=bridge;view._surface.Reset();}Active=view;return;}
        view=game.gameObject.AddComponent<NativeLoopPanel>();view._game=game;view._bridge=bridge;
        try{view._surface=new NativeLoopSurface(game.transform,()=>view._bridge.LoopStatus,count=>view._bridge.StartLoop(count),()=>view._bridge.StopLoop());Active=view;}
        catch{Destroy(view);throw;}
    }
    internal void SetCount(string count)=>_surface.SetCount(count);
    internal void Repeat()=>_surface.Repeat();
    internal void Stop()=>_surface.Stop();
    internal void Open()=>_surface.Open();
    internal void Close()=>_surface.Close();
    internal JObject Snapshot()=>_surface.Snapshot();
    private void Update()
    {
        if(_surface==null)return;
        if(Time.unscaledTime<_next)return;_next=Time.unscaledTime+.12f;_surface.Refresh(_game.CurrentGameState?.GameInfo?.Stage==GameStage.Play);
    }
    private void OnDestroy(){if(Active==this)Active=null;_surface?.Dispose();}
}
