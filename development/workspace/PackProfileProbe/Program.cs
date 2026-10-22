using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using ForgeArenaSandbox;

var root=Path.Combine(@"D:\GAMES\CodexAssets\ForgeArenaSandbox\research\pack-opening","profile-check-"+DateTime.UtcNow.ToString("yyyyMMdd-HHmmss"));
Directory.CreateDirectory(root);
var path=Path.Combine(root,"packs.json");
var catalog=@"D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab\pack-catalog.json";
int checks=0;
void Check(string label,bool value){if(!value)throw new Exception(label);checks++;Console.WriteLine("PASS "+label);}
var profile=new LocalPackProfile(path,catalog);
Check("New profile grants exactly 100 of every catalog pack",((JObject)profile.Snapshot["packs"]!).Properties().All(x=>(int)x.Value==100));
string id=Guid.NewGuid().ToString();var opened=profile.Open(100040,1,id);
Check("One pack debits once and grants eight cards",(int)profile.Snapshot["packs"]!["100040"]! ==99 && ((JObject)profile.Snapshot["cards"]!).Properties().Sum(x=>(int)x.Value)==8);
var cards=(JArray)opened["cards"]!;
Check("Native rarity slots match explicit custom policy",cards.Count(x=>(int)x["rarity"]! ==2)==5 && cards.Count(x=>(int)x["rarity"]! ==3)==2 && cards.Count(x=>(int)x["rarity"]! >=4)==1);
Check("No duplicate printing within a single pack",cards.Select(x=>(int)x["grpId"]!).Distinct().Count()==8);
Check("Same request is idempotent",JToken.DeepEquals(opened,profile.Open(100040,1,id)) && (int)profile.Snapshot["revision"]! ==1);
var reloaded=new LocalPackProfile(path,catalog);
Check("Collection and receipts survive restart",JToken.DeepEquals(profile.Snapshot,reloaded.Snapshot));
Check("Replay after restart cannot double grant",JToken.DeepEquals(opened,reloaded.Open(100040,1,id)) && (int)reloaded.Snapshot["revision"]! ==1);
var before=reloaded.Snapshot;
foreach(var request in new[]{(100040,0,Guid.NewGuid().ToString()),(100040,11,Guid.NewGuid().ToString()),(123456,1,Guid.NewGuid().ToString()),(100040,2,id)}){
 bool rejected=false;try{reloaded.Open(request.Item1,request.Item2,request.Item3);}catch{rejected=true;}Check("Invalid request rejected without profile mutation",rejected && JToken.DeepEquals(before,reloaded.Snapshot));
}
var ten=reloaded.Open(100040,10,Guid.NewGuid().ToString());
Check("Open ten commits all 80 rewards together",((JArray)ten["cards"]!).Count==80 && (int)reloaded.Snapshot["packs"]!["100040"]! ==89);
for(int i=0;i<8;i++)reloaded.Open(100040,10,Guid.NewGuid().ToString());reloaded.Open(100040,9,Guid.NewGuid().ToString());
before=reloaded.Snapshot;bool empty=false;try{reloaded.Open(100040,1,Guid.NewGuid().ToString());}catch(InvalidOperationException){empty=true;}
Check("Empty balance rejects without rewards",empty && JToken.DeepEquals(before,reloaded.Snapshot));
Check("Total collection exactly matches committed receipts",((JObject)before["cards"]!).Properties().Sum(x=>(int)x.Value)==800 && ((JArray)before["openings"]!).Sum(x=>(int)x["quantity"]!)==100);
Check("Previous transaction backup is retained",File.Exists(path+".bak"));
var isolatedPath=Path.Combine(root,"failed-save.json");
var isolated=new LocalPackProfile(isolatedPath,catalog);var isolatedBefore=isolated.Snapshot;string isolatedDisk=File.ReadAllText(isolatedPath);
File.SetAttributes(isolatedPath,File.GetAttributes(isolatedPath)|FileAttributes.ReadOnly);
bool saveFailed=false;try{isolated.Open(100040,1,Guid.NewGuid().ToString());}catch{saveFailed=true;}
finally{File.SetAttributes(isolatedPath,File.GetAttributes(isolatedPath)&~FileAttributes.ReadOnly);}
Check("Failed commit preserves both live and durable inventory",saveFailed && JToken.DeepEquals(isolatedBefore,isolated.Snapshot) && File.ReadAllText(isolatedPath)==isolatedDisk);
var uncommitted=(JObject)isolatedBefore.DeepClone();uncommitted["revision"]=99;uncommitted["cards"]!["86756"]=999;
File.WriteAllText(isolatedPath+".pending",uncommitted.ToString());
var recovered=new LocalPackProfile(isolatedPath,catalog);recovered.Open(100040,1,Guid.NewGuid().ToString());
Check("A pending failed write cannot award cards on restart",(int)recovered.Snapshot["revision"]! ==1 && ((JObject)recovered.Snapshot["cards"]!).Properties().Sum(x=>(int)x.Value)==8);
var detached=recovered.Snapshot;detached["packs"]!["100040"]=100000;
Check("Callers cannot mutate the profile through snapshots",(int)recovered.Snapshot["packs"]!["100040"]! ==99);
var corruptPath=Path.Combine(root,"corrupt.json");File.WriteAllText(corruptPath,"{\"schema\":99}");bool corrupt=false;try{new LocalPackProfile(corruptPath,catalog);}catch{corrupt=true;}
Check("Unsupported profile schema fails without reset",corrupt && File.ReadAllText(corruptPath)=="{\"schema\":99}");
File.WriteAllText(Path.Combine(root,"result.json"),new JObject{["checksPassed"]=checks,["profile"]=path,["scope"]="Actual LocalPackProfile persistence and collation; does not establish native rendering."}.ToString());
Console.WriteLine(root);
