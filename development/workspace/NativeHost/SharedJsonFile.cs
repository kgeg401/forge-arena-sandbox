using System;
using System.IO;
using System.Diagnostics;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

// The rules owner atomically replaces this file. Reparse only a changed version.
internal sealed class SharedJsonFile
{
    private readonly FileInfo _file;
    private DateTime _stamp;
    private long _length=-1;
    private JObject? _value;
    private readonly Stopwatch _blocked=new Stopwatch();
    internal long Reads { get; private set; }
    internal long Hits { get; private set; }
    internal long Retries { get; private set; }
    internal SharedJsonFile(string path)=>_file=new FileInfo(path);
    internal static bool TransientRead(Exception error)
    {
        if(error is UnauthorizedAccessException)return true;
        if(!(error is IOException))return false;
        foreach(int code in new[]{32,33,1224})
            if((error.HResult&0xffff)==code || error.Message.StartsWith("Win32 IO returned "+code+".",StringComparison.Ordinal))return true;
        return false;
    }
    internal JObject? Read()
    {
        try{var value=ReadCurrent();_blocked.Reset();return value;}
        catch(Exception error) when(TransientRead(error))
        {
            Retries++;
            if(!_blocked.IsRunning)_blocked.Start();
            if(_blocked.Elapsed.TotalSeconds>=1)throw;
            return null;
        }
    }
    private JObject? ReadCurrent()
    {
        _file.Refresh();
        if(!_file.Exists){_value=null;_length=-1;return null;}
        var stamp=_file.LastWriteTimeUtc;long length=_file.Length;
        if(_value!=null && stamp==_stamp && length==_length){Hits++;return _value;}
        using var stream=new FileStream(_file.FullName,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete);
        using var reader=new StreamReader(stream);
        var value=JObject.Parse(reader.ReadToEnd());
        _value=value;_stamp=stamp;_length=length;Reads++;return value;
    }
}
