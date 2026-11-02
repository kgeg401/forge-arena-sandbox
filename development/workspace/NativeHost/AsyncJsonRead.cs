using System;
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
    internal AsyncJsonRead(Func<string,JObject> load)=>_load=load;

    internal bool TryRead(string path,out JObject value)
    {
        value=null!;
        if(_path!=path)
        {
            Forget();_path=path;
            _read=Task.Run(()=>_load(path));
        }
        if(!_read!.IsCompleted)return false;
        value=_read.GetAwaiter().GetResult();return true;
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
