using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using ForgeArenaSandbox;

string root=Path.Combine(@"D:\GAMES\CodexAssets\ForgeArenaSandbox\research\deck-ui","storage-check-"+DateTime.UtcNow.ToString("yyyyMMdd-HHmmss"));
Directory.CreateDirectory(root);string path=Path.Combine(root,"decks.json");
string catalog=Environment.GetEnvironmentVariable("FORGE_ARENA_DECK_CATALOG")??@"D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab\deck-catalog.json";
int checks=0;void Check(string label,bool ok){if(!ok)throw new Exception(label);checks++;Console.WriteLine("PASS "+label);}
var library=new LocalDeckLibrary(path,catalog);
var deck=library.Import("Deck\n12 Plains\n12 Island\n8 Savannah Lions\n8 Oreskos Swiftclaw\n8 Impassioned Orator\n4 Unsummon\n4 Essence Scatter\n4 Divine Arrow","Practice deck");
Check("Supported names resolve to the pinned practice printings",(int)deck["main"]!["75556"]! ==12 && (int)deck["main"]!["93859"]! ==8 && library.MatchGaps(deck).Length==0);
library.Save(deck);var reloaded=new LocalDeckLibrary(path,catalog);
Check("Saved deck survives restart with ID, counts and name",reloaded.Decks.Count==1 && (string)reloaded.Decks[0]["id"]! ==(string)deck["id"]! && JToken.DeepEquals(reloaded.Decks[0]["main"],deck["main"]));
var exported=reloaded.Export(deck);var roundTrip=reloaded.Import(exported,"Round trip");
Check("Arena text round trip preserves exact printing IDs",JToken.DeepEquals(roundTrip["main"],deck["main"]));
var printing=library.Cards.Values.First(c=>!(bool)c["matchSupported"]! && ((string)c["collector"]!).All(char.IsDigit));
string line="1 "+printing["name"]+" ("+printing["set"]+") "+printing["collector"];
var general=library.Import("Deck\n40 Plains\n"+line+"\nSideboard\n2 Island\nCommander\n1 Savannah Lions\nCompanion\n1 Yoked Ox","Full piles");
Check("Unverified cards are preserved and explicitly block match admission",(int)general["main"]![((uint)printing["grpId"]!).ToString()]! ==1 && library.MatchGaps(general).Any(g=>g.Contains("Unverified")));
var fullRoundTrip=library.Import(library.Export(general),"Full round trip");
Check("All four Arena deck sections survive export and reimport",new[]{"main","sideboard","commander","companion"}.All(p=>JToken.DeepEquals(general[p],fullRoundTrip[p])) && library.MatchGaps(general).Any(g=>g.Contains("commander")) && library.MatchGaps(general).Any(g=>g.Contains("sideboard")) && library.MatchGaps(general).Any(g=>g.Contains("companion")));
bool ambiguousImport=false;try{library.Import("Deck\n40 Plains\n1 Ghalta, Primal Hunger (RIX) 130","Ambiguous");}catch(InvalidDataException){ambiguousImport=true;}
Check("Ambiguous source printing labels cannot silently change identity on import",ambiguousImport);
var ambiguous=library.New("Ambiguous exact printing");ambiguous["main"]!["66877"]=1;bool ambiguousExport=false;try{library.Export(ambiguous);}catch(InvalidDataException){ambiguousExport=true;}
Check("Export refuses labels that cannot preserve an exact saved printing",ambiguousExport);
var before=library.Decks;string disk=File.ReadAllText(path);
foreach(var invalid in new[]{"Deck\n60 Totally nonexistent card","Deck\n0 Plains","Deck\n-1 Plains","Deck\n1.5 Plains","Deck\n1000 Plains","Deck\n60 Plains (ZZZZ) 123","Sideboard\n","Deck\n999 Plains\n2 Island"})
{bool rejected=false;try{library.Import(invalid,"Bad import");}catch{rejected=true;}Check("Invalid import is rejected without saving a partial deck",rejected && JToken.DeepEquals(before,library.Decks) && File.ReadAllText(path)==disk);}
var duplicate=library.Import("Deck\n20 Plains\n20 plains\n20 Island","Repeated names");
Check("Repeated card rows combine without losing quantities",(int)duplicate["main"]!["75556"]! ==40);
if(args.Length==1)
{
    foreach(string file in Directory.GetFiles(Path.GetFullPath(args[0]),"Brawl-*.txt").OrderBy(f=>f))
    {
        var sample=library.Import(File.ReadAllText(file),Path.GetFileNameWithoutExtension(file));
        Check("Brawl sample keeps its commander and passes local format validation: "+Path.GetFileName(file),library.MatchGaps(sample,"SandboxBrawl").Length==0 && ((JObject)sample["commander"]!).Properties().Sum(p=>(int)p.Value)==1);
        Check("Practice cannot silently discard a Brawl commander: "+Path.GetFileName(file),library.MatchGaps(sample,"SandboxPractice").Any(g=>g.Contains("commander")));
        var again=library.Import(library.Export(sample),"Brawl round trip");
        Check("Brawl text round trip preserves exact main and commander printings: "+Path.GetFileName(file),JToken.DeepEquals(sample["main"],again["main"]) && JToken.DeepEquals(sample["commander"],again["commander"]));
    }
    var brawl=library.Import("Commander\n1 Isamaru, Hound of Konda\nDeck\n98 Plains\n1 Savannah Lions","Brawl boundary checks");
    Check("Commander-only admission selects the pinned Isamaru printing",((JObject)brawl["commander"]!).Property("72175")!=null);
    string islandId=library.Cards.Values.Single(c=>(string)c["name"]! =="Island" && (bool)c["preferred"]!).Value<uint>("grpId").ToString();
    var illegal=(JObject)brawl.DeepClone();illegal["main"]!["75556"]=97;illegal["main"]![islandId]=1;
    Check("Brawl rejects an admitted card outside commander color identity",library.MatchGaps(illegal).Any(g=>g.Contains("color identity")));
    illegal=(JObject)brawl.DeepClone();illegal["main"]!["93859"]=2;illegal["main"]!["75556"]=97;
    Check("Brawl rejects nonbasic duplicates independently of deck size",library.MatchGaps(illegal).Any(g=>g.Contains("singleton")));
    illegal=(JObject)brawl.DeepClone();illegal["commander"]=new JObject();
    Check("Removing a commander preserves Brawl format and reports the missing slot",library.MatchGaps(illegal).Any(g=>g.Contains("exactly one commander")));
    foreach(string file in Directory.GetFiles(Path.GetFullPath(args[0]),"*-Practice.txt").Where(f=>f.EndsWith("-Vanilla-Practice.txt") || f.EndsWith("-Keywords-Practice.txt") || f.EndsWith("-Draw-Practice.txt")).OrderBy(f=>f))
    {
        var sample=library.Import(File.ReadAllText(file),Path.GetFileNameWithoutExtension(file));
        Check("Expanded sample admits every original deck-library card: "+Path.GetFileName(file),library.MatchGaps(sample).Length==0);
        var again=library.Import(library.Export(sample),"Expanded round trip");
        Check("Expanded sample preserves exact printing IDs: "+Path.GetFileName(file),JToken.DeepEquals(sample["main"],again["main"]));
    }
}
deck["name"]="Renamed deck";deck["main"]!["75556"]=13;library.Save(deck);
Check("Editing updates one deck without creating a duplicate",library.Decks.Count==1 && (string)library.Decks[0]["name"]! =="Renamed deck" && (int)library.Decks[0]["main"]!["75556"]! ==13);
Check("Previous library version is retained",File.Exists(path+".bak"));
var metadataBefore=(JObject)library.Decks[0].DeepClone();string metadataId=(string)metadataBefore["id"]!;
library.SetFavorite(metadataId,true);library.RecordPlayed(metadataId);var metadataAfter=library.Decks[0];
Check("Favorite and played metadata preserve every card pile and modified date",new[]{"main","sideboard","commander","companion","updatedUtc"}.All(key=>JToken.DeepEquals(metadataBefore[key],metadataAfter[key])) && (bool)metadataAfter["favorite"]! && metadataAfter["lastPlayedUtc"]?.Type==JTokenType.Date);
var metadataDisk=File.ReadAllText(path);library.SetFavorite(metadataId,true);
Check("Repeating a favorite selection is idempotent",File.ReadAllText(path)==metadataDisk);
deck["name"]="Edited after favorite";library.Save(deck);var edited=library.Decks[0];
Check("Saving a stale editor draft retains latest favorite and played metadata",(bool)edited["favorite"]! && JToken.DeepEquals(edited["lastPlayedUtc"],metadataAfter["lastPlayedUtc"]));
var metadataReload=new LocalDeckLibrary(path,catalog);
Check("Favorites and played history survive a library reload",(bool)metadataReload.Decks[0]["favorite"]! && JToken.DeepEquals(metadataReload.Decks[0]["lastPlayedUtc"],edited["lastPlayedUtc"]));
var malformedFavorite=(JObject)deck.DeepClone();malformedFavorite["favorite"]="yes";bool malformedMetadata=false;
try{library.Save(malformedFavorite);}catch(InvalidDataException){malformedMetadata=true;}
Check("Malformed favorite metadata cannot corrupt saved decks",malformedMetadata && JToken.DeepEquals(library.Decks[0],edited));
before=library.Decks;disk=File.ReadAllText(path);File.SetAttributes(path,File.GetAttributes(path)|FileAttributes.ReadOnly);bool failed=false;
try{deck["name"]="Must not save";library.Save(deck);}catch{failed=true;}finally{File.SetAttributes(path,File.GetAttributes(path)&~FileAttributes.ReadOnly);}
Check("Failed write preserves both memory and durable saved decks",failed && JToken.DeepEquals(before,library.Decks) && File.ReadAllText(path)==disk);
File.WriteAllText(path+".pending","{\"schema\":999}");reloaded=new LocalDeckLibrary(path,catalog);
Check("Interrupted pending write does not replace saved decks",JToken.DeepEquals(reloaded.Decks,before));
var detached=library.Decks;detached.Clear();Check("Library snapshots cannot mutate saved decks",library.Decks.Count==1);
library.Delete((string)deck["id"]!);Check("Deletion persists across restart",new LocalDeckLibrary(path,catalog).Decks.Count==0);
File.WriteAllText(Path.Combine(root,"corrupt.json"),"{\"schema\":99}");bool corrupt=false;
try{new LocalDeckLibrary(Path.Combine(root,"corrupt.json"),catalog);}catch{corrupt=true;}
Check("Unsupported schema is rejected without reset",corrupt && File.ReadAllText(Path.Combine(root,"corrupt.json"))=="{\"schema\":99}");
var seeds=Path.Combine(root,"seed-inputs");Directory.CreateDirectory(seeds);
File.WriteAllText(Path.Combine(seeds,"allowed.txt"),"Deck\n60 Plains\n");File.WriteAllText(Path.Combine(seeds,"internal.txt"),"Deck\n60 Island\n");
string starterManifest=Path.Combine(seeds,"starter-decks.json");
var entries=new JArray(new JObject{["file"]="allowed.txt",["name"]="Friendly starter"});
void WriteStarters(JArray rows)=>File.WriteAllText(starterManifest,new JObject{["schema"]=1,["decks"]=rows}.ToString());
WriteStarters(entries);
var seeded=new LocalDeckLibrary(Path.Combine(root,"seed-profile","decks.json"),catalog);seeded.Seed(seeds);
Check("Starter manifest seeds only recommended files with friendly names",seeded.Decks.Count==1 && (string)seeded.Decks[0]["name"]! =="Friendly starter");
seeded.Seed(seeds);Check("Repeated starter seeding is idempotent",seeded.Decks.Count==1);
seeded.Delete((string)seeded.Decks[0]["id"]!);seeded.Seed(seeds);
Check("A deliberately deleted starter does not return on the next launch",seeded.Decks.Count==0);
File.WriteAllText(Path.Combine(seeds,"new.txt"),"Deck\n60 Island\n");entries.Add(new JObject{["file"]="new.txt",["name"]="New starter"});WriteStarters(entries);seeded.Seed(seeds);
Check("A later starter is added without restoring a previously deleted starter",seeded.Decks.Count==1 && (string)seeded.Decks[0]["name"]! =="New starter");
var existing=new LocalDeckLibrary(Path.Combine(root,"existing-seed-profile","decks.json"),catalog);var userDeck=existing.Import("Deck\n60 Plains\n","Friendly starter");existing.Save(userDeck);existing.Seed(seeds);
Check("A matching user deck is retained instead of being replaced by a starter",existing.Decks.OfType<JObject>().Any(d=>(string)d["id"]! ==(string)userDeck["id"]! && JToken.DeepEquals(d["main"],userDeck["main"])));
string seedDisk=File.ReadAllText(Path.Combine(root,"seed-profile","decks.json"));
WriteStarters(new JArray(new JObject{["file"]="../outside.txt",["name"]="Invalid"}));bool badSeed=false;try{seeded.Seed(seeds);}catch(InvalidDataException){badSeed=true;}
Check("A starter path cannot escape its seed directory",badSeed && File.ReadAllText(Path.Combine(root,"seed-profile","decks.json"))==seedDisk);
WriteStarters(new JArray("invalid entry"));badSeed=false;try{seeded.Seed(seeds);}catch(InvalidDataException){badSeed=true;}
Check("Malformed starter rows are rejected without changing saved decks",badSeed && File.ReadAllText(Path.Combine(root,"seed-profile","decks.json"))==seedDisk);
string preferencePath=Path.Combine(root,"printing-preferences.json");var titleMap=new System.Collections.Generic.Dictionary<uint,uint>{{100,10},{101,10},{200,20}};
var preferences=new LocalPrintingPreferences(preferencePath,titleMap);preferences.Set(10,101);
Check("A selected alternate printing survives reload",new LocalPrintingPreferences(preferencePath,titleMap).Get(10)==101);
string preferenceDisk=File.ReadAllText(preferencePath);preferences.Set(10,101);
Check("Repeated printing preference is idempotent",File.ReadAllText(preferencePath)==preferenceDisk);
bool wrongTitle=false;try{preferences.Set(10,200);}catch(InvalidDataException){wrongTitle=true;}
Check("A printing from a different title cannot be assigned",wrongTitle && preferences.Get(10)==101 && File.ReadAllText(preferencePath)==preferenceDisk);
File.SetAttributes(preferencePath,File.GetAttributes(preferencePath)|FileAttributes.ReadOnly);failed=false;
try{preferences.Set(10,100);}catch{failed=true;}finally{File.SetAttributes(preferencePath,File.GetAttributes(preferencePath)&~FileAttributes.ReadOnly);}
Check("Failed preference writes preserve in-memory and durable selection",failed && preferences.Get(10)==101 && File.ReadAllText(preferencePath)==preferenceDisk);
preferences.Set(10,null);Check("Unfavorite persists without erasing other profile files",new LocalPrintingPreferences(preferencePath,titleMap).Get(10)==null && File.Exists(path));
File.WriteAllText(preferencePath,"{\"schema\":1,\"printings\":{\"10\":200}}");bool badPrinting=false;
try{new LocalPrintingPreferences(preferencePath,titleMap);}catch(InvalidDataException){badPrinting=true;}
Check("Corrupt printing-title links are rejected without rewriting source",badPrinting && File.ReadAllText(preferencePath).Contains("200"));
File.WriteAllText(Path.Combine(root,"result.json"),new JObject{["checksPassed"]=checks,["scope"]="Actual local deck parser, exact printing round trips, printing preferences and durable persistence. Native UI tested separately.",["profile"]=path}.ToString());Console.WriteLine(root);
