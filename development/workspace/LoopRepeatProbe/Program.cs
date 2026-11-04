using System;
using System.IO;
using System.Linq;
using Google.Protobuf;
using Newtonsoft.Json.Linq;
using ForgeArenaSandbox;
using Wotc.Mtgo.Gre.External.Messaging;

// Replays observed accepted native commands only to test the repeat guard.
// Positive gameplay proof belongs to verify_recorded_loops, not this reader.
var rows=File.ReadLines(Path.Combine(args[0],"native-worker","native-model.jsonl")).Select(JObject.Parse).ToArray();
var initial=(JObject)JObject.Parse(File.ReadAllText(Path.Combine(args[0],"native-worker","ready.json")))["state"]!;
JObject current=initial;int checks=0;
string expectedKind=args.Length>1?args[1]:"mana";
void Check(string name,bool value){if(!value)throw new Exception(name);checks++;Console.WriteLine(name);}
RecordedLoop Replay(bool quietPasses=false)
{
    current=initial;var loop=new RecordedLoop(_=>"Observed ability");double now=0;
    foreach(var row in rows)
    {
        if((string?)row["kind"]=="command-submitted")
        {
            var command=JsonParser.Default.Parse<ClientToGREMessage>(row["value"]!["nativeMessage"]!.ToString());
            if(quietPasses && command.Type==ClientMessageType.PerformActionResp && command.PerformActionResp.Actions.Count==1 && command.PerformActionResp.Actions[0].ActionType==ActionType.Pass)loop.RecordQuietPass(current,now++);
            else loop.Begin(command,current,now++);
        }
        if((string?)row["kind"]!="command-complete")continue;
        current=(JObject)row["value"]!["state"]!;loop.Complete(current,true,now++);
        if(loop.Available(current) && (string?)loop.Snapshot(current)["kind"]==expectedKind)return loop;
    }
    throw new Exception("No observed complete "+expectedKind+" loop");
}
foreach(var mutation in new (string Name,Action<JObject> Change)[]{
    ("life",s=>s["life"]=(int)s["life"]!-1),
    ("opponent life",s=>s["opponentLife"]=(int)s["opponentLife"]!-1),
    ("phase",s=>s["phase"]="MAIN2"),
    ("turn",s=>s["turn"]=(int)s["turn"]!+1),
    ("permanent tapped state",s=>s["battlefield"]![0]!["tapped"]=!(bool)s["battlefield"]![0]!["tapped"]!),
    ("permanent controller",s=>s["battlefield"]![0]!["controller"]=2),
    ("library object",s=>((JArray)s["hidden"]!).RemoveAt(0)),
    ("new decision",s=>s["decision"]=new JObject{["kind"]="choice"}),
    ("new counter",s=>s["battlefield"]![0]!["counters"]=new JArray(new JObject{["type"]="P1P1",["count"]=1}))})
{
    var loop=Replay();loop.Start(100,current,50);var changed=(JObject)current.DeepClone();mutation.Change(changed);bool sent=false;loop.Tick(changed,true,false,51,_=>{sent=true;return true;});Check("Stops before submitting after changed "+mutation.Name,!loop.Running && !sent);
}
{
    var loop=Replay();foreach(int count in new[]{-1,0,1001}){bool rejected=false;try{loop.Start(count,current,50);}catch(ArgumentOutOfRangeException){rejected=true;}Check("Rejects count "+count,rejected && !loop.Running);}
    loop.Start(100,current,50);int sent=0;loop.Tick(current,false,false,51,_=>{sent++;return true;});Check("Waits for actual presentation",sent==0);
    loop.Tick(current,true,true,52,_=>{sent++;return true;});Check("Never submits for another player",sent==0);
    loop.Tick(current,true,false,53,_=>{sent++;return true;});loop.Tick(current,true,false,54,_=>{sent++;return true;});Check("No retry of an uncertain native submission",sent==1);
    loop.Tick(current,true,false,100,_=>{sent++;return true;});Check("Times out without retry",sent==1 && !loop.Running);
    loop=Replay();loop.Start(100,current,50);loop.Stop("Player stop");loop.Tick(current,true,false,51,_=>{sent++;return true;});Check("Stop leaves completed work and sends no new action",sent==1 && !loop.Running);loop.ReleasePriority();Check("Explicit yield releases held priority",!loop.HoldPriority);
    loop=Replay();loop.Start(100,current,50);string firstRun=loop.RunId;loop.Stop("Player stop");loop.Start(100,current,51);Check("Same-count batches receive distinct identities",loop.RunId!=firstRun && loop.Requested==100 && loop.Completed==0);
    loop=Replay();loop.Start(100,current,50);loop.Tick(current,true,false,51,command=>{loop.Begin(command,current,51);return true;});var random=(JObject)current.DeepClone();var events=(JArray?)random["events"]??new JArray();long eventId=events.Select(e=>(long)e["id"]!).DefaultIfEmpty().Max()+1;events.Add(new JObject{["id"]=eventId,["kind"]="coin-flip"});random["events"]=events;loop.Complete(random,true,52);Check("An unexpected random result interrupts rather than extrapolating",!loop.Running && loop.Message.Contains("random"));
}
{
    var loop=Replay();string label=(string)loop.Snapshot(current)["label"]!;var changed=(JObject)current.DeepClone();changed["phase"]="MAIN2";var pass=new ClientToGREMessage{Type=ClientMessageType.PerformActionResp,PerformActionResp=new PerformActionResp()};pass.PerformActionResp.Actions.Add(new Wotc.Mtgo.Gre.External.Messaging.Action{ActionType=ActionType.Pass});loop.Begin(pass,current,50);loop.Complete(changed,true,51);var shown=loop.Snapshot(changed);Check("Panel remains visible after its sequence becomes unavailable",(bool)shown["visible"]! && !(bool)shown["available"]! && (string?)shown["label"]==label);Check("A new match does not inherit the prior panel",!(bool)new RecordedLoop(_=>"Unused").Snapshot(current)["visible"]!);
}
{
    var loop=Replay(true);Check("Accepted automatic passes remain in the learned cycle",loop.Available(current) && (string?)loop.Snapshot(current)["kind"]==expectedKind);
}
{
    var panel=new LoopPanelVisibility();panel.Observe(false,0);Check("New detected loop can stay expanded during preparation",!panel.Collapsed);panel.Close();panel.Observe(false,0);Check("Manual dismissal stays collapsed",panel.Collapsed);panel.Open();panel.Observe(false,0);Check("Launcher reopens the same panel",!panel.Collapsed);panel.Observe(true,100);Check("Running loop shows progress controls",!panel.Collapsed);panel.Observe(false,100);Check("Stop or completion collapses the panel",panel.Collapsed);panel.Open();panel.Observe(false,100);Check("Old result does not repeatedly close a reopened panel",!panel.Collapsed);panel=new LoopPanelVisibility();panel.Observe(false,100);Check("Repairing an already-stopped client does not reopen its old menu",panel.Collapsed);
}
Console.WriteLine("Passed "+checks+" guard checks");
