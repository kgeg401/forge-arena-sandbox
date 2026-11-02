using System;
using System.IO;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

// The rules owner atomically replaces this file. Reparse only a changed version.
internal sealed class SharedJsonFile
{
    private readonly FileInfo _file;
    private DateTime _stamp;
    private long _length=-1;
    private JObject? _value;
    internal long Reads { get; private set; }
    internal long Hits { get; private set; }
    internal SharedJsonFile(string path)=>_file=new FileInfo(path);
    internal JObject? Read()
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
