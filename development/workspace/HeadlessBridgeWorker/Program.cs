using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.Loader;
using System.Threading;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using ForgeArenaSandbox;
using GreClient.Rules;
using Wotc.Mtga.Cards.Database;
using Wotc.Mtgo.Gre.External.Messaging;

internal static class Program
{
    private static int Integer(JToken? value,string field)
    {
        if(value?.Type!=JTokenType.Integer || (long)value<int.MinValue || (long)value>int.MaxValue)throw new ArgumentException(field+" must be an exact bounded integer");return (int)value;
    }
    private static void Fields(JToken value,params string[] fields)
    {
        if(value is not JObject item || !item.Properties().Select(p=>p.Name).ToHashSet().SetEquals(fields))throw new ArgumentException("Missing or unexpected native selection fields");
    }
    private static int Main(string[] args)
    {
        if(args.Length!=4)throw new ArgumentException("HeadlessBridgeWorker <managed-dir> <research-lab> <research-ipc> <empty-state-fixture>");
        string managed=Path.GetFullPath(args[0]);
        AssemblyLoadContext.Default.Resolving+=(_,name)=>{string path=Path.Combine(managed,name.Name+".dll");return File.Exists(path)?AssemblyLoadContext.Default.LoadFromAssemblyPath(path):null;};
        try{return Run(args);}catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
    private static void Write(string path,JToken value)
    {
        string temporary=path+".pending";File.WriteAllText(temporary,value.ToString(Formatting.None));
        // A Windows reader can briefly hold the old JSON without delete sharing.
        // Retain the complete pending write and retry that same atomic replace.
        for(int attempt=0;;attempt++)
        {
            try{File.Move(temporary,path,true);return;}
            catch(IOException) when(attempt<11){Thread.Sleep(10);}
            catch(UnauthorizedAccessException) when(attempt<11){Thread.Sleep(10);}
        }
    }
    private static JObject Read(string path)
    {
        using var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete);
        using var reader=new StreamReader(file);return JObject.Parse(reader.ReadToEnd());
    }
    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static int Run(string[] args)
    {
        string root=Path.GetFullPath(args[1]),ipc=Path.GetFullPath(args[2]);
        if((bool?)Read(Path.Combine(root,"bridge-card-manifest.json"))["researchOnly"]!=true || File.Exists(Path.Combine(root,"MTGA.exe")))throw new InvalidOperationException("Worker is restricted to a private research runtime without a game executable");
        string fixture=Path.Combine(root,"board-fixture.json");if(!File.Exists(fixture))File.Copy(args[3],fixture);
        string work=Path.Combine(ipc,"native-worker");Directory.CreateDirectory(work);Directory.CreateDirectory(Path.Combine(work,"requests"));Directory.CreateDirectory(Path.Combine(work,"responses"));
        if(File.Exists(Path.Combine(work,"ready.json")))throw new InvalidOperationException("Native worker cannot attach twice to the same evidence folder");
        string worker=Guid.NewGuid().ToString("N");var timer=Stopwatch.StartNew();
        using var gre=new GreInterface(NullCardDatabaseAdapter.Default,null,null,true,null);
        var local=new LocalGreConnection();local.MessageReceived+=gre.OnMessageReceived;local.Connect(null!);local.ConnectToGRE(LocalGreConnection.LocalUri,local.MatchId);
        long pollTicks=0,drainTicks=0,validationTicks=0,statusTicks=0;
        uint? presented=null;BaseUserRequest? interaction=null;MtgGameState? latest=null;long updateOrdinal=0;bool dirty=false;
        using var journal=new StreamWriter(Path.Combine(work,"native-model.jsonl"),false){AutoFlush=true};
        void Record(string kind,JToken value)=>journal.WriteLine(new JObject{["kind"]=kind,["ordinal"]=updateOrdinal,["value"]=value}.ToString(Formatting.None));
        void Drain()
        {
            for(int i=0;i<8;i++)
            {
                local.ProcessMessages();gre.ProcessQueues();
                foreach(var item in gre.RetrieveClientUpdates())if(item is GreClient.Rules.GameStateUpdate update)
                {
                    latest=update.NewState;presented=latest.Id;interaction=update.Interaction;updateOrdinal++;dirty=true;
                    foreach(var flip in update.Changes.OfType<CoinFlipEvent>())
                        Record("native-coin-flip",new JObject{["sourceId"]=flip.AffectorId,["seat"]=flip.AffectedId,["heads"]=new JArray(flip.Results)});
                    if(interaction is SelectNRequest choice)
                    {
                        // Exercise original classifiers used by the Unity
                        // workflow translator, not only the GRE parser. The
                        // Room classifier dereferences Prompt for card choices.
                        bool room=choice.IsRoomUnlockSubCardSelection(latest),revealed=choice.IsRevealedCardSelection(latest);
                        Record("original-selection-classifiers",new JObject{["roomUnlock"]=room,["revealedCards"]=revealed,["promptId"]=choice.Prompt?.PromptId});
                        if(choice.IsChoiceSelection && choice.IdType==IdType.PromptParameterIndex)Record("original-choice-ui",NativeChoicePresentation.Verify(choice,latest));
                    }
                    Record("native-update",new JObject{["stateId"]=presented,["interaction"]=interaction?.GetType().Name,
                        ["promptId"]=interaction?.Prompt?.PromptId,
                        ["promptParameters"]=interaction?.Prompt==null?new JArray():new JArray(interaction.Prompt.Parameters.Select(p=>new JObject{["name"]=p.ParameterName,["type"]=p.Type.ToString(),["number"]=p.NumberValue})),
                        ["cards"]=new JArray(latest.AllCards.Select(p=>new JObject{["id"]=p.Key,["grpId"]=p.Value.BaseGrpId,["damage"]=p.Value.Damage,["phasedOut"]=p.Value.IsPhasedOut,["zone"]=p.Value.Zone?.Type.ToString(),["keywordGrants"]=new JArray(p.Value.AbilityAdders.Select(g=>new JObject{["abilityId"]=g.AbilityId,["sourceId"]=g.AddedById,["layerId"]=g.LayeredEffectId})),["counters"]=new JArray(p.Value.Counters.Select(c=>new JObject{["type"]=c.Key.ToString(),["count"]=c.Value}))})),
                        ["events"]=new JArray(update.Changes.Select(c=>c.GetType().Name)),
                        ["phaseEvents"]=new JArray(update.Changes.OfType<CardChangedEvent>().Where(c=>c.Property==PropertyType.PhaseState).Select(c=>new JObject{["id"]=c.NewInstance.InstanceId,["from"]=c.OldInstance.Zone.Type.ToString(),["to"]=c.NewInstance.Zone.Type.ToString()})),
                        ["deletedCards"]=new JArray(update.Changes.OfType<CardDeletedEvent>().Select(c=>c.CardId)),
                        ["damageEvents"]=new JArray(update.Changes.OfType<DamageDealtEvent>().Select(c=>new JObject{["source"]=c.Damager.InstanceId,["target"]=c.Victim.InstanceId,["amount"]=c.Amount,["type"]=c.Type.ToString()}))});
                }
            }
        }
        var scenario=JObject.Parse(File.ReadAllText(Path.Combine(ipc,"scenario.json")));
        if(scenario["autoOrderTriggers"]!=null && scenario["autoOrderTriggers"]!.Type!=JTokenType.Boolean)throw new InvalidDataException("Research trigger preference must be boolean");
        bool autoOrderTriggers=(bool?)scenario["autoOrderTriggers"]??true;
        if(scenario["autoChooseReplacementEffects"]!=null && scenario["autoChooseReplacementEffects"]!.Type!=JTokenType.Boolean)throw new InvalidDataException("Research replacement preference must be boolean");
        bool autoChooseReplacementEffects=(bool?)scenario["autoChooseReplacementEffects"]??false;
        bool automaticStack=false;
        bool AutoPass()
        {
            if(!automaticStack || interaction is not ActionsAvailableRequest actions || interaction.OriginalMessage.GameStateId!=presented)return false;
            actions.SubmitPass();var outgoing=gre.DequeueOutgoingMessage()??throw new InvalidOperationException("Native automatic pass emitted no message");local.SendMessage(outgoing);Record("automatic-native-command",JObject.Parse(outgoing.ToString()));return true;
        }
        var bridge=new ForgeLandBridge(root,local,message=>Record("bridge-log",new JValue(message)),()=>presented,AutoPass,ipc,autoOrderTriggers:()=>autoOrderTriggers,autoChooseReplacementEffects:()=>autoChooseReplacementEffects);
        NativeCastAvailability.AuthoritativeCast=bridge.CanHighlightCast;
        bridge.ConfigureLoopSubmission(recorded=>{
            if(interaction?.OnSubmit==null || interaction.OriginalMessage.GameStateId!=presented)return false;
            NativeLoopSubmission.Submit(interaction,recorded);
            var outgoing=gre.DequeueOutgoingMessage()??throw new InvalidOperationException("Native loop request emitted no message");
            local.SendMessage(outgoing);Record("loop-native-command",JObject.Parse(outgoing.ToString()));return true;
        });
        JArray CastAvailability()
        {
            var result=new JArray();
            if(interaction is not ActionsAvailableRequest actions)return result;
            foreach(var action in actions.Actions.Where(a=>a.ActionType==ActionType.Cast))
            {
                var foreign=action.Clone();foreign.InstanceId=uint.MaxValue;
                var wrongPrinting=action.Clone();wrongPrinting.GrpId=uint.MaxValue;
                var activation=action.Clone();activation.ActionType=ActionType.Activate;
                bool native=global::ActionExtensions.CanAffordToCast(action);
                result.Add(new JObject{["instanceId"]=action.InstanceId,["grpId"]=action.GrpId,["nativeAffordable"]=native,["forgeAffordable"]=bridge.CanHighlightCast(action),["effectiveAffordable"]=NativeCastAvailability.Evaluate(action,native),["foreignInstanceOverride"]=NativeCastAvailability.Evaluate(foreign,false),["wrongPrintingOverride"]=NativeCastAvailability.Evaluate(wrongPrinting,false),["activationOverride"]=NativeCastAvailability.Evaluate(activation,false)});
            }
            return result;
        }
        JObject Status()=>new JObject{["schema"]=1,["worker"]=worker,["session"]=bridge.Session,["nativeStateId"]=presented,["nativeMessageId"]=interaction?.OriginalMessage.MsgId,["updateOrdinal"]=updateOrdinal,["interaction"]=interaction?.GetType().Name,["gap"]=bridge.Gap,["state"]=bridge.ResearchState,["loop"]=bridge.LoopStatus,["timingTicks"]=new JObject{["frequency"]=Stopwatch.Frequency,["poll"]=pollTicks,["drain"]=drainTicks,["validation"]=validationTicks,["status"]=statusTicks},["castAvailability"]=CastAvailability(),["podDetails"]=bridge.IsCommanderPod?bridge.PodDetails():null};
        var observedCopyIds=new Dictionary<int,uint>();
        void ValidateModel()
        {
            if(latest==null)throw new InvalidOperationException("Native parser produced no game-state model");
            var state=bridge.ResearchState;
            if((string?)state["phase"]=="COMBAT_DECLARE_ATTACKERS" && ((JArray)state["battlefield"]!).Any(c=>(int?)c["attackTargetForgeId"]>0) && (latest.NextPhase!=Phase.Combat || latest.NextStep!=Step.DeclareBlock))throw new InvalidOperationException("A planeswalker attack must retain the native blocker-step destination");
            var visible=new[]{"hand","battlefield","stack","graveyard","command","exile"}.SelectMany(k=>(JArray?)state[k]??new JArray()).ToArray();
            var hidden=((JArray?)state["hidden"]??new JArray()).ToArray();
            var liveObjects=visible.Concat(hidden).Concat((JArray?)state["stackAbilities"]??new JArray()).ToList();
            var pendingCopy=state["decision"]?["choice"]?["pendingCopyObject"] as JObject ?? state["decision"]?["pendingCopyObject"] as JObject;
            if(pendingCopy!=null)liveObjects.Add(pendingCopy);
            var currentObjectIds=liveObjects.Select(c=>(int)c["forgeId"]!).ToHashSet();
            // ObjectIdChanged retains historical identities for native animation.
            // Only the copy's latest live identity must disappear on resolution.
            foreach(var copy in liveObjects.Where(c=>(bool?)c["ephemeralCopy"]==true)){int forge=(int)copy["forgeId"]!;observedCopyIds[forge]=checked((uint)bridge.ResearchInstanceId(forge));}
            if(observedCopyIds.Any(p=>!currentObjectIds.Contains(p.Key) && latest.AllCards.ContainsKey(p.Value)))throw new InvalidOperationException("Resolved copied spell remains in the native model");
            var temporaryViews=SharedChoiceVisibility.Views(state,visible.Concat(hidden)).Where(c=>(bool?)c["privateChoice"]==true).ToDictionary(c=>(int)c["forgeId"]!);
            foreach(var card in hidden)
            {
                int forge=(int)card["forgeId"]!;uint id=checked((uint)bridge.ResearchInstanceId(forge));
                uint expected=temporaryViews.TryGetValue(forge,out var view)?checked((uint)bridge.ResearchPrintingId((string?)view["presentationKey"] ?? (string)view["name"]!)):0;
                if(latest.AllCards.TryGetValue(id,out var native)){if(native.BaseGrpId!=expected)throw new InvalidOperationException("Native hidden/temporary identity differs from the explicit chooser visibility");}
                else if(expected!=0)throw new InvalidOperationException("Explicitly revealed card is absent from the native model");
            }
            var attachedWith=new Dictionary<uint,HashSet<uint>>();
            foreach(var card in visible)
            {
                uint source=checked((uint)bridge.ResearchInstanceId((int)card["forgeId"]!));uint target=card["attachedToForgeId"]!=null?checked((uint)bridge.ResearchInstanceId((int)card["attachedToForgeId"]!)):card["attachedToSeat"]!=null?(uint)card["attachedToSeat"]!:0;
                if(target!=0){if(!attachedWith.TryGetValue(target,out var group))attachedWith[target]=group=new HashSet<uint>();group.Add(source);}
                if(latest.AllCards.TryGetValue(source,out var entity) && entity.AttachedToId!=target)throw new InvalidOperationException("Native attachment target differs from Forge");
            }
            if(state["players"] is JArray roster)
            {
                foreach(var player in roster)
                {
                    var native=latest.GetPlayerById((uint)player["seat"]!);
                    int expected=(int)player["life"]!;
                    if((int)player["seat"]! ==2 && state["horde"] is JObject horde){
                        expected=(int)horde["remainingCards"]!;
                        if(expected!=((JArray)state["hidden"]!).Count(c=>(string?)c["zone"]=="Library" && (int)c["owner"]! ==2))throw new InvalidOperationException("Horde resource differs from actual hidden library identities");
                    }
                    if(native==null || native.LifeTotal!=expected)throw new InvalidOperationException("Native player life or labelled Horde library resource differs from Forge at seat "+player["seat"]);
                    if((bool?)state["pod"]==true && (bool?)player["lost"]==true && native.Status!=PlayerStatus.Removed)throw new InvalidOperationException("Eliminated pod player remains active in the native model");
                }
            }
            else if(latest.GetPlayerById(1).LifeTotal!=(int)state["life"]! || latest.GetPlayerById(2).LifeTotal!=(int)state["opponentLife"]!)throw new InvalidOperationException("Native player life differs from Forge");
            if(latest.GetPlayerById(1).ManaPool.Sum(m=>(long)m.Count)!=(int)state["manaTotal"]!)throw new InvalidOperationException("Native mana pool quantity differs from Forge");
            foreach(var card in new[]{"hand","battlefield","stack","graveyard","command","exile"}.SelectMany(k=>(JArray?)state[k]??new JArray()))
            {
                uint id=checked((uint)bridge.ResearchInstanceId((int)card["forgeId"]!));
                if(!latest.AllCards.TryGetValue(id,out var native))throw new InvalidOperationException("Visible Forge object is absent from the native model");
                if(native.IsPhasedOut!=((bool?)card["phasedOut"]??false))throw new InvalidOperationException("Native phasing state differs from Forge");
                if((string?)card["zone"]=="Battlefield" && native.ProtectorId!=(uint)((int?)card["protectorSeat"]??0))throw new InvalidOperationException("Native battle protector differs from Forge");
                if(card["baseDefense"]!=null){int defense=(int)card["defense"]!;if((string?)card["zone"]!="Battlefield" && int.TryParse((string?)card["baseDefense"],out int printedDefense))defense=printedDefense;if(native.Defense!=(uint)defense)throw new InvalidOperationException("Native battle defense differs from Forge");}
                if(card["classLevel"]!=null && native.ClassLevel!=(int)card["classLevel"]!)throw new InvalidOperationException("Native Class level differs from Forge");
                if(card["namedCardTitleIds"] is JArray namedTitles && !native.ReferencedCardTitleIds.SetEquals(namedTitles.Select(v=>(uint)v)))throw new InvalidOperationException("Native named-card identities differ from Forge");
                if((string?)card["objectKind"]=="emblem" && native.ObjectType!=GameObjectType.Emblem)throw new InvalidOperationException("Source emblem lost its original native object type");
                if((string?)card["objectKind"]!="emblem" && card["currentTypes"] is JArray currentTypes)
                {
                    if(!native.CardTypes.Select(t=>(int)t).ToHashSet().SetEquals(currentTypes.Select(t=>bridge.ResearchTypeId("CardType",(string)t!))) || !native.Subtypes.Select(t=>(int)t).ToHashSet().SetEquals(((JArray)card["currentSubtypes"]!).Select(t=>bridge.ResearchTypeId("SubType",(string)t!))) || !native.Supertypes.Select(t=>(int)t).ToHashSet().SetEquals(((JArray)card["currentSupertypes"]!).Select(t=>bridge.ResearchTypeId("SuperType",(string)t!))))throw new InvalidOperationException("Native current card types or subtypes differ from actual Forge characteristics");
                    int colors=native.Colors.Where(c=>c>=CardColor.White && c<=CardColor.Green).Aggregate(0,(mask,c)=>mask|(1<<((int)c-1)));
                    if(colors!=(int)card["colorMask"]!)throw new InvalidOperationException("Native current colors differ from actual Forge characteristics");
                }
                if(card["keywordGrants"] is JArray keywordGrants)
                {
                    int KeywordSource(JToken grant)
                    {
                        if((string?)grant["sourceKind"]!="horde-format-rule")return bridge.ResearchInstanceId((int)grant["sourceForgeId"]!);
                        if((string?)state["scenario"]!="zombie-horde" || (int?)grant["sourceSeat"]!=2 || (int?)grant["sourceForgeId"]!=(int?)state["horde"]?["rulesEffectForgeId"] || (string?)grant["keyword"]!="Haste")throw new InvalidOperationException("Invalid declared Horde format keyword origin");
                        return 2;
                    }
                    var expectedGrants=keywordGrants.SelectMany(g=>bridge.ResearchKeywordIds((string)g["keyword"]!).Select(a=>(Ability:checked((uint)a),Source:checked((uint)KeywordSource(g)),Layer:(uint)g["layerId"]!))).OrderBy(g=>g.Layer).ThenBy(g=>g.Ability).ToArray();
                    var actualGrants=native.AbilityAdders.Select(g=>(Ability:g.AbilityId,Source:g.AddedById,Layer:g.LayeredEffectId)).OrderBy(g=>g.Layer).ThenBy(g=>g.Ability).ToArray();
                    if(!expectedGrants.SequenceEqual(actualGrants))throw new InvalidOperationException("Native active keyword identities, grant sources or layer lifetimes differ from Forge");
                }
                if(card["keywordRemovals"] is JArray removals)
                {
                    var expectedRemovals=removals.SelectMany(r=>bridge.ResearchRemovedAbilities(card,r).Select(a=>(Ability:checked((uint)a),Source:checked((uint)bridge.ResearchInstanceId((int)r["sourceForgeId"]!)),Layer:(uint)r["layerId"]!))).OrderBy(r=>r.Layer).ThenBy(r=>r.Ability).ToArray();
                    var actualRemovals=native.AbilityRemovers.Select(r=>(Ability:r.AbilityId,Source:r.RemovedById,Layer:r.LayeredEffectId)).OrderBy(r=>r.Layer).ThenBy(r=>r.Ability).ToArray();
                    if(!expectedRemovals.SequenceEqual(actualRemovals))throw new InvalidOperationException("Native ability removals or their source/lifetime differ from Forge");
                }
                if(card["rulesKeywords"] is JArray rulesKeywords)
                {
                    string name=(string?)card["presentationKey"] ?? (string)card["name"]!;
                    uint Canonical(uint ability)=>bridge.ResearchCanonicalKeyword(name,ability);
                    var known=bridge.ResearchKnownKeywords.ToHashSet();var effective=bridge.ResearchPrintedAbilities(name).Select(Canonical).Where(known.Contains).ToHashSet();
                    foreach(var modification in native.AbilityModifications)
                    {
                        if(modification.Type==AbilityModification.ModType.RemoveAll)effective.Clear();
                        else if(modification.Type==AbilityModification.ModType.Removed)effective.Remove(Canonical(modification.AbilityId));
                        else if(modification.Type==AbilityModification.ModType.Added && known.Contains(Canonical(modification.AbilityId)))effective.Add(Canonical(modification.AbilityId));
                    }
                    var expectedKeywords=rulesKeywords.SelectMany(k=>bridge.ResearchKnownKeywordIds((string)k!)).ToHashSet();
                    if(!effective.SetEquals(expectedKeywords))throw new InvalidOperationException("Native keyword modifier order disagrees for "+name+"; actual="+string.Join(",",effective.OrderBy(v=>v))+" expected="+string.Join(",",expectedKeywords.OrderBy(v=>v)));
                }
                if(!native.AttachedWithIds.SetEquals(attachedWith.TryGetValue(id,out var group)?group:new HashSet<uint>()))throw new InvalidOperationException("Native reverse attachments differ from Forge");
                var expected=((JArray?)card["counters"]??new JArray()).ToDictionary(c=>SharedCounterProtocol.Type((string)c["type"]!),c=>(int)c["count"]!);
                if(native.Counters.Count!=expected.Count || expected.Any(p=>!native.Counters.TryGetValue(p.Key,out int count) || count!=p.Value))throw new InvalidOperationException("Native counters differ from Forge");
                if((string?)card["zone"]=="Battlefield")
                {
                    if(native.IsTapped!=(bool)card["tapped"]!)throw new InvalidOperationException("Native tapped state differs from Forge");
                    if(native.CardTypes.Contains(CardType.Creature) && (native.Power.Value!=(int)card["power"]! || native.Toughness.Value!=(int)card["toughness"]! || native.HasSummoningSickness!=(bool)card["sick"]!))throw new InvalidOperationException("Native creature stats differ from Forge");
                }
            }
            foreach(var player in (JArray?)state["playerCounters"]??new JArray())
            {
                var expected=((JArray)player["counters"]!).ToDictionary(c=>SharedCounterProtocol.Type((string)c["type"]!),c=>(int)c["count"]!);var native=latest.GetPlayerById((uint)player["seat"]!).Counters;
                if(native.Count!=expected.Count || expected.Any(p=>!native.TryGetValue(p.Key,out int count) || count!=p.Value))throw new InvalidOperationException("Native player counters differ from Forge");
            }
        }
        var seen=new Dictionary<string,(JObject Body,JObject Reply)>();string? commandId=null,forgeRequest=null;long commandStart=0;DateTime commandDeadline=default;string lastLoop="";
        try
        {
            bridge.Start();Drain();ValidateModel();Write(Path.Combine(work,"ready.json"),Status());Write(Path.Combine(work,"status.json"),Status());dirty=false;
            while(!File.Exists(Path.Combine(work,"stop.request")) && !File.Exists(Path.Combine(ipc,"stop.request")))
            {
                if(timer.Elapsed>TotalLifetime)throw new TimeoutException("Bounded headless worker lifetime expired");
                long measured=Stopwatch.GetTimestamp();bridge.Poll();pollTicks+=Stopwatch.GetTimestamp()-measured;
                measured=Stopwatch.GetTimestamp();Drain();drainTicks+=Stopwatch.GetTimestamp()-measured;
                string loopStamp=bridge.LoopStatus.ToString(Formatting.None);
                if(dirty || loopStamp!=lastLoop){measured=Stopwatch.GetTimestamp();ValidateModel();validationTicks+=Stopwatch.GetTimestamp()-measured;measured=Stopwatch.GetTimestamp();Write(Path.Combine(work,"status.json"),Status());statusTicks+=Stopwatch.GetTimestamp()-measured;dirty=false;lastLoop=loopStamp;}
                if(commandId!=null)
                {
                    bool boundary=bridge.PendingResearchRequestId==null && (updateOrdinal>commandStart || !string.IsNullOrEmpty(bridge.Gap));
                    if(boundary)
                    {
                        var reply=Status();reply["id"]=commandId;reply["forgeRequestId"]=forgeRequest;reply["accepted"]=string.IsNullOrEmpty(bridge.Gap);
                        var old=seen[commandId];seen[commandId]=(old.Body,reply);Write(Path.Combine(work,"responses",commandId+".json"),reply);Record("command-complete",reply);commandId=null;forgeRequest=null;
                    }
                    else if(DateTime.UtcNow>commandDeadline)throw new TimeoutException("Native command did not reach a Forge boundary");
                }
                foreach(string path in Directory.GetFiles(Path.Combine(work,"requests"),"*.json").OrderBy(p=>p,StringComparer.Ordinal))
                {
                    var request=Read(path);string id=(string)request["id"]!;
                    if(id.Length!=32 || id.Any(c=>!Uri.IsHexDigit(c)))throw new InvalidDataException("Invalid native worker request identity");
                    if(seen.TryGetValue(id,out var prior))
                    {
                        if(!JToken.DeepEquals(prior.Body,request))Write(Path.Combine(work,"responses",id+".json"),new JObject{["id"]=id,["accepted"]=false,["reason"]="Request ID reused with different payload"});
                        else if(prior.Reply.Count>0)Write(Path.Combine(work,"responses",id+".json"),prior.Reply);
                        File.Delete(path);continue;
                    }
                    if(commandId!=null)continue;
                    if(seen.Count>=4096)throw new InvalidOperationException("Headless worker request bound exceeded");
                    seen.Add(id,((JObject)request.DeepClone(),new JObject()));File.Delete(path);
                    try
                    {
                        string op=(string)request["op"]!;bool loopControl=op is "loop_stop" or "loop_status" or "fast_stack_cancel" or "fast_stack_status";
                        Integer(request["nativeStateId"],"nativeStateId");Integer(request["forgeId"],"forgeId");
                        if(!loopControl)Integer(request["nativeMessageId"],"nativeMessageId");
                        if((string?)request["worker"]!=worker || (string?)request["session"]!=bridge.Session || !loopControl && ((uint?)request["nativeStateId"]!=presented || (uint?)request["nativeMessageId"]!=interaction?.OriginalMessage.MsgId))throw new InvalidOperationException("Stale or foreign native worker request");
                        if(op=="loop_stop" && (string?)request["loopRunId"]!=(string?)bridge.LoopStatus["runId"])throw new InvalidOperationException("Repeat batch changed; inspect before cancelling.");
                        if(request["seat"]!=null && (request["seat"]!.Type!=JTokenType.Integer || (int)request["seat"]! != 1))throw new InvalidOperationException("Native worker controls only local seat one");
                        var state=bridge.ResearchState;var decision=state["decision"] as JObject;
                        if(op is "fast_stack_start" or "fast_stack_cancel" or "fast_stack_status")
                        {
                            if(op=="fast_stack_start")
                            {
                                if(decision!=null || (bool?)state["canPass"]!=true || state["stackOrder"] is not JArray stack || stack.Count==0)throw new InvalidOperationException("Fast resolve requires real stack priority");
                                string policy=(string?)request["policy"]??"all";if(policy!="all" && policy!="own")throw new InvalidDataException("Unknown stack-yield policy");
                                automaticStack=true;var settings=new SettingsMessage{StackAutoPassOption=policy=="all"?AutoPassOption.ResolveAll:AutoPassOption.ResolveMyStackEffects};if(policy=="own")settings.AutoPassOption=AutoPassOption.ResolveMyStackEffects;
                                local.SendMessage(new ClientToGREMessage{Type=ClientMessageType.SetSettingsReq,SetSettingsReq=new SetSettingsReq{Settings=settings}});
                            }
                            else if(op=="fast_stack_cancel")
                            {
                                if((bool?)bridge.LoopStatus["fastResolving"]!=true || (string?)request["fastRunId"]!=(string?)bridge.LoopStatus["fastRunId"])throw new InvalidOperationException("Fast resolve batch changed; inspect before cancelling");
                                automaticStack=false;bridge.StopLoop();
                            }
                            var reply=Status();reply["id"]=id;reply["accepted"]=true;seen[id]=(request,reply);Write(Path.Combine(work,"responses",id+".json"),reply);continue;
                        }
                        if(op is "loop_start" or "loop_stop" or "loop_status")
                        {
                            if(op=="loop_start")bridge.StartLoop(Integer(request["count"],"count"));else if(op=="loop_stop")bridge.StopLoop();
                            var reply=Status();reply["id"]=id;reply["accepted"]=true;seen[id]=(request,reply);Write(Path.Combine(work,"responses",id+".json"),reply);continue;
                        }
                        if(decision!=null && (op.StartsWith("submit_",StringComparison.Ordinal) || op.StartsWith("select_",StringComparison.Ordinal) || op=="cancel_targets") && (string?)request["decisionToken"]!=(string?)decision["token"])throw new InvalidOperationException("Native decision token does not match Forge");
                        if(op is "select_targets" or "submit_targets" or "cancel_targets")
                            if(decision==null || (string?)request["decisionToken"]!=(string?)decision["token"])throw new InvalidOperationException("Native target token does not match Forge");
                        if(op=="concede")gre.ConcedeGame();
                        else if(op is "submit_choice" or "submit_order_cards" or "submit_mulligan" or "submit_mulligan_bottom" or "submit_starting_player" or "submit_discard" or "submit_legend_rule" or "submit_commander_return" or "submit_assign_damage")
                        {
                            if(decision==null || (string?)request["decisionToken"]!=(string?)decision["token"] || interaction==null)throw new InvalidOperationException("Native choice token does not match Forge");
                            NativeChoiceDriver.SubmitDecision(interaction,decision,(JArray)request["assignments"]!,bridge.ResearchInstanceId);
                        }
                        else if(op=="select_attackers" && interaction is DeclareAttackerRequest attackers)
                        {
                            var seenAttackers=new HashSet<int>();
                            var selected=((JArray)request["assignments"]!).Select(value=>
                            {
                                if(value["targetForgeId"]==null)Fields(value,"forgeId","targetSeat");else Fields(value,"forgeId","targetSeat","targetForgeId");int forge=Integer(value["forgeId"],"attacker");if(!seenAttackers.Add(forge))throw new ArgumentException("Repeated attacker assignment");
                                uint id=checked((uint)bridge.ResearchInstanceId(forge));var attacker=attackers.Attackers.Single(a=>a.AttackerInstanceId==id).Clone();int seat=Integer(value["targetSeat"],"targetSeat");
                                int pw=value["targetForgeId"]==null?0:Integer(value["targetForgeId"],"targetForgeId");
                                attacker.SelectedDamageRecipient=seat==0?null:attacker.LegalDamageRecipients.Single(r=>pw==0?r.Type==DamageRecType.Player && r.PlayerSystemSeatId==seat:r.Type==DamageRecType.PlanesWalker && r.PlaneswalkerInstanceId==checked((uint)bridge.ResearchInstanceId(pw))).Clone();return attacker;
                            }).ToArray();attackers.UpdateAttacker(selected);
                        }
                        else if(op=="submit_attackers" && interaction is DeclareAttackerRequest declareAttackers)declareAttackers.SubmitAttackers();
                        else if(op=="select_blockers" && interaction is DeclareBlockersRequest blockers)
                        {
                            var seenBlockers=new HashSet<int>();
                            var selected=((JArray)request["assignments"]!).Select(value=>
                            {
                                Fields(value,"forgeId","attackerIds");int forge=Integer(value["forgeId"],"blocker");if(!seenBlockers.Add(forge))throw new ArgumentException("Repeated blocker assignment");
                                uint id=checked((uint)bridge.ResearchInstanceId(forge));var blocker=blockers.AllBlockers.Single(b=>b.BlockerInstanceId==id).Clone();var targets=((JArray)value["attackerIds"]!).Select(v=>checked((uint)bridge.ResearchInstanceId(Integer(v,"blocked attacker")))).ToArray();
                                if(targets.Length>blocker.MaxAttackers || targets.Distinct().Count()!=targets.Length || targets.Any(t=>!blocker.AttackerInstanceIds.Contains(t)))throw new ArgumentException("Invalid native blocking assignment");blocker.SelectedAttackerInstanceIds.Clear();blocker.SelectedAttackerInstanceIds.AddRange(targets);return blocker;
                            }).ToArray();blockers.UpdateBlockers(selected);
                        }
                        else if(op=="submit_blockers" && interaction is DeclareBlockersRequest declareBlockers)declareBlockers.SubmitBlockers();
                        else if(op=="select_targets" && interaction is SelectTargetsRequest targets)
                        {
                            if(decision==null || (string?)request["decisionToken"]!=(string?)decision["token"])throw new InvalidOperationException("Native target token does not match Forge");
                            var values=(JArray)request["assignments"]!;if(values.Count!=1)throw new NotSupportedException("One native target update per request");
                            Fields(values[0],values[0]!["selected"]==null?new[]{"forgeId"}:new[]{"forgeId","selected"});if(values[0]!["selected"]!=null && values[0]!["selected"]!.Type!=JTokenType.Boolean)throw new ArgumentException("Target selection flag must be boolean");int forge=Integer(values[0]!["forgeId"],"target");
                            var offered=((JArray)decision["options"]!).Single(o=>(int)o["forgeId"]! == forge);uint native=checked((uint)((string?)offered["targetKind"]=="player"?(int)offered["targetSeat"]!:bridge.ResearchInstanceId(forge)));
                            var selection=targets.TargetSelections.Single();var target=selection.Targets.Single(t=>t.TargetInstanceId==native).Clone();
                            target.LegalAction=(bool?)values[0]!["selected"]==false?SelectAction.Unselect:SelectAction.Select;targets.UpdateTarget(target,selection.TargetIdx);
                        }
                        else if(op=="submit_targets" && interaction is SelectTargetsRequest submit)
                        {
                            int count=((JArray)decision!["assignments"]!).Count;
                            if(count<(int)decision["minTargets"]! || count>(int)decision["maxTargets"]!)throw new InvalidOperationException("Native target submit is disabled outside the required bounds");submit.SubmitTargets();
                        }
                        else if(op=="cancel_targets" && interaction is SelectTargetsRequest cancel)cancel.Cancel();
                        else if(op=="cancel_assign_damage" && interaction is DistributionRequest distribution)distribution.Cancel();
                        else if(interaction is ActionsAvailableRequest actions)
                        {
                            if(op=="pass_priority")actions.SubmitPass();
                            else
                            {
                                var type=op switch{"cast_spell"=>ActionType.Cast,"play_land"=>ActionType.Play,"activate_mana"=>ActionType.ActivateMana,"activate_ability"=>ActionType.Activate,_=>throw new NotSupportedException("Unmapped native worker operation "+op)};
                                uint source=checked((uint)bridge.ResearchInstanceId(Integer(request["forgeId"],"source")));int ability=op=="activate_ability" || op=="activate_mana" && request["abilityId"]!=null?Integer(request["abilityId"],"abilityId"):0;
                                if(op=="activate_ability" && ability<=0)throw new ArgumentException("Activation identity must be positive");
                                var action=actions.Actions.Single(a=>a.ActionType==type && a.InstanceId==source && (!(op=="activate_ability" || op=="activate_mana" && request["abilityId"]!=null) || a.AbilityGrpId==ability));actions.SubmitAction(action);
                            }
                        }
                        else throw new NotSupportedException("Operation does not match native interaction "+interaction?.GetType().Name);
                        var outgoing=gre.DequeueOutgoingMessage()??throw new InvalidOperationException("Native handler emitted no message");
                        commandStart=updateOrdinal;local.SendMessage(outgoing);forgeRequest=bridge.PendingResearchRequestId??throw new InvalidOperationException("Native adapter emitted no Forge request");commandId=id;commandDeadline=DateTime.UtcNow.AddSeconds(20);Record("command-submitted",new JObject{["id"]=id,["request"]=request,["nativeMessage"]=JObject.Parse(outgoing.ToString()),["forgeRequestId"]=forgeRequest});
                    }
                    catch(Exception error)
                    {
                        Console.Error.WriteLine(error);
                        var reply=Status();reply["id"]=id;reply["accepted"]=false;reply["reason"]=error.Message;seen[id]=(request,reply);Write(Path.Combine(work,"responses",id+".json"),reply);Record("command-rejected",reply);
                    }
                }
                Thread.Sleep(10);
            }
            Write(Path.Combine(work,"completed.json"),new JObject{["worker"]=worker,["updates"]=updateOrdinal,["requests"]=seen.Count,["seconds"]=timer.Elapsed.TotalSeconds,["scope"]="Persistent native parser/adapter only; no Unity, rendering, network or art database."});return 0;
        }
        finally{bridge.Detach();local.Close(Wizards.Arena.TcpConnection.TcpConnectionCloseType.NormalClosure,"Headless worker complete");}
    }
    private static readonly TimeSpan TotalLifetime=TimeSpan.FromMinutes(10);
}
