using System;
using System.IO;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace ForgeArenaSandbox;

// Observe the actual display after the native Graphics controls finish changing
// it. Debounce transitions; never write per frame or capture an exit/minimize size.
internal sealed class NativeDisplayProfile
{
    private readonly string _path;
    private string? _pending;
    private string? _saved;
    private float _changedAt;
    public NativeDisplayProfile(string root)
    {
        _path=Path.Combine(root,"local-profile","display.json");
        if(File.Exists(_path))_saved=File.ReadAllText(_path);
    }
    private static string? Snapshot()
    {
        int width=Screen.width,height=Screen.height,mode=(int)Screen.fullScreenMode;
        if(width<640 || height<360 || width>16384 || height>16384 || (mode!=0 && mode!=1 && mode!=3))return null;
        return new JObject{["schema"]=1,["width"]=width,["height"]=height,["fullScreenMode"]=mode}.ToString();
    }
    public void Poll()
    {
        var value=Snapshot();if(value==null)return;
        if(value!=_pending){_pending=value;_changedAt=Time.realtimeSinceStartup;return;}
        if(value!=_saved && Time.realtimeSinceStartup-_changedAt>=1){_changedAt=Time.realtimeSinceStartup;Save(value);}
    }
    public void Flush(){var value=Snapshot();if(value!=null && value!=_saved)Save(value);}
    private void Save(string value){LocalDeckLibrary.SaveJsonAtomically(_path,value);_saved=value;}
}
