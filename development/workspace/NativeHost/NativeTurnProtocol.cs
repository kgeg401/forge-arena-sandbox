using System;
using System.Linq;
using Newtonsoft.Json.Linq;
using Wotc.Mtgo.Gre.External.Messaging;

namespace ForgeArenaSandbox;

// Protocol shapes checked against owned Arena captures and annotation parsers.
// These describe presentation only; Forge still owns progression and legality.
internal static class NativeTurnProtocol
{
    internal static (Phase Phase,Step Step) Location(string phase) => phase switch
    {
        "PREGAME"=>(Phase.Beginning,Step.None),
        "UNTAP"=>(Phase.Beginning,Step.Untap),
        "UPKEEP"=>(Phase.Beginning,Step.Upkeep),
        "DRAW"=>(Phase.Beginning,Step.Draw),
        "MAIN1"=>(Phase.Main1,Step.None),
        "COMBAT_BEGIN"=>(Phase.Combat,Step.BeginCombat),
        "COMBAT_DECLARE_ATTACKERS"=>(Phase.Combat,Step.DeclareAttack),
        "COMBAT_DECLARE_BLOCKERS"=>(Phase.Combat,Step.DeclareBlock),
        "COMBAT_FIRST_STRIKE_DAMAGE"=>(Phase.Combat,Step.FirstStrikeDamage),
        "COMBAT_DAMAGE"=>(Phase.Combat,Step.CombatDamage),
        "COMBAT_END"=>(Phase.Combat,Step.EndCombat),
        "MAIN2"=>(Phase.Main2,Step.None),
        "END_OF_TURN"=>(Phase.Ending,Step.End),
        "CLEANUP"=>(Phase.Ending,Step.Cleanup),
        _=>throw new NotSupportedException("Unmapped Forge phase: "+phase)
    };

    internal static JObject Info(JObject state)
    {
        string current=(string)state["phase"]!;var location=Location(current);
        var result=new JObject{["phase"]="Phase_"+location.Phase,["turnNumber"]=(int)state["turn"]!,["activePlayer"]=(int)state["activeSeat"]!,["priorityPlayer"]=(int)state["prioritySeat"]!,["decisionPlayer"]=1};
        // Explicit None clears an earlier step in a native diff.
        result["step"]="Step_"+location.Step;
        // Native Next/To Combat/End Turn button presentation depends on these
        // fields; leaving them absent gives a generic Pass at every boundary.
        string? next=current switch
        {
            "UNTAP"=>"UPKEEP","UPKEEP"=>"DRAW","DRAW"=>"MAIN1",
            "MAIN1"=>"COMBAT_BEGIN","COMBAT_BEGIN"=>"COMBAT_DECLARE_ATTACKERS",
            "COMBAT_DECLARE_ATTACKERS"=>((JArray)state["battlefield"]!).Any(c=>(int?)c["attackTarget"]>0 || (int?)c["attackTargetForgeId"]>0)?"COMBAT_DECLARE_BLOCKERS":"COMBAT_END",
            "COMBAT_FIRST_STRIKE_DAMAGE"=>"COMBAT_DAMAGE","COMBAT_DAMAGE"=>"COMBAT_END",
            "COMBAT_END"=>"MAIN2","MAIN2"=>"END_OF_TURN","END_OF_TURN"=>"CLEANUP",
            _=>null
        };
        if(next!=null){var hint=Location(next);result["nextPhase"]="Phase_"+hint.Phase;result["nextStep"]="Step_"+hint.Step;}
        else{result["nextPhase"]="Phase_None";result["nextStep"]="Step_None";}
        return result;
    }

    internal static JArray Changes(JObject? previous,JObject current,ref int annotationId)
    {
        var result=new JArray();
        if((string?)current["stage"]!="Play" || (int)current["turn"]!<=0)return result;
        bool newTurn=previous==null || (string?)previous["stage"]!="Play" || (int?)previous["turn"]!=(int?)current["turn"] || (int?)previous["activeSeat"]!=(int?)current["activeSeat"];
        int active=(int)current["activeSeat"]!;
        if(newTurn)result.Add(new JObject{["id"]=annotationId++,["affectorId"]=active,["affectedIds"]=new JArray(active),["type"]=new JArray("AnnotationType_NewTurnStarted")});
        if(newTurn || (string?)previous?["phase"]!=(string?)current["phase"])
        {
            var location=Location((string)current["phase"]!);
            JObject Detail(string key,int value)=>new JObject{["key"]=key,["type"]="KeyValuePairValueType_int32",["valueInt32"]=new JArray(value)};
            result.Add(new JObject{["id"]=annotationId++,["affectedIds"]=new JArray(active),["type"]=new JArray("AnnotationType_PhaseOrStepModified"),["details"]=new JArray(Detail("phase",(int)location.Phase),Detail("step",(int)location.Step))});
        }
        return result;
    }
}
