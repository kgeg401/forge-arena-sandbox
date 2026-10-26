using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using ForgeArenaSandbox;
using GreClient.Rules;
using Wotc.Mtga.Cards.Database;
using Wotc.Mtgo.Gre.External.Messaging;

internal static class Program
{
    private static int Main(string[] args)
    {
        if(args.Length!=4)throw new ArgumentException("ForgeChoiceProbe <managed-dir> <empty-state-fixture> <input-json> <report-json>");
        string managed=Path.GetFullPath(args[0]);
        AssemblyLoadContext.Default.Resolving+=(_,name)=>{var p=Path.Combine(managed,name.Name+".dll");return File.Exists(p)?AssemblyLoadContext.Default.LoadFromAssemblyPath(p):null;};
        return Run(args);
    }
    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static int Run(string[] args)
    {
        var input=JObject.Parse(File.ReadAllText(args[2]));var decision=(JObject)input["decision"]!;var expected=(JArray)input["assignments"]!;
        var spec=(JObject)decision["choice"]!;var options=(JArray)spec["options"]!;var checks=new List<string>();
        void Check(string label,bool passed){if(!passed)throw new InvalidOperationException(label);checks.Add(label);}
        int Id(int forge)=>checked(10000+forge);
        var request=GREToClientMessage.Parser.ParseJson(SharedChoiceProtocol.Request(decision,Id,1,99).ToString(Formatting.None));
        using var gre=new GreInterface(NullCardDatabaseAdapter.Default,null,null,true,null);
        var fixture=(JObject)JObject.Parse(File.ReadAllText(args[1]))["messages"]![0]!.DeepClone();
        fixture["gameStateMessage"]!["pendingMessageCount"]=1;
        fixture["gameStateMessage"]!["gameInfo"]!["stage"]="GameStage_Play";
        fixture["gameStateMessage"]!["turnInfo"]=new JObject{["decisionPlayer"]=1,["activePlayer"]=1,["turnNumber"]=1,["phase"]="Phase_Main1",["step"]="Step_None"};
        gre.OnMessageReceived(GREToClientMessage.Parser.ParseJson(fixture.ToString(Formatting.None)));
        gre.ProcessQueues();
        gre.OnMessageReceived(request);gre.ProcessQueues();
        BaseUserRequest? interaction=null;
        foreach(var update in gre.RetrieveClientUpdates())if(update is GreClient.Rules.GameStateUpdate state && state.Interaction!=null)interaction=state.Interaction;
        Check("Installed parser created an actual native interaction",interaction!=null);
        NativeChoiceDriver.Submit(interaction!,spec,expected,Id);
        var response=gre.DequeueOutgoingMessage()??throw new InvalidOperationException("Native handler emitted no response");
        Check("Native response preserves state and request correlation",response.GameStateId==1 && response.RespId==99);
        var assignments=SharedChoiceProtocol.Response(decision,Id,response,1,99);
        JArray Canonical(JArray values)=>spec["type"]?.ToString()=="partition"?new JArray(((JArray)spec["groups"]!).SelectMany(g=>values.Where(v=>(string?)v["group"]==(string)g!))):values;
        Check("Native response round trip preserves every intended selection and its order",JToken.DeepEquals(Canonical(assignments),Canonical(expected)));
        void Reject(string label,System.Action action){bool rejected=false;try{action();}catch(Exception){rejected=true;}Check(label,rejected);}
        var stale=response.Clone();stale.RespId++;
        Reject("Stale native response is rejected",()=>SharedChoiceProtocol.Response(decision,Id,stale,1,99));
        var wrong=response.Clone();wrong.Type=ClientMessageType.ConcedeReq;
        Reject("Mismatched native response type is rejected",()=>SharedChoiceProtocol.Response(decision,Id,wrong,1,99));
        if(response.Type==ClientMessageType.GroupResp && response.GroupResp.Groups.Any(g=>g.Ids.Count>0))
        {
            var duplicate=response.Clone();var nonempty=duplicate.GroupResp.Groups.First(g=>g.Ids.Count>0);nonempty.Ids.Add(nonempty.Ids[0]);
            Reject("Duplicate grouped identity is rejected",()=>SharedChoiceProtocol.Response(decision,Id,duplicate,1,99));
            var missing=response.Clone();missing.GroupResp.Groups.First(g=>g.Ids.Count>0).Ids.RemoveAt(0);
            Reject("Incomplete grouping is rejected",()=>SharedChoiceProtocol.Response(decision,Id,missing,1,99));
            var foreign=response.Clone();foreign.GroupResp.Groups.First(g=>g.Ids.Count>0).Ids[0]=uint.MaxValue;
            Reject("Foreign grouped identity is rejected",()=>SharedChoiceProtocol.Response(decision,Id,foreign,1,99));
        }
        var report=new JObject{["passed"]=true,["checks"]=new JArray(checks),["interaction"]=interaction!.GetType().Name,["nativeRequest"]=JObject.Parse(request.ToString()),["nativeResponse"]=JObject.Parse(response.ToString()),["assignments"]=assignments,
            ["inputSha256"]=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[2]))).ToLowerInvariant(),["scope"]="Shipped Arena parser and choice-handler round trip only; no Unity, art, localized prompt rendering, animation or network connection."};
        File.WriteAllText(args[3],report.ToString(Formatting.Indented));Console.WriteLine(new JObject{["passed"]=true,["interaction"]=report["interaction"],["checks"]=checks.Count}.ToString(Formatting.None));return 0;
    }
}
