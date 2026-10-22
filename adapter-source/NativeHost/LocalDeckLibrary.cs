using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using System.Runtime.InteropServices;
using System.ComponentModel;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

// Deck storage is independent of online inventory and of the bounded match bridge.
internal sealed class LocalDeckLibrary
{
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    private static extern bool MoveFileEx(string source,string destination,uint flags);
    private readonly string _path;
    private JObject _state;
    public readonly Dictionary<uint,JObject> Cards;
    public LocalDeckLibrary(string path,string catalog)
    {
        _path=path;
        var source=JObject.Parse(File.ReadAllText(catalog));
        if((int?)source["schema"]!=1)throw new InvalidDataException("Unsupported local deck catalog.");
        Cards=((JArray)source["cards"]!).Cast<JObject>().ToDictionary(x=>(uint)x["grpId"]!);
        _state=File.Exists(path)?JObject.Parse(File.ReadAllText(path)):new JObject{["schema"]=1,["revision"]=0,["decks"]=new JArray()};
        if((int?)_state["schema"]!=1 || !(_state["decks"] is JArray) || _state["revision"]?.Type!=JTokenType.Integer || (int)_state["revision"]!<0)throw new InvalidDataException("Invalid local deck library; original file preserved.");
        foreach(var deck in (JArray)_state["decks"]!)Validate((JObject)deck);
        if(((JArray)_state["decks"]!).Select(d=>(string)d["id"]!).Distinct(StringComparer.OrdinalIgnoreCase).Count()!=((JArray)_state["decks"]!).Count)throw new InvalidDataException("Duplicate deck IDs; original library preserved.");
    }
    public JArray Decks => (JArray)_state["decks"]!.DeepClone();
    public JObject New(string name) => new JObject{["id"]=Guid.NewGuid().ToString(),["name"]=name,["main"]=new JObject(),["sideboard"]=new JObject(),["commander"]=new JObject(),["companion"]=new JObject()};
    public JObject Import(string text,string name)
    {
        if(text.Length>262144)throw new InvalidDataException("Deck text exceeds 256 KB.");
        var deck=New(name);string pile="main";int lineNumber=0;
        foreach(var raw in text.Replace("\r","").Split('\n'))
        {
            lineNumber++;string line=raw.Trim();if(line=="" || line.StartsWith("#"))continue;
            if(line=="Deck"){pile="main";continue;}if(line=="Sideboard"){pile="sideboard";continue;}
            if(line=="Commander"){pile="commander";continue;}if(line=="Companion"){pile="companion";continue;}
            var match=Regex.Match(line,@"^([1-9][0-9]{0,2})[xX]?\s+(.+?)(?:\s+\(([A-Za-z0-9]+)\)\s+([0-9]+[A-Za-z]?))?$");
            if(!match.Success)throw new InvalidDataException("Line "+lineNumber+": expected count and card name.");
            var candidates=Cards.Values.Where(c=>string.Equals((string)c["name"]!,match.Groups[2].Value,StringComparison.OrdinalIgnoreCase));
            if(match.Groups[3].Success)candidates=candidates.Where(c=>string.Equals((string)c["set"]!,match.Groups[3].Value,StringComparison.OrdinalIgnoreCase) && string.Equals((string)c["collector"]!,match.Groups[4].Value,StringComparison.OrdinalIgnoreCase));
            if(match.Groups[3].Success && candidates.Take(2).Count()>1)throw new InvalidDataException("Line "+lineNumber+": these printing labels identify multiple installed versions. Import without printing labels to choose the preferred version. Nothing was imported.");
            var card=candidates.OrderByDescending(c=>(bool)c["preferred"]!).ThenByDescending(c=>(uint)c["grpId"]!).FirstOrDefault();
            if(card==null)throw new InvalidDataException("Line "+lineNumber+": printing not found: "+match.Groups[2].Value+". Nothing was imported.");
            string key=((uint)card["grpId"]!).ToString();deck[pile]![key]=checked(((int?)deck[pile]![key]??0)+int.Parse(match.Groups[1].Value));
        }
        Validate(deck);
        if(!new[]{"main","sideboard","commander","companion"}.Any(p=>((JObject)deck[p]!).HasValues))throw new InvalidDataException("Clipboard contains no deck cards.");
        return deck;
    }
    private void Validate(JObject deck)
    {
        if(!Guid.TryParse((string?)deck["id"],out _) || string.IsNullOrWhiteSpace((string?)deck["name"]) || ((string)deck["name"]!).Length>80)throw new InvalidDataException("Deck requires an ID and a name of 1 to 80 characters.");
        int total=0;
        foreach(string pile in new[]{"main","sideboard","commander","companion"})
        {
            if(!(deck[pile] is JObject values))throw new InvalidDataException("Missing deck pile: "+pile);
            foreach(var card in values.Properties())
            {if(!uint.TryParse(card.Name,out var id) || !Cards.ContainsKey(id) || card.Value.Type!=JTokenType.Integer || (int)card.Value<1 || (int)card.Value>999)throw new InvalidDataException("Invalid or unknown deck printing: "+card.Name);total=checked(total+(int)card.Value);}
        }
        if(total>1000)throw new InvalidDataException("Local editing is limited to 1000 total cards.");
    }
    public void Save(JObject deck)
    {
        Validate(deck);var next=(JObject)_state.DeepClone();var decks=(JArray)next["decks"]!;
        var previous=decks.OfType<JObject>().FirstOrDefault(d=>(string)d["id"]! ==(string)deck["id"]!);
        var value=(JObject)deck.DeepClone();value["updatedUtc"]=DateTime.UtcNow;
        if(previous==null)decks.Add(value);else previous.Replace(value);
        Commit(next);
    }
    public void Delete(string id)
    {
        var next=(JObject)_state.DeepClone();var deck=((JArray)next["decks"]!).OfType<JObject>().FirstOrDefault(d=>(string)d["id"]! ==id)??throw new InvalidDataException("Deck no longer exists.");
        deck.Remove();Commit(next);
    }
    private void Commit(JObject next)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        if(File.Exists(_path) && (File.GetAttributes(_path)&FileAttributes.ReadOnly)!=0)throw new UnauthorizedAccessException("Local deck library is read-only; changes were not saved.");
        next["revision"]=checked((int)_state["revision"]!+1);
        using(var file=new FileStream(_path+".pending",FileMode.Create,FileAccess.Write,FileShare.None))
        using(var writer=new StreamWriter(file)){writer.Write(next.ToString(Formatting.Indented));writer.Flush();file.Flush(true);}
        if(File.Exists(_path))File.Copy(_path,_path+".bak",true);
        if(!MoveFileEx(_path+".pending",_path,0x1|0x8))throw new Win32Exception(Marshal.GetLastWin32Error(),"Could not commit local deck library.");
        _state=next;
    }
    public string Export(JObject deck)
    {
        Validate(deck);var lines=new List<string>();
        foreach(var pair in new[]{("commander","Commander"),("companion","Companion"),("main","Deck"),("sideboard","Sideboard")})
        {
            var cards=(JObject)deck[pair.Item1]!;if(pair.Item1!="main" && !cards.HasValues)continue;
            if(lines.Count>0)lines.Add("");lines.Add(pair.Item2);
            foreach(var p in cards.Properties())
            {
                var card=Cards[uint.Parse(p.Name)];
                if(Cards.Values.Count(c=>string.Equals((string)c["name"]!,(string)card["name"]!,StringComparison.OrdinalIgnoreCase) && string.Equals((string)c["set"]!,(string)card["set"]!,StringComparison.OrdinalIgnoreCase) && string.Equals((string)c["collector"]!,(string)card["collector"]!,StringComparison.OrdinalIgnoreCase))>1)throw new InvalidDataException("Exact text export is ambiguous for "+card["name"]+" ("+card["set"]+") "+card["collector"]+". Your saved deck is preserved.");
                lines.Add(p.Value+" "+card["name"]+" ("+card["set"]+") "+card["collector"]);
            }
        }
        return string.Join(Environment.NewLine,lines)+Environment.NewLine;
    }
    public string[] MatchGaps(JObject deck)
    {
        var gaps=new List<string>();int count=((JObject)deck["main"]!).Properties().Sum(p=>(int)p.Value);
        if(count<40 || count>250)gaps.Add("Practice requires 40 to 250 main-deck cards (currently "+count+").");
        foreach(string pile in new[]{"sideboard","commander","companion"})if(((JObject)deck[pile]!).HasValues)gaps.Add("Matches do not yet support "+pile+" cards.");
        foreach(var p in ((JObject)deck["main"]!).Properties())if(!(bool)Cards[uint.Parse(p.Name)]["matchSupported"]!)gaps.Add("Unverified match card: "+Cards[uint.Parse(p.Name)]["name"]);
        return gaps.ToArray();
    }
}
