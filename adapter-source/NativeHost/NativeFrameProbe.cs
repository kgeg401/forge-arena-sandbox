using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace ForgeArenaSandbox;

// Explicit bounded local observation. No input, rules or timing changes.
internal sealed class NativeFrameProbe
{
    private readonly List<double> _frames=new List<double>();
    private float _nextPoll,_end;
    private string? _id;
    private TimeSpan _cpu;
    private int _gc;

    internal void Tick(string root)
    {
        float now=Time.realtimeSinceStartup;
        if(_id!=null)
        {
            _frames.Add(Time.unscaledDeltaTime*1000d);
            if(now>=_end)
            {
                var sorted=_frames.OrderBy(v=>v).ToArray();
                double Pick(double p)=>sorted[Math.Min(sorted.Length-1,(int)(sorted.Length*p))];
                var result=new {
                    requestId=_id,utc=DateTime.UtcNow,frames=sorted.Length,
                    meanFrameMs=_frames.Average(),medianFrameMs=Pick(.5),
                    p95FrameMs=Pick(.95),p99FrameMs=Pick(.99),
                    cpuMs=(Process.GetCurrentProcess().TotalProcessorTime-_cpu).TotalMilliseconds,
                    gc0=GC.CollectionCount(0)-_gc,screen=new{Screen.width,Screen.height},
                    focused=Application.isFocused,pod=NativeCommanderPodView.Active?.Snapshot()
                };
                File.WriteAllText(Path.Combine(root,"frame-probe.json"),JsonConvert.SerializeObject(result,Formatting.Indented));
                _id=null;_frames.Clear();
            }
            return;
        }
        if(now<_nextPoll)return;
        _nextPoll=now+1;
        var path=Path.Combine(root,"frame-probe.request.json");
        if(!File.Exists(path))return;
        var request=JObject.Parse(File.ReadAllText(path));File.Delete(path);
        float seconds=(float?)request["seconds"]??20;
        if(float.IsNaN(seconds)||float.IsInfinity(seconds)||seconds<1||seconds>30)
            throw new InvalidDataException("Frame probe duration must be 1 to 30 seconds");
        _id=(string?)request["requestId"]??Guid.NewGuid().ToString();
        _end=now+seconds;_cpu=Process.GetCurrentProcess().TotalProcessorTime;_gc=GC.CollectionCount(0);
    }
}
