using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using Wotc.Mtgo.Gre.External.Messaging;

namespace ForgeArenaSandbox;

internal static class SharedCounterProtocol
{
    private static int Integer(JToken? value)
    {
        if(value?.Type!=JTokenType.Integer || (long)value<0 || (long)value>int.MaxValue)throw new InvalidDataException("Counter value must be an exact nonnegative integer");return (int)value;
    }
    internal static CounterType Type(string key)
    {
        if(!Enum.TryParse<CounterType>(key,true,out var type) || !Enum.IsDefined(typeof(CounterType),type) || type==CounterType.None)throw new NotSupportedException("Unmapped native counter type "+key);
        return type;
    }
    private static JObject Detail(string key,int value)=>new JObject{["key"]=key,["type"]="KeyValuePairValueType_int32",["valueInt32"]=new JArray(value)};
    public static JArray Persistent(JObject state,Func<int,int> cardId)
    {
        var result=new JArray();
        void Entity(int key,int native,JArray counters)
        {
            var seen=new HashSet<CounterType>();
            foreach(var counter in counters)
            {
                var type=Type((string)counter["type"]!);int count=Integer(counter["count"]);if(count==0 || !seen.Add(type))throw new InvalidDataException("Counter snapshot contains zero or duplicate types");
                int ordinal=(int)type;if(ordinal<1 || ordinal>=4096)throw new NotSupportedException("Counter ordinal exceeds annotation identity range");
                uint id=checked((uint)(2_000_000L+(long)key*4096+ordinal));
                result.Add(new JObject{["id"]=id,["affectedIds"]=new JArray(native),["type"]=new JArray("AnnotationType_Counter"),["details"]=new JArray(Detail("counter_type",ordinal),Detail("count",count))});
            }
        }
        foreach(var card in new[]{"hand","battlefield","stack","graveyard","command","exile"}.SelectMany(k=>(JArray?)state[k]??new JArray()))
            if(card["counters"] is JArray counters && counters.Count>0){int forge=Integer(card["forgeId"]);if(forge>=500000)throw new InvalidDataException("Counter card identity exceeds its reserved annotation range");Entity(checked(forge+1024),cardId(forge),counters);}
        foreach(var player in (JArray?)state["playerCounters"]??new JArray())
        {
            int seat=Integer(player["seat"]);if(!ValidSeat(state,seat))throw new InvalidDataException("Unknown counter owner seat");Entity(seat,seat,(JArray)player["counters"]!);
        }
        return result;
    }
    public static JArray Changes(JObject state,long afterEventId,Func<int,int> cardId,Func<int,int?> sourceId,ref int annotationId)
    {
        var result=new JArray();
        foreach(var e in ((JArray?)state["events"]??new JArray()).Where(e=>(long)e["id"]!>afterEventId && (string?)e["kind"]=="counter-change"))
        {
            int before=Integer(e["before"]),after=Integer(e["after"]),delta=checked(after-before);if(delta==0)continue;
            var type=Type((string)e["counterType"]!);
            int target=e["targetSeat"]!=null?Integer(e["targetSeat"]):cardId(Integer(e["targetForgeId"]));
            if(e["targetSeat"]!=null && !ValidSeat(state,target))throw new InvalidDataException("Unknown counter event player");
            var value=new JObject{["id"]=annotationId++,["affectedIds"]=new JArray(target),["type"]=new JArray(delta>0?"AnnotationType_CounterAdded":"AnnotationType_CounterRemoved"),["details"]=new JArray(Detail("counter_type",(int)type),Detail("transaction_amount",Math.Abs(delta)))};
            int? source=sourceId((int?)e["sourceStackForgeId"]??0);if(source.HasValue)value["affectorId"]=source.Value;result.Add(value);
        }
        return result;
    }
    private static bool ValidSeat(JObject state,int seat)=>seat>=1 && seat<=((int?)state["playerCount"]??2);
}
