using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

/// <summary>Temporary chooser-only views, derived solely from a pending choice.</summary>
internal static class SharedChoiceVisibility
{
    public static IEnumerable<JToken> Views(JObject state,IEnumerable<JToken> cards)
    {
        var originalCards=cards.ToArray();var objects=originalCards.ToDictionary(c=>(int)c["forgeId"]!);var named=originalCards.Where(c=>c["name"]!=null).ToArray();
        foreach(var card in named)yield return card;
        if((string?)state["decision"]?["kind"]!="choice")yield break;
        var spec=state["decision"]!["choice"]!;var seen=named.Select(c=>(int)c["forgeId"]!).ToHashSet();
        var exposed=((JArray?)spec["options"] ?? new JArray()).Concat((JArray?)spec["revealed"] ?? new JArray());
        foreach(var option in exposed)
        {
            if(option["forgeId"]==null || (bool?)option["identityVisible"]==false)continue;
            if(option["privateToSeat"]?.Type!=JTokenType.Integer || (int)option["privateToSeat"]! != 1 || option["label"]?.Type!=JTokenType.String)
                throw new InvalidDataException("Choice identity lacks explicit chooser visibility");
            int id=(int)option["forgeId"]!;
            if(!objects.TryGetValue(id,out var original))throw new InvalidDataException("Choice reveal is not a current game object");
            if(!seen.Add(id))continue;
            var view=(JObject)original.DeepClone();view["name"]=option["label"]!.DeepClone();view["privateChoice"]=true;
            view["tapped"]=false;view["token"]=false;view["sick"]=false;view["power"]=0;view["toughness"]=0;view["damage"]=0;
            yield return view;
        }
    }
}
