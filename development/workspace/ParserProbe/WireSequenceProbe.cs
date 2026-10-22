using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text.Json;
using GreClient.Rules;
using Wotc.Mtga.Cards.Database;
using Wotc.Mtgo.Gre.External.Messaging;

internal static class WireSequenceProbe
{
    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    public static int Run(string path,string output)
    {
        using var gre=new GreInterface(NullCardDatabaseAdapter.Default,null,null,true,null);
        var states=new List<object>();var events=new List<object>();var names=new List<string>();
        int amount=0;var results=new List<object>();
        foreach(var line in File.ReadLines(path))
        {
            using var document=JsonDocument.Parse(line);var root=document.RootElement;
            if(root.GetProperty("direction").GetString()!="incoming")continue;
            gre.OnMessageReceived(GREToClientMessage.Parser.ParseJson(root.GetProperty("message").GetRawText()));gre.ProcessQueues();
            foreach(var update in gre.RetrieveClientUpdates())if(update is GreClient.Rules.GameStateUpdate state)
            {
                states.Add(new{id=state.NewState.Id,life=state.NewState.Players.Select(p=>p.LifeTotal).ToArray(),commanders=state.NewState.Players.Select(p=>p.CommanderIds.ToArray()).ToArray(),interaction=state.Interaction?.GetType().Name,stage=state.NewState.Stage.ToString(),stack=state.NewState.Stack?.CardIds.ToArray()});
                foreach(var e in state.Changes)
                {
                    names.Add(e.GetType().Name);
                    if(e is DamageDealtEvent damage){amount+=(int)damage.Amount;events.Add(new{kind="damage",amount=damage.Amount,source=damage.Damager.InstanceId,target=damage.Victim.InstanceId,type=damage.Type.ToString(),sourceGrpId=damage.Damager.BaseGrpId});}
                    if(e is UpdatePlayerLifeTotal life)events.Add(new{kind="life",state=state.NewState.Id,source=life.Affector,target=life.Player.InstanceId,amount=life.LifeChange,annotation=life.GeneratedByAnnotation});
                    if(e is ZoneChangeEvent zone)events.Add(new{kind="zone",state=state.NewState.Id,card=zone.Id,from=zone.OldZone?.Type.ToString(),to=zone.NewZone?.Type.ToString(),reason=zone.Reason.ToString(),source=zone.InstigatorId});
                    if(e is GameEndEvent end)results.Add(new{result=end.Result.ToString(),loser=end.Loser.ToString(),scope=end.Scope.ToString()});
                }
            }
        }
        if(states.Count==0)throw new Exception("No native state updates parsed");
        var report=new{scope="Installed parser replay of recorded incoming bridge messages; no UI/render proof",states,damageTotal=amount,events,results,eventTypes=names.Distinct().ToArray()};
        File.WriteAllText(output,JsonSerializer.Serialize(report,new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine(JsonSerializer.Serialize(new{states=states.Count,damageTotal=amount,gameEnds=results.Count,report=output}));return 0;
    }
}
