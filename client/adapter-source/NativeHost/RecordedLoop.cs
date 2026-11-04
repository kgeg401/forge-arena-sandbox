using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Wotc.Mtgo.Gre.External.Messaging;

namespace ForgeArenaSandbox;

// Records actual accepted actions. Repeats use the same native request path;
// the rules owner still pays costs, grants priority and resolves every effect.
internal sealed class RecordedLoop
{
    internal const int MaximumRepeats=1000;
    private sealed class Position
    {
        internal string Core="",ResourceCore="",LifeCore="",Choice="",Window="";
        internal int Life;
        internal string[] Stack=Array.Empty<string>();
        internal Dictionary<int,int> Mana=new Dictionary<int,int>();
        internal long Event;
    }
    private sealed class Step
    {
        internal ClientToGREMessage Command=null!;
        internal string Key="";
        internal Position Before=null!,After=null!;
    }
    private sealed class Plan
    {
        internal Step[] Steps=Array.Empty<Step>();
        internal string Core="",Label="";
        internal bool Mana,Prepend;
        internal int LifeGain,AnchorLife;
        internal bool Cycle=>Mana || LifeGain>0;
        internal string[] Anchor=Array.Empty<string>(),Chunk=Array.Empty<string>();
        internal Dictionary<int,int> Gain=new Dictionary<int,int>();
    }
    private readonly List<Step> _history=new List<Step>();
    private readonly Func<ClientToGREMessage,string> _label;
    private Plan? _candidate,_plan;
    private Step? _inflight;
    private bool _inflightAutomatic,_expectingEmission,_awaitBoundary;
    private string _expectedKey="";
    private Position? _cycleStart;
    private string[] _baseStack=Array.Empty<string>();
    private int _step;
    private int _lifeOffset;
    private bool _showResult;
    private string? _lastLabel,_lastKind;
    private double _lastProgress;
    private JObject? _cachedState;
    private Position? _cachedPosition;
    internal bool Running {get;private set;}
    internal bool HoldPriority {get;private set;}
    internal int Requested {get;private set;}
    internal int Completed {get;private set;}
    internal string RunId {get;private set;}="";
    internal string Message {get;private set;}="Perform a mana loop twice, or activate an ability while holding priority.";
    internal RecordedLoop(Func<ClientToGREMessage,string> label){_label=label;}
    internal ClientToGREMessage? FirstCommand=>_candidate?.Steps[0].Command;
    internal void RecordQuietPass(JObject state,double seconds)
    {
        var command=new ClientToGREMessage{Type=ClientMessageType.PerformActionResp,PerformActionResp=new PerformActionResp()};
        command.PerformActionResp.Actions.Add(new Wotc.Mtgo.Gre.External.Messaging.Action{ActionType=ActionType.Pass});
        Begin(command,state,seconds);
    }

