using System;
using System.IO;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

/// <summary>Observed active keyword grants with owned literal native identities.
/// Active grants/removals preserve observed sources and effect layer order.</summary>
internal static class SharedKeywordProtocol
{
    private static JObject Detail(string key,int value)=>new JObject{["key"]=key,["type"]="KeyValuePairValueType_int32",["valueInt32"]=new JArray(value)};
    internal static string Key(string keyword)=>keyword.StartsWith("Escape:",StringComparison.Ordinal)?"escape":keyword.ToLowerInvariant();
    internal static int Ability(string keyword,JObject bindings)
    {
        // Underworld Breach grants per-card escape costs. The original client
        // links its static rule to the generic Escape identity; payment and
        // exile counts remain authoritative in Forge's cast-cost interface.
        string key=Key(keyword);
        if(bindings[key] is not JToken value || value.Type!=JTokenType.Integer || (long)value<1 || (long)value>int.MaxValue)throw new NotSupportedException("Unmapped literal native keyword: "+keyword);
        return (int)value;
    }
    internal static int[] RemovedAbilities(JToken card,JToken removal,JObject keywordBindings,JObject cardBindings)
    {
        var ids=new HashSet<int>();
        if((bool?)removal["all"]==true)
        {
            var printed=cardBindings[(string?)card["presentationKey"] ?? (string)card["name"]!]??throw new InvalidDataException("Missing printed removal identity");
            foreach(var id in (JArray)printed["abilityIds"]!)ids.Add((int)id);
            if((int?)printed["abilityId"] is int primary && primary>0)ids.Add(primary);
        }
        foreach(var keyword in (JArray?)removal["keywords"]??new JArray())ids.Add(Ability((string)keyword!,keywordBindings));
        return ids.OrderBy(i=>i).ToArray();
    }
    public static JArray Persistent(JObject state,Func<int,int> cardId,JObject bindings,JObject cardBindings)
    {
        var result=new List<(long Timestamp,int Layer,JObject Value)>();
        foreach(var card in new[]{"hand","battlefield","stack","graveyard","command","exile"}.SelectMany(k=>(JArray?)state[k]??new JArray()))
        {
            if(card["keywordPresentationGaps"] is JArray gaps && gaps.Count>0)throw new NotSupportedException(string.Join("; ",gaps.Select(g=>(string)g!)));
            foreach(var grant in (JArray?)card["keywordGrants"]??new JArray())
            {
                if(grant["layerId"]?.Type!=JTokenType.Integer || (int)grant["layerId"]!<1 || (int)grant["layerId"]!>100000)throw new InvalidDataException("Keyword annotation identity bound exceeded");
                int source=cardId((int)grant["sourceForgeId"]!),target=cardId((int)card["forgeId"]!),ability=Ability((string)grant["keyword"]!,bindings),layer=(int)grant["layerId"]!;
                result.Add(((long)grant["timestamp"]!,layer,new JObject{["id"]=3_000_000_000u+(uint)layer,["affectorId"]=source,["affectedIds"]=new JArray(target),["type"]=new JArray("AnnotationType_AddAbility"),["details"]=new JArray(Detail("grpid",ability),Detail("count",1),Detail("effect_id",layer))}));
            }
            foreach(var removal in (JArray?)card["keywordRemovals"]??new JArray())
            {
                int layer=(int)removal["layerId"]!;if(layer<1 || layer>100000)throw new InvalidDataException("Keyword removal layer identity bound exceeded");
                int source=cardId((int)removal["sourceForgeId"]!),target=cardId((int)card["forgeId"]!);var ids=RemovedAbilities(card,removal,bindings,cardBindings);
                var annotation=new JObject{["id"]=3_000_000_000u+(uint)layer,["affectorId"]=source,["affectedIds"]=new JArray(target),["type"]=new JArray("AnnotationType_RemoveAbility"),["details"]=new JArray(Detail("effect_id",layer),new JObject{["key"]=target.ToString(CultureInfo.InvariantCulture),["type"]="KeyValuePairValueType_int32",["valueInt32"]=new JArray(ids)})};
                result.Add(((long)removal["timestamp"]!,layer,annotation));
            }
        }
        return new JArray(result.OrderBy(r=>r.Timestamp).ThenBy(r=>r.Layer).Select(r=>r.Value));
    }
}
