using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.ComponentModel;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

// A single durable transaction contains the debit, collection gains and receipt.
// Presentation can be replayed; it never grants the reward a second time.
internal sealed class LocalPackProfile
{
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    private static extern bool MoveFileEx(string source,string destination,uint flags);
    private readonly string _path;
    private readonly JObject _catalog;
    private JObject _profile;
    private readonly Random _random = new Random();
    private readonly object _sync = new object();
    public LocalPackProfile(string path, string catalogPath)
    {
        _path=path; _catalog=JObject.Parse(File.ReadAllText(catalogPath));
        if ((int?)_catalog["schema"]!=1) throw new InvalidDataException("Unsupported local pack catalog.");
        if(File.Exists(path)) _profile=JObject.Parse(File.ReadAllText(path));
        else _profile=new JObject { ["schema"]=1,["profileId"]=Guid.NewGuid().ToString(),["revision"]=0,["packs"]=new JObject(),["cards"]=new JObject(),["openings"]=new JArray() };
        if((int?)_profile["schema"]!=1 || !(_profile["packs"] is JObject) || !(_profile["cards"] is JObject) || !(_profile["openings"] is JArray))throw new InvalidDataException("Invalid local pack profile; original file preserved.");
        bool changed=!File.Exists(path);
        foreach(var set in (JArray)_catalog["sets"]!) {string id=((int)set["collationId"]!).ToString(); if(_profile["packs"]![id]==null){_profile["packs"]![id]=(int)set["initialPacks"]!;changed=true;}}
        if(changed) Save(_profile);
    }
    public JArray Sets => (JArray)_catalog["sets"]!.DeepClone();
    public JObject Snapshot { get { lock(_sync) return (JObject)_profile.DeepClone(); } }
    private void Save(JObject value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        if(File.Exists(_path) && (File.GetAttributes(_path)&FileAttributes.ReadOnly)!=0)
            throw new UnauthorizedAccessException("Local profile is read-only; no rewards were committed.");
        string temporary=_path+".pending";
        using(var file=new FileStream(temporary,FileMode.Create,FileAccess.Write,FileShare.None))
        using(var writer=new StreamWriter(file)) {writer.Write(value.ToString(Formatting.Indented));writer.Flush();file.Flush(true);}
        // ReplaceFile attempts to merge ACL metadata, which is denied to the
        // zero-capability AppContainer. Same-directory MoveFileEx keeps the
        // atomic data replacement without asking for WRITE_DAC privileges.
        if(File.Exists(_path))File.Copy(_path,_path+".bak",true);
        if(!MoveFileEx(temporary,_path,0x1|0x8))throw new Win32Exception(Marshal.GetLastWin32Error(),"Could not atomically commit local pack rewards.");
    }
    public JObject Open(int collationId,int quantity,string requestId)
    {
        lock(_sync)
        {
            if(!Guid.TryParse(requestId,out _))throw new ArgumentException("Opening requires a unique request ID.");
            var existing=((JArray)_profile["openings"]!).OfType<JObject>().FirstOrDefault(x=>(string?)x["id"]==requestId);
            if(existing!=null) {if((int)existing["collationId"]! != collationId || (int)existing["quantity"]! != quantity)throw new InvalidOperationException("Request ID was reused with different contents.");return (JObject)existing.DeepClone();}
            if(quantity<1 || quantity>10)throw new ArgumentOutOfRangeException(nameof(quantity));
            var set=((JArray)_catalog["sets"]!).FirstOrDefault(x=>(int)x["collationId"]! == collationId) ?? throw new NotSupportedException("No verified local card pool for that pack.");
            string key=collationId.ToString(); int available=(int?)_profile["packs"]![key] ?? 0;
            if(available<quantity)throw new InvalidOperationException("Not enough local packs.");
            var cards=new JArray();
            for(int pack=0;pack<quantity;pack++)
            {
                foreach(var slot in new[]{new[]{2,5},new[]{3,2},new[]{4,1}})
                {
                    int rarity=slot[0]; if(rarity==4 && ((JArray)set["pools"]!["5"]!).Count>0 && _random.Next(8)==0)rarity=5;
                    var pool=((JArray)set["pools"]![rarity.ToString()]!).Select(x=>(int)x).ToList();
                    if(pool.Count<slot[1])throw new InvalidDataException("Insufficient distinct cards in local pack pool.");
                    for(int count=0;count<slot[1];count++){int index=_random.Next(pool.Count);cards.Add(new JObject{["grpId"]=pool[index],["rarity"]=rarity,["set"]=(string)set["set"]!,["packIndex"]=pack});pool.RemoveAt(index);}
                }
            }
            var next=(JObject)_profile.DeepClone(); next["packs"]![key]=available-quantity;
            foreach(var card in cards){string id=((int)card["grpId"]!).ToString();next["cards"]![id]=checked(((int?)next["cards"]![id] ?? 0)+1);}
            var receipt=new JObject{["id"]=requestId,["utc"]=DateTime.UtcNow,["collationId"]=collationId,["set"]=(string)set["set"]!,["quantity"]=quantity,["packsBefore"]=available,["packsAfter"]=available-quantity,["cards"]=cards,["policy"]=(string)_catalog["policy"]!};
            ((JArray)next["openings"]!).Add(receipt);next["revision"]=checked((int)next["revision"]!+1);
            Save(next);_profile=next;return (JObject)receipt.DeepClone();
        }
    }
}
