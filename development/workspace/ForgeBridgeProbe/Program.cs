using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.Loader;
using System.Threading;
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
        if(args.Length!=4)throw new ArgumentException("ForgeBridgeProbe <managed-dir> <empty-state-fixture> <input-json> <report-json>");
        string managed=Path.GetFullPath(args[0]);
        AssemblyLoadContext.Default.Resolving+=(_,name)=>{var p=Path.Combine(managed,name.Name+".dll");return File.Exists(p)?AssemblyLoadContext.Default.LoadFromAssemblyPath(p):null;};
        return Run(args);
    }
    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static int Run(string[] args)
    {
        var input=JObject.Parse(File.ReadAllText(args[2]));string root=(string)input["labRoot"]!,ipc=(string)input["researchIpc"]!;
        if((bool?)JObject.Parse(File.ReadAllText(Path.Combine(root,"bridge-card-manifest.json")))["researchOnly"]!=true || File.Exists(Path.Combine(root,"MTGA.exe")))throw new InvalidOperationException("Headless bridge probe requires an independent research lab without a game executable");
        string fixture=Path.Combine(root,"board-fixture.json");if(!File.Exists(fixture))File.Copy(args[1],fixture);
        var state=JObject.Parse(File.ReadAllText(Path.Combine(ipc,"state.json")));var decision=(JObject)state["decision"]!;
        if(!JToken.DeepEquals(decision,input["decision"]))throw new InvalidOperationException("Forge pending choice changed before native probe attached");
        var checks=new List<string>();var updates=new JArray();uint? presented=null;BaseUserRequest? interaction=null;MtgGameState? latest=null;
        void Check(string label,bool passed){if(!passed)throw new InvalidOperationException(label);checks.Add(label);}
        using var gre=new GreInterface(NullCardDatabaseAdapter.Default,null,null,true,null);
        var local=new LocalGreConnection();local.MessageReceived+=gre.OnMessageReceived;local.Connect(null!);local.ConnectToGRE(LocalGreConnection.LocalUri,local.MatchId);
        void Drain()
        {
            for(int i=0;i<8;i++)
            {
                local.ProcessMessages();
                gre.ProcessQueues();
                foreach(var item in gre.RetrieveClientUpdates())if(item is GreClient.Rules.GameStateUpdate update)
                {
                    latest=update.NewState;presented=latest.Id;if(update.Interaction!=null)interaction=update.Interaction;
                    updates.Add(new JObject{["stateId"]=latest.Id,["interaction"]=update.Interaction?.GetType().Name,["events"]=new JArray(update.Changes.Select(c=>c.GetType().Name)),["cardIdentities"]=new JArray(latest.AllCards.Select(p=>new JObject{["id"]=p.Key,["grpId"]=p.Value.BaseGrpId}))});
                }
            }
        }
        var bridge=new ForgeLandBridge(root,local,_=>{},()=>presented,()=>false,ipc);
        void CheckCounters(JObject snapshot)
        {
            foreach(var card in new[]{"hand","battlefield","stack","graveyard","command","exile"}.SelectMany(k=>(JArray?)snapshot[k]??new JArray()))
            {
                uint id=checked((uint)bridge.ResearchInstanceId((int)card["forgeId"]!));
                if(!latest!.AllCards.TryGetValue(id,out var native))continue;
                var expected=((JArray?)card["counters"]??new JArray()).ToDictionary(c=>SharedCounterProtocol.Type((string)c["type"]!),c=>(int)c["count"]!);
                Check("Native card counters exactly match Forge's public counter totals",native.Counters.Count==expected.Count && expected.All(p=>native.Counters.TryGetValue(p.Key,out int count) && count==p.Value));
            }
        }
        try
        {
            bridge.Start();Drain();Check("Real bridge created the native shared interaction",interaction!=null);
            CheckCounters(state);
            var all=new[]{"hand","battlefield","stack","graveyard","command","exile","hidden","stackAbilities"}.SelectMany(k=>(JArray?)state[k]??new JArray()).ToDictionary(c=>(int)c["forgeId"]!,c=>(int)c["arenaId"]!);
            var sourceCards=new[]{"hand","battlefield","stack","graveyard","command","exile","hidden","stackAbilities"}.SelectMany(k=>(JArray?)state[k]??new JArray()).ToArray();
            var privateViews=SharedChoiceVisibility.Views(state,sourceCards).Where(c=>(bool?)c["privateChoice"]==true).ToArray();
            var manifest=JObject.Parse(File.ReadAllText(Path.Combine(root,"bridge-card-manifest.json")));
            foreach(var view in privateViews)
            {
                int forge=(int)view["forgeId"]!;uint native=checked((uint)all[forge]);uint expected=(uint)manifest["cards"]![(string)view["name"]!]!["grpId"]!;
                Check("Native model receives only the explicitly peeked identity",latest!.AllCards.TryGetValue(native,out var card) && card.BaseGrpId==expected);
            }
            NativeChoiceDriver.SubmitDecision(interaction!,decision,(JArray)input["assignments"]!,id=>all[id]);
            var response=gre.DequeueOutgoingMessage()??throw new InvalidOperationException("Native interaction emitted no response");
            local.SendMessage(response);
            string submitted=bridge.PendingResearchRequestId??throw new InvalidOperationException("Bridge did not create an IPC request");
            // Forge is running in its independent owner process, not replayed.
            // Wait only for the answer we just submitted and then parse the real
            // resulting state through the production adapter's Poll/AdoptState.
            string? acceptedId=null;JObject? accepted=null;var end=DateTime.UtcNow.AddSeconds(10);
            while(DateTime.UtcNow<end)
            {
                string file=Path.Combine(ipc,"responses",submitted+".json");
                if(File.Exists(file))
                {
                    var reply=JObject.Parse(File.ReadAllText(file));
                    if((string?)reply["state"]?["session"]==(string?)state["session"] && (bool?)reply["accepted"]==true){acceptedId=(string)reply["id"]!;accepted=reply;}
                }
                bridge.Poll();Drain();if(accepted!=null)break;Thread.Sleep(10);
            }
            Check("Actual Forge accepted the native response through the bridge",acceptedId!=null);
            Check("Bridge adopted and parsed the resulting Forge state",updates.Count>=2 && string.IsNullOrEmpty(bridge.Gap));
            var after=(JObject)accepted!["state"]!;
            CheckCounters(after);
            var afterCards=new[]{"hand","battlefield","stack","graveyard","command","exile","hidden","stackAbilities"}.SelectMany(k=>(JArray?)after[k]??new JArray()).ToArray();
            var stillVisible=SharedChoiceVisibility.Views(after,afterCards).Select(c=>(int)c["forgeId"]!).ToHashSet();
            foreach(var view in privateViews.Where(c=>!stillVisible.Contains((int)c["forgeId"]!) && afterCards.Any(n=>(int)n["forgeId"]! == (int)c["forgeId"]! && (string?)n["zone"]=="Library")))
                Check("Native model conceals temporary library identity after the choice",latest!.AllCards.TryGetValue(checked((uint)all[(int)view["forgeId"]!]),out var card) && card.BaseGrpId==0);
            var report=new JObject{["passed"]=true,["checks"]=new JArray(checks),["submittedRequestId"]=acceptedId,["assignments"]=input["assignments"]!.DeepClone(),["nativeResponse"]=JObject.Parse(response.ToString()),["updates"]=updates,["scope"]="Live isolated Forge -> production C# adapter -> shipped Arena parser/handler -> adapter -> Forge -> native parser. Null art database; no Unity or rendered acceptance."};
            File.WriteAllText(args[3],report.ToString(Formatting.Indented));Console.WriteLine(new JObject{["passed"]=true,["checks"]=checks.Count,["updates"]=updates.Count}.ToString(Formatting.None));return 0;
        }
        finally{bridge.Detach();local.Close(Wizards.Arena.TcpConnection.TcpConnectionCloseType.NormalClosure,"Headless bridge probe complete");}
    }
}
