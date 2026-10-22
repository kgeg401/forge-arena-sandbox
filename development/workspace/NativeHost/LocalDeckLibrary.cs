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
    private readonly JObject _matchCards;
    public LocalDeckLibrary(string path,string catalog)
    {
        _path=path;
        var source=JObject.Parse(File.ReadAllText(catalog));
        if((int?)source["schema"]!=1)throw new InvalidDataException("Unsupported local deck catalog.");
        Cards=((JArray)source["cards"]!).Cast<JObject>().ToDictionary(x=>(uint)x["grpId"]!);
        string manifest=Path.Combine(Path.GetDirectoryName(catalog)!,"bridge-card-manifest.json");
        _matchCards=File.Exists(manifest)?(JObject)JObject.Parse(File.ReadAllText(manifest))["cards"]!:new JObject();
        _state=File.Exists(path)?JObject.Parse(File.ReadAllText(path)):new JObject{["schema"]=1,["revision"]=0,["decks"]=new JArray()};
        if((int?)_state["schema"]!=1 || !(_state["decks"] is JArray) || _state["revision"]?.Type!=JTokenType.Integer || (int)_state["revision"]!<0)throw new InvalidDataException("Invalid local deck library; original file preserved.");
        foreach(var deck in (JArray)_state["decks"]!)Validate((JObject)deck);
        if(((JArray)_state["decks"]!).Select(d=>(string)d["id"]!).Distinct(StringComparer.OrdinalIgnoreCase).Count()!=((JArray)_state["decks"]!).Count)throw new InvalidDataException("Duplicate deck IDs; original library preserved.");
    }
    public JArray Decks => (JArray)_state["decks"]!.DeepClone();
    public void Seed(string directory)
    {
        if(!Directory.Exists(directory))return;
        string receipt=Path.Combine(Path.GetDirectoryName(_path)!,"seeded-decks.json");
        var seen=File.Exists(receipt)?JArray.Parse(File.ReadAllText(receipt)).Values<string>().Select(s=>s??throw new InvalidDataException("Invalid sample-deck receipt.")).ToHashSet(StringComparer.OrdinalIgnoreCase):new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var files=Directory.GetFiles(directory,"*.txt").ToDictionary(p=>Path.GetFileName(p),p=>Path.GetFileNameWithoutExtension(p),StringComparer.OrdinalIgnoreCase);
        string manifest=Path.Combine(directory,"starter-decks.json");
        if(File.Exists(manifest))
        {
            var source=JObject.Parse(File.ReadAllText(manifest));
            if((int?)source["schema"]!=1 || !(source["decks"] is JArray entries) || entries.Count==0 || entries.Any(e=>!(e is JObject)))throw new InvalidDataException("Unsupported starter deck manifest.");
            var selected=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
            foreach(var entry in entries.OfType<JObject>())
            {
                string key=(string?)entry["file"]??"",name=(string?)entry["name"]??"";
                if(key!=Path.GetFileName(key) || !files.ContainsKey(key) || string.IsNullOrWhiteSpace(name) || name.Length>80 || selected.ContainsKey(key))throw new InvalidDataException("Invalid starter deck entry; existing decks were preserved.");
                selected.Add(key,name);
            }
            files=selected;
        }
        foreach(var sample in files.OrderBy(p=>p.Key,StringComparer.OrdinalIgnoreCase))
        {
            string key=sample.Key;if(seen.Contains(key))continue;
            string file=Path.Combine(directory,key),name=sample.Value;
            if(!Decks.Any(d=>string.Equals((string?)d["name"],name,StringComparison.OrdinalIgnoreCase)))Save(Import(File.ReadAllText(file),name));
            seen.Add(key);
        }
        SaveJsonAtomically(receipt,new JArray(seen.OrderBy(s=>s)).ToString());
    }
    public JObject New(string name) => new JObject{["id"]=Guid.NewGuid().ToString(),["name"]=name,["format"]="practice",["main"]=new JObject(),["sideboard"]=new JObject(),["commander"]=new JObject(),["companion"]=new JObject()};
    public bool IsVerifiedCommander(uint id)=>Cards.TryGetValue(id,out var card) && (bool?)_matchCards[(string)card["name"]!]?["commanderAdmitted"]==true;
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
            var card=candidates.OrderByDescending(c=>(bool?)_matchCards[(string)c["name"]!]?["commanderAdmitted"]==true && (uint?)_matchCards[(string)c["name"]!]?["grpId"]==(uint)c["grpId"]!).ThenByDescending(c=>(bool)c["preferred"]!).ThenByDescending(c=>(uint)c["grpId"]!).FirstOrDefault();
            if(card==null)throw new InvalidDataException("Line "+lineNumber+": printing not found: "+match.Groups[2].Value+". Nothing was imported.");
            string key=((uint)card["grpId"]!).ToString();deck[pile]![key]=checked(((int?)deck[pile]![key]??0)+int.Parse(match.Groups[1].Value));
        }
        Validate(deck);
        if(((JObject)deck["commander"]!).HasValues)deck["format"]="arena-brawl";
        if(!new[]{"main","sideboard","commander","companion"}.Any(p=>((JObject)deck[p]!).HasValues))throw new InvalidDataException("Clipboard contains no deck cards.");
        return deck;
    }
    private void Validate(JObject deck)
    {
        if(!Guid.TryParse((string?)deck["id"],out _) || string.IsNullOrWhiteSpace((string?)deck["name"]) || ((string)deck["name"]!).Length>80)throw new InvalidDataException("Deck requires an ID and a name of 1 to 80 characters.");
        if(deck["format"]!=null && !new[]{"practice","arena-brawl"}.Contains((string?)deck["format"]))throw new InvalidDataException("Unsupported saved sandbox deck format.");
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
        var previous=decks.OfType<JObject>().FirstOrDefault(d=>string.Equals((string)d["id"]!,(string)deck["id"]!,StringComparison.OrdinalIgnoreCase));
        var value=(JObject)deck.DeepClone();value["updatedUtc"]=DateTime.UtcNow;
        if(previous==null)decks.Add(value);else previous.Replace(value);
        Commit(next);
    }
    public void Delete(string id)
    {
        var next=(JObject)_state.DeepClone();var deck=((JArray)next["decks"]!).OfType<JObject>().FirstOrDefault(d=>string.Equals((string)d["id"]!,id,StringComparison.OrdinalIgnoreCase))??throw new InvalidDataException("Deck no longer exists.");
        deck.Remove();Commit(next);
    }
    private void Commit(JObject next)
    {
        next["revision"]=checked((int)_state["revision"]!+1);
        SaveJsonAtomically(_path,next.ToString(Formatting.Indented));
        _state=next;
    }
    internal static void SaveJsonAtomically(string path,string json)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        if(File.Exists(path) && (File.GetAttributes(path)&FileAttributes.ReadOnly)!=0)throw new UnauthorizedAccessException("The local profile is read-only; changes were not saved.");
        using(var file=new FileStream(path+".pending",FileMode.Create,FileAccess.Write,FileShare.None))
        using(var writer=new StreamWriter(file)){writer.Write(json);writer.Flush();file.Flush(true);}
        if(File.Exists(path))File.Copy(path,path+".bak",true);
        for(int attempt=0;attempt<12;attempt++)
        {
            if(MoveFileEx(path+".pending",path,0x1|0x8))return;
            int error=Marshal.GetLastWin32Error();if((error!=5 && error!=32) || attempt==11)throw new Win32Exception(error,"Could not commit the local profile.");
            System.Threading.Thread.Sleep(10);
        }
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
    public string[] MatchGaps(JObject deck,string? format=null)
    {
        var gaps=new List<string>();int count=((JObject)deck["main"]!).Properties().Sum(p=>(int)p.Value);
        var commanders=((JObject)deck["commander"]!).Properties().ToArray();
        bool brawl=format=="SandboxBrawl" || (format==null && (commanders.Length>0 || (string?)deck["format"]=="arena-brawl"));
        if(brawl)
        {
            if(commanders.Length!=1 || commanders.Sum(p=>(int)p.Value)!=1)gaps.Add("Brawl requires exactly one commander.");
            if(count!=99)gaps.Add("Brawl requires 99 main cards plus one commander (currently "+count+" main cards).");
            string? commander=commanders.Length==1?(string?)Cards[uint.Parse(commanders[0].Name)]["name"]:null;
            var definition=commander==null?null:_matchCards[commander];
            if((bool?)definition?["commanderAdmitted"]!=true)gaps.Add("This commander is not verified for Brawl.");
            var colors=new HashSet<string>((definition?["colorIdentity"] as JArray??new JArray()).Values<string>()!);
            var counts=((JObject)deck["main"]!).Properties().GroupBy(p=>(string)Cards[uint.Parse(p.Name)]["name"]!).Select(g=>new{Name=g.Key,Count=g.Sum(p=>(int)p.Value)});
            foreach(var item in counts)
            {
                var card=_matchCards[item.Name];
                if(item.Name==commander)gaps.Add("The commander also appears in the main deck.");
                if((bool?)card?["admitted"]!=true)gaps.Add("Unverified match card: "+item.Name);
                if(item.Count!=1 && !new[]{"Plains","Island","Swamp","Mountain","Forest"}.Contains(item.Name))gaps.Add("Brawl is singleton except basic lands: "+item.Name);
                if(card?["colorIdentity"] is JArray identity && identity.Values<string>().Any(c=>!colors.Contains(c!)))gaps.Add("Outside commander color identity: "+item.Name);
            }
            foreach(string pile in new[]{"sideboard","companion"})if(((JObject)deck[pile]!).HasValues)gaps.Add("Brawl does not support "+pile+" cards.");
            return gaps.ToArray();
        }
        if(count<40 || count>250)gaps.Add("Practice requires 40 to 250 main-deck cards (currently "+count+").");
        foreach(string pile in new[]{"sideboard","commander","companion"})if(((JObject)deck[pile]!).HasValues)gaps.Add("Matches do not yet support "+pile+" cards.");
        foreach(var p in ((JObject)deck["main"]!).Properties())if(!(bool)Cards[uint.Parse(p.Name)]["matchSupported"]!)gaps.Add("Unverified match card: "+Cards[uint.Parse(p.Name)]["name"]);
        return gaps.ToArray();
    }
}
