using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using Wotc.Mtgo.Gre.External.Messaging;

namespace ForgeArenaSandbox;

/// <summary>
/// Research-only translation of explicit Forge choices to shipped GRE controls.
/// Parser/response parity is tested headlessly; rendered acceptance is separate.
/// Does not assign modal ability IDs or localized prompts by guessing.
/// </summary>
internal static class SharedChoiceProtocol
{
    internal static CardColor ColorType(string name)=>name.ToLowerInvariant() switch
    {
        "white"=>CardColor.White,"blue"=>CardColor.Blue,"black"=>CardColor.Black,"red"=>CardColor.Red,"green"=>CardColor.Green,"colorless"=>CardColor.Colorless,
        _=>throw new NotSupportedException("Unmapped offered color "+name)
    };
    private static int Integer(JToken? value)
    {
        if(value?.Type!=JTokenType.Integer || (long)value<int.MinValue || (long)value>int.MaxValue)
            throw new InvalidDataException("Shared choice requires an exact bounded integer");
        return (int)value;
    }
    private static JObject Spec(JObject decision)
    {
        if((string?)decision["kind"]!="choice" || decision["choice"] is not JObject spec || Integer(spec["schema"])!=1)
            throw new InvalidDataException("Unknown shared choice contract");
        if(spec["options"] is not JArray || spec["type"]?.Type!=JTokenType.String)
            throw new InvalidDataException("Incomplete shared choice contract");
        return spec;
    }
    private static Dictionary<int,JToken> Options(JObject spec)
    {
        var offered=new Dictionary<int,JToken>();
        foreach(var option in (JArray)spec["options"]!)
            if(!offered.TryAdd(Integer(option["choiceId"]),option))throw new InvalidDataException("Duplicate shared option identity");
        return offered;
    }
    private static int NativeId(JToken option,Func<int,int> cardId)
    {
        if((string?)option["entityKind"]=="player")
        {
            int seat=Integer(option["targetSeat"]);if(seat!=1 && seat!=2)throw new InvalidDataException("Unmapped player seat");return seat;
        }
        int id=cardId(Integer(option["forgeId"]));if(id<=2)throw new InvalidDataException("Card identity overlaps player seats");return id;
    }
    private static (string Zone,string Sub) Group(string name)=>name switch
    {
        "top"=>("ZoneType_Library","SubZoneType_Top"),
        "bottom"=>("ZoneType_Library","SubZoneType_Bottom"),
        "graveyard"=>("ZoneType_Graveyard","SubZoneType_None"),
        _=>throw new NotSupportedException("Unmapped shared partition group "+name)
    };
    public static JObject Request(JObject decision,Func<int,int> cardId,uint stateId,uint messageId)
    {
        var spec=Spec(decision);var options=Options(spec);string kind=(string)spec["type"]!;
        JObject payload;string type,key;
        if(kind=="partition")
        {
            var groups=((JArray)spec["groups"]!).Select(v=>(string)v!).ToArray();
            if(groups.Length!=2 || groups[0]!="top" || (groups[1]!="bottom" && groups[1]!="graveyard"))throw new NotSupportedException("Unmapped partition shape");
            int count=Integer(spec["count"]);if(count!=options.Count)throw new InvalidDataException("Partition cardinality differs");
            payload=new JObject{["instanceIds"]=new JArray(options.Values.Select(o=>NativeId(o,cardId))),["groupType"]="GroupType_Ordered",["context"]=groups[1]=="bottom"?"GroupingContext_Scry":"GroupingContext_Surveil",
                ["groupSpecs"]=new JArray(groups.Select(g=>{var zone=Group(g);return new JObject{["lowerBound"]=0,["upperBound"]=count,["zoneType"]=zone.Zone,["subZoneType"]=zone.Sub};}))};
            type="GREMessageType_GroupReq";key="groupReq";
        }
        else if(kind=="number")
        {
            int min=Integer(spec["min"]),max=Integer(spec["max"]);if(min<0 || max<min)throw new NotSupportedException("Arena numeric control cannot represent these bounds");
            payload=new JObject{["minValue"]=min,["maxValue"]=max,["stepSize"]=1,["numericInputType"]="NumericInputType_ChooseAnyAmount"};
            type="GREMessageType_NumericInputReq";key="numericInputReq";
        }
        else if(kind=="confirm")
        {
            payload=new JObject{["recipientIds"]=new JArray(1)};type="GREMessageType_OptionalActionMessage";key="optionalActionMessage";
        }
        else if(kind=="modes")
        {
            int source=cardId(Integer(spec["sourceForgeId"])),parent=Integer(spec["nativeParentAbilityId"]);
            int min=Integer(spec["min"]),max=Integer(spec["max"]);bool repeats=(bool)spec["repeats"]!;
            var modes=options.Values.Select(o=>Integer(o["nativeAbilityId"])).ToArray();
            if(parent<=0 || modes.Any(id=>id<=0) || modes.Distinct().Count()!=modes.Length || min<0 || max<min || !repeats && max>modes.Length)throw new InvalidDataException("Modal choice lacks unambiguous source-bound native identities");
            var modal=new JObject{["abilityGrpId"]=parent,["minSel"]=min,["maxSel"]=max,["repeatedSelectAllowed"]=repeats,["modalOptions"]=new JArray(modes.Select(id=>new JObject{["grpId"]=id}))};
            payload=new JObject{["castingTimeOptionReq"]=new JArray(new JObject{["ctoId"]=1,["castingTimeOptionType"]="CastingTimeOptionType_Modal",["isRequired"]=true,["affectorId"]=source,["modalReq"]=modal})};
            type="GREMessageType_CastingTimeOptionsReq";key="castingTimeOptionsReq";
        }
        else if(kind is "abilities" or "options")
        {
            var values=options.Values.ToArray();int min=Integer(spec["min"]),max=Integer(spec["max"]);var labels=values.Select(o=>(string)o["label"]!).ToArray();
            if(min<0 || max<min || max>values.Length || labels.Any(string.IsNullOrWhiteSpace) || labels.Distinct(StringComparer.Ordinal).Count()!=labels.Length || (bool?)spec["repeats"]!=false)throw new InvalidDataException("Invalid explicit native ability choice");
            payload=new JObject{["minSel"]=min,["maxSel"]=max,["context"]="SelectionContext_Resolution",["optionContext"]="OptionContext_Resolution",["listType"]="SelectionListType_Dynamic",["idType"]="IdType_PromptParameterIndex",["ids"]=new JArray(Enumerable.Range(0,values.Length)),["validationType"]="SelectionValidationType_NonRepeatable",["prompt"]=new JObject{["promptId"]=Integer(spec["nativePromptId"]),["parameters"]=new JArray(labels.Select((label,index)=>new JObject{["parameterName"]="option"+index,["type"]="ParameterType_NonLocalizedString",["stringValue"]=label}))}};
            type="GREMessageType_SelectNReq";key="selectNReq";
        }
        else if(kind=="type")
        {
            string list=(string?)spec["typeKind"] switch{"SubType"=>"SubTypes","CardType"=>"CardTypes","SuperType"=>"SuperTypes",_=>throw new NotSupportedException("Unmapped source type-selection family")};
            var ids=options.Values.Select(o=>Integer(o["nativeTypeId"])).ToArray();
            if(ids.Distinct().Count()!=ids.Length || Integer(spec["max"])!=1)throw new InvalidDataException("Invalid source-bound type selection");
            payload=new JObject{["minSel"]=Integer(spec["min"]),["maxSel"]=1,["context"]="SelectionContext_Resolution",["optionContext"]="OptionContext_Resolution",["listType"]="SelectionListType_StaticSubset",["staticList"]="StaticList_"+list,["idType"]="IdType_None",["ids"]=new JArray(ids),["validationType"]="SelectionValidationType_NonRepeatable"};
            type="GREMessageType_SelectNReq";key="selectNReq";
        }
        else if(kind=="card-name")
        {
            var titles=options.Values.Select(o=>Integer(o["nativeTitleId"])).ToArray();
            if(Integer(spec["min"])!=1 || Integer(spec["max"])!=1 || titles.Any(id=>id<=0) || titles.Distinct().Count()!=titles.Length)throw new InvalidDataException("Card-name selection lacks unique source-bound title IDs");
            payload=new JObject{["minSel"]=1,["maxSel"]=1,["context"]="SelectionContext_Resolution",["optionContext"]="OptionContext_Resolution",["listType"]="SelectionListType_StaticSubset",["staticList"]="StaticList_CardNames",["idType"]="IdType_None",["ids"]=new JArray(titles),["validationType"]="SelectionValidationType_NonRepeatable"};
            type="GREMessageType_SelectNReq";key="selectNReq";
        }
        else if(kind=="colors")
        {
            var colors=options.Values.Select(o=>(int)ColorType((string)o["color"]!)).ToArray();int min=Integer(spec["min"]),max=Integer(spec["max"]);
            if(min<0 || max<min || max>colors.Length || colors.Distinct().Count()!=colors.Length || (bool?)spec["repeats"]!=false)throw new InvalidDataException("Invalid color selection");
            payload=new JObject{["minSel"]=min,["maxSel"]=max,["context"]="SelectionContext_Resolution",["optionContext"]="OptionContext_Resolution",["listType"]="SelectionListType_StaticSubset",["staticList"]="StaticList_CardColors",["ids"]=new JArray(colors),["validationType"]="SelectionValidationType_NonRepeatable"};
            type="GREMessageType_SelectNReq";key="selectNReq";
        }
        else if(kind=="counter-type")
        {
            var types=options.Values.Select(o=>(int)SharedCounterProtocol.Type((string)o["counterType"]!)).ToArray();
            if(Integer(spec["min"])!=1 || Integer(spec["max"])!=1 || types.Distinct().Count()!=types.Length)throw new InvalidDataException("Invalid counter-type selection");
            payload=new JObject{["minSel"]=1,["maxSel"]=1,["context"]="SelectionContext_Resolution",["optionContext"]="OptionContext_Resolution",["listType"]="SelectionListType_StaticSubset",["staticList"]="StaticList_CounterTypes",["ids"]=new JArray(types),["validationType"]="SelectionValidationType_NonRepeatable"};
            type="GREMessageType_SelectNReq";key="selectNReq";
        }
        else if(kind is "entities" or "cards-zone" or "cards-effect" or "sacrifice" or "discard-effect" or "look")
        {
            if((bool?)spec["repeats"]!=false)throw new NotSupportedException("Entity choice repetition is not mapped");
            int min=Integer(spec["min"]),max=Integer(spec["max"]);if(min<0 || max<min || max>options.Count)throw new InvalidDataException("Invalid entity bounds");
            payload=new JObject{["minSel"]=min,["maxSel"]=max,["context"]=kind=="discard-effect"?"SelectionContext_Discard":"SelectionContext_Resolution",["optionContext"]="OptionContext_Resolution",["listType"]="SelectionListType_Dynamic",["idType"]="IdType_InstanceId",["ids"]=new JArray(options.Values.Select(o=>NativeId(o,cardId))),["validationType"]="SelectionValidationType_NonRepeatable"};
            type="GREMessageType_SelectNReq";key="selectNReq";
        }
        else if(kind=="order")
        {
            if((string?)spec["destination"]!="Library" && (string?)spec["destination"]!="Graveyard" && (string?)spec["destination"]!="Exile")throw new NotSupportedException("Unmapped ordering zone");
            payload=new JObject{["ids"]=new JArray(options.Values.Select(o=>NativeId(o,cardId))),["orderingContext"]="OrderingContext_None"};type="GREMessageType_OrderReq";key="orderReq";
        }
        else throw new NotSupportedException("Native shared choice requires an explicit presentation binding: "+kind);
        // The shipped Unity workflow classifiers dereference ReqPrompt even
        // for instance-id choices. A parser-only replay accepts a null prompt,
        // but the original SelectNWorkflowTranslation cannot render it.
        // Pinned owned Prompts: 2428="Choose a card.", 23="Choose options.".
        if(type=="GREMessageType_SelectNReq" && payload["prompt"]==null)
            payload["prompt"]=new JObject{["promptId"]=payload["idType"]?.ToString()=="IdType_InstanceId" && (int)payload["maxSel"]!<=1?2428:23};
        if(kind!="modes" && kind!="order" && spec["sourceForgeId"]!=null)payload["sourceId"]=cardId(Integer(spec["sourceForgeId"]));
        var message=new JObject{["type"]=type,["systemSeatIds"]=new JArray(1),["msgId"]=messageId,["gameStateId"]=stateId,["allowCancel"]="AllowCancel_No",[key]=payload};
        // BaseUserRequest.Prompt comes from the envelope; ReqPrompt comes from
        // SelectNReq. Both original UI paths need the same bound instruction.
        if(payload["prompt"] is JObject prompt)message["prompt"]=prompt.DeepClone();
        return message;
    }