    private static string Text(JToken value)=>value.ToString(Formatting.None);
    private static string Fingerprint(JToken value)
    {
        using var hash=SHA256.Create();return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(Text(Canonical(value))))).Replace("-","");
    }
    private static JToken Canonical(JToken value)
    {
        if(value is JObject obj)return new JObject(obj.Properties().OrderBy(p=>p.Name,StringComparer.Ordinal).Select(p=>new JProperty(p.Name,Canonical(p.Value))));
        if(value is JArray array)return new JArray(array.Select(Canonical));
        return value.DeepClone();
    }
    private static string Core(JObject state,bool resourceTaps=false,bool ignoreLife=false)
    {
        var value=new JObject();
        foreach(string key in new[]{"session","phase","turn","activeSeat","life","opponentLife","players","playerCounters","commanderDamage","hand","battlefield","graveyard","exile","command","hidden","horde"})
            if(state[key]!=null)value[key]=state[key]!.DeepClone();
        // Resolved spells briefly retain presentation targets; attachments have their own fields.
        foreach(var zone in value.Properties().Select(p=>p.Value).OfType<JArray>())foreach(var card in zone.OfType<JObject>())card.Remove("targetForgeIds");
        if(resourceTaps && value["battlefield"] is JArray cards)foreach(var card in cards.OfType<JObject>().Where(c=>(int?)c["controller"]==1))card.Remove("tapped");
        if(ignoreLife){value.Remove("life");if(value["players"] is JArray players)foreach(var player in players.OfType<JObject>().Where(p=>(int?)p["seat"]==1))player.Remove("life");}
        return Fingerprint(value);
    }
    private static string Choice(JObject state)
    {
        if(state["decision"] is not JObject decision)return "";
        var value=(JObject)decision.DeepClone();
        void Strip(JToken token)
        {
            if(token is JObject obj){foreach(string key in new[]{"token","parentRequestId","session","state"})obj.Remove(key);foreach(var property in obj.Properties())Strip(property.Value);}
            else if(token is JArray array)foreach(var item in array)Strip(item);
        }
        Strip(value);return Fingerprint(value);
    }
    private static string[] Stack(JObject state)
    {
        var cards=((JArray?)state["stack"]??new JArray()).Concat((JArray?)state["stackAbilities"]??new JArray()).ToDictionary(c=>(int)c["forgeId"]!);
        return ((JArray?)state["stackOrder"]??new JArray()).Select(id=>{
            var card=(JObject)cards[(int)id].DeepClone();
            if((string?)card["objectKind"]=="ability")foreach(string key in new[]{"forgeId","arenaId","stackInstanceId"})card.Remove(key);
            return Text(Canonical(card));
        }).ToArray();
    }
    private static Position Capture(JObject state)=>new Position{Core=Core(state),ResourceCore=Core(state,true),LifeCore=Core(state,ignoreLife:true),Life=(int)state["life"]!,Window=string.Join("|",new[]{"session","turn","phase","activeSeat"}.Select(k=>state[k]?.ToString()??"")),Choice=Choice(state),Stack=Stack(state),Mana=((JArray?)state["mana"]??new JArray()).GroupBy(m=>(int)m["color"]!).ToDictionary(g=>g.Key,g=>g.Sum(m=>(int?)m["count"]??1)),Event=((JArray?)state["events"]??new JArray()).Select(e=>(long)e["id"]!).DefaultIfEmpty().Max()};
    private static string CoreFor(Plan plan,Position position)=>plan.LifeGain>0?position.LifeCore:plan.Mana?position.Core:position.ResourceCore;
    // Adopted states are immutable. Do this work once per rules state, not per UI frame.
    private Position PositionOf(JObject state){if(!ReferenceEquals(_cachedState,state)){_cachedState=state;_cachedPosition=Capture(state);}return _cachedPosition!;}
    private static Dictionary<int,int> Delta(Position before,Position after)=>before.Mana.Keys.Union(after.Mana.Keys).ToDictionary(k=>k,k=>after.Mana.GetValueOrDefault(k)-before.Mana.GetValueOrDefault(k));
    private static bool SameGain(Dictionary<int,int> a,Dictionary<int,int> b)=>a.Keys.Union(b.Keys).All(k=>a.GetValueOrDefault(k)==b.GetValueOrDefault(k));
    private static bool IsActivation(ClientToGREMessage command,ActionType type)=>command.Type==ClientMessageType.PerformActionResp && command.PerformActionResp.Actions.Count==1 && command.PerformActionResp.Actions[0].ActionType==type;
    private static string Key(ClientToGREMessage command)
    {
        if(command.Type==ClientMessageType.PerformActionResp && command.PerformActionResp.Actions.Count==1){var a=command.PerformActionResp.Actions[0];return a.ActionType+":"+a.InstanceId+":"+a.GrpId+":"+a.AbilityGrpId;}
        var copy=command.Clone();copy.GameStateId=0;copy.RespId=0;return copy.ToString();
    }
    private static bool Supported(ClientToGREMessage command,JObject state)
    {
        if(command.Type==ClientMessageType.PerformActionResp)return IsActivation(command,ActionType.Activate) || IsActivation(command,ActionType.ActivateMana) || IsActivation(command,ActionType.Pass);
        if(command.Type==ClientMessageType.SelectNresp)return (string?)state["decision"]?["kind"]=="choice" && (string?)state["decision"]?["choice"]?["type"]=="colors";
        return (command.Type==ClientMessageType.SelectTargetsResp || command.Type==ClientMessageType.SubmitTargetsReq) && (string?)state["decision"]?["kind"]=="targets";
    }
    internal bool Available(JObject state)=>_candidate!=null && !Running && state["decision"]==null && CoreFor(_candidate,PositionOf(state))==_candidate.Core && (_candidate.LifeGain==0 || PositionOf(state).Life==_candidate.AnchorLife) && (_candidate.Cycle?PositionOf(state).Stack.Length==0:PositionOf(state).Stack.SequenceEqual(_candidate.Anchor));
    internal JObject Snapshot(JObject state)
    {
        if(_candidate!=null){_lastLabel=_candidate.Label;_lastKind=_candidate.LifeGain>0?"life":_candidate.Mana?"mana":"stack";}
        bool available=Available(state);
        return new JObject{["runId"]=RunId,["available"]=available,["visible"]=Running || available || _showResult || _lastLabel!=null,["running"]=Running,["holdPriority"]=HoldPriority,["label"]=_candidate?.Label??_lastLabel,["kind"]=_lastKind??"stack",["lifeGainPerCycle"]=_candidate?.LifeGain??0,["requested"]=Requested,["completed"]=Completed,["step"]=_step,["message"]=!Running && !available && !_showResult && _lastLabel!=null?"Finish the same complete cycle twice. Repeat enables when ready.":Message,["maximum"]=MaximumRepeats};
    }
    internal void Begin(ClientToGREMessage command,JObject state,double seconds)
    {
        bool automatic=_expectingEmission && Key(command)==_expectedKey;
        _expectingEmission=false;
        if(!automatic){if(Running)Stop("Stopped by player input. Completed actions remain applied.");HoldPriority=false;_showResult=false;}
        if(!Supported(command,state)){_history.Clear();_candidate=null;_inflight=null;return;}
        // Arm on a nonmana activation: ordinary turn passes and land taps need no board fingerprint.
        if(!automatic && _history.Count==0 && !IsActivation(command,ActionType.Activate)){_inflight=null;return;}
        _inflight=new Step{Command=command.Clone(),Key=Key(command),Before=PositionOf(state)};_inflightAutomatic=automatic;_lastProgress=seconds;
    }
    internal void Complete(JObject state,bool accepted,double seconds)
    {
        var step=_inflight;_inflight=null;if(step==null)return;
        step.After=PositionOf(state);_lastProgress=seconds;
        bool random=((JArray?)state["events"]??new JArray()).Any(e=>(long)e["id"]!>step.Before.Event && (string?)e["kind"]=="coin-flip");
        if(!accepted || random){_history.Clear();_candidate=null;if(Running)Stop(!accepted?"Forge rejected the repeat; no action was retried.":"A random result interrupted this sequence.");return;}
        if(step.Before.Window!=step.After.Window){_history.Clear();_candidate=null;if(Running)Stop("Stopped: the turn or phase changed.");return;}
        if(_inflightAutomatic){if(Running){_step++;if(_step==_plan!.Steps.Length)_awaitBoundary=true;}return;}
        _history.Add(step);if(_history.Count>64)_history.RemoveAt(0);
        if(step.After.Choice!="")return;
        FindPlan();
    }
    private void FindPlan()
    {
        var end=_history[_history.Count-1].After;
        for(int length=2;length<=16 && length*2<=_history.Count;length++)
        {
            var first=_history.Skip(_history.Count-length*2).Take(length).ToArray();var second=_history.Skip(_history.Count-length).ToArray();
            if(end.Stack.Length!=0 || first[0].Before.Choice!="" || second[0].Before.Choice!="" || first[0].Before.Stack.Length!=0 || second[0].Before.Stack.Length!=0)continue;
            int lifeGain=end.Life-second[0].Before.Life;
            bool life=lifeGain>0 && lifeGain==second[0].Before.Life-first[0].Before.Life && first[0].Before.LifeCore==end.LifeCore && second[0].Before.LifeCore==end.LifeCore;
            if(!life && (first[0].Before.Core!=end.Core || second[0].Before.Core!=end.Core) || !first.Zip(second,(a,b)=>a.Key==b.Key && a.Before.Choice==b.Before.Choice).All(v=>v))continue;
            if(!second.Any(s=>IsActivation(s.Command,ActionType.Activate)) || !life && !second.Any(s=>IsActivation(s.Command,ActionType.ActivateMana)))continue;
            var gain=Delta(second[0].Before,end);
            if(!life && (gain.Values.Any(v=>v<0) || !gain.Values.Any(v=>v>0)) || !SameGain(gain,Delta(first[0].Before,second[0].Before)))continue;
            _candidate=new Plan{Steps=second,Core=life?end.LifeCore:end.Core,Mana=!life,LifeGain=life?lifeGain:0,AnchorLife=end.Life,Gain=gain,Label=(life?"Life loop: ":"Mana loop: ")+string.Join(" / ",second.Where(s=>s.Command.Type==ClientMessageType.PerformActionResp && !IsActivation(s.Command,ActionType.Pass)).Select(s=>_label(s.Command)).Distinct())};Message=life?"Observed twice. Repeat complete life-gain cycles, paying every cost.":"Observed twice. Repeat additional complete cycles.";return;
        }
        for(int start=_history.Count-1;start>=Math.Max(0,_history.Count-12);start--)
        {
            var steps=_history.Skip(start).ToArray();var head=steps[0];
            if(!IsActivation(head.Command,ActionType.Activate))continue;
            if(steps.Skip(1).Any(s=>s.Command.Type==ClientMessageType.PerformActionResp) || head.Before.Choice!="" || head.Before.ResourceCore!=end.ResourceCore)break;
            if(!Added(head.Before.Stack,end.Stack,out var chunk,out bool prepend) || chunk.Length==0)break;
            if(chunk.Any(s=>{var card=JObject.Parse(s);return (string?)card["objectKind"]!="ability" || (int?)card["controller"]!=1;}))break;
            _candidate=new Plan{Steps=steps,Core=end.ResourceCore,Mana=false,Anchor=end.Stack,Chunk=chunk,Prepend=prepend,Label="Stack repeats: "+_label(head.Command)};Message="Repeat additional activations, paying every cost. Hold priority.";return;
        }
        if(_candidate!=null && (_candidate.Core!=CoreFor(_candidate,end) || (_candidate.LifeGain>0 && _candidate.AnchorLife!=end.Life) || (!_candidate.Cycle && !_candidate.Anchor.SequenceEqual(end.Stack))))_candidate=null;
    }
    private static bool Added(string[] before,string[] after,out string[] added,out bool prepend)
    {
        int count=after.Length-before.Length;added=Array.Empty<string>();prepend=false;if(count<0)return false;
        if(after.Take(before.Length).SequenceEqual(before)){added=after.Skip(before.Length).ToArray();return true;}
        if(after.Skip(count).SequenceEqual(before)){added=after.Take(count).ToArray();prepend=true;return true;}
        return false;
    }
    internal void Start(int count,JObject state,double seconds)
    {
        if(count<1 || count>MaximumRepeats)throw new ArgumentOutOfRangeException(nameof(count),"Enter 1 to "+MaximumRepeats+" additional repeats.");
        if(!Available(state))throw new InvalidOperationException("No unchanged, repeatable sequence is ready.");
        _plan=_candidate;_baseStack=PositionOf(state).Stack;_cycleStart=PositionOf(state);_lifeOffset=_cycleStart.Life-_plan!.Steps[0].Before.Life;_step=0;_awaitBoundary=false;_expectingEmission=false;RunId=Guid.NewGuid().ToString("N");Requested=count;Completed=0;Running=true;HoldPriority=true;_showResult=true;Message="Repeating 0 / "+Requested;_lastProgress=seconds;
    }
    internal void Stop(string reason){Running=false;_expectingEmission=false;_awaitBoundary=false;Message=reason;}
    internal void ReleasePriority(){if(Running)Stop("Stopped by priority settings. Completed actions remain applied.");HoldPriority=false;}
    internal bool Tick(JObject state,bool ready,bool waiting,double seconds,Func<ClientToGREMessage,bool> submit)
    {
        if(!Running)return false;
        if((bool?)state["gameOver"]==true){Stop("Match ended.");return false;}
        if(waiting){_lastProgress=seconds;Message="Waiting for the other player. "+Completed+" / "+Requested;return true;}
        if(seconds-_lastProgress>45){Stop("Paused: no completed action for 45 seconds. No retry was sent.");return false;}
        if(!ready || _expectingEmission || _inflight!=null)return true;
        var plan=_plan!;var now=PositionOf(state);
        if(_awaitBoundary)
        {
            bool matches=CoreFor(plan,now)==plan.Core && now.Choice=="" && (plan.Cycle?now.Stack.Length==0:now.Stack.SequenceEqual(ExpectedStack(plan.Steps[plan.Steps.Length-1].After.Stack,Completed)));
            if(!matches || plan.Cycle && !SameGain(plan.Gain,Delta(_cycleStart!,now)) || plan.LifeGain>0 && now.Life-_cycleStart!.Life!=plan.LifeGain){Stop("Stopped: the loop's board, stack, choice, life or mana result changed. Completed actions remain applied.");return false;}
            Completed++;_step=0;_awaitBoundary=false;_cycleStart=now;Message="Repeated "+Completed+" / "+Requested;_lastProgress=seconds;
            if(Completed==Requested){Running=false;if(!plan.Cycle)plan.Anchor=now.Stack;plan.AnchorLife=now.Life;return false;}
        }
        var next=plan.Steps[_step];now=PositionOf(state);
        bool stackMatches=plan.Cycle?now.Stack.SequenceEqual(next.Before.Stack):now.Stack.SequenceEqual(ExpectedStack(next.Before.Stack,Completed));
        if(CoreFor(plan,now)!=CoreFor(plan,next.Before) || now.Choice!=next.Before.Choice || !stackMatches || plan.LifeGain>0 && now.Life!=next.Before.Life+_lifeOffset+Completed*plan.LifeGain){Stop("Stopped: the next recorded action no longer matches this position.");return false;}
        _expectedKey=next.Key;_expectingEmission=true;
        try{if(!submit(next.Command)){_expectingEmission=false;return true;}}
        catch(InvalidOperationException error){_expectingEmission=false;Stop("Stopped: "+error.Message);return false;}
        _lastProgress=seconds;return true;
    }
    private string[] ExpectedStack(string[] recorded,int completed)
    {
        var plan=_plan!;var original=plan.Steps[0].Before.Stack;
        if(!Added(original,recorded,out var partial,out _))return Array.Empty<string>();
        var repeated=Enumerable.Range(0,completed).SelectMany(_=>plan.Chunk);
        return plan.Prepend?partial.Concat(repeated).Concat(_baseStack).ToArray():_baseStack.Concat(repeated).Concat(partial).ToArray();
    }
}
