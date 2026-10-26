using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.Loader;
using System.Threading;
using ForgeArenaSandbox;
using GreClient.Rules;
using Newtonsoft.Json.Linq;
using Wotc.Mtga.Cards.Database;
using Wotc.Mtgo.Gre.External.Messaging;

internal static class Program
{
    private static int Main(string[] args)
    {
        if(args.Length!=6)throw new ArgumentException("TurnFlowProbe <managed> <research-lab> <ipc> <fixture> <flow|combat|stop|response|no-response> <report>");
        string managed=Path.GetFullPath(args[0]);
        AssemblyLoadContext.Default.Resolving+=(_,name)=>{string path=Path.Combine(managed,name.Name+".dll");return File.Exists(path)?AssemblyLoadContext.Default.LoadFromAssemblyPath(path):null;};
        return Run(args);
    }

    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static int Run(string[] args)
    {
        string root=args[1],ipc=args[2],mode=args[4];
        if((bool?)JObject.Parse(File.ReadAllText(Path.Combine(root,"bridge-card-manifest.json")))["researchOnly"]!=true || File.Exists(Path.Combine(root,"MTGA.exe")))throw new InvalidOperationException("Private headless runtime required");
        if(!File.Exists(Path.Combine(root,"board-fixture.json")))File.Copy(args[3],Path.Combine(root,"board-fixture.json"));
        var checks=new List<string>();var passes=new JArray();var transitions=new JArray();var nativeEvents=new List<string>();
        void Check(string text,bool condition){if(!condition)throw new InvalidOperationException(text);checks.Add(text);}
        double clock=0;int schedulerCalls=0;var pacing=new AutomaticPassPacing(()=>clock);
        bool Submit(bool accepted){schedulerCalls++;return accepted;}
        Check("Ready request submits immediately without a phase dwell",pacing.TrySubmit(1,1,()=>Submit(true)));
        for(int i=0;i<50;i++)pacing.TrySubmit(1,1,()=>Submit(true));
        Check("Accepted native request is submitted only once",schedulerCalls==1);
        Check("Next state has no inherited timer",pacing.TrySubmit(2,2,()=>Submit(true)));
        Check("A new request in the same state has no inherited timer",pacing.TrySubmit(2,3,()=>Submit(true)));
        Check("Unready workflow does not count as a submitted pass",!pacing.TrySubmit(3,4,()=>Submit(false)));
        int beforeRetry=schedulerCalls;clock=.049;pacing.TrySubmit(3,4,()=>Submit(true));
        Check("Unready workflow retries are bounded",schedulerCalls==beforeRetry);
        clock=.051;Check("Workflow readiness can recover after 50 ms",pacing.TrySubmit(3,4,()=>Submit(true)));
        Check("New state bypasses the prior workflow retry timer",pacing.TrySubmit(4,5,()=>Submit(true)));

        using var gre=new GreInterface(NullCardDatabaseAdapter.Default,null,null,true,null);
        var local=new LocalGreConnection();local.MessageReceived+=gre.OnMessageReceived;local.Connect(null!);local.ConnectToGRE(LocalGreConnection.LocalUri,local.MatchId);
        uint? presented=null;BaseUserRequest? request=null;MtgGameState? latest=null;
        bool presentationReady=true,workflowReady=true;int attempts=0;long presentedAt=0;
        var timer=Stopwatch.StartNew();ForgeLandBridge? bridge=null;
        void Drain()
        {
            for(int i=0;i<8;i++)
            {
                local.ProcessMessages();gre.ProcessQueues();
                foreach(var item in gre.RetrieveClientUpdates())if(item is GreClient.Rules.GameStateUpdate update)
                {
                    latest=update.NewState;presented=latest.Id;request=update.Interaction;presentedAt=timer.ElapsedTicks;
                    nativeEvents.AddRange(update.Changes.Select(c=>c.GetType().Name));
                    transitions.Add(new JObject{["nativeStateId"]=presented,["interaction"]=request?.GetType().Name,["hasInteraction"]=request!=null,["phase"]=latest.CurrentPhase.ToString(),["step"]=latest.CurrentStep.ToString(),["nextPhase"]=latest.NextPhase.ToString(),["nextStep"]=latest.NextStep.ToString(),["events"]=new JArray(update.Changes.Select(c=>c.GetType().Name))});
                }
            }
        }
        void Forward()
        {
            var message=gre.DequeueOutgoingMessage()??throw new InvalidOperationException("Native handler emitted no message");local.SendMessage(message);
        }
        bool AutoPass()
        {
            attempts++;
            if(!workflowReady || request is not ActionsAvailableRequest actions || !actions.CanPass)return false;
            Check("Automatic pass is bound to the presented native request",actions.OriginalMessage.GameStateId==presented);
            passes.Add(new JObject{["phase"]=bridge!.Phase,["turn"]=bridge.Turn,["nativeStateId"]=presented,["requestId"]=actions.OriginalMessage.MsgId,["readyToSubmitMs"]=(timer.ElapsedTicks-presentedAt)*1000.0/Stopwatch.Frequency});
            actions.SubmitPass();Forward();return true;
        }
        bridge=new ForgeLandBridge(root,local,_=>{},()=>presentationReady?presented:null,AutoPass,ipc, mode=="delayed-response" ? ()=>clock : null);
        void Settings(SettingsMessage settings){local.SendMessage(new ClientToGREMessage{Type=ClientMessageType.SetSettingsReq,SetSettingsReq=new SetSettingsReq{Settings=settings}});Drain();}
        void Tick(){bridge.Poll();Drain();if(bridge.Gap!=null)throw new InvalidOperationException(bridge.Gap);}
        void Until(Func<bool> condition)
        {
            var end=timer.Elapsed+TimeSpan.FromSeconds(15);
            while(!condition()){if(timer.Elapsed>end)throw new TimeoutException("Turn progression did not reach its expected boundary");Tick();Thread.Sleep(2);}
        }
        void Manual(ActionType type)
        {
            if(request is not ActionsAvailableRequest actions)throw new InvalidOperationException("Expected native actions");
            if(type==ActionType.Pass)actions.SubmitPass();else actions.SubmitAction(actions.Actions.First(a=>a.ActionType==type));
            uint? old=presented;Forward();Until(()=>presented!=old);
        }
        try
        {
            bridge.Start();Drain();
            if(mode=="delayed-response")
            {
                if(request is not ActionsAvailableRequest available)throw new InvalidOperationException("Fixture must offer a native priority request");
                available.SubmitPass();Forward();
                string pending=bridge.PendingResearchRequestId??throw new InvalidOperationException("No pending request");
                uint? before=presented;
                clock=14.9;Tick();Check("Normal calculation does not show a slow warning",!bridge.RulesCalculationSlow);
                foreach(double elapsed in new[]{15.1,106,600})
                {
                    clock=elapsed;for(int i=0;i<5;i++)Tick();
                    Check("Delayed response remains pending at "+elapsed+" seconds",bridge.PendingResearchRequestId==pending && bridge.Gap==null && presented==before && bridge.RulesCalculationSlow);
                }
                Check("Pending action was never duplicated",Directory.GetFiles(Path.Combine(ipc,"requests"),"*.json").Length==1);
                var state=bridge.ResearchState;
                File.WriteAllText(Path.Combine(ipc,"responses",pending+".json"),new JObject{["id"]=pending,["session"]=bridge.Session,["accepted"]=true,["state"]=state}.ToString());
                Tick();
                Check("Valid late response retires the original request",bridge.PendingResearchRequestId==null && presented!=before && bridge.Gap==null);
                Check("Slow warning clears when the result arrives",!bridge.RulesCalculationSlow && bridge.RulesWaitSeconds==0);
                uint? adopted=presented;for(int i=0;i<10;i++)Tick();Check("Late response applies only once",presented==adopted);
                // A second request must start a fresh timer, and foreign-session
                // responses must remain rejected even after a long wait.
                if(request is not ActionsAvailableRequest next)throw new InvalidOperationException("Missing follow-up priority request");
                next.SubmitPass();Forward();Check("Next request has a fresh wait timer",!bridge.RulesCalculationSlow);
                string second=bridge.PendingResearchRequestId!;
                File.WriteAllText(Path.Combine(ipc,"responses",second+".json"),new JObject{["id"]=second,["session"]="foreign-session",["accepted"]=true,["state"]=state}.ToString());
                bool rejected=false;try{bridge.Poll();}catch(InvalidOperationException){rejected=true;}
                Check("Late-response recovery still rejects a foreign session",rejected && presented==adopted);
                File.WriteAllText(args[5],new JObject{["passed"]=true,["checks"]=new JArray(checks),["scope"]="Real native handlers and adapter, controlled clock and delayed response transport; no live Forge computation or rendered UI."}.ToString());return 0;
            }
            for(int i=0;i<30;i++)Tick();Check("Settings handshake is required before automatic passing",attempts==0);
            Check("Original parser receives a native turn-change event",nativeEvents.Contains("TurnChangeEvent"));
            Check("Original parser receives a native phase-change event",nativeEvents.Contains("GamePhaseChangeEvent"));
            if(mode=="yield" || mode=="yield-turn")
            {
                int hand=bridge.HandCount;Settings(new SettingsMessage{AutoPassOption=mode=="yield"?AutoPassOption.UnlessOpponentAction:AutoPassOption.Turn,DefaultAutoPassOption=AutoPassOption.ResolveMyStackEffects});
                Tick();Check("Native end-turn mode passes available actions by player choice",passes.Count==1);
                Until(()=>bridge.Turn>=3 && bridge.ActiveSeat==1 && bridge.Phase=="MAIN1");
                Check("End-turn mode expires before the next playable turn",bridge.ResearchState["legalLands"]!.HasValues && bridge.LandsPlayed==0 && bridge.HandCount==hand+1);
                int before=passes.Count;for(int i=0;i<30;i++)Tick();Check("End-turn mode does not skip the next playable main phase",passes.Count==before);
                File.WriteAllText(args[5],new JObject{["passed"]=true,["checks"]=new JArray(checks),["nativeUpdates"]=transitions,["scope"]="Original native settings and Forge turns; no rendered UI."}.ToString());return 0;
            }
            if(mode=="response" || mode=="no-response" || mode=="resolve-all")
            {
                var initial=bridge.ResearchState;
                Check("Fixture has a real opponent creature spell on the stack",((JArray)initial["stack"]!).Any(c=>(int)c["owner"]! ==2 && (string?)c["name"]=="Savannah Lions"));
                Check("Forge determines whether the counterspell is payable",initial["legalCasts"]!.HasValues==(mode!="no-response"));
                presentationReady=false;Settings(new SettingsMessage{AutoPassOption=AutoPassOption.Clear,StackAutoPassOption=mode=="resolve-all"?AutoPassOption.ResolveAll:AutoPassOption.Clear});
                for(int i=0;i<30;i++)Tick();Check("Opponent spell waits for presentation",attempts==0);
                presentationReady=true;Tick();
                if(mode=="response")
                {
                    for(int i=0;i<30;i++)Tick();
                    Check("Available counterspell preserves opponent-spell response window",attempts==0 && bridge.ResearchState["stack"]!.HasValues);
                }
                else
                {
                    Check(mode=="resolve-all"?"Player-selected Resolve All passes the response window":"Unanswerable opponent spell passes immediately",passes.Count==1);
                    Until(()=>!bridge.ResearchState["stack"]!.HasValues);
                    Check("Forge resolves the unanswerable creature normally",((JArray)bridge.ResearchState["battlefield"]!).Any(c=>(int)c["owner"]! ==2 && (string?)c["name"]=="Savannah Lions"));
                }
                File.WriteAllText(args[5],new JObject{["passed"]=true,["checks"]=new JArray(checks),["automaticPasses"]=passes,["scope"]="Real Forge stack/payment legality and native handlers; no rendered UI."}.ToString());return 0;
            }
            Settings(new SettingsMessage{AutoPassOption=AutoPassOption.Clear});
            for(int i=0;i<30;i++)Tick();Check("Playable main-phase actions remain a player stop",attempts==0 && bridge.Phase=="MAIN1");
            if(mode=="flow" || mode=="stop")
            {
                Manual(ActionType.Play);
                // Block the ready callback while the original native Cast handler places the spell.
                presentationReady=false;Manual(ActionType.Cast);
                int before=attempts;for(int i=0;i<30;i++)Tick();Check("Unpresented state cannot advance",attempts==before && bridge.ResearchState["stack"]!.HasValues);
                presentationReady=true;
                Settings(new SettingsMessage{AutoPassOption=AutoPassOption.FullControl});
                for(int i=0;i<30;i++)Tick();Check("Full control preserves the response window",attempts==before);
                Settings(new SettingsMessage{AutoPassOption=AutoPassOption.Clear});
                if(mode=="stop")
                {
                    Settings(new SettingsMessage{Stops={new Stop()}});
                    for(int i=0;i<30;i++)Tick();Check("Explicit phase stops preserve the response window",attempts==before);
                    File.WriteAllText(args[5],new JObject{["passed"]=true,["checks"]=new JArray(checks),["automaticPasses"]=passes,["scope"]="Native handler and Forge state; no rendered UI."}.ToString());return 0;
                }
                workflowReady=false;Tick();Check("Applying native workflow does not submit a pass",passes.Count==0);
                workflowReady=true;
                Until(()=>bridge.Turn>=3 && bridge.ActiveSeat==1 && bridge.Phase=="MAIN1");
                int quiet=File.ReadLines(Path.Combine(ipc,"native-wire.jsonl")).Select(JObject.Parse).Count(r=>(string?)r["direction"]=="internal-rules" && (bool?)r["request"]?["automaticRulesStep"]==true);
                Check("Automatic empty steps reach the next playable turn",quiet>=3 && bridge.ResearchState["legalLands"]!.HasValues);
                Check("Empty rules steps do not flash native action workflows",transitions.Count(t=>(bool?)t["hasInteraction"]==false)>=3);
                Check("Main-phase navigation exposes the original To Combat destination",latest!.NextPhase==Phase.Combat && latest.NextStep==Step.BeginCombat);
                Check("Turn and phase annotations continue through automatic progression",nativeEvents.Count(e=>e=="TurnChangeEvent")>=3 && nativeEvents.Count(e=>e=="GamePhaseChangeEvent")>=3);
                Check("Original Forge untap and draw were retained",((JArray)bridge.ResearchState["battlefield"]!).Any(c=>(string?)c["name"]=="Plains" && (bool?)c["tapped"]==false) && ((JArray)bridge.ResearchState["hand"]!).Count==2);
                Check("Original native model follows the final Forge state",latest!=null && latest.Id==presented && latest.GetPlayerById(1).LifeTotal==(int)bridge.ResearchState["life"]!);
                before=passes.Count;for(int i=0;i<30;i++)Tick();Check("Next playable main phase stays stopped",passes.Count==before);
            }
            else if(mode=="combat")
            {
                Manual(ActionType.Pass);Until(()=>bridge.DecisionKind=="attackers");
                int before=passes.Count;for(int i=0;i<30;i++)Tick();Check("Attack declaration remains an explicit player decision",passes.Count==before && request is DeclareAttackerRequest);
            }
            else throw new ArgumentException("Unknown probe mode");
            Check("Each automated native request was retired once",passes.Select(p=>((uint)p["nativeStateId"]!,(uint)p["requestId"]!)).Distinct().Count()==passes.Count);
            File.WriteAllText(args[5],new JObject{["passed"]=true,["checks"]=new JArray(checks),["automaticPasses"]=passes,["nativeUpdates"]=transitions,["nativeEvents"]=new JArray(nativeEvents),["scope"]="Actual Forge and native parser/handlers. Presentation/workflow readiness is simulated; rendered UX timing requires a separate game check."}.ToString());return 0;
        }
        finally{bridge.Detach();local.Close(Wizards.Arena.TcpConnection.TcpConnectionCloseType.NormalClosure,"Turn-flow probe done");}
    }
}
