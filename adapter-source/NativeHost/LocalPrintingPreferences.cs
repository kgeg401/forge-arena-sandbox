using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

// Only local preferences; this never changes a deck or the source inventory.
internal sealed class LocalPrintingPreferences
{
    private readonly string _path;
    private readonly IReadOnlyDictionary<uint,uint> _titles;
    private Dictionary<uint,uint> _values=new Dictionary<uint,uint>();
    public LocalPrintingPreferences(string path,IReadOnlyDictionary<uint,uint> titles)
    {
        _path=path;_titles=titles;
        if(!File.Exists(path))return;
        var source=JObject.Parse(File.ReadAllText(path));
        if((int?)source["schema"]!=1 || !(source["printings"] is JObject entries))throw new InvalidDataException("Invalid local printing preferences; original file preserved.");
        foreach(var entry in entries.Properties())
        {
            if(!uint.TryParse(entry.Name,out var title) || entry.Value.Type!=JTokenType.Integer || !uint.TryParse(entry.Value.ToString(),out var printing) || !_titles.TryGetValue(printing,out var actual) || actual!=title)throw new InvalidDataException("Unknown preferred printing; original file preserved.");
            _values.Add(title,printing);
        }
    }
    public IReadOnlyDictionary<uint,uint> Values=>new Dictionary<uint,uint>(_values);
    public uint? Get(uint title)=>_values.TryGetValue(title,out var id)?id:(uint?)null;
    public void Set(uint title,uint? printing)
    {
        if(printing is uint id && (!_titles.TryGetValue(id,out var actual) || actual!=title))throw new InvalidDataException("Preferred printing must belong to the selected card title.");
        if(Get(title)==printing)return;
        var next=new Dictionary<uint,uint>(_values);if(printing is uint value)next[title]=value;else next.Remove(title);
        var entries=new JObject();foreach(var pair in next.OrderBy(p=>p.Key))entries[pair.Key.ToString()]=pair.Value;
        LocalDeckLibrary.SaveJsonAtomically(_path,new JObject{["schema"]=1,["printings"]=entries}.ToString());_values=next;
    }
}
