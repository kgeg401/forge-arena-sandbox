using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using ForgeArenaSandbox;
using GreClient.Rules;
using Wotc.Mtgo.Gre.External.Messaging;

internal static class NativeChoiceDriver
{
    private static int Integer(JToken? value)
    {
        if(value?.Type!=JTokenType.Integer || (long)value<int.MinValue || (long)value>int.MaxValue)throw new ArgumentException("Choice requires an exact bounded integer");return (int)value;
    }
    private static void Fields(JToken value,params string[] fields)
    {
        if(value is not JObject item || !item.Properties().Select(p=>p.Name).ToHashSet().SetEquals(fields))throw new ArgumentException("Choice contains missing or unexpected fields");
    }
    private static void Validate(JObject spec,JArray assignments)
    {
        string type=(string)spec["type"]!;
        if(type=="number")
        {
            if(assignments.Count!=1)throw new ArgumentException("Choose exactly one number");Fields(assignments[0],"number");int value=Integer(assignments[0]!["number"]);
            if(value<Integer(spec["min"]) || value>Integer(spec["max"]))throw new ArgumentException("Number outside offered bounds");return;
        }
        if(type=="confirm")
        {
            if(assignments.Count!=1)throw new ArgumentException("Choose exactly one confirmation");Fields(assignments[0],"accept");if(assignments[0]!["accept"]?.Type!=JTokenType.Boolean)throw new ArgumentException("Confirmation must be boolean");return;
        }
        var offered=((JArray)spec["options"]!).Select(o=>Integer(o["choiceId"])).ToHashSet();var seen=new HashSet<int>();
        if(type=="partition")
        {
            if(assignments.Count!=offered.Count)throw new ArgumentException("Partition must include every offered card");var groups=((JArray)spec["groups"]!).Select(g=>(string)g!).ToHashSet();
            foreach(var value in assignments){Fields(value,"choiceId","group");int id=Integer(value["choiceId"]);if(!offered.Contains(id) || !seen.Add(id) || value["group"]?.Type!=JTokenType.String || !groups.Contains((string)value["group"]!))throw new ArgumentException("Invalid partition");}return;
        }
        if(assignments.Count<Integer(spec["min"]) || assignments.Count>Integer(spec["max"]))throw new ArgumentException("Selection count outside offered bounds");
        foreach(var value in assignments){Fields(value,"choiceId");int id=Integer(value["choiceId"]);if(!offered.Contains(id) || (bool?)spec["repeats"]!=true && !seen.Add(id))throw new ArgumentException("Repeated or unoffered selection");}
    }
    public static void SubmitDecision(BaseUserRequest interaction,JObject decision,JArray assignments,Func<int,int> cardId)
    {
        if((string?)decision["kind"]=="choice"){Submit(interaction,(JObject)decision["choice"]!,assignments,cardId);return;}
        string kind=(string)decision["kind"]!;
        if(kind=="mulligan" && interaction is MulliganRequest mulligan)
        {
            if(assignments.Count!=1)throw new ArgumentException("Choose whether to keep the hand");Fields(assignments[0],"keep");if(assignments[0]!["keep"]?.Type!=JTokenType.Boolean)throw new ArgumentException("Keep must be boolean");if((bool)assignments[0]!["keep"]!)mulligan.KeepHand();else mulligan.MulliganHand();return;
        }
        if(kind=="starting_player" && interaction is ChooseStartingPlayerRequest starting)
        {
            if(assignments.Count!=1)throw new ArgumentException("Choose one starting player");Fields(assignments[0],"startingSeat");int seat=Integer(assignments[0]!["startingSeat"]);if(seat!=1 && seat!=2)throw new ArgumentException("Unknown starting seat");starting.ChooseStartingPlayer((uint)seat);return;
        }
        if(kind=="commander_return" && interaction is OptionalActionMessageRequest commander)
        {
            if(assignments.Count!=1)throw new ArgumentException("Choose one commander destination");Fields(assignments[0],"returnToCommand");if(assignments[0]!["returnToCommand"]?.Type!=JTokenType.Boolean)throw new ArgumentException("Commander return must be boolean");commander.SubmitResponse((bool)assignments[0]!["returnToCommand"]!?OptionResponse.AllowYes:OptionResponse.CancelNo);return;
        }
        if(kind is "discard" or "legend_rule" or "mulligan_bottom")
        {
            var offered=((JArray)decision["options"]!).Select(v=>Integer(v["forgeId"])).ToHashSet();var selected=new HashSet<int>();
            foreach(var value in assignments){Fields(value,"forgeId");int id=Integer(value["forgeId"]);if(!offered.Contains(id) || !selected.Add(id))throw new ArgumentException("Unmapped or duplicate selected object");}
            if(assignments.Count!=Integer(decision["count"]))throw new ArgumentException("Selection count does not match the native decision");
            if(kind=="mulligan_bottom" && interaction is GroupRequest bottom)
            {
                var keep=new Group{ZoneType=ZoneType.Hand,SubZoneType=SubZoneType.Top};keep.Ids.AddRange(bottom.InstanceIds.Where(id=>!selected.Select(cardId).Contains((int)id)));
                var library=new Group{ZoneType=ZoneType.Library,SubZoneType=SubZoneType.Bottom};library.Ids.AddRange(assignments.Select(v=>checked((uint)cardId((int)v["forgeId"]!))));bottom.SubmitGroups(new[]{keep,library});return;
            }
            if(interaction is SelectNRequest selection){selection.SubmitSelection(assignments.Select(v=>checked((uint)cardId((int)v["forgeId"]!))));return;}
        }
        if(kind=="assign_damage" && interaction is AssignDamageRequest damage)
        {
            var offered=((JArray)decision["options"]!).ToDictionary(v=>Integer(v["forgeId"]));var seen=new HashSet<int>();var assigner=damage.Assigners.Single().Clone();var values=new List<DamageAssignment>();int total=0;
            foreach(var value in assignments)
            {
                Fields(value,"forgeId","amount");int forge=Integer(value["forgeId"]),amount=Integer(value["amount"]);if(!offered.TryGetValue(forge,out var option) || !seen.Add(forge) || amount<0)throw new ArgumentException("Invalid damage recipient or amount");
                uint native=checked((uint)((string?)option["targetKind"]=="player"?(int)option["targetSeat"]!:cardId(forge)));var item=assigner.Assignments.Single(a=>a.InstanceId==native).Clone();item.AssignedDamage=(uint)amount;values.Add(item);total=checked(total+amount);
            }
            if(seen.Count!=offered.Count || total!=assigner.TotalDamage)throw new ArgumentException("Assign every point of damage exactly once");assigner.Assignments.Clear();assigner.Assignments.AddRange(values);damage.SubmitAssignment(new[]{assigner});return;
        }
        if((string?)decision["kind"]=="order_cards" && interaction is OrderRequest order)
        {
            var offered=((JArray)decision["options"]!).Select(v=>Integer(v["forgeId"])).ToHashSet();var selected=new HashSet<int>();
            foreach(var value in assignments){Fields(value,"forgeId");int id=Integer(value["forgeId"]);if(!offered.Contains(id) || !selected.Add(id))throw new ArgumentException("Unmapped ordered object");}
            if(!selected.SetEquals(offered))throw new ArgumentException("Order every offered object once");order.SubmitOrder(assignments.Select(v=>checked((uint)cardId((int)v["forgeId"]!))));return;
        }
        throw new NotSupportedException("Unmapped native decision driver "+decision["kind"]);
    }
    public static void Submit(BaseUserRequest interaction,JObject spec,JArray assignments,Func<int,int> cardId)
    {
        Validate(spec,assignments);
        if(((string?)spec["type"] is "abilities" or "options") && (interaction is not SelectNRequest abilityChoice || !abilityChoice.IsChoiceSelection || abilityChoice.IdType!=IdType.PromptParameterIndex))throw new InvalidOperationException("Ability choice must use the original native prompt-parameter control");
        if((string?)spec["type"]=="look" && (interaction is not SelectNRequest look || !look.IsLookSelection))throw new InvalidOperationException("Native reveal must use the original look-only control");
        var options=(JArray)spec["options"]!;
        uint Native(JToken value){var option=options.Single(o=>(int)o["choiceId"]! == (int)value["choiceId"]!);if((string?)spec["type"]=="type")return checked((uint)(int)option["nativeTypeId"]!);if((string?)spec["type"]=="card-name")return checked((uint)(int)option["nativeTitleId"]!);if((string?)spec["type"]=="counter-type")return (uint)SharedCounterProtocol.Type((string)option["counterType"]!);if((string?)spec["type"]=="colors")return (uint)SharedChoiceProtocol.ColorType((string)option["color"]!);if(((string?)spec["type"] is "abilities" or "options"))return checked((uint)options.IndexOf(option));return checked((uint)((string?)option["entityKind"]=="player"?(int)option["targetSeat"]!:cardId((int)option["forgeId"]!)));}
        switch(interaction)
        {
            case GroupRequest groups:
                groups.SubmitGroups(((JArray)spec["groups"]!).Select(g=>
                {
                    string name=(string)g!;var group=new Group{ZoneType=name=="graveyard"?ZoneType.Graveyard:ZoneType.Library,SubZoneType=name=="top"?SubZoneType.Top:name=="bottom"?SubZoneType.Bottom:SubZoneType.None};
                    group.Ids.AddRange(assignments.Where(v=>(string?)v["group"]==name).Select(Native));return group;
                }));break;
            case SelectNRequest selection:selection.SubmitSelection(assignments.Select(Native));break;
            case OrderRequest order:order.SubmitOrder(assignments.Select(Native));break;
            case NumericInputRequest numeric:numeric.SubmitValue(checked((uint)(int)assignments[0]!["number"]!));break;
            case CastingTimeOptionRequest casting when casting.ChildRequests.Count==1 && casting.ChildRequests[0] is CastingTimeOption_ModalRequest modal:
                modal.SubmitModal(assignments.Select(value=>checked((uint)(int)options.Single(o=>(int)o["choiceId"]! == (int)value["choiceId"]!)["nativeAbilityId"]!)));break;
            case OptionalActionMessageRequest confirm:confirm.SubmitResponse((bool)assignments[0]!["accept"]!?OptionResponse.AllowYes:OptionResponse.CancelNo);break;
            default:throw new NotSupportedException("Unexpected native shared interaction "+interaction?.GetType().Name);
        }
    }
}
