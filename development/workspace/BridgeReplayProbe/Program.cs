using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

// Replay recorded rules states through a compiled adapter, without Unity or Forge.
if(args.Length!=5)throw new ArgumentException("BridgeReplayProbe <NativeHost.dll> <managed> <private-root> <states.json> <new-report.json>");
string dll=Path.GetFullPath(args[0]),managed=Path.GetFullPath(args[1]),root=Path.GetFullPath(args[2]);
if(File.Exists(args[4]))throw new IOException("Preserve the existing report");
AssemblyLoadContext.Default.Resolving+=(_,name)=>{
    foreach(string folder in new[]{Path.GetDirectoryName(dll)!,managed}){string path=Path.Combine(folder,name.Name+".dll");if(File.Exists(path))return AssemblyLoadContext.Default.LoadFromAssemblyPath(path);}return null;};
var host=AssemblyLoadContext.Default.LoadFromAssemblyPath(dll);
var states=JArray.Parse(File.ReadAllText(args[3]));if(states.Count==0)throw new ArgumentException("No recorded states");
string ipc=Path.GetFullPath(Path.Combine(root,"..","research","replay-"+Guid.NewGuid().ToString("N")));Directory.CreateDirectory(ipc);
File.WriteAllText(Path.Combine(ipc,"state.json"),states[0]!.ToString());
var connectionType=AssemblyLoadContext.Default.LoadFromAssemblyPath(Path.Combine(Path.GetDirectoryName(dll)!,"LocalTransport.dll")).GetType("ForgeArenaSandbox.LocalGreConnection",true)!;
var connection=Activator.CreateInstance(connectionType,new object[]{"recorded-replay",256})!;
connectionType.GetMethod("Connect")!.Invoke(connection,new object?[]{null});
connectionType.GetMethod("ConnectToGRE")!.Invoke(connection,new object[]{"sandbox://local","recorded-replay"});
var type=host.GetType("ForgeArenaSandbox.ForgeLandBridge",true)!;
var bridge=Activator.CreateInstance(type,new object?[]{root,connection,(Action<string>)(_=>{}),(Func<uint?>)(()=>null),(Func<bool>)(()=>false),ipc,(Func<double>)(()=>0),null,null})!;
void Drain(){for(int i=0;i<16;i++)connectionType.GetMethod("ProcessMessages")!.Invoke(connection,null);}
type.GetMethod("Start")!.Invoke(bridge,null);Drain();
var adopt=type.GetMethod("AdoptState",BindingFlags.Instance|BindingFlags.NonPublic)!;
long allocated=0;double ms=0;int maxTokens=0;
foreach(var state in states.Skip(1))
{
    maxTokens=Math.Max(maxTokens,((JArray)state["battlefield"]!).Count(c=>(bool?)c["token"]==true));
    long before=GC.GetAllocatedBytesForCurrentThread();var timer=Stopwatch.StartNew();
    try{adopt.Invoke(bridge,new object[]{state});}catch(TargetInvocationException error){throw new InvalidOperationException("Recorded transition failed: "+state["turn"]+" / "+state["phase"],error.InnerException);}
    timer.Stop();ms+=timer.Elapsed.TotalMilliseconds;allocated+=GC.GetAllocatedBytesForCurrentThread()-before;Drain();
}
var messages=new JArray(File.ReadLines(Path.Combine(ipc,"native-wire.jsonl")).Select(line=>JObject.Parse(line)["message"]!));
var result=new JObject{["transitions"]=states.Count-1,["maxTokens"]=maxTokens,["allocatedBytes"]=allocated,["elapsedMs"]=ms,["messages"]=messages,
    ["scope"]="Recorded-state projection and GRE message equivalence; not new rules execution, native rendering or fps."};
File.WriteAllText(args[4],result.ToString(Formatting.None));
Console.WriteLine(new JObject{["transitions"]=states.Count-1,["messages"]=messages.Count,["allocatedBytes"]=allocated,["elapsedMs"]=ms,["maxTokens"]=maxTokens});
