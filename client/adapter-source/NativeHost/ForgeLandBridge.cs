using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Wotc.Mtgo.Gre.External.Messaging;
using Wotc.Mtga.Extensions;

namespace ForgeArenaSandbox;

/// <summary>Native Arena adapter for the admitted local practice cards. Forge owns game rules.</summary>
internal sealed class ForgeLandBridge
{
    public void Detach(){_connection.LocalCommand-=Handle;}
    // Forge replaces/retire files atomically while the Unity thread polls. A
    // read handle must permit deletion or Windows can stop the rules owner.
    private static string ReadShared(string path)
    {
        using var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete);
        using var reader=new StreamReader(stream);return reader.ReadToEnd();
    }
    private readonly string _ipc;
    private readonly LocalGreConnection _connection;
    private readonly System.Action<string> _log;
    private readonly JObject _template;
    private readonly JObject _cardManifest;
    private readonly JObject _keywordBindings;
    private readonly JObject _typeBindings;
    private readonly Dictionary<int,int> _ids = new Dictionary<int,int>();
    private JObject _state;
    private readonly string _session;
    private uint _stateId=1, _messageId=100, _requestId;
    private int _nextArenaId=10000;
    private string? _pending;
    private int _pendingForgeId;
    private string _pendingOp="";
    private string _lastDecisionToken="";
    private long _lastEventId;
    private readonly string _wire;
    private readonly bool _fullControl;
    private readonly SettingsMessage _settings=new SettingsMessage();
    private bool _hasSettings;
    private readonly AutomaticPassPacing _passPacing = new AutomaticPassPacing();
    private readonly Func<uint?> _presentedState;
    private readonly Func<bool> _submitAutomaticPass;
    private readonly Func<bool> _autoOrderTriggers;
    private readonly Func<bool> _autoChooseReplacementEffects;
    private bool _automaticSuspended;
    private bool _quietAdvance;
    private int _yieldTurn=-1;
    private bool _yieldAcrossPod;
    private readonly Func<double> _seconds;
    private double _pendingStarted;
    private bool _slowRequestReported;
    public double RulesWaitSeconds => _pending == null ? 0 : Math.Max(0, _seconds() - _pendingStarted);
    public bool RulesCalculationSlow => _pending != null && RulesWaitSeconds >= 15;
    private void BeginRulesWait(){_pendingStarted=_seconds();_slowRequestReported=false;}
    private DateTime? _decisionReadDeniedSince;
    public string? Gap { get; private set; }
    internal string? PendingResearchRequestId => _pending;
    internal int ResearchInstanceId(int forgeId)=>_ids[forgeId];
    internal int ResearchPrintingId(string name)=>Identity(name).Grp;
    internal int ResearchKeywordId(string keyword)=>SharedKeywordProtocol.Ability(keyword,_keywordBindings);
    internal int ResearchTypeId(string kind,string name)=>SharedCharacteristicsProtocol.TypeId(_typeBindings,kind,name);
    internal int[] ResearchRemovedAbilities(JToken card,JToken removal)=>SharedKeywordProtocol.RemovedAbilities(card,removal,_keywordBindings,_cardManifest);
    internal IEnumerable<uint> ResearchPrintedAbilities(string name)=>((JArray)Definition(name)["abilityIds"]!).Select(v=>(uint)v).Concat(new[]{(uint)Identity(name).Ability}).Where(v=>v!=0).Distinct();
    internal IEnumerable<uint> ResearchKnownKeywords=>_keywordBindings.Properties().Select(p=>(uint)p.Value);
    internal uint ResearchCanonicalKeyword(string name,uint ability)=>Definition(name)["abilityBindings"]?["printedKeywordBases"]?[ability.ToString(System.Globalization.CultureInfo.InvariantCulture)] is JToken value?(uint)value:ability;
    internal uint? ResearchKnownKeyword(string keyword)=>_keywordBindings[SharedKeywordProtocol.Key(keyword)] is JToken value?(uint)value:null;
    internal JObject ResearchState => (JObject)_state.DeepClone();
    public string Session => _session;
    public string Phase => (string)_state["phase"]!;
    public int Turn => (int)_state["turn"]!;
    public int ActiveSeat => (int)_state["activeSeat"]!;
    public int ManaTotal => (int?)_state["manaTotal"] ?? 0;
    public int LandsPlayed => (int)_state["landsPlayed"]!;
    public int HandCount => ((JArray)_state["hand"]!).Count;
    public int BattlefieldCount => ((JArray)_state["battlefield"]!).Count;
    public bool GameOver => (bool?)_state["gameOver"] ?? false;
    public string Scenario => (string?)_state["scenario"] ?? "starter";
    public string? DecisionKind => (string?)Decision?["kind"];
    public IReadOnlyList<Wizards.Mtga.FrontDoorModels.ClientCommanderInfo> Commanders(int seat) => VisibleCards(_state).Where(c=>(bool?)c["commander"]==true && (int)c["owner"]! == seat)
        .Select(c=>new Wizards.Mtga.FrontDoorModels.ClientCommanderInfo{GrpId=(uint)Identity((string)c["name"]!).Grp,StyleCode=""}).ToList();

    public string PodDetails()
    {
        if(!IsCommanderPod)throw new InvalidOperationException("Commander pod details require a four-player match.");
        var players=(JArray)_state["players"]!;var damage=(JArray)_state["commanderDamage"]!;
        var names=players.SelectMany(p=>(p["commanders"] as JArray??new JArray()).Select(c=>new{Id=(int)c["forgeId"]!,Name=(string)c["name"]!,Owner=(int)p["seat"]!})).ToDictionary(c=>c.Id);
        var lines=new List<string>{"40 starting life. Elimination at 21 combat damage from any one commander.",""};
        foreach(var player in players)
        {
            int seat=(int)player["seat"]!;bool lost=(bool)player["lost"]!;
            lines.Add(PlayerName(seat)+" - "+(lost?"Eliminated ("+(string)player["lossReason"]!+")":(int)player["life"]!+" life"));
            var received=damage.Where(d=>(int)d["seat"]! == seat && (int)d["amount"]!>0).Select(d=>{
                int id=(int)d["commanderForgeId"]!;return (names.TryGetValue(id,out var source)?source.Name+" ("+PlayerName(source.Owner)+")":"Commander #"+id)+": "+(int)d["amount"]!+"/21";
            }).ToArray();
            lines.Add("Commander damage received: "+(received.Length==0?"none":string.Join("; ",received)));lines.Add("");
        }
        return string.Join("\n",lines).TrimEnd();
    }

    public ForgeLandBridge(string root, LocalGreConnection connection, System.Action<string> log, Func<uint?> presentedState, Func<bool> submitAutomaticPass,string? researchIpc=null, Func<double>? seconds=null, Func<bool>? autoOrderTriggers=null, Func<bool>? autoChooseReplacementEffects=null)
    {
        if(researchIpc!=null)
        {
            var researchManifest=JObject.Parse(File.ReadAllText(Path.Combine(root,"bridge-card-manifest.json")));
            var allowed=Path.GetFullPath(Path.Combine(root,"..","research"))+Path.DirectorySeparatorChar;
            if((bool?)researchManifest["researchOnly"]!=true || File.Exists(Path.Combine(root,"MTGA.exe")) || !Path.GetFullPath(researchIpc).StartsWith(allowed,StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("Explicit IPC override requires a private headless research runtime");
        }
        var clock=System.Diagnostics.Stopwatch.StartNew();_seconds=seconds??(()=>clock.Elapsed.TotalSeconds);
        _autoOrderTriggers=autoOrderTriggers??(()=>true);
        _autoChooseReplacementEffects=autoChooseReplacementEffects??(()=>false);
        _ipc=researchIpc??Path.Combine(root,"forge-ipc");_wire=Path.Combine(_ipc,"native-wire.jsonl");_connection=connection;_log=log;_presentedState=presentedState;_submitAutomaticPass=submitAutomaticPass;_fullControl=File.Exists(Path.Combine(root,"full-control-test.flag"));
        _state=JObject.Parse(ReadShared(Path.Combine(_ipc,"state.json")));
        var manifest=JObject.Parse(File.ReadAllText(Path.Combine(root,"bridge-card-manifest.json")));
        if((int?)manifest["schema"]!=1)throw new InvalidDataException("Unsupported generated card manifest.");
        _cardManifest=(JObject)manifest["cards"]!;
        _keywordBindings=(JObject?)manifest["keywordAbilityIds"]??new JObject();
        _typeBindings=(JObject?)manifest["typeEnumIds"]??new JObject();
        _session=(string)_state["session"]!;
        if(LandsPlayed!=0)throw new InvalidOperationException("Start a fresh Forge land scenario before opening this native test.");
        _template=(JObject)JObject.Parse(File.ReadAllText(Path.Combine(root,"board-fixture.json")))["messages"]![0]!["gameStateMessage"]!;
        ExtendPodTemplate();
        foreach(var c in Cards(_state))_ids[(int)c["forgeId"]!]=(int)c["arenaId"]!;
        _connection.LocalCommand+=Handle;
    }

    private static IEnumerable<JToken> Cards(JObject state){
        var cards=((JArray)state["hand"]!).Concat((JArray)state["battlefield"]!).Concat((JArray)state["stack"]!).Concat((JArray?)state["graveyard"] ?? new JArray()).Concat((JArray?)state["command"] ?? new JArray()).Concat((JArray?)state["exile"] ?? new JArray()).Concat((JArray?)state["hidden"] ?? new JArray()).Concat((JArray?)state["stackAbilities"] ?? new JArray()).ToArray();
        foreach(var card in cards)yield return card;
        var pending=state["decision"]?["choice"]?["pendingCopyObject"] as JObject ?? state["decision"]?["pendingCopyObject"] as JObject;
        if(pending!=null && !cards.Any(c=>(int)c["forgeId"]! == (int)pending["forgeId"]!))yield return pending;
    }
    private static IEnumerable<JToken> VisibleCards(JObject state) => SharedChoiceVisibility.Views(state,Cards(state));
    private int Id(JToken card) => _ids[(int)card["forgeId"]!];
    private int TargetId(JToken option)=>(string?)option["targetKind"]=="player"?(int)option["targetSeat"]!:_ids[(int)option["forgeId"]!];
    private static GREToClientMessage Parse(JObject message) => GREToClientMessage.Parser.ParseJson(message.ToString(Formatting.None));
    private JObject Envelope(string type,JObject payload,string key)
    {
        if(type=="GREMessageType_SelectNReq" && payload["prompt"]==null)
            payload["prompt"]=new JObject{["promptId"]=(int?)payload["maxSel"]<=1?2428:23};
        return new JObject{["type"]=type,["systemSeatIds"]=new JArray(1),["msgId"]=++_messageId,["gameStateId"]=_stateId,[key]=payload};
    }

    private JObject? Decision => _state["decision"] as JObject;
    public int PlayerCount=>(int?)_state["playerCount"]??2;
    public bool IsCommanderPod=>(bool?)_state["pod"]==true;
    private bool LocalPodEliminated=>IsCommanderPod && PlayerLost(1);
    public string PlayerName(int seat)=>(string?)((JArray?)_state["players"])?.SingleOrDefault(p=>(int)p["seat"]! == seat)?["name"] ?? (seat==1?"Local Player":"Opponent");
    private void ExtendPodTemplate()
    {
        if(PlayerCount==2)return;
        if(!IsCommanderPod || PlayerCount!=4)throw new NotSupportedException("Only a four-seat Commander roster is connected.");
        var players=(JArray)_template["players"]!;var zones=(JArray)_template["zones"]!;
        _template["teams"]=new JArray(Enumerable.Range(1,PlayerCount).Select(seat=>new JObject{["id"]=seat,["playerIds"]=new JArray(seat),["status"]="TeamStatus_InGame"}));
        for(int seat=3;seat<=4;seat++)
        {
            var player=(JObject)players[1]!.DeepClone();player["systemSeatNumber"]=seat;player["teamId"]=seat;player["controllerSeatId"]=seat;players.Add(player);
            var revealed=(JObject)zones.Single(z=>(int)z["zoneId"]! == 19).DeepClone();revealed["zoneId"]=17+seat;revealed["ownerSeatId"]=seat;zones.Add(revealed);
            foreach(var prototype in zones.Where(z=>(int?)z["ownerSeatId"]==2 && (int)z["zoneId"]!>=35).ToArray())
            {
                var zone=(JObject)prototype.DeepClone();zone["zoneId"]=(int)zone["zoneId"]!+4*(seat-2);zone["ownerSeatId"]=seat;
                if(zone["viewers"]!=null)zone["viewers"]=new JArray(seat);zones.Add(zone);
            }
        }
    }
    private static int ZoneId(JToken card) => (string)card["zone"]! switch
    { "Hand"=>31+4*((int)card["owner"]!-1),"Library"=>32+4*((int)card["owner"]!-1),"Battlefield"=>28,"Stack"=>27,"Command"=>26,"Exile"=>29,"Limbo"=>30,"Graveyard"=>33+4*((int)card["owner"]!-1),_=>throw new NotSupportedException("Unmapped card zone") };

    // Identities/costs checked against the pinned installed read-only Arena database.
    // Creature power, toughness, damage and legality always come from Forge.
    private JObject Definition(string name)=>(JObject?)_cardManifest[name]??throw new NotSupportedException("No generated native mapping for "+name);
    private (int Grp,int Title,string[] Subtypes,int Generic,bool Instant,int Ability) Identity(string name)
    {
        var card=Definition(name);return ((int)card["grpId"]!,(int)card["titleId"]!,((JArray)card["subtypes"]!).Select(x=>(string)x!).ToArray(),(int)card["genericCost"]!,((JArray)card["types"]!).Any(t=>(string)t! =="Instant"),(int)card["abilityId"]!);
    }
    private bool BasicLand(string name)=>((JArray)Definition(name)["types"]!).Any(t=>(string)t! =="Land");
    private string Color(string name)=>(string)Definition(name)["color"]!;
    private string ManaColor(string name)=>(string?)Definition(name)["manaColor"]??throw new NotSupportedException("No source-bound mana production for "+name);
    private int StackAbilityId(JToken card)=>(int?)card["abilityId"] is int id && id!=0?id:Identity(PresentationKey(card)).Ability;
    private static string PresentationKey(JToken card)=>(string?)card["presentationKey"] ?? (string)card["name"]!;
    private IEnumerable<int> PresentedAbilities(JToken card)=>((JArray)Definition(PresentationKey(card))["abilityIds"]!).Select(v=>(int)v).Concat((card["currentAbilityIds"] as JArray ?? new JArray()).Select(v=>(int)v)).Concat(new[]{Identity(PresentationKey(card)).Ability}).Where(id=>id!=0).Distinct();
    private readonly Dictionary<(int Card,int Ability),int> _dynamicAbilityIds=new();
    private int _nextDynamicAbilityId=1000000000;
    private int UniqueAbility(JToken card,int ability){
        var definition=Definition(PresentationKey(card));var ids=((JArray)definition["abilityIds"]!).Select(v=>(int)v).Concat(new[]{(int)definition["abilityId"]!}).Where(id=>id!=0).Distinct().ToArray();
        int index=Array.IndexOf(ids,ability),forge=(int)card["forgeId"]!;
        if(index>=0 && index<16)return index==0?50000+forge:500000+16*forge+index;
        if(index<0 && !(card["currentAbilityIds"] is JArray live && live.Any(id=>(int)id==ability)))throw new NotSupportedException("Ability has no source-bound live or printed identity");
        if(!_dynamicAbilityIds.TryGetValue((forge,ability),out int unique))_dynamicAbilityIds[(forge,ability)]=unique=checked(_nextDynamicAbilityId++);
        return unique;
    }
    private static JArray NativeCost(JToken values)=>new JArray(values.Select(v=>new JObject{["color"]=v["colors"] is JArray colors?new JArray(colors.Select(c=>"ManaColor_"+(string)c!)):new JArray("ManaColor_"+(string)v["color"]!),["count"]=(int)v["count"]!}));
    private static string ManaColorName(int forgeColor) => forgeColor switch{0 or 32=>"Colorless",1=>"White",2=>"Blue",4=>"Black",8=>"Red",16=>"Green",_=>throw new NotSupportedException("Unmapped Forge mana color "+forgeColor)};
    // Owned Prompts1010/Loc244217 is exactly "Target a creature." These eight
    // pump definitions were independently qualified as one unrestricted creature
    // target. Unknown cards still fail explicitly rather than using this prompt.
    private int TargetPrompt(string name)
    {
        // Generated only from an explicit policy binding checked against the
        // owned prompt database. Unknown sources still fail, never guess.
        if(_cardManifest[name]?["targetPromptId"] is JToken prompt)
        {
            int id=(int)prompt;if(id<=0)throw new InvalidDataException("Invalid source-bound target prompt for "+name);return id;
        }
        return name switch{"Divine Arrow"=>1008,"Unsummon" or "Aegis of the Heavens" or "Antagonize" or "Dark Remedy" or "Feral Ferocity" or "Giant Growth" or "Infuriate" or "Show of Valor" or "Titanic Growth"=>1010,"Essence Scatter"=>1077,"Emry, Lurker of the Loch"=>5287,"Aether Spellbomb"=>1010,"Tormod's Crypt"=>1019,_=>throw new NotSupportedException("Unmapped target prompt for "+name)};
    }

    private JObject CardObject(JToken card)
    {
        if((string?)card["objectKind"]=="emblem"){
            var definition=Definition(PresentationKey(card));var origin=Identity((string)definition["parentName"]!);
            return new JObject{["instanceId"]=Id(card),["grpId"]=(uint)WellKnownCatalogId.Emblem,["overlayGrpId"]=(uint)WellKnownCatalogId.Emblem,["name"]=origin.Title,["type"]="GameObjectType_Emblem",["zoneId"]=26,["visibility"]="Visibility_Public",["ownerSeatId"]=(int)card["owner"]!,["controllerSeatId"]=(int)card["controller"]!,["objectSourceGrpId"]=origin.Grp,["uniqueAbilities"]=new JArray(((JArray)definition["abilityIds"]!).Select(id=>new JObject{["id"]=UniqueAbility(card,(int)id),["grpId"]=(int)id}))};
        }
        if((string?)card["objectKind"]=="ability")return new JObject
        {
            ["instanceId"]=Id(card),["grpId"]=StackAbilityId(card),
            ["type"]="GameObjectType_Ability",["zoneId"]=27,["visibility"]="Visibility_Public",
            ["ownerSeatId"]=(int)card["owner"]!,["controllerSeatId"]=(int)card["controller"]!,
            ["objectSourceGrpId"]=(bool?)Definition(PresentationKey(card))["emblemPresentation"]==true?Identity((string)Definition(PresentationKey(card))["parentName"]!).Grp:Identity(PresentationKey(card)).Grp,["parentId"]=_ids[(int)card["sourceForgeId"]!]
        };
        int zone=ZoneId(card),owner=(int)card["owner"]!;
        string name=PresentationKey(card);
        var identity=Identity(name);
        bool plains=BasicLand(name);
        var result=new JObject
        {
            ["instanceId"]=Id(card),["grpId"]=identity.Grp,["overlayGrpId"]=identity.Grp,["name"]=identity.Title,
            ["type"]="GameObjectType_Card",["zoneId"]=zone,["ownerSeatId"]=owner,["controllerSeatId"]=(int?)card["controller"] ?? owner,
            ["isTapped"]=(bool)card["tapped"]!,["visibility"]=zone==31 || (bool?)card["privateChoice"]==true?"Visibility_Private":"Visibility_Public",
            ["cardTypes"]=new JArray(((JArray)Definition(name)["types"]!).Select(t=>"CardType_"+(string)t!)),
            ["subtypes"]=new JArray(identity.Subtypes.Select(s=>"SubType_"+s)),["viewers"]=new JArray(1)
        };
        result["superTypes"]=new JArray(((JArray)Definition(name)["supertypes"]!).Select(t=>"SuperType_"+(string)t!));
        if(((JArray)Definition(name)["types"]!).Any(t=>(string)t! =="Planeswalker") && card["loyalty"]!=null){
            int loyalty=(int)card["loyalty"]!;
            if((string?)card["zone"]!="Battlefield" && int.TryParse((string?)card["baseLoyalty"],System.Globalization.NumberStyles.Integer,System.Globalization.CultureInfo.InvariantCulture,out int printed))loyalty=printed;
            result["loyalty"]=new JObject{["value"]=loyalty};
        }
        if(((JArray)Definition(name)["types"]!).Any(t=>(string)t! =="Battle") && card["defense"]!=null){
            int defense=(int)card["defense"]!;
            if((string?)card["zone"]!="Battlefield" && int.TryParse((string?)card["baseDefense"],System.Globalization.NumberStyles.Integer,System.Globalization.CultureInfo.InvariantCulture,out int printed))defense=printed;
            result["defense"]=new JObject{["value"]=defense};
        }
        if((bool?)card["token"]==true)result["type"]="GameObjectType_Token";
        SharedCharacteristicsProtocol.Apply(result,card,_typeBindings);
        bool creature=card["currentTypes"] is JArray currentTypes?currentTypes.Any(t=>(string)t! == "Creature"):((JArray)Definition(name)["types"]!).Any(t=>(string)t! == "Creature");
        if(creature){result["power"]=new JObject{["value"]=(int)card["power"]!};result["toughness"]=new JObject{["value"]=(int)card["toughness"]!};result["hasSummoningSickness"]=(bool)card["sick"]!;result["damage"]=(int)card["damage"]!;}
        int? mask=(int?)card["colorMask"];
        result["color"]=mask.HasValue?new JArray(new[]{"White","Blue","Black","Red","Green"}.Where((c,i)=>(mask.Value&(1<<i))!=0).Select(c=>"CardColor_"+c)):new JArray("CardColor_"+Color(name));
        if(plains && card["currentAbilityIds"]==null)result["uniqueAbilities"]=new JArray(new JObject{["id"]=50000+(int)card["forgeId"]!,["grpId"]=identity.Ability});
        else if(!identity.Instant && identity.Ability!=0)result["uniqueAbilities"]=new JArray(PresentedAbilities(card).Select(id=>new JObject{["id"]=UniqueAbility(card,id),["grpId"]=id}));
        if(identity.Instant){result["uniqueAbilities"]=new JArray(new JObject{["id"]=50000+(int)card["forgeId"]!,["grpId"]=identity.Ability});return result;}
            if(!creature)return result;
            result["power"]=new JObject{["value"]=(int)card["power"]!};result["toughness"]=new JObject{["value"]=(int)card["toughness"]!};
            result["hasSummoningSickness"]=(bool)card["sick"]!;result["damage"]=(int)card["damage"]!;
            int target=(int?)card["attackTarget"] ?? 0;int targetForge=(int?)card["attackTargetForgeId"] ?? 0;bool declared=false;
            var blocking=(JArray?)card["blocking"] ?? new JArray();
            if(Decision!=null)
            {
                var selected=((JArray)Decision["assignments"]!).SingleOrDefault(a=>(int)a["forgeId"]! == (int)card["forgeId"]!);
                if((string)Decision["kind"]! == "attackers" && selected!=null){target=(int)selected["targetSeat"]!;targetForge=(int?)selected["targetForgeId"] ?? 0;declared=target!=0 || targetForge!=0;}
                if((string)Decision["kind"]! == "blockers" && selected!=null){blocking=(JArray)selected["attackerIds"]!;declared=true;}
            }
            result["attackState"]=target==0 && targetForge==0?"AttackState_None":declared?"AttackState_Declared":"AttackState_Attacking";
            if(target!=0 || targetForge!=0)result["attackInfo"]=new JObject{["targetId"]=targetForge!=0?_ids[targetForge]:target};
            result["blockState"]=blocking.Count==0?((bool?)card["blocked"]==true?"BlockState_Blocked":"BlockState_None"):declared?"BlockState_Declared":"BlockState_Blocking";
            if(blocking.Count>0)result["blockInfo"]=new JObject{["attackerIds"]=new JArray(blocking.Select(id=>_ids[(int)id]))};
        return result;
    }

    private JArray Zones(IEnumerable<int>? retired=null)
    {
        var zones=(JArray)_template["zones"]!.DeepClone();
        foreach(var zone in zones)
        {
            var id=(int)zone["zoneId"]!;
            zone["objectInstanceIds"]=id==30 && retired!=null?new JArray(retired):new JArray(Cards(_state).Where(c=>ZoneId(c)==id).Select(Id));
            if(id==27 && _state["stackOrder"] is JArray order)
            {
                // Forge moves a card onto the stack before its human controller
                // finishes target/cost choices. It is not in GameStack yet, but
                // Arena must already find that card in its declared zone when
                // presenting the cast and the ensuing selection workflow.
                var stackIds=order.Select(key=>_ids[(int)key]).ToList();
                stackIds.AddRange(Cards(_state).Where(c=>ZoneId(c)==27).Select(Id).Where(cardId=>!stackIds.Contains(cardId)));
                zone["objectInstanceIds"]=new JArray(stackIds);
            }
        }
        return zones;
    }

    private JArray Offers()
    {
        if(Decision!=null || GameOver)return new JArray();
        var legal=((JArray)_state["legalLands"]!).Select(v=>(int)v).ToHashSet();
        var offers=new JArray();
        foreach(var card in VisibleCards(_state))
            if(legal.Contains((int)card["forgeId"]!))offers.Add(new JObject
            { ["actionType"]="ActionType_Play",["grpId"]=Identity(PresentationKey(card)).Grp,["instanceId"]=Id(card),["facetId"]=Id(card),["shouldStop"]=true });
        var legalMana=((JArray)_state["legalMana"]!).Select(v=>(int)v).ToHashSet();
        if(_state["legalManaOffers"] is JArray manaOffers){
            foreach(var offer in manaOffers){
                var card=((JArray)_state["battlefield"]!).Single(c=>(int)c["forgeId"]! == (int)offer["forgeId"]!);int ability=(int)offer["abilityId"]!;
                offers.Add(new JObject{["actionType"]="ActionType_Activate_Mana",["grpId"]=Identity(PresentationKey(card)).Grp,["instanceId"]=Id(card),["facetId"]=Id(card),["abilityGrpId"]=ability,["uniqueAbilityId"]=UniqueAbility(card,ability),["isBatchable"]=false});
            }
        }else foreach(var card in (JArray)_state["battlefield"]!)
            if(legalMana.Contains((int)card["forgeId"]!))offers.Add(new JObject
            { ["actionType"]="ActionType_Activate_Mana",["grpId"]=Identity(PresentationKey(card)).Grp,["instanceId"]=Id(card),["facetId"]=Id(card),
              ["abilityGrpId"]=Identity(PresentationKey(card)).Ability,["uniqueAbilityId"]=50000+(int)card["forgeId"]!,["isBatchable"]=false,
              ["manaSelections"]=new JArray(new JObject{["instanceId"]=Id(card),["abilityGrpId"]=Identity(PresentationKey(card)).Ability,
                  ["options"]=new JArray(new JObject{["mana"]=new JArray(new JObject{["color"]="ManaColor_"+ManaColor((string)card["name"]!),["count"]=1})})}) });
        var legalCasts=((JArray)_state["legalCasts"]!).Select(v=>(int)v).ToHashSet();
        foreach(var card in VisibleCards(_state))
            if(legalCasts.Contains((int)card["forgeId"]!))
            {
                var identity=Identity(PresentationKey(card));
                var cast=((JArray)_state["castOffers"]!).Single(a=>(int)a["forgeId"]! == (int)card["forgeId"]!);
                var cost=NativeCost(cast["manaCost"]!);
                offers.Add(new JObject{["actionType"]="ActionType_Cast",["grpId"]=identity.Grp,["instanceId"]=Id(card),["facetId"]=Id(card),["shouldStop"]=true,["manaCost"]=cost});
            }
        foreach(var activation in (JArray)_state["legalActivations"]!){var card=VisibleCards(_state).Single(c=>(int)c["forgeId"]! == (int)activation["forgeId"]!);int ability=(int)activation["abilityId"]!;
            offers.Add(new JObject{["actionType"]="ActionType_Activate",["grpId"]=Identity(PresentationKey(card)).Grp,["instanceId"]=Id(card),["facetId"]=Id(card),["abilityGrpId"]=ability,["uniqueAbilityId"]=UniqueAbility(card,ability),["manaCost"]=NativeCost(activation["manaCost"]!),["shouldStop"]=true});}
        if((bool?)_state["canPass"] ?? false)offers.Add(new JObject{["actionType"]="ActionType_Pass",["shouldStop"]=true});
        return offers;
    }

    private JObject TurnInfo() => NativeTurnProtocol.Info(_state);

    private static JToken? PlayerState(JObject state,int seat)=>((JArray?)state["players"])?.SingleOrDefault(p=>(int)p["seat"]! == seat);
    private static int PlayerLife(JObject state,int seat)=>(int?)PlayerState(state,seat)?["life"] ?? (int)state[seat==1?"life":"opponentLife"]!;
    private bool PlayerLost(int seat)=>(bool?)PlayerState(_state,seat)?["lost"] ?? (bool?)_state[seat==1?"localLost":"opponentLost"] ?? false;

    private JArray Players()
    {
        var players=(JArray)_template["players"]!.DeepClone();
        foreach(var player in players)
        {
            int seat=(int)player["systemSeatNumber"]!;bool local=seat==1;
            var authoritative=((JArray?)_state["players"])?.SingleOrDefault(p=>(int)p["seat"]! == seat);
            bool lost=(bool?)authoritative?["lost"] ?? (bool?)_state[local?"localLost":"opponentLost"] ?? false;
            player["lifeTotal"]=authoritative?["life"]?.DeepClone() ?? (local ? _state["life"]!.DeepClone() : _state["opponentLife"]!.DeepClone());
            player["startingLifeTotal"]=(int?)authoritative?["startingLifeTotal"] ?? (int?)_state[local?"startingLifeTotal":"opponentStartingLifeTotal"] ?? ((string?)_state["format"]=="commander-40"?40:(string?)_state["format"]=="arena-brawl"?25:20);
            ((JObject)player).Remove("pendingMessageType");
            if(!lost && (string?)Decision?["kind"]=="starting_player" && local)player["pendingMessageType"]="ClientMessageType_ChooseStartingPlayerResp";
            else if(!lost && (string?)_state["stage"]=="Mulligan" && (local || !((bool?)authoritative?["kept"] ?? (bool?)_state["opponentKept"] ?? false)))player["pendingMessageType"]="ClientMessageType_MulliganResp";
            player["mulliganCount"]=(int?)authoritative?["mulligans"] ?? (int?)_state[local?"mulligans":"opponentMulligans"] ?? 0;
            player["status"]=lost?(IsCommanderPod?"PlayerStatus_Removed":"PlayerStatus_PendingLoss"):"PlayerStatus_InGame";
            var mana=new JArray();
            if(local) foreach(var m in (JArray)_state["mana"]!)
            {
                string color=ManaColorName((int)m["color"]!);
                string key=(string?)m["sourcePresentationKey"] ?? PresentationKey(VisibleCards(_state).Single(c=>(int)c["forgeId"]! == (int)m["sourceForgeId"]!));
                mana.Add(new JObject{["manaId"]=(int)m["id"]!,["color"]="ManaColor_"+color,["srcInstanceId"]=_ids[(int)m["sourceForgeId"]!],["abilityGrpId"]=Identity(key).Ability,["count"]=(int?)m["count"] ?? 1});
            }
            player["manaPool"]=mana;
        }
        return players;
    }

    private JObject GameInfo()
    {
        var info=(JObject)_template["gameInfo"]!.DeepClone();
        if(IsCommanderPod)info["type"]="GameType_MultiPlayer";
        info["matchID"]="forge-"+_session;info["stage"]=GameOver?"GameStage_GameOver":(string?)_state["stage"]=="Mulligan" || (string?)_state["stage"]=="BeforeMulligan"?"GameStage_Start":"GameStage_Play";
        // A local sandbox has no multi-game series scoring. SingleElimination
        // would make the shipped workflow auto-choose Play and hide its browser.
        if(Scenario=="opening-duel" || Scenario=="spell-duel" || Scenario=="trigger-duel" || Scenario=="blue-duel" || Scenario=="custom-duel" || Scenario=="brawl-duel" || Scenario=="commander-duel" || Scenario=="commander-pod")info["matchWinCondition"]="MatchWinCondition_None";
        if((string?)_state["format"]=="arena-brawl" || (string?)_state["format"]=="commander-40"){info["variant"]=(string?)_state["format"]=="commander-40"?"GameVariant_Commander":"GameVariant_Brawl";info["deckConstraintInfo"]=new JObject{["minDeckSize"]=100,["maxDeckSize"]=100,["maxSideboardSize"]=0};}
        info["matchState"]=GameOver?"MatchState_MatchComplete":"MatchState_GameInProgress";
        info.Remove("results");
        if(GameOver)info["results"]=new JArray(new[]{"MatchScope_Game","MatchScope_Match"}.Select(scope=>new JObject{["scope"]=scope,["result"]=(int)_state["winnerSeat"]! == 0?"ResultType_Draw":"ResultType_WinLoss",["winningTeamId"]=(int)_state["winnerSeat"]!,["reason"]=(string?)_state["lossReason"]=="Conceded"?"ResultReason_Concede":"ResultReason_Game"}));
        return info;
    }
    private JArray TargetAnnotations()
    {
        var result=new JArray();
        foreach(var card in VisibleCards(_state).Where(c=>c["namedCardTitleIds"] is JArray names && names.Count>0))
            result.Add(new JObject{["id"]=920000+(int)card["forgeId"]!,["affectorId"]=Id(card),["affectedIds"]=card["namedCardTitleIds"]!.DeepClone(),["type"]=new JArray("AnnotationType_ReferencedCardNames")});
        foreach(var card in VisibleCards(_state).Where(c=>(bool?)c["commander"]==true))
            result.Add(new JObject{["id"]=910000+(int)card["forgeId"]!,["affectedIds"]=new JArray(Id(card)),["type"]=new JArray("AnnotationType_Designation"),
                ["details"]=new JArray(Detail("DesignationType",(int)Designation.Commander),Detail("CostIncrease",(int?)card["commanderTax"] ?? 0),Detail("grpid",Identity(PresentationKey(card)).Grp),Detail("ColorIdentity",CommanderColorIdentity((string)card["name"]!)))});
        foreach(var card in ((JArray)_state["battlefield"]!).Where(c=>(int?)c["protectorSeat"]>0))
            result.Add(new JObject{["id"]=930000+(int)card["forgeId"]!,["affectorId"]=Id(card),["affectedIds"]=new JArray((int)card["protectorSeat"]!),["type"]=new JArray("AnnotationType_Designation"),["details"]=new JArray(Detail("DesignationType",(int)Designation.Protector))});
        foreach(var card in VisibleCards(_state).Where(c=>(int?)c["classLevel"]>0))
            result.Add(new JObject{["id"]=940000+(int)card["forgeId"]!,["affectorId"]=Id(card),["affectedIds"]=new JArray(Id(card)),["type"]=new JArray("AnnotationType_ClassLevel"),["details"]=new JArray(Detail("Level",(int)card["classLevel"]!))});
        foreach(var card in ((JArray)_state["stack"]!).Concat((JArray)_state["stackAbilities"]!))
        {
            var targets=(JArray?)card["targetForgeIds"] ?? new JArray();var seats=(JArray?)card["targetSeats"] ?? new JArray();if(targets.Count+seats.Count==0)continue;
            var identity=Identity(PresentationKey(card));
            result.Add(new JObject{["id"]=900000+(int)card["forgeId"]!,["affectorId"]=Id(card),["affectedIds"]=new JArray(targets.Select(id=>_ids[(int)id]).Concat(seats.Select(s=>(int)s))),["type"]=new JArray("AnnotationType_TargetSpec"),["details"]=new JArray(Detail("abilityGrpId",(int?)card["abilityId"] is int ability && ability!=0?ability:identity.Ability),Detail("index",1),Detail("promptId",TargetPrompt(PresentationKey(card))))});
        }
        return result;
    }

    private JObject ActionRequest()
    {
        JObject message;
        if(Decision==null)message=Envelope("GREMessageType_ActionsAvailableReq",new JObject{["actions"]=Offers()},"actionsAvailableReq");
        else if(DecisionKind=="choice")
        {
            message=SharedChoiceProtocol.Request(Decision,id=>_ids[id],_stateId,++_messageId);_requestId=_messageId;return message;
        }
        else if((string)Decision["kind"]! == "assign_damage")
        {
            int source=_ids[(int)Decision["sourceForgeId"]!];int total=(int)Decision["totalDamage"]!;
            if((string?)Decision["policy"]=="divided-spell")
            {
                // Spell/ability division uses Arena's battlefield spinners,
                // not the combat damage-order browser.
                var targets=new JArray(((JArray)Decision["options"]!).Select(TargetId));
                message=Envelope("GREMessageType_DistributionReq",new JObject{["sourceId"]=source,["minAmount"]=total,["maxAmount"]=total,["minPerTarget"]=1,["targetIds"]=targets,["validSelectedTargetIds"]=targets.DeepClone()},"distributionReq");
                message["allowCancel"]=(bool?)Decision["canCancel"]==true?"AllowCancel_Abort":"AllowCancel_No";
                message["prompt"]=new JObject{["promptId"]=8,["parameters"]=new JArray(new JObject{["parameterName"]="CardId",["type"]="ParameterType_Number",["numberValue"]=source})};
                _requestId=(uint)message["msgId"]!;return message;
            }
            var assigner=new JObject{["instanceId"]=source,["totalDamage"]=total,
                ["assignments"]=new JArray(((JArray)Decision["options"]!).Select(o=>new JObject{["instanceId"]=TargetId(o),["minDamage"]=(int?)o["minimumDamage"] ?? (int?)o["lethalDamage"] ?? 0,["maxDamage"]=total,["assignedDamage"]=(int)o["assignedDamage"]!})),
                ["decisionPrompt"]=new JObject{["promptId"]=8,["parameters"]=new JArray(new JObject{["parameterName"]="CardId",["type"]="ParameterType_Number",["numberValue"]=source})}};
            message=Envelope("GREMessageType_AssignDamageReq",new JObject{["damageAssigners"]=new JArray(assigner)},"assignDamageReq");
        }
        else if((string)Decision["kind"]! == "commander_return")
        {
            int id=_ids[(int)Decision["sourceForgeId"]!];
            message=Envelope("GREMessageType_OptionalActionMessage",new JObject{["sourceId"]=id,["optionalActionTypes"]=new JArray("CardMechanicType_ZoneTransfer"),["recipientIds"]=new JArray(1)},"optionalActionMessage");
        }
        else if((string)Decision["kind"]! == "starting_player")message=Envelope("GREMessageType_ChooseStartingPlayerReq",new JObject{["teamType"]="TeamType_Individual",["systemSeatIds"]=new JArray(Enumerable.Range(1,PlayerCount))},"chooseStartingPlayerReq");
        else if((string)Decision["kind"]! == "targets")
        {
            int source=(int)Decision["sourceForgeId"]!;
            string sourceName=PresentationKey(Cards(_state).Single(c=>(int)c["forgeId"]! == source));
            int ability=(int?)Decision["sourceAbilityId"] is int nativeAbility && nativeAbility!=0?nativeAbility:Identity(sourceName).Ability;
            var selected=((JArray)Decision["assignments"]!).Select(a=>(int)a["forgeId"]!).ToHashSet();
            var selection=new JObject{["targetIdx"]=1,["minTargets"]=(int)Decision["minTargets"]!,["maxTargets"]=(int)Decision["maxTargets"]!,["selectedTargets"]=selected.Count,["targetingAbilityGrpId"]=ability,["targetingPlayer"]=1,
                ["prompt"]=new JObject{["promptId"]=TargetPrompt(sourceName)},
                ["targets"]=new JArray(((JArray)Decision["options"]!).Select(o=>new JObject{["targetInstanceId"]=TargetId(o),["legalAction"]=selected.Contains((int)o["forgeId"]!)?"SelectAction_Unselect":"SelectAction_Select",["highlight"]="HighlightType_Hot"}))};
            message=Envelope("GREMessageType_SelectTargetsReq",new JObject{["targets"]=new JArray(selection),["sourceId"]=_ids[source],["abilityGrpId"]=ability},"selectTargetsReq");
            message["allowCancel"]=(bool?)Decision["canCancel"] == false ? "AllowCancel_No" : "AllowCancel_Abort";
        }
        else if((string)Decision["kind"]! == "mulligan")
        {
            message=Envelope("GREMessageType_MulliganReq",new JObject{["mulliganType"]="MulliganType_London",["mulliganCount"]=(int)Decision["mulligans"]!,["freeMulliganCount"]=(int?)_state["freeMulliganCount"] ?? 0},"mulliganReq");
        }
        else if((string)Decision["kind"]! == "mulligan_bottom")
        {
            int count=(int)Decision["count"]!;int total=((JArray)Decision["options"]!).Count;
            message=Envelope("GREMessageType_GroupReq",new JObject{
                ["instanceIds"]=new JArray(((JArray)Decision["options"]!).Select(o=>_ids[(int)o["forgeId"]!])),
                ["groupSpecs"]=new JArray(
                    new JObject{["lowerBound"]=total-count,["upperBound"]=total-count,["zoneType"]="ZoneType_Hand",["subZoneType"]="SubZoneType_Top"},
                    new JObject{["lowerBound"]=count,["upperBound"]=count,["zoneType"]="ZoneType_Library",["subZoneType"]="SubZoneType_Bottom"}),
                ["groupType"]="GroupType_Ordered",["context"]="GroupingContext_LondonMulligan"},"groupReq");
            message["allowCancel"]="AllowCancel_No";
        }
        else if((string)Decision["kind"]! == "discard")
        {
            int count=(int)Decision["count"]!;
            message=Envelope("GREMessageType_SelectNReq",new JObject{["minSel"]=count,["maxSel"]=count,["context"]="SelectionContext_Discard",["optionContext"]="OptionContext_TurnBased",["listType"]="SelectionListType_Dynamic",["ids"]=new JArray(((JArray)Decision["options"]!).Select(o=>_ids[(int)o["forgeId"]!])),["idType"]="IdType_InstanceId",["validationType"]="SelectionValidationType_NonRepeatable"},"selectNReq");
        }
        else if(DecisionKind=="legend_rule")message=Envelope("GREMessageType_SelectNReq",new JObject{["minSel"]=1,["maxSel"]=1,["context"]="SelectionContext_None",["optionContext"]="OptionContext_TurnBased",["listType"]="SelectionListType_Dynamic",["ids"]=new JArray(((JArray)Decision["options"]!).Select(o=>_ids[(int)o["forgeId"]!])),["idType"]="IdType_InstanceId",["validationType"]="SelectionValidationType_NonRepeatable"},"selectNReq");
        else if(DecisionKind=="order_cards")
        {
            if((string?)Decision!["destination"]!="Graveyard")throw new NotSupportedException("Unmapped native ordering destination");
            message=Envelope("GREMessageType_OrderReq",new JObject{["ids"]=new JArray(((JArray)Decision["options"]!).Select(o=>_ids[(int)o["forgeId"]!])),["orderingContext"]="OrderingContext_None"},"orderReq");
            message["allowCancel"]="AllowCancel_No";
        }
        else
        {
            string kind=(string)Decision["kind"]!;
            var options=(JArray)Decision["options"]!;var assignments=(JArray)Decision["assignments"]!;
            var values=new JArray();
            foreach(var option in options)
            {
                int forge=(int)option["forgeId"]!;var chosen=assignments.SingleOrDefault(a=>(int)a["forgeId"]! == forge);
                if(kind=="attackers")
                {
                    var recipients=new JArray(((JArray)option["attackTargets"]!).Select(r=>(int)r["targetForgeId"]! == 0?
                        new JObject{["type"]="DamageRecType_Player",["playerSystemSeatId"]=(int)r["targetSeat"]!}:
                        new JObject{["type"]="DamageRecType_PlanesWalker",["planeswalkerInstanceId"]=_ids[(int)r["targetForgeId"]!]}));
                    var attacker=new JObject{["attackerInstanceId"]=_ids[forge],["legalDamageRecipients"]=recipients};
                    if(chosen!=null && (int)chosen["targetSeat"]! != 0){int pw=(int?)chosen["targetForgeId"] ?? 0;attacker["selectedDamageRecipient"]=recipients.Single(r=>pw==0?(int?)r["playerSystemSeatId"]==(int)chosen["targetSeat"]!:(int?)r["planeswalkerInstanceId"]==_ids[pw]).DeepClone();}
                    values.Add(attacker);
                }
                else if(kind=="blockers")values.Add(new JObject{["blockerInstanceId"]=_ids[forge],["attackerInstanceIds"]=new JArray(((JArray)option["attackerIds"]!).Select(id=>_ids[(int)id])),["selectedAttackerInstanceIds"]=chosen==null?new JArray():new JArray(((JArray)chosen["attackerIds"]!).Select(id=>_ids[(int)id])),["maxAttackers"]=1});
                else throw new NotSupportedException("Unmapped controller decision: "+kind);
            }
            if(kind=="attackers")message=Envelope("GREMessageType_DeclareAttackersReq",new JObject{["attackers"]=values,["qualifiedAttackers"]=values.DeepClone(),["canSubmitAttackers"]=true},"declareAttackersReq");
            else message=Envelope("GREMessageType_DeclareBlockersReq",new JObject{["blockers"]=values},"declareBlockersReq");
        }
        message["prompt"]=new JObject{["promptId"]=Decision==null?2:(string)Decision["kind"]! == "assign_damage"?8:(string)Decision["kind"]! == "targets"?10:(string)Decision["kind"]! == "starting_player"?32:(string)Decision["kind"]! == "mulligan"?34:(string)Decision["kind"]! == "mulligan_bottom"?40:(string)Decision["kind"]! == "discard"?14:(string)Decision["kind"]! == "attackers"?6:7};
        if(Decision!=null && (string)Decision["kind"]! == "mulligan")message["prompt"]!["parameters"]=new JArray(new JObject{["parameterName"]="NumberOfCards",["type"]="ParameterType_Number",["numberValue"]=7});
        if(Decision!=null && (string)Decision["kind"]! == "discard")message["prompt"]!["parameters"]=new JArray(new JObject{["parameterName"]="NumberOfCards",["type"]="ParameterType_Number",["numberValue"]=(int)Decision["count"]!});
        if(DecisionKind=="assign_damage")message.Remove("prompt"); // Native capture uses the assigner's own CardId prompt.
        if(DecisionKind=="legend_rule")message["prompt"]=new JObject{["promptId"]=72};
        if(DecisionKind=="order_cards")message["prompt"]=new JObject{["promptId"]=85}; // Owned Prompts/LocId 175: graveyard ordering.
        if(DecisionKind=="commander_return")
        {
            string zone=(string?)Decision!["choiceZone"] ?? (string)Decision!["fromZone"]!;
            int prompt=zone switch{"Graveyard"=>133,"Exile"=>134,"Library"=>135,"Hand"=>136,_=>throw new NotSupportedException("Unmapped commander return zone: "+zone)};
            var destination=zone switch{"Graveyard"=>Wotc.Mtgo.Gre.External.Messaging.ZoneType.Graveyard,"Exile"=>Wotc.Mtgo.Gre.External.Messaging.ZoneType.Exile,"Library"=>Wotc.Mtgo.Gre.External.Messaging.ZoneType.Library,_=>Wotc.Mtgo.Gre.External.Messaging.ZoneType.Hand};
            message["prompt"]=new JObject{["promptId"]=prompt,["parameters"]=new JArray(new JObject{["parameterName"]="CardId",["type"]="ParameterType_Number",["numberValue"]=_ids[(int)Decision["sourceForgeId"]!]},new JObject{["parameterName"]="CardId",["type"]="ParameterType_Number",["numberValue"]=(int)destination})};
        }
        _requestId=(uint)message["msgId"]!;return message;
    }
    private void Queue(GREToClientMessage message)
    {
        File.AppendAllText(_wire,new JObject{["direction"]="incoming",["session"]=_session,["utc"]=DateTime.UtcNow,["message"]=JObject.Parse(message.ToString())}.ToString(Formatting.None)+Environment.NewLine);
        _connection.Enqueue(message);
    }

    public void Start()
    {
        var state=(JObject)_template.DeepClone();
        state["type"]="GameStateType_Full";state["gameStateId"]=_stateId;state["pendingMessageCount"]=1;
        state["gameInfo"]=GameInfo();
        state["zones"]=Zones();state["gameObjects"]=new JArray(VisibleCards(_state).Select(CardObject));
        int turnAnnotationId=(int)_stateId*100;state["annotations"]=NativeTurnProtocol.Changes(null,_state,ref turnAnnotationId);state["persistentAnnotations"]=new JArray(TargetAnnotations().Concat(SharedCounterProtocol.Persistent(_state,id=>_ids[id])).Concat(SharedAttachmentProtocol.Persistent(_state,id=>_ids[id])).Concat(SharedKeywordProtocol.Persistent(_state,id=>_ids[id],_keywordBindings,_cardManifest)));state.Remove("diffDeletedInstanceIds");
        state["players"]=Players();state["turnInfo"]=TurnInfo();
        state["actions"]=new JArray(Offers().Select(a=>new JObject{["seatId"]=1,["action"]=a.DeepClone()}));
        Queue(Parse(Envelope("GREMessageType_GameStateMessage",state,"gameStateMessage")));
        _lastEventId=((JArray?)_state["events"]??new JArray()).Select(e=>(long)e["id"]!).DefaultIfEmpty(0).Max();
        if(!GameOver)Queue(Parse(ActionRequest()));
        _log("Forge offers " + ((JArray)_state["legalLands"]!).Count + " legal land plays");
    }

    private void Handle(ClientToGREMessage command)
    {
        if(command.Type==ClientMessageType.Uimessage)return;
        File.AppendAllText(_wire,new JObject{["direction"]="outgoing",["session"]=_session,["utc"]=DateTime.UtcNow,["message"]=JObject.Parse(command.ToString())}.ToString(Formatting.None)+Environment.NewLine);
        if(command.Type==ClientMessageType.SetSettingsReq)
        {
            _settings.MergeFrom(command.SetSettingsReq.Settings);
            _hasSettings=true;
            if(command.SetSettingsReq.Settings.AutoPassOption is AutoPassOption.Turn or AutoPassOption.UnlessOpponentAction){_yieldTurn=Turn;_yieldAcrossPod=IsCommanderPod && ActiveSeat!=1;}
            else if(command.SetSettingsReq.Settings.AutoPassOption!=AutoPassOption.None){_yieldTurn=-1;_yieldAcrossPod=false;}
            if(_fullControl){_settings.AutoPassOption=AutoPassOption.FullControl;_settings.DefaultAutoPassOption=AutoPassOption.FullControl;}
            Queue(new GREToClientMessage { Type=GREMessageType.SetSettingsResp, MsgId=++_messageId,
                SystemSeatIds={1},SetSettingsResp=new SetSettingsResp{Settings=_settings.Clone()} });
            return;
        }
        bool conceding=command.Type==ClientMessageType.ConcedeReq;
        bool cancelling=command.Type==ClientMessageType.CancelActionReq && (DecisionKind=="targets" || DecisionKind=="assign_damage" && (string?)Decision?["policy"]=="divided-spell");
        if(conceding && GameOver)return;
        if(!conceding && (_pending!=null || command.GameStateId!=_stateId || (!cancelling && command.RespId!=_requestId)))
            throw new InvalidOperationException("Rejected pending/stale native response.");
        var fields=new JObject();int nativeId=0;_pendingForgeId=0;
        int ForgeId(int native) => (DecisionKind=="targets" || DecisionKind=="assign_damage") && (native>=1 && native<=PlayerCount)?(int)((JArray)Decision!["options"]!).Single(o=>(string?)o["targetKind"]=="player" && (int)o["targetSeat"]! == native)["forgeId"]!:_ids.Single(pair=>pair.Value==native).Key;
        if(conceding)_pendingOp="concede";
        else if(Decision!=null)
        {
            string kind=(string)Decision["kind"]!;fields["decisionToken"]=Decision["token"]!.DeepClone();var assignments=new JArray();
            if(kind=="choice")
            {
                _pendingOp="submit_choice";assignments=SharedChoiceProtocol.Response(Decision,id=>_ids[id],command,_stateId,_requestId);
            }
            else if(kind=="commander_return" && command.Type==ClientMessageType.OptionalActionResp)
            {
                var answer=command.OptionalResp.Response;
                if(answer!=OptionResponse.AllowYes && answer!=OptionResponse.CancelNo)throw new InvalidOperationException("Invalid commander return response");
                _pendingOp="submit_commander_return";assignments.Add(new JObject{["returnToCommand"]=answer==OptionResponse.AllowYes});
            }
            else if(kind=="assign_damage" && cancelling)
            {
                if((bool?)Decision["canCancel"]!=true)throw new InvalidOperationException("Mandatory allocation cannot be canceled");
                _pendingOp="cancel_assign_damage";
            }
            else if(kind=="assign_damage" && (string?)Decision["policy"]=="divided-spell" && command.Type==ClientMessageType.DistributionResp)
            {
                _pendingOp="submit_assign_damage";
                foreach(var value in command.DistributionResp.Distributions)assignments.Add(new JObject{["forgeId"]=ForgeId(checked((int)value.InstanceId)),["amount"]=checked((int)value.Amount)});
            }
            else if(kind=="assign_damage" && (string?)Decision["policy"]!="divided-spell" && command.Type==ClientMessageType.AssignDamageResp)
            {
                var assigners=command.AssignDamageResp.Assigners;
                if(assigners.Count!=1 || assigners[0].InstanceId!=_ids[(int)Decision["sourceForgeId"]!] || assigners[0].TotalDamage!=(int)Decision["totalDamage"]!)throw new InvalidOperationException("Native damage source/total does not match the pending Forge choice.");
                _pendingOp="submit_assign_damage";
                foreach(var assignment in assigners[0].Assignments)assignments.Add(new JObject{["forgeId"]=ForgeId((int)assignment.InstanceId),["amount"]=(int)assignment.AssignedDamage});
            }
            else if(kind=="targets" && cancelling)_pendingOp="cancel_targets";
            else if(kind=="targets" && command.Type==ClientMessageType.SelectTargetsResp)
            {
                var choice=command.SelectTargetsResp.Target;
                if(choice.TargetIdx!=1 || choice.Targets.Count!=1 || (choice.Targets[0].LegalAction!=SelectAction.Select && choice.Targets[0].LegalAction!=SelectAction.Unselect))throw new InvalidOperationException("Unmapped native target selection");
                _pendingOp="select_targets";assignments.Add(new JObject{["forgeId"]=ForgeId((int)choice.Targets[0].TargetInstanceId),["selected"]=choice.Targets[0].LegalAction==SelectAction.Select});
            }
            else if(kind=="targets" && command.Type==ClientMessageType.SubmitTargetsReq)_pendingOp="submit_targets";
            else if(kind=="starting_player" && command.Type==ClientMessageType.ChooseStartingPlayerResp)
            {
                _pendingOp="submit_starting_player";assignments.Add(new JObject{["startingSeat"]=(int)command.ChooseStartingPlayerResp.SystemSeatId});
            }
            else if(kind=="mulligan" && command.Type==ClientMessageType.MulliganResp)
            {
                if(command.MulliganResp.Decision!=MulliganOption.AcceptHand && command.MulliganResp.Decision!=MulliganOption.Mulligan)throw new InvalidOperationException("Invalid native mulligan choice");
                _pendingOp="submit_mulligan";assignments.Add(new JObject{["keep"]=command.MulliganResp.Decision==MulliganOption.AcceptHand});
            }
            else if(kind=="mulligan_bottom" && command.Type==ClientMessageType.GroupResp)
            {
                var groups=command.GroupResp.Groups;
                if(groups.Count!=2 || groups[0].ZoneType!=Wotc.Mtgo.Gre.External.Messaging.ZoneType.Hand || groups[1].ZoneType!=Wotc.Mtgo.Gre.External.Messaging.ZoneType.Library || groups[1].SubZoneType!=SubZoneType.Bottom)throw new InvalidOperationException("Native London groups do not match hand/library bottom");
                var ids=groups.SelectMany(g=>g.Ids).ToArray();var offered=((JArray)Decision["options"]!).Select(o=>_ids[(int)o["forgeId"]!]).OrderBy(id=>id).ToArray();
                if(ids.Distinct().Count()!=ids.Length || !ids.Select(id=>(int)id).OrderBy(id=>id).SequenceEqual(offered))throw new InvalidOperationException("Native London groups must partition the offered hand");
                _pendingOp="submit_mulligan_bottom";foreach(var id in groups[1].Ids)assignments.Add(new JObject{["forgeId"]=ForgeId((int)id)});
            }
            else if((kind=="discard" || kind=="legend_rule") && command.Type==ClientMessageType.SelectNresp)
            {
                _pendingOp="submit_"+kind;foreach(var id in command.SelectNResp.Ids)assignments.Add(new JObject{["forgeId"]=ForgeId((int)id)});
            }
            else if(kind=="order_cards" && command.Type==ClientMessageType.OrderResp)
            {
                if(command.OrderResp.Ordering!=OrderingType.OrderAsIndicated)throw new NotSupportedException("Graveyard order needs the player's explicit permutation");
                // Shipped OrderRequest.SubmitOrder reverses the displayed list.
                // Forge consumes movement order, which appends bottom to top.
                _pendingOp="submit_order_cards";foreach(var id in command.OrderResp.Ids.Reverse())assignments.Add(new JObject{["forgeId"]=ForgeId((int)id)});
            }
            else if(kind=="attackers" && command.Type==ClientMessageType.DeclareAttackersResp)
            {
                _pendingOp="select_attackers";
                if(command.DeclareAttackersResp.AutoDeclare)
                {
                    foreach(var option in (JArray)Decision["options"]!)assignments.Add(AttackAssignment((int)option["forgeId"]!,command.DeclareAttackersResp.AutoDeclareDamageRecipient));
                }
                else foreach(var a in command.DeclareAttackersResp.SelectedAttackers)assignments.Add(AttackAssignment(ForgeId((int)a.AttackerInstanceId),a.SelectedDamageRecipient));
            }
            else if(kind=="attackers" && command.Type==ClientMessageType.SubmitAttackersReq)_pendingOp="submit_attackers";
            else if(kind=="blockers" && command.Type==ClientMessageType.DeclareBlockersResp)
            {
                _pendingOp="select_blockers";
                foreach(var b in command.DeclareBlockersResp.SelectedBlockers)assignments.Add(new JObject{["forgeId"]=ForgeId((int)b.BlockerInstanceId),["attackerIds"]=new JArray(b.SelectedAttackerInstanceIds.Select(id=>ForgeId((int)id)))});
            }
            else if(kind=="blockers" && command.Type==ClientMessageType.SubmitBlockersReq)_pendingOp="submit_blockers";
            else throw new NotSupportedException("Native response does not match the pending combat declaration: "+command.Type);
            fields["assignments"]=assignments;
        }
        else
        {
            if(command.Type!=ClientMessageType.PerformActionResp || command.PerformActionResp.Actions.Count!=1)throw new NotSupportedException("Unsupported native command: "+command.Type);
            var action=command.PerformActionResp.Actions[0];nativeId=(int)action.InstanceId;
            if(action.ActionType==ActionType.Pass)_pendingOp="pass_priority";
            else
            {
                if(action.ActionType!=ActionType.Play && action.ActionType!=ActionType.ActivateMana && action.ActionType!=ActionType.Cast && action.ActionType!=ActionType.Activate)throw new NotSupportedException("Unmapped native action "+action.ActionType);
                _pendingOp=action.ActionType==ActionType.Play?"play_land":action.ActionType==ActionType.Cast?"cast_spell":action.ActionType==ActionType.Activate?"activate_ability":"activate_mana";
                var card=Cards(_state).SingleOrDefault(c=>Id(c)==action.InstanceId)??throw new InvalidOperationException("Native card does not map to Forge's current state.");
                if(_pendingOp=="activate_ability"){
                    if(!((JArray)_state["legalActivations"]!).Any(a=>(int)a["forgeId"]! == (int)card["forgeId"]! && (int)a["abilityId"]! == action.AbilityGrpId))throw new InvalidOperationException("Activation was not offered by Forge");fields["abilityId"]=(int)action.AbilityGrpId;
                }else{var legal=(JArray)_state[_pendingOp=="play_land"?"legalLands":_pendingOp=="cast_spell"?"legalCasts":"legalMana"]!;
                if(!legal.Any(id=>(int)id==(int)card["forgeId"]!))throw new InvalidOperationException("Native choice was not offered by Forge.");}
                if(_pendingOp=="activate_mana"){
                    if(_state["legalManaOffers"] is JArray manaOffers){
                        if(!manaOffers.Any(a=>(int)a["forgeId"]! == (int)card["forgeId"]! && (int)a["abilityId"]! == action.AbilityGrpId))throw new InvalidOperationException("Mana activation was not offered by Forge");
                        fields["abilityId"]=(int)action.AbilityGrpId;
                    }else if(action.AbilityGrpId!=Identity(PresentationKey(card)).Ability)throw new InvalidOperationException("Unsupported native mana ability identity.");
                }
                _pendingForgeId=(int)card["forgeId"]!;
            }
        }
        _automaticSuspended=false;_pending="arena_"+Guid.NewGuid().ToString("N");BeginRulesWait();
        var request=new JObject{["id"]=_pending,["session"]=_session,["op"]=_pendingOp,["seat"]=1,["forgeId"]=_pendingForgeId,["nativeStateId"]=_stateId,["nativeResponseId"]=_requestId,["nativeArenaId"]=nativeId};
        request.Merge(fields);request["autoOrderTriggers"]=_autoOrderTriggers();request["autoChooseReplacementEffects"]=_autoChooseReplacementEffects();var path=Path.Combine(_ipc,"requests",_pending+".json");File.WriteAllText(path+".tmp",request.ToString());File.Move(path+".tmp",path);
        _log("Sent native "+_pendingOp+" choice to Forge: "+_pendingForgeId);
    }

    public void Poll()
    {
        if(_pending==null)
        {
            if(_quietAdvance)
            {
                if(!ShouldAutoPass(false))
                {
                    // Full control/a new stop can arrive while a quiet state is
                    // being presented. Offer the current decision instead.
                    _quietAdvance=false;Queue(Parse(ActionRequest()));return;
                }
                if(_presentedState()==_stateId)SubmitQuietPass();
                return;
            }
            if(ShouldAutoPass())
            {
                // Close Arena's current request through its own workflow. Advancing Forge
                // directly leaves that native request alive and can strand the next Resolve.
                if(_passPacing.TrySubmit(_stateId,_requestId,_submitAutomaticPass))_log("Native workflow auto-pass: presented request ready, no repeated phase delay");
            }
            return;
        }
        var progressPath=Path.Combine(_ipc,"decision.json");
        if(File.Exists(progressPath))
        {
            JObject? progress=null;
            try{progress=JObject.Parse(ReadShared(progressPath));_decisionReadDeniedSince=null;}
            catch(FileNotFoundException){_decisionReadDeniedSince=null;}
            catch(UnauthorizedAccessException){
                // Windows can report access denied while an atomically replaced
                // file is delete-pending. Retry on a later frame, never sleep on
                // Unity's thread. A persistent ACL failure must still stop.
                _decisionReadDeniedSince??=DateTime.UtcNow;
                if(DateTime.UtcNow-_decisionReadDeniedSince.Value>TimeSpan.FromSeconds(1))throw;
            }
            if(progress!=null && (string?)progress["session"]==_session && (string?)progress["parentRequestId"]==_pending && (string?)progress["token"]!=_lastDecisionToken)
            {
                _lastDecisionToken=(string)progress["token"]!;_pending=null;AdoptState((JObject)progress["state"]!);return;
            }
        }
        var path=Path.Combine(_ipc,"responses",_pending+".json");
        if(!File.Exists(path))
        {
            // A large combat evaluation can exceed 15 seconds without failing.
            // Keep this exact request outstanding: never resend a game action
            // and never discard its eventual session-validated result.
            // Actual engine exits are reported by the separate match service.
            if(RulesCalculationSlow && !_slowRequestReported){_slowRequestReported=true;_log("Forge is still calculating; retaining the pending request for its eventual response.");}
            return;
        }
        var response=JObject.Parse(ReadShared(path));
        if((string)response["id"]! != _pending || (string)response["session"]! != _session)throw new InvalidOperationException("Mismatched Forge response.");
        _pending=null;
        if(!(bool)response["accepted"]!){
            _automaticSuspended=true;
            // Mana abilities can already have resolved when a human payment is
            // declined or becomes unpayable. Retire its chooser using Forge's
            // authoritative result, not the stale pre-payment decision.
            AdoptState((JObject)response["state"]!);
            Gap="Forge rejected action: "+response["reason"];_log(Gap);return;
        }
        AdoptState((JObject)response["state"]!);
    }
    private void AdoptState(JObject nextState)
    {
        int previousMana=ManaTotal;var prior=_state;var oldIds=new Dictionary<int,int>(_ids);long previousEventId=_lastEventId;_state=nextState;
        Gap=(string?)_state["fidelityGap"];if(string.IsNullOrEmpty(Gap))Gap=null;
        UpdateYieldSettings(prior);
        foreach(var c in Cards(_state))if(!_ids.ContainsKey((int)c["forgeId"]!))_ids[(int)c["forgeId"]!]=_nextArenaId++;
        if(_pendingOp=="activate_mana" && _state["legalManaOffers"]==null)
        {
            var tapped=((JArray)_state["battlefield"]!).Single(c=>(int)c["forgeId"]! == _pendingForgeId);
            if(!(bool)tapped["tapped"]! || ManaTotal!=previousMana+1)throw new InvalidOperationException("Forge did not confirm basic-land mana production.");
        }
        var previous=_stateId++;
        var retired=new List<int>();int annotationId=(int)_stateId*100;var annotations=NativeTurnProtocol.Changes(prior,_state,ref annotationId);
        var countered=((JArray?)_state["events"] ?? new JArray()).Where(e=>(long)e["id"]!>_lastEventId && (string?)e["kind"]=="countered").ToDictionary(e=>(int)e["targetForgeId"]!,e=>(int)e["sourceForgeId"]!);
        var sacrificed=((JArray?)_state["events"] ?? new JArray()).Where(e=>(long)e["id"]!>_lastEventId && (string?)e["kind"]=="sacrificed").Select(e=>(int)e["sourceForgeId"]!).ToHashSet();
        foreach(var card in Cards(_state))
        {
            var before=Cards(prior).SingleOrDefault(c=>(int)c["forgeId"]! == (int)card["forgeId"]!);
            if(before==null)continue;
            if(ZoneId(before)!=ZoneId(card))
            {
                int old=Id(card),next=_nextArenaId++;retired.Add(old);_ids[(int)card["forgeId"]!]=next;
                string from=(string)before["zone"]!,to=(string)card["zone"]!;
                string category=from=="Battlefield" && to=="Hand"?"Return":from=="Library"?"Draw":to=="Stack"?"CastSpell":from=="Stack"?"Resolve":from=="Hand" && to=="Graveyard"?"Discard":to=="Graveyard"?"SBA_Damage":"PlayLand";
                if(ZoneId(card)==26)category="Put"; // Source parser supports Put; a commander return is not a land play.
                if(ZoneId(card)==29)category="Exile";
                if(from=="Library" && to=="Graveyard")category="Mill";
                if(from=="Battlefield" && to=="Graveyard" && sacrificed.Contains((int)card["forgeId"]!))category="Sacrifice";
                if(from=="Battlefield" && to=="Graveyard" && (string?)prior["decision"]?["kind"]=="legend_rule")category="SBA_Legend";
                bool wasCountered=countered.TryGetValue((int)card["forgeId"]!,out int counterSource);
                if(wasCountered)category="Countered";
                annotations.Add(new JObject{["id"]=annotationId++,["affectedIds"]=new JArray(old),["type"]=new JArray("AnnotationType_ObjectIdChanged"),["details"]=new JArray(Detail("orig_id",old),Detail("new_id",next))});
                annotations.Add(new JObject{["id"]=annotationId++,["affectedIds"]=new JArray(next),["type"]=new JArray("AnnotationType_ZoneTransfer"),["details"]=new JArray(Detail("zone_src",ZoneId(before)),Detail("zone_dest",ZoneId(card)),new JObject{["key"]="category",["type"]="KeyValuePairValueType_string",["valueString"]=new JArray(category)})});
                if(wasCountered)((JObject)annotations.Last!)["affectorId"]=oldIds[counterSource];
            }
            if(ZoneId(before)==28 && ZoneId(card)==28 && (bool?)before["tapped"] != (bool?)card["tapped"])
                annotations.Add(new JObject{["id"]=annotationId++,["affectorId"]=Id(card),["affectedIds"]=new JArray(Id(card)),["type"]=new JArray("AnnotationType_TappedUntappedPermanent"),["details"]=new JArray(Detail("tapped",(bool)card["tapped"]!?1:0))});
        }
        var priorAbilities=(JArray?)prior["stackAbilities"] ?? new JArray();
        var nextAbilities=(JArray?)_state["stackAbilities"] ?? new JArray();
        foreach(var ability in nextAbilities.Where(a=>!priorAbilities.Any(p=>(int)p["forgeId"]! == (int)a["forgeId"]!))){
            int source=(int)ability["sourceForgeId"]!;
            var sourceCard=Cards(prior).FirstOrDefault(c=>(int)c["forgeId"]! == source) ?? Cards(_state).First(c=>(int)c["forgeId"]! == source);
            annotations.Add(new JObject{["id"]=annotationId++,["affectorId"]=_ids[source],["affectedIds"]=new JArray(Id(ability)),["type"]=new JArray("AnnotationType_AbilityInstanceCreated"),["details"]=new JArray(Detail("source_zone",ZoneId(sourceCard)))});
        }
        var resolvedAbilities=priorAbilities.Where(a=>!nextAbilities.Any(n=>(int)n["forgeId"]! == (int)a["forgeId"]!)).ToList();
        foreach(var ability in resolvedAbilities)
            annotations.Add(new JObject{["id"]=annotationId++,["affectorId"]=oldIds[(int)ability["forgeId"]!],["affectedIds"]=new JArray(oldIds[(int)ability["forgeId"]!]),["type"]=new JArray("AnnotationType_ResolutionStart"),["details"]=new JArray(Detail("grpid",StackAbilityId(ability)))});
        // The owned TokenCreatedEventParser requires an explicit annotation;
        // merely adding a token to the object list does not create its native view.
        foreach(var token in VisibleCards(_state).Where(c=>(bool?)c["token"]==true && !VisibleCards(prior).Any(p=>(int)p["forgeId"]! ==(int)c["forgeId"]!)))
        {
            var created=new JObject{["id"]=annotationId++,["affectedIds"]=new JArray(Id(token)),["type"]=new JArray("AnnotationType_TokenCreated")};
            if((int?)token["sourceForgeId"] is int source && _ids.TryGetValue(source,out int sourceId))created["affectorId"]=sourceId;
            annotations.Add(created);
        }
        var vanishedTokens=VisibleCards(prior).Where(c=>(bool?)c["token"]==true && !VisibleCards(_state).Any(n=>(int)n["forgeId"]! ==(int)c["forgeId"]!)).Select(c=>oldIds[(int)c["forgeId"]!]).ToList();
        if(vanishedTokens.Count>0)annotations.Add(new JObject{["id"]=annotationId++,["affectedIds"]=new JArray(vanishedTokens),["type"]=new JArray("AnnotationType_TokenDeleted")});
        // A copied spell ceases to exist after resolution/countering. It has no
        // graveyard card to carry an ObjectIdChanged event into the next state.
        var currentObjectIds=Cards(_state).Select(c=>(int)c["forgeId"]!).ToHashSet();
        var vanishedCopies=Cards(prior).Where(c=>(bool?)c["ephemeralCopy"]==true && !currentObjectIds.Contains((int)c["forgeId"]!)).Select(c=>oldIds[(int)c["forgeId"]!]).ToList();
        var eliminatedObjects=IsCommanderPod?Cards(prior).Where(c=>PlayerLost((int)c["owner"]!) && !currentObjectIds.Contains((int)c["forgeId"]!)).Select(c=>oldIds[(int)c["forgeId"]!]).ToList():new List<int>();
        var damageSources=new Dictionary<int,int>();
        foreach(var e in (JArray?)_state["events"] ?? new JArray())
        {
            long eventId=(long)e["id"]!;if(eventId<=_lastEventId)continue;_lastEventId=eventId;
            if((string?)e["kind"]=="life-gain")
            {
                int gainSource=(int)e["sourceStackForgeId"]!;
                if(oldIds.TryGetValue(gainSource,out int gainSourceId))damageSources[(int)e["targetSeat"]!]=gainSourceId;
                continue;
            }
            if((string?)e["kind"]!="damage")continue;
            int source=(int)e["sourceForgeId"]!;int sourceId=oldIds.ContainsKey(source)?oldIds[source]:_ids[source];
            int target=e["targetSeat"]!=null?(int)e["targetSeat"]!:oldIds[(int)e["targetForgeId"]!];
            annotations.Insert(0,new JObject{["id"]=annotationId++,["affectorId"]=sourceId,["affectedIds"]=new JArray(target),["type"]=new JArray("AnnotationType_DamageDealt"),["details"]=new JArray(Detail("damage",(int)e["amount"]!),Detail("type",(int)((bool)e["combat"]!?DamageType.Combat:DamageType.Direct)),Detail("markDamage",1))});
            if(e["targetSeat"]!=null)
            {
                damageSources[target]=sourceId;
            }
        }
        foreach(int seat in Enumerable.Range(1,PlayerCount))
        {
            int change=PlayerLife(_state,seat)-PlayerLife(prior,seat);
            // Arena distributes one aggregate life-loss event across all combat hits to this player.
            // Separate source-specific life events make its ModifyEventsList cap later hits at zero.
            if(change!=0)annotations.Add(new JObject{["id"]=annotationId++,["affectorId"]=damageSources.TryGetValue(seat,out int sourceId)?sourceId:seat,["affectedIds"]=new JArray(seat),["type"]=new JArray("AnnotationType_ModifiedLife"),["details"]=new JArray(Detail("life",change))});
        }
        foreach(var ability in resolvedAbilities)
        {
            int id=oldIds[(int)ability["forgeId"]!];
            annotations.Add(new JObject{["id"]=annotationId++,["affectorId"]=id,["affectedIds"]=new JArray(id),["type"]=new JArray("AnnotationType_ResolutionComplete"),["details"]=new JArray(Detail("grpid",StackAbilityId(ability)))});
        }
        var newlyCast=((JArray)_state["stack"]!).SingleOrDefault(c=>(int)c["owner"]! == 1 && ((JArray)prior["hand"]!).Any(p=>(int)p["forgeId"]! == (int)c["forgeId"]!));
        if(newlyCast!=null)foreach(var mana in (JArray)prior["mana"]!)
            if(!((JArray)_state["mana"]!).Any(m=>(int)m["id"]! == (int)mana["id"]!))
                annotations.Add(new JObject{["id"]=annotationId++,["affectorId"]=_ids[(int)mana["sourceForgeId"]!],["affectedIds"]=new JArray(Id(newlyCast)),["type"]=new JArray("AnnotationType_ManaPaid"),["details"]=new JArray(Detail("id",(int)mana["id"]!),Detail("color",(int)mana["color"]!))});
        foreach(var counter in SharedCounterProtocol.Changes(_state,previousEventId,id=>_ids[id],id=>oldIds.TryGetValue(id,out int priorId)?priorId:_ids.TryGetValue(id,out int native)?native:null,ref annotationId))annotations.Add(counter);
        var nextCounterState=SharedCounterProtocol.Persistent(_state,id=>_ids[id]);var counterIds=nextCounterState.Select(c=>(uint)c["id"]!).ToHashSet();
        var retiredCounters=SharedCounterProtocol.Persistent(prior,id=>oldIds[id]).Where(c=>!counterIds.Contains((uint)c["id"]!)).Select(c=>(uint)c["id"]!);
        foreach(var attachment in SharedAttachmentProtocol.CreatedEvents(_state,previousEventId,id=>_ids[id],ref annotationId))annotations.Add(attachment);
        var nextAttachmentState=SharedAttachmentProtocol.Persistent(_state,id=>_ids[id]);var attachmentIds=nextAttachmentState.Select(c=>(uint)c["id"]!).ToHashSet();
        var retiredAttachments=SharedAttachmentProtocol.Persistent(prior,id=>oldIds[id]).Where(c=>!attachmentIds.Contains((uint)c["id"]!)).Select(c=>(uint)c["id"]!);
        var nextKeywordState=SharedKeywordProtocol.Persistent(_state,id=>_ids[id],_keywordBindings,_cardManifest);var keywordIds=nextKeywordState.Select(c=>(uint)c["id"]!).ToHashSet();
        var retiredKeywords=SharedKeywordProtocol.Persistent(prior,id=>oldIds[id],_keywordBindings,_cardManifest).Where(c=>!keywordIds.Contains((uint)c["id"]!)).Select(c=>(uint)c["id"]!);
        var nowVisible=VisibleCards(_state).ToArray();var visibleIds=nowVisible.Select(c=>(int)c["forgeId"]!).ToHashSet();
        var concealed=VisibleCards(prior).Where(c=>(bool?)c["privateChoice"]==true && !visibleIds.Contains((int)c["forgeId"]!)).Select(c=>Cards(_state).Single(n=>(int)n["forgeId"]! == (int)c["forgeId"]!)).Select(c=>new JObject
            {["instanceId"]=Id(c),["grpId"]=0,["overlayGrpId"]=0,["name"]=0,["type"]="GameObjectType_Card",["zoneId"]=ZoneId(c),["ownerSeatId"]=(int)c["owner"]!,["controllerSeatId"]=(int)c["controller"]!,["visibility"]="Visibility_Hidden"});
        bool quiet=!GameOver && ShouldAutoPass(false);
        var delta=new JObject { ["type"]="GameStateType_Diff",["gameStateId"]=_stateId,["prevGameStateId"]=previous,["pendingMessageCount"]=quiet || LocalPodEliminated?0:1,
            ["zones"]=Zones(retired),["players"]=Players(),["turnInfo"]=TurnInfo(),["gameObjects"]=new JArray(nowVisible.Select(CardObject).Concat(concealed)),["annotations"]=annotations,
            ["persistentAnnotations"]=new JArray(TargetAnnotations().Concat(nextCounterState).Concat(nextAttachmentState).Concat(nextKeywordState)),
            ["diffDeletedInstanceIds"]=new JArray(resolvedAbilities.Select(a=>oldIds[(int)a["forgeId"]!]).Concat(vanishedTokens).Concat(vanishedCopies).Concat(eliminatedObjects).Distinct()),
            ["diffDeletedPersistentAnnotationIds"]=new JArray(((JArray)prior["stack"]!).Concat(priorAbilities).Where(c=>(((JArray?)c["targetForgeIds"])?.Count ?? 0)+(((JArray?)c["targetSeats"])?.Count ?? 0)>0 && !((JArray)_state["stack"]!).Concat(nextAbilities).Any(n=>(int)n["forgeId"]! == (int)c["forgeId"]!)).Select(c=>900000+(int)c["forgeId"]!)),
            ["actions"]=new JArray(Offers().Select(a=>new JObject{["seatId"]=1,["action"]=a.DeepClone()})) };
        if(GameOver || (string?)prior["stage"] != (string?)_state["stage"])delta["gameInfo"]=GameInfo();
        foreach(uint id in retiredCounters)((JArray)delta["diffDeletedPersistentAnnotationIds"]!).Add(id);
        foreach(var card in ((JArray)prior["battlefield"]!).Where(c=>(int?)c["protectorSeat"]>0 && !((JArray)_state["battlefield"]!).Any(n=>(int)n["forgeId"]! == (int)c["forgeId"]! && (int?)n["protectorSeat"]>0)))
            ((JArray)delta["diffDeletedPersistentAnnotationIds"]!).Add(930000+(int)card["forgeId"]!);
        foreach(var card in VisibleCards(prior).Where(c=>(int?)c["classLevel"]>0 && !VisibleCards(_state).Any(n=>(int)n["forgeId"]! == (int)c["forgeId"]! && (int?)n["classLevel"]>0)))
            ((JArray)delta["diffDeletedPersistentAnnotationIds"]!).Add(940000+(int)card["forgeId"]!);
        foreach(uint id in retiredAttachments)((JArray)delta["diffDeletedPersistentAnnotationIds"]!).Add(id);
        foreach(uint id in retiredKeywords)((JArray)delta["diffDeletedPersistentAnnotationIds"]!).Add(id);
        if(GameOver)
        {
            delta["gameInfo"]=GameInfo();
            delta["teams"]=new JArray(Enumerable.Range(1,PlayerCount).Select(seat=>new JObject{["id"]=seat,["playerIds"]=new JArray(seat),["status"]=PlayerLost(seat)?"TeamStatus_PendingLoss":"TeamStatus_InGame"}));
            string reason=(string?)_state["lossReason"] switch {"LifeReachedZero"=>"SBA_LifeTotal","Milled"=>"SBA_DrawFromEmptyLib","Conceded"=>"SBA_Concede",_=>"Other"};
            delta["persistentAnnotations"]=new JArray(new JObject{["id"]=annotationId++,["affectedIds"]=new JArray(Enumerable.Range(1,PlayerCount).Where(PlayerLost)),["type"]=new JArray("AnnotationType_LossOfGame"),["details"]=new JArray(new JObject{["key"]="reason",["type"]="KeyValuePairValueType_string",["valueString"]=new JArray(reason)})});
        }
        Queue(Parse(Envelope("GREMessageType_GameStateMessage",delta,"gameStateMessage")));
        _quietAdvance=quiet;
        if(quiet)_requestId=0;
        else if(!GameOver && !LocalPodEliminated)Queue(Parse(ActionRequest()));
        else if(LocalPodEliminated && !GameOver)_requestId=0;
        else Queue(Parse(Envelope("GREMessageType_IntermissionReq",new JObject
        {
            ["result"]=((JArray)GameInfo()["results"]!)[1].DeepClone(),
            ["intermissionPrompt"]=new JObject{["promptId"]=27,["parameters"]=new JArray(new JObject{["parameterName"]="WinningTeamId",["type"]="ParameterType_Number",["numberValue"]=(int)_state["winnerSeat"]!})}
        },"intermissionReq")));
        _log("Forge accepted "+_pendingOp+"; native update queued; mana="+ManaTotal);
        Gap=(string?)_state["fidelityGap"];if(string.IsNullOrEmpty(Gap))Gap=null;
    }
    private void SubmitQuietPass()
    {
        // There is no native user request to retire for this state. Like the
        // captured Arena server, Forge advances an empty priority window without
        // briefly opening a Pass/Next workflow for every rules sub-step.
        _quietAdvance=false;_pendingOp="pass_priority";_pendingForgeId=0;
        _pending="rules_"+Guid.NewGuid().ToString("N");BeginRulesWait();
        var request=new JObject{["id"]=_pending,["session"]=_session,["op"]=_pendingOp,["seat"]=1,["forgeId"]=0,["nativeStateId"]=_stateId,["nativeResponseId"]=0,["automaticRulesStep"]=true};
        request["autoOrderTriggers"]=_autoOrderTriggers();
        request["autoChooseReplacementEffects"]=_autoChooseReplacementEffects();
        var path=Path.Combine(_ipc,"requests",_pending+".json");File.WriteAllText(path+".tmp",request.ToString());File.Move(path+".tmp",path);
        File.AppendAllText(_wire,new JObject{["direction"]="internal-rules",["session"]=_session,["utc"]=DateTime.UtcNow,["request"]=request}.ToString(Formatting.None)+Environment.NewLine);
        _log("Forge automatic progression without an unnecessary native action prompt");
    }
    private void UpdateYieldSettings(JObject prior)
    {
        bool changed=false;
        if(_yieldTurn>=0)
        {
            bool opponentAction=Cards(_state).Any(c=>(string?)c["zone"]=="Stack" && (int?)c["controller"]!=1 && !Cards(prior).Any(p=>(string?)p["zone"]=="Stack" && (int?)p["forgeId"]==(int?)c["forgeId"]))
                || ((JArray)_state["battlefield"]!).Any(c=>(int?)c["controller"]!=1 && ((int?)c["attackTarget"]>0 || (int?)c["attackTargetForgeId"]>0) && !((JArray)prior["battlefield"]!).Any(p=>(int?)p["forgeId"]==(int?)c["forgeId"] && ((int?)p["attackTarget"]>0 || (int?)p["attackTargetForgeId"]>0)));
            // In a pod, yielding during another player's turn means waiting
            // through every remaining opponent, including extra turns, until
            // the human actually receives the next turn. Own-turn and duel
            // boundaries retain the previously accepted behavior.
            bool boundary=_yieldAcrossPod?ActiveSeat==1 && Turn!=_yieldTurn:Turn!=_yieldTurn || Phase=="END_OF_TURN";
            if(boundary || (_settings.TurnAutoPassOption()==AutoPassOption.UnlessOpponentAction && opponentAction))
            {_yieldTurn=-1;_yieldAcrossPod=false;_settings.AutoPassOption=AutoPassOption.Clear;changed=true;}
        }
        if(_settings.StackAutoPassOption==AutoPassOption.ResolveAll && !((JArray)_state["stack"]!).HasValues && !((JArray?)_state["stackAbilities"]??new JArray()).HasValues)
        {_settings.StackAutoPassOption=AutoPassOption.Clear;changed=true;}
        if(changed)Queue(new GREToClientMessage{Type=GREMessageType.SetSettingsResp,MsgId=++_messageId,SystemSeatIds={1},SetSettingsResp=new SetSettingsResp{Settings=_settings.Clone()}});
    }
    private bool ShouldAutoPass(bool requirePresentation=true)
    {
        if(_automaticSuspended || !_hasSettings || _fullControl || _settings.FullControlEnabled() || _settings.Stops.Count>0 || _settings.TransientStops.Count>0 || (requirePresentation && _presentedState()!=_stateId) || GameOver || LocalPodEliminated || Gap!=null || Decision!=null || !((bool?)_state["canPass"] ?? false))return false;
        // Local bridge automation policy, not a reconstruction of Arena's
        // server-side smart-stop engine. Legal offers remain Forge-owned.
        var mode=_settings.TurnAutoPassOption();
        if(mode is AutoPassOption.Turn or AutoPassOption.UnlessOpponentAction)return true;
        if(mode!=AutoPassOption.ResolveMyStackEffects && mode!=AutoPassOption.None)return false;
        bool noActions=((JArray)_state["legalLands"]!).Count==0 && ((JArray)_state["legalCasts"]!).Count==0 && ((JArray)_state["legalActivations"]!).Count==0;
        var order=(JArray?)_state["stackOrder"];
        if(order!=null && order.Count>0)return noActions || _settings.StackAutoPassOption==AutoPassOption.ResolveAll || (mode==AutoPassOption.ResolveMyStackEffects && (int)Cards(_state).Single(c=>(int)c["forgeId"]! == (int)order[0])["controller"]! == 1);
        var stack=(JArray)_state["stack"]!;
        if(stack.Count>0)return noActions || _settings.StackAutoPassOption==AutoPassOption.ResolveAll || (mode==AutoPassOption.ResolveMyStackEffects && (int)stack.Last!["owner"]! == 1);
        return noActions;
    }
    private JObject AttackAssignment(int attacker,DamageRecipient? recipient)
    {
        if(recipient==null || recipient.Type==DamageRecType.None)return new JObject{["forgeId"]=attacker,["targetSeat"]=0};
        if(recipient.Type==DamageRecType.Player)return new JObject{["forgeId"]=attacker,["targetSeat"]=(int)recipient.PlayerSystemSeatId};
        if(recipient.Type==DamageRecType.PlanesWalker)
        {
            int target=_ids.Single(pair=>pair.Value==(int)recipient.PlaneswalkerInstanceId).Key;
            var option=((JArray)Decision!["options"]!).Single(c=>(int)c["forgeId"]! == attacker);
            var offered=((JArray)option["attackTargets"]!).Single(c=>(int)c["targetForgeId"]! == target);
            return new JObject{["forgeId"]=attacker,["targetSeat"]=(int)offered["targetSeat"]!,["targetForgeId"]=target};
        }
        throw new NotSupportedException("Unmapped attack recipient: "+recipient.Type);
    }
    private int[] CommanderColorIdentity(string name)
    {
        var identity=((JArray)Definition(name)["colorIdentity"]!).Select(c=>(string)c!).ToHashSet();
        var colors=new[]{("W",CardColor.White),("U",CardColor.Blue),("B",CardColor.Black),("R",CardColor.Red),("G",CardColor.Green)};
        if(identity.Except(colors.Select(c=>c.Item1)).Any())throw new NotSupportedException("Unknown commander colour identity: "+name);
        return colors.Where(c=>identity.Contains(c.Item1)).Select(c=>(int)c.Item2).ToArray();
    }
    private static JObject Detail(string key,params int[] values) => new JObject{["key"]=key,["type"]="KeyValuePairValueType_int32",["valueInt32"]=new JArray(values)};
}
