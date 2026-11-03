using System;
using System.IO;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using ForgeArenaSandbox;

var root=Path.Combine(Path.GetTempPath(),"arena-manifest-startup-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
int checks=0;
void Check(bool value,string label){if(!value)throw new Exception(label);checks++;}
string hash=new string('a',64),oldHash=new string('b',64);
JObject Bundle(string name,string path)=>new JObject{["Name"]=name,["IndexedAssets"]=new JArray(path)};
JObject Database(string digest)=>new JObject{["Name"]="Raw_CardDatabase_"+digest+".mtga",["sha256"]=Convert.ToBase64String(Convert.FromHexString(digest))};
void Write(string name,params JObject[] assets)=>File.WriteAllText(Path.Combine(root,name),new JObject{["Assets"]=new JArray(assets)}.ToString());
string[] Select()=>InstalledManifestPlan.Select(root,hash,_=>{});
void Reject(Action action,string text){try{action();}catch(InvalidDataException e){Check(e.Message.Contains(text),text);return;}throw new Exception("Unexpected acceptance: "+text);}
const string art="Assets/Core/CardArt/458000/458294_AIF.tga";
try
{
    Write("Manifest_old.mtga",Database(oldHash),Bundle("old-art.mtga",art));
    Write("Manifest_current.mtga",Database(hash),Bundle("current-art.mtga",art));
    Write("Manifest_Audio.mtga",Bundle("audio.pck","audio/example"));
    var files=Select();Check(files.Length==2 && !files.Any(f=>f.EndsWith("Manifest_old.mtga")),"Stale manifest with the reported colliding art path is excluded by database identity");
    Check(JObject.Parse(File.ReadAllText(Path.Combine(root,"Manifest_old.mtga")))["Assets"]!.Count()==2,"Stale installed files are preserved");
    Write("Manifest_same.mtga",Database(hash),Bundle("current-art.mtga",art));
    Check(Select().Length==3,"Identical repeated bundle records remain safe for native bundle-name deduplication");
    Write("Manifest_same.mtga",Database(hash),Bundle("conflicting-art.mtga",art));
    Reject(()=>Select(),"Conflicting installed asset");
    Write("Manifest_same.mtga",Database(hash),Bundle("current-art.mtga","different/path"));
    Reject(()=>Select(),"Conflicting installed bundle metadata");
    File.Delete(Path.Combine(root,"Manifest_same.mtga"));File.Delete(Path.Combine(root,"Manifest_current.mtga"));
    Reject(()=>Select(),"No installed asset manifest matches");
    Reject(()=>InstalledManifestPlan.Select(root,"invalid",_=>{}),"Missing validated");
    Write("Manifest_invalid.mtga",Bundle("invalid","unused"));File.WriteAllText(Path.Combine(root,"Manifest_invalid.mtga"),"{}");
    Reject(()=>Select(),"Invalid installed manifest");
    IEnumerator Failure(){yield return "before";throw new InvalidOperationException("captured inner startup fault");}
    IEnumerator Nested(){yield return Failure();yield return "must not run";}
    Exception? failure=null;var seen=new List<object?>();var guarded=GuardedCoroutine.Run(Nested(),e=>failure=e);
    while(guarded.MoveNext())seen.Add(guarded.Current);
    Check(failure?.Message=="captured inner startup fault" && seen.SequenceEqual(new object?[]{"before"}),"Nested startup exception is surfaced without continuing the failed routine");
    IEnumerator Normal(){yield return new object?[]{null,"frame"}.GetEnumerator();yield return "done";}
    failure=null;seen.Clear();guarded=GuardedCoroutine.Run(Normal(),e=>failure=e);while(guarded.MoveNext())seen.Add(guarded.Current);
    Check(failure==null && seen.SequenceEqual(new object?[]{null,"frame","done"}),"Nested normal yields retain their order");
    if(args.Length==2)Check(InstalledManifestPlan.Select(args[0],args[1],_=>{}).Length>0,"Actual installed manifests form a nonconflicting plan");
    Console.WriteLine(new JObject{["passed"]=true,["checks"]=checks});
}
finally{Directory.Delete(root,true);}
