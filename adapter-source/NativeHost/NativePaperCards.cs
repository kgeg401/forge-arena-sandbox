using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using GreClient.CardData;
using HarmonyLib;
using Newtonsoft.Json.Linq;
using Wotc.Mtga.Cards.Database;
using Wotc.Mtga.Extensions;
using Wotc.Mtgo.Gre.External.Messaging;

namespace ForgeArenaSandbox;

// A local-only extension of presentation records. Forge still executes every
// rule. Existing SQL records and the owned database file are never replaced.
public static class NativePaperCards
{
    private static readonly Dictionary<uint,CardPrintingRecord> Cards=new Dictionary<uint,CardPrintingRecord>();
    private static readonly Dictionary<uint,AbilityPrintingRecord> Abilities=new Dictionary<uint,AbilityPrintingRecord>();
    private static readonly Dictionary<uint,string> Text=new Dictionary<uint,string>();
    private static readonly Dictionary<SqlCardDataProvider,Dictionary<uint,CardPrintingData>> Printings=new Dictionary<SqlCardDataProvider,Dictionary<uint,CardPrintingData>>();
    private static T[] Values<T>(JToken? values) where T:struct => (values as JArray ?? new JArray()).Select(v=>(T)Enum.Parse(typeof(T),(string)v!)).ToArray();
    public static void Install(string root)
    {
        if(Cards.Count!=0)throw new InvalidOperationException("Paper extension already installed");
        var manifest=JObject.Parse(File.ReadAllText(Path.Combine(root,"bridge-card-manifest.json")));
        if(manifest["paperExtension"] is not JObject extension)return;
        if((int?)extension["schema"]!=1)throw new InvalidDataException("Unknown paper extension schema");
        var h=new Harmony("local.forge-arena.paper-cards");
        NativePaperArt.Install(root,manifest,h);
        foreach(var p in ((JObject)extension["localizations"]!).Properties())Text.Add(uint.Parse(p.Name), (string)p.Value!);
        foreach(var a in (JArray)extension["abilities"]!)
        {
            uint id=(uint)a["id"]!;
            Abilities.Add(id,new AbilityPrintingRecord(id:id,baseId:(uint?)a["baseId"]??id,textId:(uint)a["textId"]!,category:(AbilityCategory)(int)a["category"]!,subCategory:(AbilitySubCategory)(int)a["subCategory"]!));
        }
        foreach(var c in ((JObject)manifest["cards"]!).Properties().Where(p=>(bool?)p.Value["paperOnly"]==true))
        {
            var d=c.Value;var p=d["paperDefinition"]!;uint id=(uint)d["grpId"]!;
            if(id<2000000 || id>=2100000)throw new InvalidDataException("Paper printing outside its reserved range");
            Cards.Add(id,new CardPrintingRecord(grpId:id,titleId:(uint)d["titleId"]!,typeTextId:(uint)p["typeTextId"]!,subtypeTextId:(uint)p["subtypeTextId"]!,
                artId:id,artistCredit:NativePaperArt.Artist(id),rarity:CardRarity.Rare,expansionCode:"ANA",collectorNumber:(id-2000000).ToString(),
                oldSchoolManaText:(string)p["manaText"]!,power:new StringBackedInt((string?)p["power"]),toughness:new StringBackedInt((string?)p["toughness"]),
                colors:Values<CardColor>(d["colors"]),colorIdentity:Values<CardColor>(p["colorIdentity"]),frameColors:Values<CardColor>(d["colors"]),
                types:Values<CardType>(d["types"]),subtypes:Values<SubType>(d["subtypes"]),supertypes:Values<SuperType>(d["supertypes"]),
                abilityIds:((JArray)d["abilityIds"]!).Select(v=>((uint)v,0u)).ToArray()));
        }
        Patch(h,typeof(SqlCardDataProvider),"GetCardRecordById",nameof(CardRecord));
        Patch(h,typeof(SqlCardDataProvider),"GetCardPrintingById",nameof(CardPrinting));
        Patch(h,typeof(SqlAbilityDataProvider),"GetAbilityRecordById",nameof(AbilityRecord));
        Patch(h,typeof(SqlAbilityDataProvider),"GetAbilityPrintingById",nameof(AbilityPrinting));
        Patch(h,typeof(SqlGreLocalizationProvider),"GetLocalizedText",nameof(Localized));
    }
    private static void Patch(Harmony h,Type type,string method,string handler)=>h.Patch(AccessTools.Method(type,method),prefix:new HarmonyMethod(typeof(NativePaperCards),handler));
    private static bool CardRecord(uint id,ref CardPrintingRecord __result){if(!Cards.TryGetValue(id,out __result))return true;return false;}
    private static bool CardPrinting(SqlCardDataProvider __instance,uint id,ref CardPrintingData __result)
    {
        if(!Cards.TryGetValue(id,out var record))return true;
        if(!Printings.TryGetValue(__instance,out var cache))Printings.Add(__instance,cache=new Dictionary<uint,CardPrintingData>());
        if(cache.TryGetValue(id,out __result))return false;
        var abilities=(IAbilityDataProvider)AccessTools.Field(typeof(SqlCardDataProvider),"_abilityDataProvider").GetValue(__instance);
        cache.Add(id,__result=new CardPrintingData(record,__instance,abilities));return false;
    }
    private static bool AbilityRecord(uint id,ref AbilityPrintingRecord __result){if(!Abilities.TryGetValue(id,out __result))return true;return false;}
    private static bool AbilityPrinting(SqlAbilityDataProvider __instance,uint id,ref AbilityPrintingData __result){if(!Abilities.TryGetValue(id,out var record))return true;__result=new AbilityPrintingData(record,__instance);return false;}
    private static bool Localized(uint locId,ref string __result){if(!Text.TryGetValue(locId,out __result))return true;return false;}
}
