using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

internal static class SharedCharacteristicsProtocol
{
    internal static int TypeId(JObject bindings,string kind,string name)
    {
        var value=bindings[kind]?[name.ToLowerInvariant()];
        if(value?.Type!=JTokenType.Integer || (long)value<0 || (long)value>int.MaxValue)throw new NotSupportedException("Unmapped current "+kind+": "+name);
        return (int)value;
    }
    internal static JArray Values(JToken card,string field,string kind,JObject bindings)
    {
        if(card[field] is not JArray names)throw new InvalidDataException("Missing actual current characteristics");
        var result=names.Select(n=>TypeId(bindings,kind,(string)n!)).ToArray();
        if(result.Distinct().Count()!=result.Length)throw new InvalidDataException("Duplicate current native type identity");return new JArray(result);
    }
    internal static void Apply(JObject output,JToken card,JObject bindings)
    {
        if(card["currentTypes"]==null)return;
        output["cardTypes"]=Values(card,"currentTypes","CardType",bindings);output["superTypes"]=Values(card,"currentSupertypes","SuperType",bindings);output["subtypes"]=Values(card,"currentSubtypes","SubType",bindings);
    }
}