    public static JArray Response(JObject decision,Func<int,int> cardId,ClientToGREMessage response,uint stateId,uint requestId)
    {
        if(response.GameStateId!=stateId || response.RespId!=requestId)throw new InvalidOperationException("Stale native shared-choice response");
        var spec=Spec(decision);var options=Options(spec);string kind=(string)spec["type"]!;
        var result=new JArray();
        if(kind=="partition" && response.Type==ClientMessageType.GroupResp)
        {
            var expected=((JArray)spec["groups"]!).Select(v=>(string)v!).ToArray();var groups=response.GroupResp.Groups;
            // The shipped GroupRequest still copies this legacy field. Validate
            // the actual pinned handler's output even though protobuf marks it obsolete.
#pragma warning disable CS0612
            if(response.GroupResp.GroupType!=GroupType.Ordered || groups.Count!=expected.Length)throw new InvalidOperationException("Shared grouping type/count mismatch");
#pragma warning restore CS0612
            var native=options.ToDictionary(p=>NativeId(p.Value,cardId),p=>p.Key);var seen=new HashSet<int>();
            for(int i=0;i<expected.Length;i++)
            {
                var zone=Group(expected[i]);var actual=groups[i];
                if("ZoneType_"+actual.ZoneType!=zone.Zone || "SubZoneType_"+actual.SubZoneType!=zone.Sub)throw new InvalidOperationException("Shared grouping zone mismatch");
                foreach(uint raw in actual.Ids)
                {
                    if(raw>int.MaxValue || !native.TryGetValue((int)raw,out int id) || !seen.Add(id))throw new InvalidOperationException("Duplicate or unoffered grouped object");
                    result.Add(new JObject{["choiceId"]=id,["group"]=expected[i]});
                }
            }
            if(seen.Count!=options.Count)throw new InvalidOperationException("Grouping omitted an offered object");
        }
        else if(kind=="number" && response.Type==ClientMessageType.NumericInputResp)
        {
            uint n=response.NumericInputResp.NumericInputValue;if(n>int.MaxValue || n<Integer(spec["min"]) || n>Integer(spec["max"]))throw new InvalidOperationException("Native number outside Forge bounds");
            result.Add(new JObject{["number"]=(int)n});
        }
        else if(kind=="confirm" && response.Type==ClientMessageType.OptionalActionResp)
        {
            var value=response.OptionalResp.Response;if(value!=OptionResponse.AllowYes && value!=OptionResponse.CancelNo)throw new InvalidOperationException("Unknown native confirmation");
            result.Add(new JObject{["accept"]=value==OptionResponse.AllowYes});
        }
        else if(kind=="modes" && response.Type==ClientMessageType.CastingTimeOptionsResp)
        {
            var choice=response.CastingTimeOptionsResp.CastingTimeOptionResp;
            if(choice==null || choice.CtoId!=1 || choice.CastingTimeOptionType!=CastingTimeOptionType.Modal || choice.ChooseModalResp==null)throw new InvalidOperationException("Native modal response is not the pending option");
            var native=options.ToDictionary(p=>Integer(p.Value["nativeAbilityId"]),p=>p.Key);var seen=new HashSet<int>();bool repeats=(bool)spec["repeats"]!;
            foreach(uint raw in choice.ChooseModalResp.GrpIds)
            {
                if(raw>int.MaxValue || !native.TryGetValue((int)raw,out int id) || !repeats && !seen.Add(id))throw new InvalidOperationException("Repeated or unoffered native mode");
                result.Add(new JObject{["choiceId"]=id});
            }
            if(result.Count<Integer(spec["min"]) || result.Count>Integer(spec["max"]))throw new InvalidOperationException("Native mode count outside Forge bounds");
        }
        else if(kind is "abilities" or "options" && response.Type==ClientMessageType.SelectNresp)
        {
            var values=options.ToArray();var seen=new HashSet<uint>();
            foreach(uint raw in response.SelectNResp.Ids){if(raw>=values.Length || !seen.Add(raw))throw new InvalidOperationException("Repeated or unoffered native ability-choice index");result.Add(new JObject{["choiceId"]=values[raw].Key});}
            if(result.Count<Integer(spec["min"]) || result.Count>Integer(spec["max"]))throw new InvalidOperationException("Native ability choice count differs from Forge");
        }
        else if(kind=="type" && response.Type==ClientMessageType.SelectNresp)
        {
            var native=options.ToDictionary(p=>(uint)Integer(p.Value["nativeTypeId"]),p=>p.Key);var seen=new HashSet<uint>();
            foreach(uint id in response.SelectNResp.Ids){if(!native.TryGetValue(id,out int choice) || !seen.Add(id))throw new InvalidOperationException("Type selection was not offered by Forge");result.Add(new JObject{["choiceId"]=choice});}
            if(result.Count<Integer(spec["min"]) || result.Count>Integer(spec["max"]))throw new InvalidOperationException("Type selection count differs from Forge");
        }
        else if(kind=="card-name" && response.Type==ClientMessageType.SelectNresp)
        {
            if(response.SelectNResp.Ids.Count!=1)throw new InvalidOperationException("Choose exactly one card name");
            uint title=response.SelectNResp.Ids[0];var match=options.SingleOrDefault(p=>(uint)Integer(p.Value["nativeTitleId"])==title);
            if(match.Value==null)throw new InvalidOperationException("Card name was not offered by Forge");result.Add(new JObject{["choiceId"]=match.Key});
        }
        else if(kind=="colors" && response.Type==ClientMessageType.SelectNresp)
        {
            var native=options.ToDictionary(p=>(uint)ColorType((string)p.Value["color"]!),p=>p.Key);var seen=new HashSet<uint>();
            foreach(uint raw in response.SelectNResp.Ids){if(!native.TryGetValue(raw,out int id) || !seen.Add(raw))throw new InvalidOperationException("Duplicate or unoffered native color");result.Add(new JObject{["choiceId"]=id});}
            if(result.Count<Integer(spec["min"]) || result.Count>Integer(spec["max"]))throw new InvalidOperationException("Native color count outside Forge bounds");
        }
        else if(kind=="counter-type" && response.Type==ClientMessageType.SelectNresp)
        {
            if(response.SelectNResp.Ids.Count!=1)throw new InvalidOperationException("Select exactly one offered counter type");
            uint raw=response.SelectNResp.Ids[0];
            var matches=options.Where(p=>(uint)SharedCounterProtocol.Type((string)p.Value["counterType"]!)==raw).ToArray();
            if(matches.Length!=1)throw new InvalidOperationException("Native counter type was not uniquely offered");result.Add(new JObject{["choiceId"]=matches[0].Key});
        }
        else if(kind is "entities" or "cards-zone" or "cards-effect" or "sacrifice" or "discard-effect" or "look" && response.Type==ClientMessageType.SelectNresp)
        {
            var native=options.ToDictionary(p=>NativeId(p.Value,cardId),p=>p.Key);var seen=new HashSet<int>();
            foreach(uint raw in response.SelectNResp.Ids)
            {
                if(raw>int.MaxValue || !native.TryGetValue((int)raw,out int id) || !seen.Add(id))throw new InvalidOperationException("Duplicate or unoffered selected object");
                result.Add(new JObject{["choiceId"]=id});
            }
            if(result.Count<Integer(spec["min"]) || result.Count>Integer(spec["max"]))throw new InvalidOperationException("Native selection outside Forge bounds");
        }
        else if(kind=="order" && response.Type==ClientMessageType.OrderResp)
        {
            if(response.OrderResp.Ordering!=OrderingType.OrderAsIndicated)throw new NotSupportedException("An explicit ordering is required");
            var native=options.ToDictionary(p=>NativeId(p.Value,cardId),p=>p.Key);var seen=new HashSet<int>();
            // Shipped OrderRequest.SubmitOrder reverses its displayed list;
            // this is undone here before returning Forge's movement order.
            foreach(uint raw in response.OrderResp.Ids.Reverse())
            {
                if(raw>int.MaxValue || !native.TryGetValue((int)raw,out int id) || !seen.Add(id))throw new InvalidOperationException("Duplicate or unoffered ordered object");
                result.Add(new JObject{["choiceId"]=id});
            }
            if(result.Count!=options.Count)throw new InvalidOperationException("Order must include every offered object");
        }
        else throw new NotSupportedException("Native response does not match shared choice "+kind);
        return result;
    }
}
