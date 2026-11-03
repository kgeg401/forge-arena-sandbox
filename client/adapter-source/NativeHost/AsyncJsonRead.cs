using System;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

// Only immutable request-response files belong here. The Unity thread owns
// selection, validation and adoption; a worker only reads/parses JSON bytes.
internal sealed class AsyncJsonRead
{
    private readonly Func<string,JObject> _load;
    private string? _path;
    private Task<JObject>? _read;
    private int _retries;
    internal int Retries=>Volatile.Read(ref _retries);
    internal AsyncJsonRead(Func<string,JObject> load)=>_load=load;

    internal bool TryRead(string path,out JObject value)
    {
        value=null!;
        if(_path!=path)
        {
            Forget();_path=path;
            _read=Task.Run(()=>Load(path));
        }
        if(!_read!.IsCompleted)return false;
        value=_read.GetAwaiter().GetResult();return true;
    }

    private JObject Load(string path)
    {
        var retry=Stopwatch.StartNew();
        while(true)
        {
            try{return _load(path);}
            catch(Exception error) when(SharedJsonFile.TransientRead(error) && retry.Elapsed.TotalSeconds<1)
            {
                // Only the worker waits; the exact response and input remain pending.
                Interlocked.Increment(ref _retries);
                Thread.Sleep(20);
            }
        }
    }

    internal void Forget()
    {
        // An obsolete read cannot publish into a newer request. Observe its
        // failure even if a choice or match exit has retired that response.
        var old=_read;_read=null;_path=null;
        if(old==null)return;
        if(old.IsCompleted){if(old.IsFaulted)_=old.Exception;return;}
        _=old.ContinueWith(task=>{_=task.Exception;},CancellationToken.None,
            TaskContinuationOptions.OnlyOnFaulted|TaskContinuationOptions.ExecuteSynchronously,TaskScheduler.Default);
    }
}
