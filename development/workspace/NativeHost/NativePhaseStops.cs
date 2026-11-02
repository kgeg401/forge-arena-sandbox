using System;
using System.Collections.Generic;
using System.Linq;
using Wotc.Mtgo.Gre.External.Messaging;

namespace ForgeArenaSandbox;

// Original phase-ladder messages contain Set/Clear commands scoped to a side.
// Protobuf MergeFrom appends those commands; it does not maintain stop state.
internal static class NativePhaseStops
{
    internal static void Merge(SettingsMessage current,SettingsMessage update)
    {
        var permanent=Entries(current.Stops,update.Stops,update.ClearAllStops==SettingStatus.Set);
        var temporary=Entries(current.TransientStops,update.TransientStops,update.ClearAllStops==SettingStatus.Set);
        current.MergeFrom(update);
        current.Stops.Clear();current.Stops.Add(permanent);
        current.TransientStops.Clear();current.TransientStops.Add(temporary);
    }

    private static Stop[] Entries(IEnumerable<Stop> prior,IEnumerable<Stop> updates,bool clear)
    {
        var values=new Dictionary<(StopType,SettingScope),Stop>();
        foreach(var stop in prior.Concat(updates))
        {
            if(!Enum.IsDefined(typeof(StopType),stop.StopType) || !Enum.IsDefined(typeof(SettingScope),stop.AppliesTo) || !Enum.IsDefined(typeof(SettingStatus),stop.Status))throw new InvalidOperationException("Unknown native phase-stop command");
            if(stop.StopType==StopType.None || stop.AppliesTo==SettingScope.None || stop.Status==SettingStatus.None)continue;
            if(stop.AppliesTo is not (SettingScope.Team or SettingScope.Opponents or SettingScope.AnyPlayer))throw new InvalidOperationException("Unsupported native phase-stop scope");
        }
        void Apply(Stop stop,bool reset)
        {
            if(stop.StopType==StopType.None || stop.AppliesTo==SettingScope.None || stop.Status==SettingStatus.None)return;
            foreach(var scope in stop.AppliesTo==SettingScope.AnyPlayer?new[]{SettingScope.Team,SettingScope.Opponents}:new[]{stop.AppliesTo})
                values[(stop.StopType,scope)]=new Stop{StopType=stop.StopType,AppliesTo=scope,Status=reset?SettingStatus.Clear:stop.Status};
        }
        foreach(var stop in prior)Apply(stop,clear);
        foreach(var stop in updates)Apply(stop,false);
        return values.Values.ToArray();
    }

    internal static bool Holds(SettingsMessage settings,string phase,int activeSeat)
    {
        var type=Type(phase);
        return type!=StopType.None && settings.Stops.Concat(settings.TransientStops).Any(s=>s.Status==SettingStatus.Set && s.StopType==type && Applies(s,activeSeat));
    }

    internal static bool LeavePhase(SettingsMessage settings,string phase,int activeSeat,int turn,string nextPhase,int nextSeat,int nextTurn)
    {
        if(phase==nextPhase && activeSeat==nextSeat && turn==nextTurn)return false;
        bool changed=false;var type=Type(phase);
        foreach(var stop in settings.TransientStops)if(stop.Status==SettingStatus.Set && stop.StopType==type && Applies(stop,activeSeat)){stop.Status=SettingStatus.Clear;changed=true;}
        return changed;
    }

    private static bool Applies(Stop stop,int seat)=>stop.AppliesTo==SettingScope.AnyPlayer || stop.AppliesTo==(seat==1?SettingScope.Team:SettingScope.Opponents);
    private static StopType Type(string phase)=>phase switch
    {
        "UPKEEP"=>StopType.UpkeepStep,"DRAW"=>StopType.DrawStep,"MAIN1"=>StopType.PrecombatMainPhase,
        "COMBAT_BEGIN"=>StopType.BeginCombatStep,"COMBAT_DECLARE_ATTACKERS"=>StopType.DeclareAttackersStep,"COMBAT_DECLARE_BLOCKERS"=>StopType.DeclareBlockersStep,
        "COMBAT_FIRST_STRIKE_DAMAGE"=>StopType.FirstStrikeDamageStep,"COMBAT_DAMAGE"=>StopType.CombatDamageStep,"COMBAT_END"=>StopType.EndCombatStep,
        "MAIN2"=>StopType.PostcombatMainPhase,"END_OF_TURN"=>StopType.EndStep,_=>StopType.None
    };
}
