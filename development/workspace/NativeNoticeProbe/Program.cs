using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

string dll=Path.GetFullPath(args[0]),managed=Path.GetFullPath(args[1]);
AssemblyLoadContext.Default.Resolving+=(_,name)=>{
    foreach(string root in new[]{Path.GetDirectoryName(dll)!,managed}){string path=Path.Combine(root,name.Name+".dll");if(File.Exists(path))return AssemblyLoadContext.Default.LoadFromAssemblyPath(path);}return null;};
var assembly=AssemblyLoadContext.Default.LoadFromAssemblyPath(dll);var checks=new List<string>();
void Check(string name,bool value){if(!value)throw new Exception(name);checks.Add(name);}
void Set(object owner,string name,object? value)=>owner.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic)!.SetValue(owner,value);
object? Get(object owner,string name)=>owner.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(owner);
var state=JObject.Parse(File.ReadAllText(args[2]));string original=state.ToString(Formatting.None);
var bridge=RuntimeHelpers.GetUninitializedObject(assembly.GetType("ForgeArenaSandbox.ForgeLandBridge",true)!);Set(bridge,"_state",state);Set(bridge,"_session",(string)state["session"]!);
JObject Notice()=>(JObject)bridge.GetType().GetProperty("ClientNotice")!.GetValue(bridge)!;
var notice=Notice();
Check("Notice retains actual session and elimination",(string?)notice["session"]==(string?)state["session"] && (bool?)notice["localLost"]==(bool?)state["localLost"]);
Check("No board, event history or hidden cards in notices",new[]{"battlefield","hand","hidden","events","library"}.All(key=>notice[key]==null));
Check("Decision is a boolean, not a cloned choice",notice["decisionPending"]!.Type==JTokenType.Boolean);
Set(bridge,"_pending","still-calculating");Check("Busy bridge is explicitly reported",(bool)Notice()["requestPending"]!);Set(bridge,"_pending",null);
Set(bridge,"<Gap>k__BackingField","Forge rejected action: invalid choice");notice=Notice();Check("Recoverable rejection is distinguished from fatal display failures",(bool)notice["recoverableFailure"]!);
Set(bridge,"<Gap>k__BackingField","Unsupported native mapping");Check("Fatal gap retains its actual reason",(string?)Notice()["bridgeFailure"]=="Unsupported native mapping" && !(bool)Notice()["recoverableFailure"]!);
Check("Notice reads do not mutate the real board",state.ToString(Formatting.None)==original);
long before=GC.GetAllocatedBytesForCurrentThread();for(int i=0;i<100;i++)Notice();long perNotice=(GC.GetAllocatedBytesForCurrentThread()-before)/100;
Check("Large-board notice allocation stays below one board's encoded size",perNotice<System.Text.Encoding.UTF8.GetByteCount(original));
var shell=RuntimeHelpers.GetUninitializedObject(assembly.GetType("ForgeArenaSandbox.NativeClientShell",true)!);Set(shell,"_rulesSession","current");Set(shell,"_matchRequest",Guid.NewGuid().ToString());Set(shell,"_reportedBridgeFailures",new HashSet<string>());
var report=shell.GetType().GetMethod("ReportBridgeFailure")!;
void Report(string? session,string message,bool recoverable=false)=>report.Invoke(shell,new object?[]{session,message,recoverable});
Report("stale","old failure");Check("Foreign match errors are ignored",Get(shell,"_pendingBridgeFailure")==null);
Report("current","actual action rejection",true);var pending=((string session,string message,bool recoverable))Get(shell,"_pendingBridgeFailure")!;Check("Current rejection is retained for a Continue notice",pending.session=="current" && pending.recoverable);
Set(shell,"_pendingBridgeFailure",null);((HashSet<string>)Get(shell,"_reportedBridgeFailures")!).Add("current\nseen");Report("current","seen");Check("Repeated failures do not spam dialogs",Get(shell,"_pendingBridgeFailure")==null);
Set(shell,"_returning",true);Report("current","during exit");Check("Return Home cannot be interrupted by another error notice",Get(shell,"_pendingBridgeFailure")==null);Set(shell,"_returning",false);
Report(null,"constructor failure");Check("Constructor failures use the established rules session",Get(shell,"_pendingBridgeFailure")!=null);Set(shell,"_pendingBridgeFailure",null);Set(shell,"_rulesSession",null);Report(null,"unowned failure");Check("No rules session means no bridge notice",Get(shell,"_pendingBridgeFailure")==null);
var result=new{checks=checks.Count,passed=checks,allocatedBytesPerNotice=perNotice,scope="Compiled product notice projection and error ownership. No native dialog rendering or gameplay."};File.WriteAllText(args[3],JsonConvert.SerializeObject(result,Formatting.Indented));Console.WriteLine(JsonConvert.SerializeObject(result));
