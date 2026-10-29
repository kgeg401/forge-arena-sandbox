import java.io.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
import forge.*;
import forge.ai.*;
import forge.deck.Deck;
import forge.deck.DeckSection;
import forge.game.*;
import forge.game.card.*;
import forge.game.player.*;
import forge.game.phase.PhaseType;
import forge.game.spellability.LandAbility;
import forge.game.spellability.SpellAbility;
import forge.game.mana.Mana;
import forge.game.combat.*;
import java.util.function.Consumer;
import java.util.function.Supplier;
import com.google.common.eventbus.Subscribe;
import forge.game.event.*;
import forge.game.zone.ZoneType;
import forge.gui.GuiBase;
import forge.item.PaperCard;
import forge.model.FModel;

/** Local practice-match adapter; the installed Forge engine owns game rules. */
public final class ForgeLandEngine {
    static final Gson JSON = new GsonBuilder().setPrettyPrinting().create();
    static Path ipc;
    static Game game;
    static Player local;
    static Player opponent; // Legacy duel alias; pod identities use the stable roster.
    static final List<Player> seatPlayers=new ArrayList<>();
    static final Map<Integer,Integer> seatMulligans=new HashMap<>();
    static final Map<Integer,Boolean> seatKept=new HashMap<>();
    static boolean commanderPod;
    static JsonArray podOpponentDecks;
    static int seatId(int forgePlayerId){for(int i=0;i<seatPlayers.size();i++)if(seatPlayers.get(i).getId()==forgePlayerId)return i+1;throw new IllegalArgumentException("Unknown Forge player id: "+forgePlayerId);}
    static int seat(Player p){return p==null?0:seatId(p.getId());}
    static Player playerAtSeat(int seat){if(seat<1 || seat>seatPlayers.size())throw new IllegalArgumentException("Player seat outside the stable roster");return seatPlayers.get(seat-1);}
    static List<Map<String,Object>> playerSnapshots(){
        List<Map<String,Object>> result=new ArrayList<>();
        for(Player p:seatPlayers){int id=seat(p);Map<String,Object> item=new LinkedHashMap<>();item.put("seat",id);item.put("name",p.getName());item.put("life",p.getLife());item.put("startingLifeTotal",p.getStartingLife());item.put("lost",p.hasLost());item.put("won",p.hasWon());item.put("lossReason",p.hasLost()?p.getOutcome().lossState.name():"");item.put("counters",counters(p));item.put("mulligans",p==local?mulligans:seatMulligans.getOrDefault(id,0));item.put("kept",seatKept.getOrDefault(id,false));item.put("commanders",p.getCommanders().stream().map(c->Map.of("forgeId",c.getId(),"name",c.getName())).toList());result.add(item);}return result;
    }
    static JsonObject currentRequest;
    static JsonObject decision;
    // Headless-only shared decision schema. The installed/native path is kept
    // separate until its original controls have rendered acceptance evidence.
    static JsonObject sharedChoice;
    static int discardCount;
    static final List<JsonObject> deferredSubmissions = new ArrayList<>();
    static PrintWriter journal;
    static String scenario="starter";
    static final Set<String> ADMITTED_CARDS=new LinkedHashSet<>();
    static final Set<String> MAPPED_OBJECTS=new LinkedHashSet<>();
    static final Set<String> BRAWL_COMMANDERS=new LinkedHashSet<>();
    static final Map<String,String> CARD_COLORS=new LinkedHashMap<>();
    static final Map<String,String> MANA_COLORS=new LinkedHashMap<>();
    static final Map<String,Set<String>> COLOR_IDENTITIES=new LinkedHashMap<>();
    static final Map<String,JsonObject> ABILITY_BINDINGS=new LinkedHashMap<>();
    static final Map<String,JsonObject> MODAL_BINDINGS=new LinkedHashMap<>();
    static final Map<String,JsonObject> GENERIC_CHOICE_BINDINGS=new LinkedHashMap<>();
    static final Map<String,Integer> CARD_NAME_IDS=new LinkedHashMap<>();
    static final Map<String,forge.card.ICardFace> CARD_NAME_FACES=new LinkedHashMap<>();
    static JsonObject TYPE_ENUM_IDS=new JsonObject();
    static boolean arenaBrawl,commanderMode;
    static boolean commanderGame(){return arenaBrawl || commanderMode;}
    static String unsupportedDecision="";
    static void loadAdmission(JsonObject manifest){
        CARD_NAME_IDS.clear();CARD_NAME_FACES.clear();
        TYPE_ENUM_IDS=manifest.has("typeEnumIds")?manifest.getAsJsonObject("typeEnumIds").deepCopy():new JsonObject();
        if(manifest.has("cardNameIds"))for(var entry:manifest.getAsJsonObject("cardNameIds").entrySet())CARD_NAME_IDS.put(entry.getKey(),entry.getValue().getAsInt());
        if(!manifest.has("admissionSchema") || manifest.get("admissionSchema").getAsInt()!=1)throw new IllegalArgumentException("Regenerate runtime card admission metadata for this engine");
        var next=new LinkedHashSet<String>();var mapped=new LinkedHashSet<String>();var commanders=new LinkedHashSet<String>();var colors=new LinkedHashMap<String,String>();var identities=new LinkedHashMap<String,Set<String>>();var bindings=new LinkedHashMap<String,JsonObject>();
        for(var entry:manifest.getAsJsonObject("cards").entrySet()){
            var card=entry.getValue().getAsJsonObject();
            if(!card.has("admitted") || !card.get("admitted").isJsonPrimitive() || !card.getAsJsonPrimitive("admitted").isBoolean())throw new IllegalArgumentException("Card admission must be explicit boolean: "+entry.getKey());
            if(!card.has("token") || !card.get("token").isJsonPrimitive() || !card.getAsJsonPrimitive("token").isBoolean())throw new IllegalArgumentException("Token identity must be an explicit boolean: "+entry.getKey());
            if(card.get("admitted").getAsBoolean() && !card.get("token").getAsBoolean())next.add(entry.getKey());
            if(card.get("admitted").getAsBoolean() || card.get("token").getAsBoolean() || card.has("facePresentation") && card.get("facePresentation").getAsBoolean() || card.has("emblemPresentation") && card.get("emblemPresentation").getAsBoolean())mapped.add(entry.getKey());
            if(card.has("commanderAdmitted")){
                if(!card.get("commanderAdmitted").isJsonPrimitive() || !card.getAsJsonPrimitive("commanderAdmitted").isBoolean())throw new IllegalArgumentException("Commander admission must be boolean");
                if(card.get("commanderAdmitted").getAsBoolean()){
                    if(card.get("token").getAsBoolean() || !card.getAsJsonArray("supertypes").contains(new JsonPrimitive("Legendary")))throw new IllegalArgumentException("Commander requires a legendary primary mapping");
                    commanders.add(entry.getKey());
                    mapped.add(entry.getKey());
                }
            }
            if(card.has("color"))colors.put(entry.getKey(),card.get("color").getAsString());
            Set<String> identity=new LinkedHashSet<>();if(card.has("colorIdentity"))for(var c:card.getAsJsonArray("colorIdentity")){String value=c.getAsString();if(!Set.of("W","U","B","R","G").contains(value))throw new IllegalArgumentException("Unknown color identity symbol");identity.add(value);}identities.put(entry.getKey(),identity);
            if(card.has("abilityBindings"))bindings.put(entry.getKey(),card.getAsJsonObject("abilityBindings").deepCopy());
        }
        MODAL_BINDINGS.clear();
        GENERIC_CHOICE_BINDINGS.clear();for(var entry:manifest.getAsJsonObject("cards").entrySet())if(entry.getValue().getAsJsonObject().has("genericChoiceBinding"))GENERIC_CHOICE_BINDINGS.put(entry.getKey(),entry.getValue().getAsJsonObject().getAsJsonObject("genericChoiceBinding").deepCopy());
        for(var entry:manifest.getAsJsonObject("cards").entrySet())if(entry.getValue().getAsJsonObject().has("modalBinding"))MODAL_BINDINGS.put(entry.getKey(),entry.getValue().getAsJsonObject().getAsJsonObject("modalBinding").deepCopy());
        MANA_COLORS.clear();
        for(var entry:manifest.getAsJsonObject("cards").entrySet())if(entry.getValue().getAsJsonObject().has("manaColor"))MANA_COLORS.put(entry.getKey(),entry.getValue().getAsJsonObject().get("manaColor").getAsString());
        ADMITTED_CARDS.clear();ADMITTED_CARDS.addAll(next);
        MAPPED_OBJECTS.clear();MAPPED_OBJECTS.addAll(mapped);
        BRAWL_COMMANDERS.clear();BRAWL_COMMANDERS.addAll(commanders);CARD_COLORS.clear();CARD_COLORS.putAll(colors);
        COLOR_IDENTITIES.clear();COLOR_IDENTITIES.putAll(identities);ABILITY_BINDINGS.clear();ABILITY_BINDINGS.putAll(bindings);
    }
    static JsonObject localDeck,opponentDeck;
    static JsonObject fixtureConfig;
    static boolean warmResearch;
    static boolean researchAdmission;
    static boolean fullHumanChoices;
    static boolean researchOpponentAttackAll;
    static boolean researchOpponentBlockAll;
    static final Deque<String> researchOpponentSpellPlan=new ArrayDeque<>();
    static final List<String> researchCallbackAudit=new ArrayList<>();
    static boolean normalGame(){return scenario.equals("opening-duel") || scenario.equals("spell-duel") || scenario.equals("trigger-duel") || scenario.equals("blue-duel") || scenario.equals("custom-duel") || scenario.equals("brawl-duel") || scenario.equals("commander-duel") || scenario.equals("commander-pod");}
    static void validateDeck(JsonObject deck){
        if(deck==null || !deck.has("cards") || !deck.get("cards").isJsonArray())throw new IllegalArgumentException("Imported deck requires a cards array");
        boolean brawl=deck.has("format") && Set.of("arena-brawl","commander-40").contains(deck.get("format").getAsString());
        if(deck.has("format") && !brawl)throw new IllegalArgumentException("Unknown imported deck format");
        String commander="";
        if(brawl){
            if(!deck.has("commander") || !deck.get("commander").isJsonObject())throw new IllegalArgumentException("Brawl requires one commander object");
            var c=deck.getAsJsonObject("commander");commander=c.get("name").getAsString();
            if(!BRAWL_COMMANDERS.contains(commander) || !c.get("count").isJsonPrimitive() || !c.getAsJsonPrimitive("count").isNumber() || !c.get("count").getAsString().equals("1"))throw new IllegalArgumentException("Unverified or invalid Brawl commander");
        }else if(deck.has("commander"))throw new IllegalArgumentException("Commander requires a commander deck format");
        int total=0;Set<String> names=new HashSet<>();
        for(JsonElement item:deck.getAsJsonArray("cards")){
            JsonObject entry=item.getAsJsonObject();String name=entry.get("name").getAsString();
            if(!ADMITTED_CARDS.contains(name) || !names.add(name))throw new IllegalArgumentException("Unmapped or duplicate imported card: "+name);
            if(!entry.get("count").isJsonPrimitive() || !entry.getAsJsonPrimitive("count").isNumber())throw new IllegalArgumentException("Imported card count must be a number");
            String count=entry.get("count").getAsString();if(!count.matches("[1-9][0-9]{0,2}"))throw new IllegalArgumentException("Invalid imported card count");
            total+=Integer.parseInt(count);
            if(brawl){
                if(name.equals(commander))throw new IllegalArgumentException("Commander duplicated in main deck");
                if(Integer.parseInt(count)!=1 && !Set.of("Plains","Island","Swamp","Mountain","Forest").contains(name))throw new IllegalArgumentException("Brawl nonbasic cards must be singleton");
                if(!COLOR_IDENTITIES.get(commander).containsAll(COLOR_IDENTITIES.get(name)))throw new IllegalArgumentException("Outside admitted commander color identity: "+name);
            }
        }
        if(total<40 || total>250)throw new IllegalArgumentException("Imported practice deck must contain 40 to 250 cards");
        if(brawl && total!=99)throw new IllegalArgumentException("Arena Brawl requires exactly 99 main cards plus one commander");
    }
    static boolean aiDuel(){return scenario.equals("duel") || scenario.equals("mixed-duel") || scenario.startsWith("counter-ready") || normalGame();}
    static int mulligans;
    static Long randomSeed;
    static String startingPlayerPolicy="coin-toss";
    static int startingSeat;
    static boolean opponentKept;
    static int opponentMulligans;
    static boolean targetCancelled;
    static int targetSourceId,targetSourceAbilityId,targetMinimum,targetMaximum;
    static JsonObject targetSourceContext;
    static boolean mandatoryTriggerTarget;
    static int actionProbeDepth;
    static final Map<String,Map<String,Object>> unavailableActions=new LinkedHashMap<>();
    static <T> T probeAction(Card card,String action,Supplier<T> query){
        if(!researchAdmission)return query.get();
        String previous=unsupportedDecision;actionProbeDepth++;
        try{return query.get();}
        catch(UnsupportedOperationException error){
            unavailableActions.put(action+":"+card.getId(),Map.of("forgeId",card.getId(),"name",card.getName(),"action",action,"reason",error.getMessage()==null?error.toString():error.getMessage()));
            return null;
        }finally{actionProbeDepth--;unsupportedDecision=previous;}
    }
    static int damageSourceId,damageTotal;
    static int commanderDecisionId;
    static String commanderDecisionZone;
    static String orderDecisionZone;
    static final Map<Integer,List<Integer>> spellTargets=new HashMap<>();
    static final Map<String,String> failedPlays=new HashMap<>();
    static class StopRequested extends RuntimeException {}
    static String phaseName(){return game.getPhaseHandler().getPhase()==null?"PREGAME":game.getPhaseHandler().getPhase().name();}
    static final List<Map<String,Object>> events=new ArrayList<>();static long eventId;
    static final List<Map<String,Object>> researchTrace=new ArrayList<>();static long researchTraceId;
    static void researchEvent(Map<String,Object> values){
        if(!researchAdmission)return;
        if(researchTrace.size()>=16384){unsupportedDecision="Research trace capacity exceeded; evidence would be incomplete";return;}
        Map<String,Object> row=new LinkedHashMap<>(values);row.put("ordinal",++researchTraceId);row.put("phase",phaseName());row.put("turn",game.getPhaseHandler().getTurn());
        var top=game.getStack().peek();row.put("sourceStackForgeId",game.getStack().isResolving() && top!=null?(top.isSpell()?top.getSourceCard().getId():-1-top.getId()):0);
        researchTrace.add(row);
    }
    static void event(Map<String,Object> values){Map<String,Object> e=new LinkedHashMap<>(values);e.put("id",++eventId);e.put("phase",phaseName());events.add(e);if(events.size()>2048)events.remove(0);}
    static String counterKey(CounterType type){return type instanceof CounterEnumType known?known.name():fullHumanChoices?type.getName():"unmapped:"+type.getName();}
    static List<Map<String,Object>> counters(GameEntity entity){
        List<Map<String,Object>> values=new ArrayList<>();
        for(var entry:entity.getCounters().entrySet())values.add(Map.of("type",counterKey(entry.getElement()),"label",entry.getElement().getName(),"count",entry.getCount()));
        values.sort(Comparator.comparing(v->v.get("type").toString()));return values;
    }
    static int resolvingSource(){var top=game.getStack().peek();return game.getStack().isResolving() && top!=null?(top.isSpell()?top.getSourceCard().getId():-1-top.getId()):0;}
    static final Map<String,Integer> keywordLayerIds=new LinkedHashMap<>(),keywordLayerSources=new LinkedHashMap<>();
    static String keywordLayerKey(Card card,long timestamp,long staticId,int ordinal){return card.getId()+":"+timestamp+":"+staticId+":"+ordinal;}
    static void rememberKeywordLayer(String key,int source){
        keywordLayerSources.compute(key,(k,prior)->prior==null || prior==0?source:prior);
        if(!keywordLayerIds.containsKey(key)){if(keywordLayerIds.size()>=100000)throw new UnsupportedOperationException("Keyword layer evidence bound exceeded");keywordLayerIds.put(key,keywordLayerIds.size()+1);}
    }
    static int keywordPresentationSource(Card source){
        Set<Integer> seen=new HashSet<>();int original=source.getId();
        while(fullHumanChoices && source.isImmutable() && !source.isEmblem()){
            if(!seen.add(source.getId()) || seen.size()>16)return 0;
            Card parent=source.getEffectSource();if(parent==null && source.getEffectSourceAbility()!=null)parent=source.getEffectSourceAbility().getHostCard();
            if(parent==null)return 0;source=parent;
        }
        if(source.getId()!=original && researchAdmission)researchEffectOrigins.putIfAbsent(original,source.getId());
        return source.getId();
    }
    static final Map<Integer,Integer> researchEffectOrigins=new LinkedHashMap<>();
    static int keywordLayerSource(long staticId,forge.game.spellability.SpellAbilityStackInstance resolving){
        if(staticId!=0)for(Card source:game.getCardsInGame())for(var ability:source.getStaticAbilities())if(ability.getId()==staticId)return keywordPresentationSource(source);
        return resolving!=null?keywordPresentationSource(resolving.getSourceCard()):0;
    }
    static void rememberKeywordSources(Card card){
        if(!researchAdmission)return;
        var resolving=game.getStack().isResolving()?game.getStack().peek():null;
        for(var cell:card.getChangedCardKeywords().cellSet()){
            var change=cell.getValue();int defaultSource=keywordLayerSource(cell.getColumnKey(),resolving);
            if(change.isRemoveAllKeywords() || !change.getRemoveKeywords().isEmpty() || !change.getRemovedKeywordInstances().isEmpty())rememberKeywordLayer(keywordLayerKey(card,cell.getRowKey(),cell.getColumnKey(),-1),defaultSource);
            int ordinal=0;for(var keyword:change.getKeywords()){
                String key=keywordLayerKey(card,cell.getRowKey(),cell.getColumnKey(),ordinal++);
                int source=keyword.getStatic()!=null?keywordPresentationSource(keyword.getStatic().getHostCard()):defaultSource;
                rememberKeywordLayer(key,source);
            }
        }
    }
    static void keywordPresentation(Card card,Map<String,Object> result){
        if(!researchAdmission)return;rememberKeywordSources(card);
        List<Map<String,Object>> grants=new ArrayList<>(),removals=new ArrayList<>();List<String> gaps=new ArrayList<>();var active=card.getKeywords();
        if(!card.getChangedCardKeywordsByText().isEmpty())gaps.add("Text-modified keyword layers need explicit native reconstruction");
        for(var cell:card.getChangedCardKeywords().cellSet()){
            var change=cell.getValue();
            if(change.isRemoveAllKeywords() || !change.getRemoveKeywords().isEmpty() || !change.getRemovedKeywordInstances().isEmpty()){
                String key=keywordLayerKey(card,cell.getRowKey(),cell.getColumnKey(),-1);int source=keywordLayerSources.get(key);Set<String> removed=new LinkedHashSet<>(change.getRemoveKeywords());for(var keyword:change.getRemovedKeywordInstances())removed.add(keyword.getOriginal());
                if(source==0)gaps.add("Keyword removal lacks an observed source");
                else removals.add(Map.of("layerId",keywordLayerIds.get(key),"sourceForgeId",source,"all",change.isRemoveAllKeywords(),"keywords",new ArrayList<>(removed),"timestamp",cell.getRowKey()));
            }
            int ordinal=0;for(var keyword:change.getKeywords()){
                String key=keywordLayerKey(card,cell.getRowKey(),cell.getColumnKey(),ordinal++);if(!active.contains(keyword))continue;
                int source=keywordLayerSources.get(key);if(source==0){gaps.add("Keyword grant lacks an observed resolving source: "+keyword.getOriginal());continue;}
                grants.add(Map.of("layerId",keywordLayerIds.get(key),"sourceForgeId",source,"keyword",keyword.getOriginal(),"timestamp",cell.getRowKey()));
            }
        }
        grants.sort(Comparator.comparingLong(v->((Number)v.get("timestamp")).longValue()));removals.sort(Comparator.comparingLong(v->((Number)v.get("timestamp")).longValue()));result.put("keywordGrants",grants);result.put("keywordRemovals",removals);result.put("keywordPresentationGaps",gaps);
    }
    public static class EventRecorder {
        @Subscribe public void characteristics(GameEventCardStatsChanged e){if(researchAdmission)for(CardView view:e.cards())for(Card card:game.getCardsInGame())if(card.getId()==view.getId()){rememberKeywordSources(card);break;}}
        @Subscribe public void attachment(GameEventCardAttachment e){
            Map<String,Object> value=new LinkedHashMap<>();value.put("kind","attachment-change");value.put("sourceForgeId",e.equipment().getId());
            attachmentEndpoint(value,"from",e.oldEntity());attachmentEndpoint(value,"to",e.newTarget());event(value);
        }
        @Subscribe public void cardCounters(GameEventCardCounters e){
            if(e.type()==null){if(currentRequest!=null)unsupportedDecision="Aggregate card counter reset needs explicit event reconstruction";return;}
            event(Map.of("kind","counter-change","targetForgeId",e.card().getId(),"counterType",counterKey(e.type()),"before",e.oldValue(),"after",e.newValue(),"sourceStackForgeId",resolvingSource()));
        }
        @Subscribe public void playerCounters(GameEventPlayerCounters e){
            if(e.type()==null){if(currentRequest!=null)unsupportedDecision="Aggregate player counter reset needs explicit event reconstruction";return;}
            // The pinned Player.setCounters constructor passes old total and
            // new total; the event's field named amount is not a delta.
            event(Map.of("kind","counter-change","targetSeat",seatId(e.receiver().getId()),"counterType",counterKey(e.type()),"before",e.oldValue(),"after",e.amount(),"sourceStackForgeId",resolvingSource()));
        }
        @Subscribe public void resolved(GameEventSpellResolved e){researchEvent(Map.of("kind","spell-resolved","sourceForgeId",e.spell().getHostCard().getId(),"hasFizzled",e.hasFizzled()));}
        @Subscribe public void sacrificed(GameEventCardSacrificed e){event(Map.of("kind","sacrificed","sourceForgeId",e.card().getId()));}
        @Subscribe public void zoneChanged(GameEventCardChangeZone e){
            if(e.from()!=null && e.to()!=null)researchEvent(Map.of("kind","zone-change","forgeId",e.card().getId(),"ownerSeat",seatId(e.card().getOwner().getId()),"from",e.from().zoneType().name(),"to",e.to().zoneType().name()));
            var top=game.getStack().peek();
            if(e.from()==null || e.to()==null || e.from().zoneType()!=ZoneType.Stack || !game.getStack().isResolving() || top==null || top.getSpellAbility().getApi()!=forge.game.ability.ApiType.Counter)return;
            for(SpellAbility target:top.getTargetChoices().getTargetSpells())if(target.getHostCard().getId()==e.card().getId())event(Map.of("kind","countered","sourceForgeId",top.getSourceCard().getId(),"targetForgeId",e.card().getId()));
        }
        @Subscribe public void lifeChanged(GameEventPlayerLivesChanged e){
            researchEvent(Map.of("kind","life-change","targetSeat",seatId(e.player().getId()),"before",e.oldLives(),"after",e.newLives()));
            if(e.newLives()<=e.oldLives())return;
            var top=game.getStack().peek();
            int source=game.getStack().isResolving() && top!=null?(top.isSpell()?top.getSourceCard().getId():-1-top.getId()):0;
            event(Map.of("kind","life-gain","targetSeat",seatId(e.player().getId()),"amount",e.newLives()-e.oldLives(),"sourceStackForgeId",source));
        }
        @Subscribe public void spellCast(GameEventSpellAbilityCast e){
            List<Integer> targets=new ArrayList<>();if(e.si()!=null && e.si().getTargetCards()!=null)for(CardView c:e.si().getTargetCards())targets.add(c.getId());
            spellTargets.put(e.sa().getHostCard().getId(),List.copyOf(targets));
        }
        @Subscribe public void playerDamage(GameEventPlayerDamaged e){event(Map.of("kind","damage","sourceForgeId",e.source().getId(),"targetSeat",seatId(e.target().getId()),"amount",e.amount(),"combat",e.combat()));}
        @Subscribe public void cardDamage(GameEventCardDamaged e){
            // This Forge event omits the combat flag. Ordinary spell/ability
            // damage occurs synchronously while the stack is resolving;
            // supported creature combat occurs outside resolution in a damage
            // step. Never infer damage kind from one hardcoded card name.
            boolean combat;
            if(game.getStack().isResolving())combat=false;
            else if(Set.of("COMBAT_FIRST_STRIKE_DAMAGE","COMBAT_DAMAGE").contains(phaseName()))combat=true;
            else {unsupportedDecision="Unmapped card damage outside resolving stack or combat damage step";throw new UnsupportedOperationException(unsupportedDecision);}
            event(Map.of("kind","damage","sourceForgeId",e.source().getId(),"targetForgeId",e.card().getId(),"amount",e.amount(),"combat",combat));
        }
    }
    static void attachmentEndpoint(Map<String,Object> values,String prefix,GameEntityView entity){
        if(entity instanceof CardView card)values.put(prefix+"ForgeId",card.getId());
        else if(entity instanceof PlayerView player)values.put(prefix+"Seat",seatId(player.getId()));
        else if(entity!=null)throw new UnsupportedOperationException("Unknown attachment event endpoint");
    }
    static final String SESSION = UUID.randomUUID().toString();
    static final IdentityHashMap<Mana,Integer> manaIds = new IdentityHashMap<>();
    static int nextManaId=1;
    static java.lang.reflect.Method priorityChecks;
    static final Map<String,JsonObject> requestBodies = new HashMap<>();
    static final Map<String,JsonObject> acceptedRequests = new HashMap<>();

    static void write(Path path, Object value) throws Exception {
        Path temp = path.resolveSibling(path.getFileName()+".tmp");
        Files.writeString(temp,JSON.toJson(value));
        for(int attempt=0;;attempt++){
            try{Files.move(temp,path,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);break;}
            catch(java.nio.file.FileSystemException ex){if(attempt>=99)throw ex;Thread.sleep(10);}
        }
    }
    static void retireFile(Path path) throws Exception {
        for(int attempt=0;;attempt++){
            try{Files.deleteIfExists(path);return;}
            catch(java.nio.file.FileSystemException ex){if(attempt>=99)throw ex;Thread.sleep(10);}
        }
    }
    static boolean auditedFixedLandMana(Card card){
        if(!card.isLand() || !MANA_COLORS.containsKey(card.getName()) || card.getManaAbilities().size()!=1)return false;
        SpellAbility mana=card.getManaAbilities().get(0);var costs=mana.getPayCosts();
        String produced=mana.getParam("Produced"),amount=mana.getParamOrDefault("Amount","1");
        String color=produced==null?null:Map.of("W","White","U","Blue","B","Black","R","Red","G","Green","C","Colorless").get(produced);
        return mana.getApi()==forge.game.ability.ApiType.Mana && "1".equals(amount) && color!=null && color.equals(MANA_COLORS.get(card.getName())) && costs!=null && costs.getCostParts().size()==1 && costs.getCostParts().get(0) instanceof forge.game.cost.CostTap;
    }
    // Human cost decisions are separate from availability estimation and auto-tap.
    // Forge still owns cost adjustment, payment, rollback and stack insertion.
    static <T> List<T> optionChoice(String prompt,List<T> offered,int minimum,int maximum,java.util.function.Function<T,String> label,SpellAbility source){
        JsonObject context=choiceSource(source);context.addProperty("nativePromptId",23);
        Map<T,String> labels=new IdentityHashMap<>();Map<String,Integer> frequencies=new HashMap<>();
        for(T value:offered)frequencies.merge(label.apply(value),1,Integer::sum);
        int ordinal=0;for(T value:offered){String text=label.apply(value);labels.put(value,frequencies.get(text)>1?text+" (option "+(++ordinal)+")":text);}
        return selectChoice("options",prompt,offered,minimum,maximum,false,value->{JsonObject o=new JsonObject();o.addProperty("label",labels.get(value));return o;},context);
    }
    static <T> List<T> sourceOrderChoice(String prompt,List<T> offered,java.util.function.Function<T,Card> host,java.util.function.Function<T,String> description){
        JsonObject context=choiceSource(null);context.addProperty("nativePromptId",23);
        return selectChoice("options",prompt,offered,1,1,false,value->{
            JsonObject option=new JsonObject();Card card=host.apply(value);String name=card.getName();
            long sameName=offered.stream().filter(other->host.apply(other).getName().equals(name)).count();
            option.addProperty("label",name+(sameName>1?" (#"+(offered.indexOf(value)+1)+")":""));
            option.addProperty("description",description.apply(value));option.addProperty("effectSourceForgeId",card.getId());return option;
        },context);
    }
    static boolean automaticManaCost(SpellAbility mana){
        if(mana.getPayCosts()==null)return false;
        for(var part:mana.getPayCosts().getCostParts()){
            if(part instanceof forge.game.cost.CostTap)continue;
            if(part instanceof forge.game.cost.CostPartMana p && p.getMana().isZero())continue;
            if(part instanceof forge.game.cost.CostPayLife && part.getAmount().matches("[0-9]+"))continue;
            if(part instanceof forge.game.cost.CostSacrifice && part.payCostFromSource())continue;
            return false;
        }
        return true;
    }
    static List<SpellAbility> availableManaAbilities(){
        List<SpellAbility> offered=new ArrayList<>();
        for(Card card:local.getCardsIn(ZoneType.Battlefield))for(SpellAbility a:card.getManaAbilities()){
            a.setActivatingPlayer(local);if(!a.canPlay() || a.getPayCosts()==null)continue;
            boolean possible=true;for(var cost:a.getPayCosts().getCostParts())if(!cost.canPay(a,local,false)){possible=false;break;}
            if(possible)offered.add(a);
        }
        return offered;
    }
    // Ask the pinned Forge planner for its exact proposed abilities before
    // paying anything. Merely owning a Tower must not force manual payment.
    @SuppressWarnings("unchecked")
    static List<SpellAbility> automaticPaymentPlan(forge.game.mana.ManaCostBeingPaid cost,SpellAbility source,boolean effect){
        List<SpellAbility> suppressed=new ArrayList<>();
        try{
            // Filter only this read-only planning pass. Restore before paying so
            // selected sacrifice abilities remain available for manual payment.
            for(Card card:local.getCardsIn(ZoneType.Battlefield))for(SpellAbility mana:card.getManaAbilities())
                if(!mana.isSuppressed() && !automaticManaCost(mana)){mana.setSuppressed(true);suppressed.add(mana);}
            var method=ComputerUtilMana.class.getDeclaredMethod("payManaCost",forge.game.mana.ManaCostBeingPaid.class,SpellAbility.class,Player.class,boolean.class,boolean.class,boolean.class);
            method.setAccessible(true);
            var plan=(List<SpellAbility>)method.invoke(null,new forge.game.mana.ManaCostBeingPaid(cost),source,local,true,true,effect);
            return plan!=null && plan.stream().allMatch(ForgeLandEngine::automaticManaCost)?plan:null;
        }catch(ReflectiveOperationException error){throw new UnsupportedOperationException("Pinned Forge mana planner unavailable",error);}
        finally{for(SpellAbility mana:suppressed)mana.setSuppressed(false);}
    }
    static boolean payAutomaticPlan(List<SpellAbility> plan,forge.game.mana.ManaCostBeingPaid cost,SpellAbility source,boolean effect){
        forge.ai.AiCardMemory.clearMemorySet(local,forge.ai.AiCardMemory.MemorySet.PAYS_TAP_COST);
        forge.ai.AiCardMemory.clearMemorySet(local,forge.ai.AiCardMemory.MemorySet.PAYS_SAC_COST);
        for(SpellAbility mana:plan){
            if(local.getManaPool().payManaCostFromPool(cost,source,false,source.getPayingMana()))return true;
            if(!automaticManaCost(mana) || !mana.canPlay())return false;
            var shards=new ArrayList<>(cost.getUnpaidShards());
            shards.sort(Comparator.comparing(shard->shard.isGeneric()));
            SpellAbility selected=null;
            for(var shard:shards){
                selected=ComputerUtilMana.chooseManaAbility(cost,source,local,shard,new ArrayList<>(List.of(mana)),true);
                if(selected!=null)break;
            }
            // Forge still chooses colors, validates/pays source costs and
            // resolves mana abilities; execute only the validated safe plan.
            if(selected!=mana)return false;
            var payment=new forge.game.cost.CostPayment(mana.getPayCosts(),mana);
            if(!payment.payComputerCosts(new forge.ai.AiCostDecision(local,mana,effect,true)))return false;
            game.getStack().addAndUnfreeze(mana);
            local.getManaPool().payManaFromAbility(source,cost,mana);
        }
        return local.getManaPool().payManaCostFromPool(cost,source,false,source.getPayingMana());
    }
    static boolean payHumanMana(forge.game.mana.ManaCostBeingPaid cost,SpellAbility source,boolean effect,forge.game.mana.ManaConversionMatrix conversion){
        if(cost.isPaid())return true;
        for(var shard:new ArrayList<>(cost.getUnpaidShards()))if(shard.isPhyrexian()){
            boolean life=local.canPayLife(2,effect,source) && booleanChoice(source,"Pay 2 life instead of "+shard+" for "+source.getHostCard().getName()+"?","phyrexian-payment");
            cost.decreaseShard(shard,1);
            if(life){source.setSpendPhyrexianMana(true);local.payLife(2,source,effect);}
            else cost.increaseShard(forge.card.mana.ManaCostShard.parseNonGeneric(shard.toShortString().replace("/P","").replace("P","")),1);
        }
        if(cost.isPaid())return true;
        List<SpellAbility> offered=availableManaAbilities();
        if(offered.stream().allMatch(ForgeLandEngine::automaticManaCost)){
            researchCallbackAudit.add("explicit-auto-tap-policy-fixed-source-costs");
            return ComputerUtilMana.payManaCost(cost,source,local,effect);
        }
        List<SpellAbility> automaticPlan=automaticPaymentPlan(cost,source,effect);
        if(automaticPlan!=null){
            researchCallbackAudit.add("explicit-auto-tap-validated-payment-plan");
            return payAutomaticPlan(automaticPlan,cost,source,effect);
        }
        // A creature sacrifice or another selected cost is never delegated to
        // auto-tap. Activate the player's chosen source through Forge's human path.
        local.getManaPool().restoreColorReplacements();
        if(conversion!=null)local.getManaPool().applyCardMatrix(conversion);
        if(source.getMayPlayOption()!=null)source.getMayPlayOption().applyManaConvert(local.getManaPool());
        if(source.hasParam("ManaConversion"))forge.game.ability.AbilityUtils.applyManaColorConversion(local.getManaPool(),source.getParam("ManaConversion"));
        forge.game.staticability.StaticAbilityManaConvert.manaConvert(local.getManaPool(),local,source.getHostCard(),source);
        for(int step=0;step<256;step++){
            if(local.getManaPool().payManaCostFromPool(cost,source,false,source.getPayingMana()))return true;
            offered=availableManaAbilities();
            if(offered.isEmpty()){
                if(cost.containsPhyrexianMana() && local.canPayLife(2,effect,source) && booleanChoice(source,"Pay 2 life for Phyrexian mana?","phyrexian-payment")){
                    if(!cost.payPhyrexian())return false;local.payLife(2,source,effect);continue;
                }
                return false;
            }
            List<SpellAbility> selected=optionChoice("Choose a mana source for "+source.getHostCard().getName(),offered,1,1,a->a.getHostCard().getName()+" #"+a.getHostCard().getId()+": "+a.toString(),source);
            if(!forge.game.player.PlaySpellAbility.playSpellAbility(local.getController(),local,selected.get(0)))return false;
        }
        throw new UnsupportedOperationException("Mana payment exceeded its bounded activation count");
    }
    static class HumanPayments extends forge.game.cost.CostDecisionMakerBase {
        HumanPayments(Player p,SpellAbility ability,boolean effect){super(p,effect,ability,ability.getHostCard());}
        @Override public boolean paysRightAfterDecision(){return true;}
        private forge.game.cost.PaymentDecision cards(forge.game.cost.CostPart cost,Iterable<Card> offered,int n,String instruction){
            List<Card> choices=new ArrayList<>();for(Card c:offered)choices.add(c);
            if(n<0 || n>choices.size())return null;
            if(n==0)return forge.game.cost.PaymentDecision.card(new CardCollection());
            JsonObject context=choiceSource(ability);
            List<Card> picked=selectChoice("cards-effect",instruction,choices,n,n,false,c->{JsonObject o=new JsonObject();o.addProperty("forgeId",c.getId());o.addProperty("label",c.getName());o.addProperty("entityKind","card");o.addProperty("privateToSeat",1);o.addProperty("identityVisible",true);return o;},context);
            return forge.game.cost.PaymentDecision.card(picked);
        }
        private CardCollection valid(Iterable<Card> cards,forge.game.cost.CostPart cost){return CardLists.getValidCards(cards,cost.getType().split(";"),player,source,ability);}
        private forge.game.cost.PaymentDecision decide(forge.game.cost.CostPart cost){
            if(!cost.canPay(ability,player,isEffect()))return null;
            if(cost instanceof forge.game.cost.CostTap || cost instanceof forge.game.cost.CostUntap)return forge.game.cost.PaymentDecision.number(1);
            if(cost instanceof forge.game.cost.CostPartMana)return forge.game.cost.PaymentDecision.number(0);
            if(cost instanceof forge.game.cost.CostSacrifice){
                if(cost.payCostFromSource())return forge.game.cost.PaymentDecision.card(source);
                CardCollection candidates=valid(CardLists.filter(player.getCardsIn(ZoneType.Battlefield),CardPredicates.canBeSacrificedBy(ability,isEffect())),cost);
                int count=cost.getAmount().equals("All")?candidates.size():cost.getAbilityAmount(ability);
                return cards(cost,candidates,count,"Sacrifice "+count+" permanent(s) to pay for "+source.getName());
            }
            if(cost instanceof forge.game.cost.CostDiscard){
                if(cost.payCostFromSource())return forge.game.cost.PaymentDecision.card(source);
                if(cost.getType().equals("Hand")){
                    if(!(ability.getPayCosts()!=null && ability.getPayCosts().isMandatory()) && !booleanChoice(ability,"Discard your hand for "+source.getName()+"?","discard-hand-payment"))return null;
                    CardCollectionView hand=player.getCardsIn(ZoneType.Hand);if(hand.size()>1)hand=player.getController().orderMoveToZoneList(hand,ZoneType.Graveyard,ability);
                    return forge.game.cost.PaymentDecision.card(hand);
                }
                CardCollection candidates=cost.getType().equals("Hand")?new CardCollection(player.getCardsIn(ZoneType.Hand)):valid(player.getCardsIn(ZoneType.Hand),cost);
                int count=cost.getAmount().equals("All")?candidates.size():cost.getAbilityAmount(ability);
                return cards(cost,candidates,count,"Discard "+count+" card(s) to pay for "+source.getName());
            }
            if(cost instanceof forge.game.cost.CostExile exile){
                Card only=cost.payCostFromSource()?source:cost.getType().equals("OriginalHost")?ability.getOriginalHost():null;
                if(only!=null){
                    if(!only.canExiledBy(ability,isEffect()) || !exile.from.contains(only.getZone().getZoneType()))return null;
                    return ability.getPayCosts()!=null && ability.getPayCosts().isMandatory() || booleanChoice(ability,"Exile "+only.getName()+" to pay this cost?","exile-payment")?forge.game.cost.PaymentDecision.card(only):null;
                }
                if(cost.getType().contains("FromTopGrave") || cost.getType().contains("+with"))throw new UnsupportedOperationException("Exile payment needs its combined card constraint: "+cost.getType());
                CardCollection pool=new CardCollection(exile.zoneRestriction==1?player.getCardsIn(exile.from):game.getCardsIn(exile.from));
                CardCollection candidates=CardLists.filter(cost.getType().equals("All")?pool:valid(pool,cost),CardPredicates.canExiledBy(ability,isEffect()));
                int n=cost.getType().equals("All")?candidates.size():cost.getAbilityAmount(ability);
                return cards(cost,candidates,n,"Exile "+n+" card(s) to pay for "+source.getName());
            }
            if(cost instanceof forge.game.cost.CostReturn){
                if(cost.payCostFromSource())return ability.getPayCosts()!=null && ability.getPayCosts().isMandatory() || booleanChoice(ability,"Return "+source.getName()+" to hand to pay this cost?","return-payment")?forge.game.cost.PaymentDecision.card(source):null;
                return cards(cost,valid(player.getCardsIn(ZoneType.Battlefield),cost),cost.getAbilityAmount(ability),"Return permanents to hand to pay for "+source.getName());
            }
            if(cost instanceof forge.game.cost.CostReveal reveal){
                if(cost.payCostFromSource())return forge.game.cost.PaymentDecision.card(source);
                if(cost.getType().equals("Hand"))return forge.game.cost.PaymentDecision.card(player.getCardsIn(ZoneType.Hand));
                if(cost.getType().equals("SameColor"))throw new UnsupportedOperationException("Reveal payment needs a shared-color card group constraint");
                return cards(cost,valid(player.getCardsIn(reveal.getRevealFrom()),cost),cost.getAbilityAmount(ability),"Reveal cards to pay for "+source.getName());
            }
            if(cost instanceof forge.game.cost.CostPayLife){
                int n=cost.getAbilityAmount(ability);
                if(!player.canPayLife(n,isEffect(),ability))return null;
                if(n==0 || ability.getPayCosts()!=null && ability.getPayCosts().isMandatory() || booleanChoice(ability,"Pay "+n+" life for "+source.getName()+"?","life-payment"))return forge.game.cost.PaymentDecision.number(n);
                return null;
            }
            if(cost instanceof forge.game.cost.CostTapType){
                CardCollection candidates=valid(player.getCardsIn(ZoneType.Battlefield),cost);
                candidates=CardLists.filter(candidates,ability.isCrew()?CardPredicates.CAN_CREW:CardPredicates.CAN_TAP);
                return cards(cost,candidates,cost.getAbilityAmount(ability),"Choose permanents to tap for "+source.getName());
            }
            if(cost instanceof forge.game.cost.CostPutCounter c && cost.payCostFromSource())return forge.game.cost.PaymentDecision.card(source);
            if(cost instanceof forge.game.cost.CostRemoveCounter c && cost.payCostFromSource()){
                int n=cost.getAmount().equals("All")?source.getCounters(c.counter):cost.getAbilityAmount(ability);
                if(c.counter==null)throw new UnsupportedOperationException("Cost requires selecting counter types");
                // CostRemoveCounter consumes the unowned (Optional.empty) row,
                // as the original human generateCounterTable does. A player
                // row is reserved for added counters and would remove nothing.
                var table=new GameEntityCounterTable();table.put(null,source,c.counter,n);
                return forge.game.cost.PaymentDecision.counters(table);
            }
            if(cost instanceof forge.game.cost.CostMill || cost instanceof forge.game.cost.CostDraw || cost instanceof forge.game.cost.CostGainLife || cost instanceof forge.game.cost.CostDamage)return forge.game.cost.PaymentDecision.number(cost.getAbilityAmount(ability));
            throw new UnsupportedOperationException("Human payment adapter not yet implemented for "+cost.getClass().getSimpleName()+" on "+source.getName());
        }
                @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostBehold cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostBeholdExile cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostGainControl cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostChooseColor cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostChooseCreatureType cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostCollectEvidence cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostDiscard cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostDamage cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostDraw cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostExile cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostExileFromStack cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostExiledMoveToGrave cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostExert cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostEnlist cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostFlipCoin cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostForage cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostRollDice cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostMill cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostAddMana cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostPayLife cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostPayEnergy cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostGainLife cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostPartMana cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostPromiseGift cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostPutCardToLib cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostTap cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostSacrifice cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostReturn cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostReveal cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostRevealChosen cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostRemoveAnyCounter cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostRemoveCounter cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostPutCounter cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostPutCounterYou cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostUntapType cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostUntap cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostUnattach cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostTapType cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostPayShards cost){return decide(cost);}
        @Override public forge.game.cost.PaymentDecision visit(forge.game.cost.CostBlight cost){return decide(cost);}
    }

    static class PassiveController extends PlayerControllerAi {
        private Boolean bufferedKeep;
        private final boolean humanSeat;
        PassiveController(Game g,Player p,LobbyPlayer l){super(g,p,l);humanSeat=l instanceof LocalSeat seat && seat.humanSeat;}
        // PlayerView caches this when the first controller is installed, before
        // the global local reference exists. Bind identity to the registered
        // seat, never to a display name or the previous warm-research game.
        @Override public boolean isAI(){return !humanSeat;}
        @Override public CardCollectionView cheatShuffle(CardCollectionView cards){return humanSeat?cards:super.cheatShuffle(cards);}
        @Override public forge.game.cost.CostDecisionMakerBase getCostDecisionMaker(Player p,SpellAbility ability,boolean effect,String prompt){
            return fullHumanChoices && p==local?new HumanPayments(p,ability,effect):super.getCostDecisionMaker(p,ability,effect,prompt);
        }
        @Override public SpellAbility getAbilityToPlay(Card card,List<SpellAbility> offered,forge.util.ITriggerEvent event){
            if(!fullHumanChoices || getPlayer()!=local)return super.getAbilityToPlay(card,offered,event);
            if(offered.isEmpty())return null;if(offered.size()==1)return offered.get(0);
            return optionChoice("Choose how to play "+card.getName(),offered,1,1,Object::toString,offered.get(0)).get(0);
        }
        @Override public boolean payManaCost(forge.card.mana.ManaCost mana,forge.game.cost.CostPartMana part,SpellAbility sa,String prompt,forge.game.mana.ManaConversionMatrix conversion,boolean isAbility){
            if(!researchAdmission || getPlayer()!=local)return super.payManaCost(mana,part,sa,prompt,conversion,isAbility);
            if(fullHumanChoices)return forge.game.player.PlaySpellAbility.payManaCost(this,mana,part,sa,local,prompt,conversion,isAbility);
            // Explicit client auto-tap policy. The pinned inherited implementation
            // simply delegates to this Forge utility; no choice is hidden here.
            // Unusual costs or mana sources need a separate audited adapter.
            if(mana.getGenericCost()==0 && !mana.iterator().hasNext()){
                researchCallbackAudit.add("automatic-zero-mana-payment");
                return true;
            }
            boolean simple=sa!=null && sa.getPayCosts()!=null;
            if(simple)for(var item:sa.getPayCosts().getCostParts())if(!(item instanceof forge.game.cost.CostPartMana) && !(item instanceof forge.game.cost.CostTap) && !(item instanceof forge.game.cost.CostSacrifice && item.payCostFromSource()))simple=false;
            boolean basicTap=sa!=null && sa.isManaAbility() && sa.getHostCard().getController()==local && auditedFixedLandMana(sa.getHostCard()) && mana.getCMC()==0;
            for(var shard:mana)if(!Set.of("{W}","{U}","{B}","{R}","{G}","{C}").contains(shard.toString()))simple=false;
            if(simple)for(Card c:local.getCardsIn(ZoneType.Battlefield))if(!c.getManaAbilities().isEmpty() && !auditedFixedLandMana(c))simple=false;
            if(!simple && !basicTap){unsupportedDecision="Automatic payment requires audited fixed costs and basic-land sources; source="+(sa==null?"null":sa.getHostCard().getName())+"; costs="+(sa==null || sa.getPayCosts()==null?"null":sa.getPayCosts().getCostParts().stream().map(v->v.getClass().getName()).toList())+"; shards="+java.util.stream.StreamSupport.stream(mana.spliterator(),false).map(Object::toString).toList();throw new UnsupportedOperationException(unsupportedDecision);}
            researchCallbackAudit.add(basicTap?(Set.of("Plains","Island","Swamp","Mountain","Forest").contains(sa.getHostCard().getName())?"automatic-basic-land-tap":"automatic-bound-fixed-land-tap"):"automatic-fixed-mana-and-forced-source-costs");
            return ComputerUtilMana.payManaCost(new forge.game.cost.Cost(mana,isAbility),local,sa,isAbility);
        }
        @Override public boolean confirmAction(SpellAbility sa,PlayerActionConfirmMode mode,String message,List<String> options,Card host,Map<String,Object> params){
            Card card=sa==null?host:sa.getHostCard();
            if(commanderGame() && getPlayer()==local && mode==PlayerActionConfirmMode.ChangeZoneToAltDestination && card!=null && card.isRealCommander() && card.getOwner()==local){
                return chooseCommanderReturn(card,card.getZone().getZoneType());
            }
            if(commanderGame() && getPlayer()==local){unsupportedDecision="Unmapped human Brawl confirmation: "+mode+" / "+message;throw new UnsupportedOperationException(unsupportedDecision);}
            if(researchAdmission && getPlayer()==local){unsupportedDecision="Unmapped human confirmation: "+mode+" / "+message;throw new UnsupportedOperationException(unsupportedDecision);}
            return super.confirmAction(sa,mode,message,options,host,params);
        }
        @Override public boolean confirmReplacementEffect(forge.game.replacement.ReplacementEffect effect,SpellAbility sa,GameEntity affected,String question){
            if(commanderGame() && getPlayer()==local && affected instanceof Card card && card.isRealCommander() && card.getOwner()==local){
                Object original=sa==null?null:sa.getReplacingObject(forge.game.ability.AbilityKey.OriginalParams);
                Object destination=original instanceof Map<?,?> params?params.get(forge.game.ability.AbilityKey.Destination):null;
                if(sa!=null && "Command".equals(sa.getParam("Destination")) && "ReplacedCard".equals(sa.getParam("Defined")) && (destination==ZoneType.Hand || destination==ZoneType.Library))return chooseCommanderReturn(card,(ZoneType)destination);
                unsupportedDecision="Unmapped human commander replacement: "+question;throw new UnsupportedOperationException(unsupportedDecision);
            }
            if(fullHumanChoices && getPlayer()==local)return booleanChoice(sa,question,"replacement-choice");
            if(researchAdmission && getPlayer()==local){unsupportedDecision="Unmapped human replacement choice: "+question;throw new UnsupportedOperationException(unsupportedDecision);}
            return super.confirmReplacementEffect(effect,sa,affected,question);
        }
        private boolean chooseCommanderReturn(Card card,ZoneType alternative){
            boolean[] move={false};commanderDecisionId=card.getId();commanderDecisionZone=alternative.name();JsonArray choices=new JsonArray();
            for(boolean yes:new boolean[]{true,false}){JsonObject choice=new JsonObject();choice.addProperty("returnToCommand",yes);choices.add(choice);}
            waitForDecision("commander_return",choices,values->{
                if(values.size()!=1 || !values.get(0).isJsonObject() || !values.get(0).getAsJsonObject().has("returnToCommand") || !values.get(0).getAsJsonObject().get("returnToCommand").isJsonPrimitive() || !values.get(0).getAsJsonObject().getAsJsonPrimitive("returnToCommand").isBoolean())throw new IllegalArgumentException("Choose whether to return this commander");
                move[0]=values.get(0).getAsJsonObject().get("returnToCommand").getAsBoolean();
            });return move[0];
        }
        @Override public <T extends GameEntity> T chooseSingleEntityForEffect(forge.util.collect.FCollectionView<T> entities,DelayedReveal reveal,SpellAbility sa,String title,boolean optional,Player related,Map<String,Object> params){
            if(getPlayer()!=local)return super.chooseSingleEntityForEffect(entities,reveal,sa,title,optional,related,params);
            if(sa!=null && sa.getApi()==forge.game.ability.ApiType.InternalLegendaryRule){
                Map<Integer,T> offered=new LinkedHashMap<>();JsonArray options=new JsonArray();List<T> selected=new ArrayList<>();
                for(T entity:entities){if(!(entity instanceof Card c) || !ADMITTED_CARDS.contains(c.getName()) || c.getController()!=local || !c.isInZone(ZoneType.Battlefield))throw new UnsupportedOperationException("Legend choice contains an unmapped permanent");offered.put(c.getId(),entity);JsonObject o=new JsonObject();o.addProperty("forgeId",c.getId());options.add(o);}
                waitForDecision("legend_rule",options,values->{if(values.size()!=1)throw new IllegalArgumentException("Choose one legendary permanent to keep");int id=values.get(0).getAsJsonObject().get("forgeId").getAsInt();T choice=offered.get(id);if(choice==null || !((Card)choice).isInZone(ZoneType.Battlefield))throw new IllegalArgumentException("Legendary permanent was not offered");selected.clear();selected.add(choice);});return selected.get(0);
            }
            if(!optional && entities.size()==1)return entities.getFirst();
            unsupportedDecision="Unmapped human single-entity choice: "+title;throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public List<SpellAbility> chooseSpellAbilityToPlay(){
            if(commanderPod && local!=null && local.hasLost())waitForPodExit();
            if(getPlayer()==local && normalGame())return waitForPriority();
            if(getPlayer()!=local && fullHumanChoices && scenario.equals("card-family") && !researchOpponentSpellPlan.isEmpty()){
                for(Card card:getPlayer().getCardsIn(ZoneType.Hand))if(card.getName().equals(researchOpponentSpellPlan.peekFirst()))for(SpellAbility a:card.getAllPossibleAbilities(getPlayer(),false))if(a.isSpell() && !a.usesTargeting()){
                    a.setActivatingPlayer(getPlayer());if(a.canPlay() && ComputerUtilCost.canPayCost(a,getPlayer(),false)){researchOpponentSpellPlan.removeFirst();return List.of(a);}
                }
            }
            return aiDuel() && getPlayer()!=local?super.chooseSpellAbilityToPlay():null;
        }
        @Override public boolean playChosenSpellAbility(SpellAbility chosen){
            if(getPlayer()!=local || !normalGame())return super.playChosenSpellAbility(chosen);
            if(fullHumanChoices){
                if(chosen.isSpell())chosen=chooseHumanCastAbility(chosen.getHostCard());
                else if(chosen.isLandAbility())chosen=chooseHumanLandAbility(chosen.getHostCard());
                boolean played=chosen!=null && (chosen.isLandAbility()?playHumanLand(chosen):forge.game.player.PlaySpellAbility.playSpellAbility(this,local,chosen));
                // Canceling the offered prepayment targets is a successful UI
                // action. Forge correctly returns false for the unplayed ability;
                // do not turn that explicit cancellation into a rejected command.
                boolean canceled=targetCancelled && currentRequest!=null && "cancel_targets".equals(currentRequest.get("op").getAsString());
                if(!played && !canceled)failedPlays.put(currentRequest.get("id").getAsString(),"Human play could not complete its original Forge costs");
                return played;
            }
            boolean played;
            if(chosen.isLandAbility()){played=chosen.canPlay();if(played)chosen.resolve();}
            else if(chosen.isManaAbility())played=ComputerUtil.playNoStack(local,chosen,game,false);
            else {
                if(!selectHumanTargets(chosen))return false;
                played=ComputerUtil.playStack(chosen,local,game);
            }
            if(!played)failedPlays.put(currentRequest.get("id").getAsString(),"Forge could not execute the selected ability");
            return played;
        }
        @Override public Player chooseStartingPlayer(boolean firstGame){
            if(!normalGame())return super.chooseStartingPlayer(firstGame);
            if(startingPlayerPolicy.equals("local-first")){startingSeat=1;return local;}
            if(getPlayer()!=local){Player chosen=super.chooseStartingPlayer(firstGame);startingSeat=seat(chosen);return chosen;}
            JsonArray options=new JsonArray();for(int seat=1;seat<=seatPlayers.size();seat++){JsonObject o=new JsonObject();o.addProperty("startingSeat",seat);options.add(o);}
            waitForDecision("starting_player",options,values->{
                if(values.size()!=1)throw new IllegalArgumentException("Choose exactly one starting seat");
                int seat=values.get(0).getAsJsonObject().get("startingSeat").getAsInt();if(seat<1 || seat>seatPlayers.size())throw new IllegalArgumentException("Starting seat was not offered");startingSeat=seat;
            });return playerAtSeat(startingSeat);
        }
        @Override public boolean mulliganKeepHand(Player first,int cardsToReturn){
            if(getPlayer()!=local){boolean keep=super.mulliganKeepHand(first,cardsToReturn);int id=seat(getPlayer());seatKept.put(id,keep);if(!keep)seatMulligans.merge(id,1,Integer::sum);if(getPlayer()==opponent){opponentKept=keep;opponentMulligans=seatMulligans.getOrDefault(id,0);}return keep;}
            if(bufferedKeep!=null){boolean keep=bufferedKeep;bufferedKeep=null;return keep;}
            return askMulligan(cardsToReturn);
        }
        private boolean askMulligan(int cardsToReturn){
            boolean[] keep={true};discardCount=cardsToReturn;
            JsonArray options=new JsonArray();for(boolean accept:new boolean[]{true,false}){JsonObject o=new JsonObject();o.addProperty("keep",accept);options.add(o);}
            waitForDecision("mulligan",options,values->{
                if(values.size()!=1 || !values.get(0).getAsJsonObject().has("keep"))throw new IllegalArgumentException("Choose keep or mulligan");
                boolean accepted=values.get(0).getAsJsonObject().get("keep").getAsBoolean();
                if(!accepted && cardsToReturn>=local.getStartingHandSize())throw new IllegalArgumentException("Cannot mulligan below zero cards; keep this hand");
                keep[0]=accepted;seatKept.put(1,accepted);if(!keep[0])mulligans++;
            });return keep[0];
        }
        @Override public CardCollectionView tuckCardsViaMulligan(CardCollectionView hand,int count){
            if(getPlayer()!=local)return super.tuckCardsViaMulligan(hand,count);
            if(count==0)return new CardCollection();
            // This Forge build tucks before asking Keep. Ask the native London
            // question while all seven are still visible, and buffer its answer
            // for Forge's following callback. A rejected hand will immediately
            // be shuffled again, so its unobservable bottom choice uses the
            // offered first N; a kept hand always requires the player's choice.
            bufferedKeep=askMulligan(count);
            if(game.isGameOver())return new CardCollection();
            if(!bufferedKeep){CardCollection obsolete=new CardCollection();for(Card c:hand){if(obsolete.size()==count)break;obsolete.add(c);}event(Map.of("kind","obsolete-mulligan-bottom","count",count,"policy","first offered cards; rejected hand immediately reshuffled by Forge"));return obsolete;}
            discardCount=count;JsonArray options=new JsonArray();CardCollection chosen=new CardCollection();
            for(Card c:hand){JsonObject o=new JsonObject();o.addProperty("forgeId",c.getId());options.add(o);}
            waitForDecision("mulligan_bottom",options,values->{
                if(values.size()!=count)throw new IllegalArgumentException("Forge requires exactly "+count+" cards to bottom");
                chosen.clear();Set<Integer> unique=new HashSet<>();
                for(JsonElement v:values){int id=v.getAsJsonObject().get("forgeId").getAsInt();if(!unique.add(id))throw new IllegalArgumentException("duplicate bottom card");Card c=findCard(id);if(!hand.contains(c))throw new IllegalArgumentException("bottom card was not in the offered hand");chosen.add(c);}
            });return chosen;
        }
        @Override public CardCollectionView chooseCardsToDiscardToMaximumHandSize(int count){
            if(getPlayer()!=local)return super.chooseCardsToDiscardToMaximumHandSize(count);
            discardCount=count;JsonArray options=new JsonArray();CardCollection selected=new CardCollection();
            for(Card c:local.getCardsIn(ZoneType.Hand)){JsonObject option=new JsonObject();option.addProperty("forgeId",c.getId());options.add(option);}
            waitForDecision("discard",options,assignments->{
                if(assignments.size()!=count)throw new IllegalArgumentException("Forge requires exactly "+count+" discards");
                selected.clear();Set<Integer> unique=new HashSet<>();
                for(JsonElement e:assignments){int id=e.getAsJsonObject().get("forgeId").getAsInt();if(!unique.add(id))throw new IllegalArgumentException("duplicate discard");Card c=findCard(id);if(c.getController()!=local || !c.isInZone(ZoneType.Hand))throw new IllegalArgumentException("discard must be in local hand");selected.add(c);}
            });return selected;
        }
        @Override public CardCollectionView orderMoveToZoneList(CardCollectionView cards,ZoneType destination,SpellAbility cause){
            if(getPlayer()!=local)return super.orderMoveToZoneList(cards,destination,cause);
            if(fullHumanChoices && destination==ZoneType.Graveyard){
                for(Card c:cards)if(!MAPPED_OBJECTS.contains(presentationKey(c)))throw new UnsupportedOperationException("Unmapped graveyard ordering identity: "+presentationKey(c));
                CardCollection ordered=new CardCollection();
                if(cards.size()<2){ordered.addAll(cards);return ordered;}
                List<Card> offered=new ArrayList<>();for(Card c:cards)offered.add(c);
                JsonObject context=choiceSource(cause);context.addProperty("destination","Graveyard");
                ordered.addAll(selectChoice("order","Order cards entering the graveyard",offered,offered.size(),offered.size(),false,c->{JsonObject o=new JsonObject();o.addProperty("forgeId",c.getId());o.addProperty("entityKind","card");o.addProperty("label",c.getName());o.addProperty("privateToSeat",1);o.addProperty("identityVisible",true);return o;},context));
                return ordered;
            }
            if(destination!=ZoneType.Graveyard){
                if(!researchAdmission)return super.orderMoveToZoneList(cards,destination,cause);
                unsupportedDecision="Unmapped human zone ordering: "+destination;throw new UnsupportedOperationException(unsupportedDecision);
            }
            Map<Integer,Card> offered=new LinkedHashMap<>();JsonArray options=new JsonArray();
            for(Card c:cards){
                if(c.getOwner()!=local || !MAPPED_OBJECTS.contains(c.getName()) || c.isInZone(ZoneType.Library)){
                    unsupportedDecision="Graveyard ordering needs mapped public/local-hand objects";throw new UnsupportedOperationException(unsupportedDecision);
                }
                offered.put(c.getId(),c);JsonObject option=new JsonObject();option.addProperty("forgeId",c.getId());options.add(option);
            }
            if(cards.size()<2){CardCollection forced=new CardCollection();forced.addAll(cards);return forced;}
            orderDecisionZone=destination.name();CardCollection chosen=new CardCollection();
            waitForDecision("order_cards",options,values->{
                if(values.size()!=offered.size())throw new IllegalArgumentException("Order every offered card exactly once");
                CardCollection selection=new CardCollection();Set<Integer> unique=new HashSet<>();
                for(JsonElement value:values){JsonElement raw=value.getAsJsonObject().get("forgeId");
                    if(raw==null || !raw.isJsonPrimitive() || !raw.getAsJsonPrimitive().isNumber() || !raw.getAsString().matches("[0-9]+"))throw new IllegalArgumentException("Ordering needs integer original object IDs");
                    int id=raw.getAsInt();Card c=offered.get(id);if(c==null || !unique.add(id))throw new IllegalArgumentException("Duplicate or unoffered ordered card");selection.add(c);
                }
                chosen.clear();chosen.addAll(selection);
            });return chosen;
        }
        @Override public void declareAttackers(Player p,Combat combat){
            if(p!=local){
                if(aiDuel()){super.declareAttackers(p,combat);return;}
                if(scenario.startsWith("defend") || researchOpponentAttackAll)for(Card c:p.getCreaturesInPlay())if(CombatUtil.canAttack(c,local))combat.addAttacker(c,local);
                return;
            }
            JsonArray options=new JsonArray();
            for(Card c:p.getCreaturesInPlay()){
                JsonArray recipients=new JsonArray();
                for(Player defending:p.getOpponents()){
                    if(CombatUtil.canAttack(c,defending)){JsonObject r=new JsonObject();r.addProperty("targetSeat",seat(defending));r.addProperty("targetForgeId",0);recipients.add(r);}
                    for(Card pw:defending.getCardsIn(ZoneType.Battlefield))if(pw.isPlaneswalker() && CombatUtil.canAttack(c,pw)){
                        JsonObject r=new JsonObject();r.addProperty("targetSeat",seat(defending));r.addProperty("targetForgeId",pw.getId());recipients.add(r);
                    }
                }
                if(recipients.size()>0){JsonObject option=new JsonObject();option.addProperty("forgeId",c.getId());option.addProperty("targetSeat",recipients.get(0).getAsJsonObject().get("targetSeat").getAsInt());option.add("attackTargets",recipients);options.add(option);}
            }
            waitForDecision("attackers",options,assignments->{
                combat.clearAttackers();
                for(JsonElement e:assignments){JsonObject a=e.getAsJsonObject();if(a.get("targetSeat").getAsInt()!=0){int target=a.has("targetForgeId")?a.get("targetForgeId").getAsInt():0;combat.addAttacker(findCard(a.get("forgeId").getAsInt()),target==0?playerAtSeat(a.get("targetSeat").getAsInt()):findCard(target));}}
                if(!CombatUtil.validateAttackers(combat)){combat.clearAttackers();throw new IllegalArgumentException("Forge rejected the complete attacker declaration");}
            });
        }
        @Override public void declareBlockers(Player p,Combat combat){
            if(p!=local){
                if(aiDuel()){super.declareBlockers(p,combat);return;}
                if(scenario.contains("blocked") || researchOpponentBlockAll)for(Card c:p.getCreaturesInPlay())for(Card a:combat.getAttackers())if(CombatUtil.canBlock(a,c,combat)){combat.addBlocker(a,c);break;}
                if(researchOpponentBlockAll){String error=CombatUtil.validateBlocks(combat,p);if(error!=null)throw new IllegalArgumentException("Authored block-all opponent is illegal: "+error);}
                return;
            }
            JsonArray options=new JsonArray();
            for(Card c:p.getCreaturesInPlay()){
                JsonArray attackers=new JsonArray();for(Card a:combat.getAttackers())if(CombatUtil.canBlock(a,c,combat))attackers.add(a.getId());
                if(attackers.size()>0){JsonObject option=new JsonObject();option.addProperty("forgeId",c.getId());option.add("attackerIds",attackers);options.add(option);}
            }
            waitForDecision("blockers",options,assignments->{
                for(Card c:p.getCreaturesInPlay())combat.undoBlockingAssignment(c);
                for(JsonElement e:assignments){JsonObject a=e.getAsJsonObject();for(JsonElement id:a.getAsJsonArray("attackerIds"))combat.addBlocker(findCard(id.getAsInt()),findCard(a.get("forgeId").getAsInt()));}
                String error=CombatUtil.validateBlocks(combat,p);if(error!=null){for(Card c:p.getCreaturesInPlay())combat.undoBlockingAssignment(c);throw new IllegalArgumentException(error);}
            });
        }
        @Override public Map<Card,Integer> assignCombatDamage(Card source,CardCollectionView recipients,CardCollectionView remaining,int total,GameEntity defender,boolean overrideOrder){
            if(getPlayer()!=local)return super.assignCombatDamage(source,recipients,remaining,total,defender,overrideOrder);
            if(source.hasKeyword("Banding")){
                unsupportedDecision="Unmapped keyword combat damage allocation";throw new UnsupportedOperationException(unsupportedDecision);
            }
            boolean trample=source.hasKeyword("Trample") && !recipients.isEmpty() && game.getCombat()!=null && game.getCombat().isAttacking(source);
            if(trample){
                GameEntity actual=game.getCombat().getDefenderByAttacker(source);
                if(!(actual instanceof Player) || actual==local){unsupportedDecision="Trample allocation requires a defending opposing player";throw new UnsupportedOperationException(unsupportedDecision);}
            }
            if(!trample && recipients.size()<=1){Map<Card,Integer> forced=new LinkedHashMap<>();forced.put(recipients.isEmpty()?null:recipients.get(0),total);return forced;}
            if(!overrideOrder && recipients.size()>1){unsupportedDecision="Unmapped ordered combat damage choice";throw new UnsupportedOperationException(unsupportedDecision);}
            damageSourceId=source.getId();damageTotal=total;
            JsonArray options=new JsonArray();Map<Integer,Card> offered=new LinkedHashMap<>();Map<Card,Integer> lethal=new LinkedHashMap<>();int unassigned=total;
            // Recovered native priority: lethal in displayed order, then the
            // remainder to the last recipient. This only suggests UI values;
            // the rules wait for an explicit complete human submission.
            for(Card card:recipients){
                int health=Math.max(0,card.getNetToughness()-card.getDamage());int needed=source.hasKeyword("Deathtouch") && health>0?1:health;lethal.put(card,needed);
                int suggestion=Math.min(unassigned,needed);unassigned-=suggestion;
                offered.put(card.getId(),card);JsonObject option=new JsonObject();option.addProperty("forgeId",card.getId());option.addProperty("lethalDamage",needed);option.addProperty("assignedDamage",suggestion);options.add(option);
            }
            if(trample){
                int defendingSeat=seat((Player)game.getCombat().getDefenderByAttacker(source));offered.put(-1000000-defendingSeat,null);JsonObject option=new JsonObject();option.addProperty("forgeId",-1000000-defendingSeat);option.addProperty("targetKind","player");option.addProperty("targetSeat",defendingSeat);option.addProperty("lethalDamage",0);option.addProperty("assignedDamage",unassigned);options.add(option);
            }else if(unassigned>0){JsonObject last=options.get(options.size()-1).getAsJsonObject();last.addProperty("assignedDamage",last.get("assignedDamage").getAsInt()+unassigned);}
            Map<Card,Integer> result=new LinkedHashMap<>();
            waitForDecision("assign_damage",options,values->{
                if(values.size()!=offered.size())throw new IllegalArgumentException("Assign damage to every offered recipient, including zero allocations");
                Map<Card,Integer> selected=new LinkedHashMap<>();int sum=0;
                for(JsonElement value:values){JsonObject entry=value.getAsJsonObject();int id=entry.get("forgeId").getAsInt();Card card=offered.get(id);JsonElement amount=entry.get("amount");
                    if(!offered.containsKey(id) || selected.containsKey(card))throw new IllegalArgumentException("Duplicate or unoffered damage recipient");
                    if(amount==null || !amount.isJsonPrimitive() || !amount.getAsJsonPrimitive().isNumber() || !amount.getAsString().matches("[0-9]+"))throw new IllegalArgumentException("Damage must be a nonnegative integer");
                    int count=Integer.parseInt(amount.getAsString());if(count<0 || count>total)throw new IllegalArgumentException("Damage exceeds the source total");sum+=count;selected.put(card,count);
                }
                if(sum!=total)throw new IllegalArgumentException("All combat damage must be assigned exactly once");
                if(trample && selected.getOrDefault(null,0)>0)for(Card card:recipients)if(selected.getOrDefault(card,0)<lethal.get(card))throw new IllegalArgumentException("Assign lethal to every blocker before trample damage to the player");
                result.clear();result.putAll(selected);
            });return result;
        }
    }
    static int choiceInteger(JsonObject value,String field){
        JsonElement raw=value.get(field);
        if(raw==null || !raw.isJsonPrimitive() || !raw.getAsJsonPrimitive().isNumber() || !raw.getAsString().matches("-?(0|[1-9][0-9]*)"))throw new IllegalArgumentException("Choice needs integer "+field);
        try{return Integer.parseInt(raw.getAsString());}catch(NumberFormatException ex){throw new IllegalArgumentException("Choice integer is outside supported range");}
    }
    static void choiceFields(JsonObject value,String... fields){
        if(!value.keySet().equals(new HashSet<>(Arrays.asList(fields))))throw new IllegalArgumentException("Unexpected choice fields");
    }
    static void sharedDecision(JsonObject spec,Consumer<JsonArray> submit){
        if(!researchAdmission || !(local.getController() instanceof ResearchStrictController))throw new UnsupportedOperationException("Shared choices await native acceptance; independent research runtime required");
        if(sharedChoice!=null)throw new IllegalStateException("Nested shared choice has not completed");
        spec.addProperty("schema",1);sharedChoice=spec;
        try{waitForDecision("choice",spec.getAsJsonArray("options"),submit);}finally{sharedChoice=null;}
    }
    static JsonObject choiceSpec(String type,String prompt){
        JsonObject value=new JsonObject();value.addProperty("type",type);value.addProperty("prompt",prompt==null?"Choose":prompt);value.add("options",new JsonArray());return value;
    }
    static JsonObject choiceSource(SpellAbility source){
        JsonObject value=new JsonObject();
        if(source!=null){
            Card host=source.getHostCard();int sourceId=keywordPresentationSource(host);
            if(sourceId==0)throw new UnsupportedOperationException("Unmapped choice effect source");
            value.addProperty("sourceForgeId",sourceId);
            boolean registered=false;for(Card c:game.getCardsInGame())if(c.getId()==host.getId()){registered=true;break;}
            if(fullHumanChoices && source.isCopied() && !registered)value.add("pendingCopyObject",JSON.toJsonTree(card(host,host.getZone()==null?"Limbo":null)));
        }
        return value;
    }
    static <T> List<T> selectChoice(String type,String prompt,List<T> offered,int minimum,int maximum,boolean repeats,java.util.function.Function<T,JsonObject> describe){
        return selectChoice(type,prompt,offered,minimum,maximum,repeats,describe,new JsonObject());
    }
    static <T> List<T> selectChoice(String type,String prompt,List<T> offered,int minimum,int maximum,boolean repeats,java.util.function.Function<T,JsonObject> describe,JsonObject context){
        int optionLimit=fullHumanChoices && type.equals("card-name")?32768:1024;
        if(minimum<0 || maximum<minimum || maximum>1024 || offered.size()>optionLimit || (!repeats && minimum>offered.size()))throw new UnsupportedOperationException("Invalid or unbounded shared selection");
        if(maximum==0)return new ArrayList<>();
        JsonObject spec=choiceSpec(type,prompt);for(var field:context.entrySet())spec.add(field.getKey(),field.getValue());spec.addProperty("min",minimum);spec.addProperty("max",repeats?maximum:Math.min(maximum,offered.size()));spec.addProperty("repeats",repeats);
        for(int i=0;i<offered.size();i++){JsonObject option=describe.apply(offered.get(i));option.addProperty("choiceId",i+1);spec.getAsJsonArray("options").add(option);}
        List<T> result=new ArrayList<>();
        sharedDecision(spec,values->{
            if(values==null || values.size()<minimum || values.size()>spec.get("max").getAsInt())throw new IllegalArgumentException("Selection count is outside Forge bounds");
            Set<Integer> seen=new HashSet<>();List<T> selected=new ArrayList<>();
            for(JsonElement element:values){JsonObject value=element.getAsJsonObject();choiceFields(value,"choiceId");int id=choiceInteger(value,"choiceId");if(id<1 || id>offered.size() || (!repeats && !seen.add(id)))throw new IllegalArgumentException("Choice was repeated or not offered");selected.add(offered.get(id-1));}
            result.clear();result.addAll(selected);
        });return result;
    }
    static org.apache.commons.lang3.tuple.ImmutablePair<CardCollection,CardCollection> partitionChoice(CardCollection cards,String other){
        CardCollection top=new CardCollection(),rest=new CardCollection();if(cards.isEmpty())return org.apache.commons.lang3.tuple.ImmutablePair.of(top,rest);
        JsonObject spec=choiceSpec("partition",other.equals("bottom")?"Scry: order cards on top or bottom":"Surveil: order cards on top or move to graveyard");
        int source=resolvingSource();if(source!=0)spec.addProperty("sourceForgeId",source);
        spec.addProperty("count",cards.size());spec.addProperty("topOrder","next card drawn first");spec.addProperty("otherOrder",other.equals("bottom")?"closest to library top first":"Forge insertion order");
        spec.add("groups",JSON.toJsonTree(List.of("top",other)));
        Map<Integer,Card> identities=new LinkedHashMap<>();
        for(Card card:cards){if(identities.put(card.getId(),card)!=null)throw new IllegalStateException("Duplicate offered card identity");JsonObject option=new JsonObject();option.addProperty("choiceId",card.getId());option.addProperty("forgeId",card.getId());option.addProperty("label",card.getName());option.addProperty("privateToSeat",1);spec.getAsJsonArray("options").add(option);}
        sharedDecision(spec,values->{
            if(values==null || values.size()!=identities.size())throw new IllegalArgumentException("Partition must contain every offered card once");
            Set<Integer> seen=new HashSet<>();CardCollection selectedTop=new CardCollection(),selectedRest=new CardCollection();
            for(JsonElement element:values){JsonObject value=element.getAsJsonObject();choiceFields(value,"choiceId","group");int id=choiceInteger(value,"choiceId");JsonElement raw=value.get("group");if(!raw.isJsonPrimitive() || !raw.getAsJsonPrimitive().isString())throw new IllegalArgumentException("Partition group must be a string");String group=raw.getAsString();Card card=identities.get(id);if(card==null || !seen.add(id) || !(group.equals("top") || group.equals(other)))throw new IllegalArgumentException("Invalid, repeated or unoffered partition entry");if(group.equals("top"))selectedTop.add(card);else selectedRest.add(card);}
            top.clear();top.addAll(selectedTop);rest.clear();rest.addAll(selectedRest);
        });return org.apache.commons.lang3.tuple.ImmutablePair.of(top,rest);
    }
    static String cardNameChoice(SpellAbility source,List<forge.card.ICardFace> faces,String prompt){
        List<forge.card.ICardFace> offered=new ArrayList<>();Set<Integer> seen=new HashSet<>();
        for(var face:faces){Integer id=CARD_NAME_IDS.get(face.getName());if(id!=null && seen.add(id))offered.add(face);}
        if(offered.isEmpty())throw new UnsupportedOperationException("No Arena-present card name satisfies the Forge name restriction");
        return selectChoice("card-name",prompt,offered,1,1,false,face->{JsonObject value=new JsonObject();value.addProperty("label",face.getName());value.addProperty("nativeTitleId",CARD_NAME_IDS.get(face.getName()));return value;},choiceSource(source)).get(0).getName();
    }
    static int numberChoice(SpellAbility source,String prompt,int minimum,int maximum){
        if(maximum<minimum)throw new IllegalArgumentException("Invalid numeric choice bounds");
        if(minimum==maximum){researchCallbackAudit.add("forced-number:"+minimum);return minimum;}
        JsonObject spec=choiceSpec("number",prompt);spec.addProperty("min",minimum);spec.addProperty("max",maximum);int[] result={minimum};
        for(var field:choiceSource(source).entrySet())spec.add(field.getKey(),field.getValue());
        sharedDecision(spec,values->{if(values==null || values.size()!=1)throw new IllegalArgumentException("Choose exactly one number");JsonObject value=values.get(0).getAsJsonObject();choiceFields(value,"number");int number=choiceInteger(value,"number");if(number<minimum || number>maximum)throw new IllegalArgumentException("Number is outside Forge bounds");result[0]=number;});return result[0];
    }
    static boolean booleanChoice(SpellAbility source,String prompt,String context){
        if(scenario.equals("card-family") && fixtureConfig!=null && fixtureConfig.has("traceChoices") && fixtureConfig.get("traceChoices").getAsBoolean())researchEvent(Map.of("kind","choice-callsite","context",context,"prompt",prompt,"callers",StackWalker.getInstance().walk(s->s.limit(10).map(Object::toString).toList())));
        JsonObject spec=choiceSpec("confirm",prompt);spec.addProperty("context",context);boolean[] result={false};
        for(var field:choiceSource(source).entrySet())spec.add(field.getKey(),field.getValue());
        sharedDecision(spec,values->{if(values==null || values.size()!=1)throw new IllegalArgumentException("Choose exactly one confirmation");JsonObject value=values.get(0).getAsJsonObject();choiceFields(value,"accept");JsonElement accept=value.get("accept");if(!accept.isJsonPrimitive() || !accept.getAsJsonPrimitive().isBoolean())throw new IllegalArgumentException("Confirmation must be boolean");result[0]=accept.getAsBoolean();});return result[0];
    }
    static class HeadlessChoiceController extends PassiveController {
        private boolean forcedMandatoryTrigger(SpellAbility ability){
            if(!ability.isTrigger() || ability.isCopied() || ability.isOptionalTrigger() || !ability.isMandatory())return false;
            int count=0;for(SpellAbility part=ability;part!=null;part=part.getSubAbility())if(++count>64 || part.isAnnouncing("X") || part.usesTargeting() && (!researchAdmission || nativeAbility(ability,true)==0))return false;
            return true;
        }
        @Override public void orderAndPlaySimultaneousSa(List<SpellAbility> abilities){
            if(getPlayer()!=local){super.orderAndPlaySimultaneousSa(abilities);return;}
            if(abilities.isEmpty())return;
            if(fullHumanChoices){
                List<SpellAbility> remaining=new ArrayList<>(abilities),ordered=new ArrayList<>();
                while(remaining.size()>1){
                    SpellAbility next=sourceOrderChoice("Choose the ability that resolves next",remaining,a->a.getHostCard(),Object::toString).get(0);
                    ordered.add(next);remaining.remove(next);
                }
                ordered.addAll(remaining);
                for(int i=ordered.size()-1;i>=0;i--){
                    SpellAbility next=ordered.get(i);
                    if(next.isTrigger() && !next.isCopied()){forge.game.player.PlaySpellAbility.playSpellAbility(this,getPlayer(),next);continue;}
                    if(next.isCopied()){
                        if(next.isSpell()){
                            if(!next.getHostCard().isInZone(ZoneType.Stack))next.setHostCard(game.getAction().moveToStack(next.getHostCard(),next));
                            else game.getStackZone().add(next.getHostCard());
                        }
                        if(next.isMayChooseNewTargets())next.setupNewTargets(getPlayer());
                    }
                    game.getStack().add(next);
                }
                return;
            }
            if(abilities.size()!=1 || !forcedMandatoryTrigger(abilities.get(0))){unsupportedDecision="Unmapped human trigger ordering, optional trigger or triggered target: "+abilities.stream().map(a->a.getHostCard().getName()).toList();throw new UnsupportedOperationException(unsupportedDecision);}
            SpellAbility ability=abilities.get(0);String audit="forced-single-mandatory-trigger:"+ability.getHostCard().getId()+":"+ability.getId();if(!researchCallbackAudit.contains(audit))researchCallbackAudit.add(audit);
            if(!forge.game.player.PlaySpellAbility.playSpellAbility(this,getPlayer(),ability))throw new UnsupportedOperationException("Original human trigger execution refused the mandatory ability");
        }
        @Override public boolean playTrigger(Card host,forge.game.trigger.WrappedAbility ability,boolean mandatory){
            if(getPlayer()!=local)return super.playTrigger(host,ability,mandatory);
            if(fullHumanChoices)return forge.game.player.PlaySpellAbility.playSpellAbilityNoStack(this,getPlayer(),ability,false);
            if(!mandatory || !forcedMandatoryTrigger(ability)){unsupportedDecision="Unmapped optional or targeted no-stack trigger";throw new UnsupportedOperationException(unsupportedDecision);}
            return forge.game.player.PlaySpellAbility.playSpellAbilityNoStack(this,getPlayer(),ability,false);
        }

        @Override public forge.game.staticability.StaticAbility chooseSingleStaticAbility(List<forge.game.staticability.StaticAbility> choices){
            if(getPlayer()!=local)return super.chooseSingleStaticAbility(choices);
            // The pinned Human controller returns the sole option directly.
            // Multiple reducers/abilities still require an explicit order UI.
            if(choices.size()==1){String audit="forced-single-static-ability:"+choices.get(0).getId();if(!researchCallbackAudit.contains(audit))researchCallbackAudit.add(audit);return choices.get(0);}
            if(fullHumanChoices)return sourceOrderChoice("Choose which static ability applies next",choices,a->a.getHostCard(),Object::toString).get(0);
            unsupportedDecision="Unmapped human order of multiple static/cost abilities";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public List<SpellAbility> chooseSpellAbilitiesForEffect(List<SpellAbility> options,SpellAbility source,String prompt,int count,Map<String,Object> params){
            if(getPlayer()!=local)return super.chooseSpellAbilitiesForEffect(options,source,prompt,count,params);
            if(fullHumanChoices)return optionChoice(prompt,options,count,count,SpellAbility::toString,source);
            JsonObject binding=source==null?null:GENERIC_CHOICE_BINDINGS.get(source.getHostCard().getName());
            if(binding==null || source.hasParam("ShowCurrentCard")){unsupportedDecision="Unmapped human chooseSpellAbilitiesForEffect native prompt binding for "+(source==null?"unknown source":source.getHostCard().getName());throw new UnsupportedOperationException(unsupportedDecision);}
            Set<String> allowed=new HashSet<>();for(var label:binding.getAsJsonArray("labels"))allowed.add(label.getAsString());Set<String> seen=new HashSet<>();
            for(SpellAbility option:options)if(!allowed.contains(option.toString()) || !seen.add(option.toString()))throw new UnsupportedOperationException("Generic choice label is not uniquely bound to the owned source");
            JsonObject context=choiceSource(source);context.add("nativePromptId",binding.get("promptId"));
            return selectChoice("abilities",prompt,options,count,count,false,option->{JsonObject value=new JsonObject();value.addProperty("label",option.toString());return value;},context);
        }

        private void revealViews(List<forge.game.card.CardView> cards,String prompt){
            if(cards.isEmpty())return;
            JsonObject spec=choiceSpec("look",prompt==null?"Look at revealed cards":prompt);int source=resolvingSource();if(source!=0)spec.addProperty("sourceForgeId",source);
            spec.addProperty("min",0);spec.addProperty("max",0);spec.addProperty("repeats",false);
            Set<Integer> seen=new HashSet<>();int ordinal=1;
            for(var view:cards){Card actual=findCard(view.getId());if(actual==null || !seen.add(view.getId()))throw new UnsupportedOperationException("Reveal contains a stale or duplicate object");JsonObject value=new JsonObject();value.addProperty("choiceId",ordinal++);value.addProperty("forgeId",actual.getId());value.addProperty("label",view.getName());value.addProperty("privateToSeat",1);value.addProperty("identityVisible",true);spec.getAsJsonArray("options").add(value);}
            sharedDecision(spec,values->{if(values==null || !values.isEmpty())throw new IllegalArgumentException("Reveal acknowledgement must not select or move any object");});
        }
        @Override public void reveal(CardCollectionView cards,ZoneType zone,Player owner,String prompt,boolean remember){
            if(getPlayer()!=local){super.reveal(cards,zone,owner,prompt,remember);return;}
            List<forge.game.card.CardView> views=new ArrayList<>();for(Card card:cards)views.add(card.getView());revealViews(views,prompt);
        }
        @Override public void reveal(List<forge.game.card.CardView> cards,ZoneType zone,forge.game.player.PlayerView owner,String prompt,boolean remember){
            if(getPlayer()!=local){super.reveal(cards,zone,owner,prompt,remember);return;}
            revealViews(cards,prompt);
        }
        @Override public String chooseProtectionType(SpellAbility source,List<String> options){
            if(getPlayer()!=local)return super.chooseProtectionType(source,options);
            for(String option:options)if(!Set.of("white","blue","black","red","green").contains(option.toLowerCase(Locale.ROOT)))throw new UnsupportedOperationException("Non-color protection selection needs an explicit native binding: "+option);
            return selectChoice("colors","Choose a protection color",options,1,1,false,color->{JsonObject value=new JsonObject();value.addProperty("color",color.toLowerCase(Locale.ROOT));value.addProperty("label",color);return value;},choiceSource(source)).get(0);
        }
        private List<forge.card.MagicColor.Color> colorChoice(String prompt,forge.card.ColorSet colors,int minimum,int maximum,boolean colorless,JsonObject context){
            List<forge.card.MagicColor.Color> options=new ArrayList<>(colors.getOrderedColors());
            if(colorless)options.add(forge.card.MagicColor.Color.COLORLESS);
            return selectChoice("colors",prompt,options,minimum,maximum,false,color->{JsonObject value=new JsonObject();value.addProperty("color",color.getName());value.addProperty("label",color.getName());return value;},context);
        }
        @Override public byte chooseColor(String prompt,SpellAbility source,forge.card.ColorSet colors){
            if(getPlayer()!=local)return super.chooseColor(prompt,source,colors);
            if(colors.countColors()<2){researchCallbackAudit.add("forced-color:"+colors.getColor());return colors.getColor();}
            return colorChoice(prompt,colors,1,1,false,choiceSource(source)).get(0).getColorMask();
        }
        @Override public byte chooseColorAllowColorless(String prompt,Card source,forge.card.ColorSet colors){
            if(getPlayer()!=local)return super.chooseColorAllowColorless(prompt,source,colors);
            if(colors.isColorless()){researchCallbackAudit.add("forced-colorless");return 0;}
            JsonObject context=new JsonObject();if(source!=null)context.addProperty("sourceForgeId",source.getId());
            return colorChoice(prompt,colors,1,1,true,context).get(0).getColorMask();
        }
        @Override public forge.card.ColorSet chooseColors(String prompt,SpellAbility source,int minimum,int maximum,forge.card.ColorSet colors){
            if(getPlayer()!=local)return super.chooseColors(prompt,source,minimum,maximum,colors);
            return forge.card.ColorSet.fromEnums(colorChoice(prompt,colors,minimum,maximum,false,choiceSource(source)));
        }
        HeadlessChoiceController(Game g,Player p,LobbyPlayer l){super(g,p,l);}
        @Override public CardCollectionView orderMoveToZoneList(CardCollectionView cards,ZoneType destination,SpellAbility cause){
            if(getPlayer()!=local || destination==ZoneType.Graveyard && cards.stream().noneMatch(c->c.isInZone(ZoneType.Library)))return super.orderMoveToZoneList(cards,destination,cause);
            if(destination!=ZoneType.Library && destination!=ZoneType.Graveyard && destination!=ZoneType.Exile){unsupportedDecision="Unmapped shared ordering destination "+destination;throw new UnsupportedOperationException(unsupportedDecision);}
            if(cards.size()<2)return new CardCollection(cards);
            JsonObject context=choiceSource(cause);context.addProperty("destination",destination.name());context.addProperty("orderSemantics","Forge effect movement order; no implicit reversal");
            List<Card> offered=new ArrayList<>();for(Card card:cards)offered.add(card);
            return new CardCollection(selectChoice("order","Order cards for "+destination.name(),offered,offered.size(),offered.size(),false,c->entityDescription(c,true),context));
        }
        private JsonObject entityDescription(GameEntity entity,boolean visible){
            JsonObject value=new JsonObject();value.addProperty("privateToSeat",1);
            if(entity instanceof Card card){value.addProperty("forgeId",card.getId());value.addProperty("entityKind","card");value.addProperty("label",visible?card.getName():"Hidden card");value.addProperty("identityVisible",visible);}
            else if(entity instanceof Player player){value.addProperty("entityKind","player");value.addProperty("targetSeat",seat(player));value.addProperty("label",player==local?"You":player.getName());}
            else throw new UnsupportedOperationException("Unmapped shared entity class "+entity.getClass().getName());
            return value;
        }
        private <T extends GameEntity> List<T> entityChoice(String type,String prompt,Iterable<T> offered,int minimum,int maximum,SpellAbility source,DelayedReveal reveal){
            List<T> options=new ArrayList<>();for(T entity:offered)options.add(entity);
            JsonObject context=choiceSource(source);JsonArray revealed=new JsonArray();
            // Human Forge temporarily exposes exactly these supplied views to
            // the chooser. They are not added to the public game snapshot.
            if(reveal!=null)for(var card:reveal.getCards()){JsonObject value=new JsonObject();value.addProperty("forgeId",card.getId());value.addProperty("label",card.getName());value.addProperty("privateToSeat",1);revealed.add(value);}
            context.add("revealed",revealed);
            return selectChoice(type,prompt,options,Math.min(minimum,options.size()),Math.min(maximum,options.size()),false,e->entityDescription(e,true),context);
        }
        @Override public <T extends GameEntity> T chooseSingleEntityForEffect(forge.util.collect.FCollectionView<T> entities,DelayedReveal reveal,SpellAbility source,String prompt,boolean optional,Player related,Map<String,Object> params){
            if(getPlayer()!=local || (source!=null && source.getApi()==forge.game.ability.ApiType.InternalLegendaryRule))return super.chooseSingleEntityForEffect(entities,reveal,source,prompt,optional,related,params);
            List<T> chosen=entityChoice("entities",prompt,entities,optional?0:1,1,source,reveal);return chosen.isEmpty()?null:chosen.get(0);
        }
        @Override public <T extends GameEntity> List<T> chooseEntitiesForEffect(forge.util.collect.FCollectionView<T> entities,int minimum,int maximum,DelayedReveal reveal,SpellAbility source,String prompt,Player related,Map<String,Object> params){
            if(getPlayer()!=local)return super.chooseEntitiesForEffect(entities,minimum,maximum,reveal,source,prompt,related,params);
            return entityChoice("entities",prompt,entities,minimum,maximum,source,reveal);
        }
        @Override public Card chooseSingleCardForZoneChange(ZoneType destination,List<ZoneType> origins,SpellAbility source,CardCollection cards,DelayedReveal reveal,String prompt,boolean optional,Player related){
            if(getPlayer()!=local)return super.chooseSingleCardForZoneChange(destination,origins,source,cards,reveal,prompt,optional,related);
            List<Card> chosen=entityChoice("cards-zone",prompt,cards,optional?0:1,1,source,reveal);return chosen.isEmpty()?null:chosen.get(0);
        }
        @Override public List<Card> chooseCardsForZoneChange(ZoneType destination,List<ZoneType> origins,SpellAbility source,CardCollection cards,int minimum,int maximum,DelayedReveal reveal,String prompt,Player related){
            if(getPlayer()!=local)return super.chooseCardsForZoneChange(destination,origins,source,cards,minimum,maximum,reveal,prompt,related);
            return entityChoice("cards-zone",prompt,cards,minimum,maximum,source,reveal);
        }
        @Override public CardCollectionView chooseCardsForEffect(CardCollectionView cards,SpellAbility source,String prompt,int minimum,int maximum,boolean optional,Map<String,Object> params){
            if(getPlayer()!=local)return super.chooseCardsForEffect(cards,source,prompt,minimum,maximum,optional,params);
            return new CardCollection(entityChoice("cards-effect",prompt,cards,optional?0:minimum,maximum,source,null));
        }
        @Override public CardCollectionView choosePermanentsToSacrifice(SpellAbility source,int minimum,int maximum,CardCollectionView cards,String prompt){
            if(getPlayer()!=local)return super.choosePermanentsToSacrifice(source,minimum,maximum,cards,prompt);
            return new CardCollection(entityChoice("sacrifice",prompt,cards,minimum,maximum,source,null));
        }
        @Override public CardCollection chooseCardsToDiscardFrom(Player player,SpellAbility source,CardCollection cards,int minimum,int maximum,CardCollectionView visible){
            if(getPlayer()!=local)return super.chooseCardsToDiscardFrom(player,source,cards,minimum,maximum,visible);
            List<Card> offered=new ArrayList<>();for(Card card:cards)offered.add(card);
            JsonObject context=choiceSource(source);JsonArray revealed=new JsonArray();
            if(visible!=null)for(Card card:visible){JsonObject value=new JsonObject();value.addProperty("forgeId",card.getId());value.addProperty("label",card.getName());value.addProperty("privateToSeat",1);revealed.add(value);}
            context.add("revealed",revealed);
            return new CardCollection(selectChoice("discard-effect","Choose cards to discard",offered,Math.min(minimum,offered.size()),Math.min(maximum,offered.size()),false,c->entityDescription(c,player==local || visible!=null && visible.contains(c)),context));
        }
        @Override public CardCollectionView chooseCardsToDiscardFrom(Player player,SpellAbility source,CardCollection cards,int minimum,int maximum){
            if(getPlayer()!=local)return super.chooseCardsToDiscardFrom(player,source,cards,minimum,maximum);
            return chooseCardsToDiscardFrom(player,source,cards,minimum,maximum,CardCollection.EMPTY);
        }
        @Override public org.apache.commons.lang3.tuple.ImmutablePair<CardCollection,CardCollection> arrangeForScry(CardCollection cards){if(getPlayer()!=local)return super.arrangeForScry(cards);return partitionChoice(cards,"bottom");}
        @Override public org.apache.commons.lang3.tuple.ImmutablePair<CardCollection,CardCollection> arrangeForSurveil(CardCollection cards){if(getPlayer()!=local)return super.arrangeForSurveil(cards);return partitionChoice(cards,"graveyard");}
        @Override public List<forge.game.spellability.AbilitySub> chooseModeForAbility(SpellAbility source,List<forge.game.spellability.AbilitySub> modes,int minimum,int maximum,boolean repeats){
            if(getPlayer()!=local)return super.chooseModeForAbility(source,modes,minimum,maximum,repeats);
            JsonObject context=new JsonObject();context.addProperty("sourceForgeId",source.getHostCard().getId());
            JsonObject binding=MODAL_BINDINGS.get(source.getHostCard().getName());Map<String,Integer> nativeModes=new HashMap<>();
            if(binding!=null){context.add("nativeParentAbilityId",binding.get("parentAbilityId"));for(JsonElement mode:binding.getAsJsonArray("choices")){JsonObject value=mode.getAsJsonObject();nativeModes.put(value.get("forgeDescription").getAsString(),value.get("nativeAbilityId").getAsInt());}}
            return selectChoice("modes","Choose modes for "+source.getHostCard().getName(),modes,minimum,maximum,repeats,mode->{
                JsonObject value=new JsonObject();String label=mode.toString();value.addProperty("label",label);
                String key=java.text.Normalizer.normalize(label,java.text.Normalizer.Form.NFKC).replaceAll("\\s+"," ").trim();
                if(nativeModes.containsKey(key))value.addProperty("nativeAbilityId",nativeModes.get(key));return value;
            },context);
        }
        @Override public int chooseNumber(SpellAbility source,String prompt,int minimum,int maximum){if(getPlayer()!=local)return super.chooseNumber(source,prompt,minimum,maximum);return numberChoice(source,prompt,minimum,maximum);}
        @Override public CounterType chooseCounterType(List<CounterType> types,SpellAbility source,String prompt,Map<String,Object> params){
            if(getPlayer()!=local)return super.chooseCounterType(types,source,prompt,params);
            if(types.size()==1){researchCallbackAudit.add("forced-counter-type:"+counterKey(types.get(0)));return types.get(0);}
            return selectChoice("counter-type",prompt,types,1,1,false,type->{JsonObject value=new JsonObject();value.addProperty("counterType",counterKey(type));value.addProperty("label",type.getName());return value;},choiceSource(source)).get(0);
        }
        @Override public int chooseNumber(SpellAbility source,String prompt,int minimum,int maximum,Map<String,Object> params){if(getPlayer()!=local)return super.chooseNumber(source,prompt,minimum,maximum,params);return numberChoice(source,prompt,minimum,maximum);}
        @Override public int chooseNumber(SpellAbility source,String prompt,List<Integer> offered,Player related){
            if(getPlayer()!=local)return super.chooseNumber(source,prompt,offered,related);
            return selectChoice("number-options",prompt,offered,1,1,false,n->{JsonObject value=new JsonObject();value.addProperty("number",n);value.addProperty("label",n.toString());return value;}).get(0);
        }
        @Override public boolean chooseBinary(SpellAbility source,String prompt,PlayerController.BinaryChoiceType type,Boolean defaultChoice){if(getPlayer()!=local)return super.chooseBinary(source,prompt,type,defaultChoice);return booleanChoice(source,prompt,type.name());}
        @Override public boolean chooseBinary(SpellAbility source,String prompt,PlayerController.BinaryChoiceType type,Map<String,Object> params){if(getPlayer()!=local)return super.chooseBinary(source,prompt,type,params);return booleanChoice(source,prompt,type.name());}
        @Override public boolean confirmAction(SpellAbility sa,PlayerActionConfirmMode mode,String message,List<String> options,Card host,Map<String,Object> params){
            if(getPlayer()!=local || (commanderGame() && mode==PlayerActionConfirmMode.ChangeZoneToAltDestination && (sa==null?host:sa.getHostCard())!=null && (sa==null?host:sa.getHostCard()).isRealCommander()))return super.confirmAction(sa,mode,message,options,host,params);
            return booleanChoice(sa,message,mode==null?"effect-confirmation":mode.name());
        }
    }
    static class ResearchStrictController extends HeadlessChoiceController {
        ResearchStrictController(forge.game.Game g,forge.game.player.Player p,forge.LobbyPlayer l){super(g,p,l);}
        @Override public boolean applyManaToCost(forge.game.mana.ManaCostBeingPaid a0,forge.game.spellability.SpellAbility a1,java.lang.String a2,forge.game.mana.ManaConversionMatrix a3,boolean a4) {
            if(getPlayer()!=local){return super.applyManaToCost(a0,a1,a2,a3,a4);}
            if(fullHumanChoices)return payHumanMana(a0,a1,a4,a3);
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.applyManaToCost(forge.game.mana.ManaCostBeingPaid,forge.game.spellability.SpellAbility,java.lang.String,forge.game.mana.ManaConversionMatrix,boolean)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean chooseCardsPile(forge.game.spellability.SpellAbility a0,forge.game.card.CardCollectionView a1,forge.game.card.CardCollectionView a2,java.lang.String a3) {
            if(getPlayer()!=local){return super.chooseCardsPile(a0,a1,a2,a3);}
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.chooseCardsPile(forge.game.spellability.SpellAbility,forge.game.card.CardCollectionView,forge.game.card.CardCollectionView,java.lang.String)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean chooseFlipResult(forge.game.spellability.SpellAbility a0,forge.game.player.Player a1,boolean a2) {
            if(getPlayer()!=local){return super.chooseFlipResult(a0,a1,a2);}
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.chooseFlipResult(forge.game.spellability.SpellAbility,forge.game.player.Player,boolean)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean chooseTargetsFor(forge.game.spellability.SpellAbility a0) {
            if(getPlayer()!=local){return super.chooseTargetsFor(a0);}
            // Forge setupTargets visits each targeting subability separately.
            // Do not announce/pay again or let the AI choose a human target.
            return selectHumanTargetsForPart(a0);
        }
        @Override public boolean confirmBidAction(forge.game.spellability.SpellAbility a0,forge.game.player.PlayerActionConfirmMode a1,java.lang.String a2,int a3,forge.game.player.Player a4) {
            if(getPlayer()!=local){return super.confirmBidAction(a0,a1,a2,a3,a4);}
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.confirmBidAction(forge.game.spellability.SpellAbility,forge.game.player.PlayerActionConfirmMode,java.lang.String,int,forge.game.player.Player)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean confirmPayment(forge.game.cost.CostPart a0,java.lang.String a1,forge.game.spellability.SpellAbility a2) {
            if(getPlayer()!=local){return super.confirmPayment(a0,a1,a2);}
            if(fullHumanChoices)return booleanChoice(a2,a1,"cost-confirmation");
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.confirmPayment(forge.game.cost.CostPart,java.lang.String,forge.game.spellability.SpellAbility)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean confirmStaticApplication(forge.game.card.Card a0,forge.game.player.PlayerActionConfirmMode a1,java.lang.String a2,java.lang.String a3) {
            if(getPlayer()!=local){return super.confirmStaticApplication(a0,a1,a2,a3);}
            if(fullHumanChoices)return booleanChoice(null,a3==null?a2:a3,"static-application");
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.confirmStaticApplication(forge.game.card.Card,forge.game.player.PlayerActionConfirmMode,java.lang.String,java.lang.String)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean confirmTrigger(forge.game.trigger.WrappedAbility a0) {
            if(getPlayer()!=local){return super.confirmTrigger(a0);}
            if(fullHumanChoices)return booleanChoice(a0,"Use "+a0.getHostCard().getName()+": "+a0.toString(),"optional-trigger");
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.confirmTrigger(forge.game.trigger.WrappedAbility)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean payCombatCost(forge.game.card.Card a0,forge.game.cost.Cost a1,forge.game.spellability.SpellAbility a2,java.lang.String a3) {
            if(getPlayer()!=local){return super.payCombatCost(a0,a1,a2,a3);}
            if(fullHumanChoices)return forge.game.player.PlaySpellAbility.payCostDuringAbilityResolve(this,local,a1,a2,a3);
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.payCombatCost(forge.game.card.Card,forge.game.cost.Cost,forge.game.spellability.SpellAbility,java.lang.String)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean payCostDuringRoll(forge.game.cost.Cost a0,forge.game.spellability.SpellAbility a1) {
            if(getPlayer()!=local){return super.payCostDuringRoll(a0,a1);}
            if(fullHumanChoices)return forge.game.player.PlaySpellAbility.payCostDuringAbilityResolve(this,local,a0,a1,null);
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.payCostDuringRoll(forge.game.cost.Cost,forge.game.spellability.SpellAbility)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean payCostToPreventEffect(forge.game.cost.Cost a0,forge.game.spellability.SpellAbility a1,boolean a2,forge.util.collect.FCollectionView<forge.game.player.Player> a3) {
            if(getPlayer()!=local){return super.payCostToPreventEffect(a0,a1,a2,a3);}
            if(fullHumanChoices){
                // Normal spell mana costs auto-pay; an "unless" cost is a
                // separate optional decision and must first obtain consent.
                // Mana-only prevention costs otherwise auto-confirm during
                // auto-tap. Life and selected costs have their own human prompt.
                if(a0.isOnlyManaCost() && !booleanChoice(a1,"Pay "+a0+" for "+a1.getHostCard().getName()+"?","unless-payment"))return false;
                return forge.game.player.PlaySpellAbility.payCostDuringAbilityResolve(this,local,a0,a1,null);
            }
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.payCostToPreventEffect(forge.game.cost.Cost,forge.game.spellability.SpellAbility,boolean,forge.util.collect.FCollectionView<forge.game.player.Player>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean playSaFromPlayEffect(forge.game.spellability.SpellAbility a0) {
            if(getPlayer()!=local){return super.playSaFromPlayEffect(a0);}
            if(fullHumanChoices)return forge.game.player.PlaySpellAbility.playSpellAbility(this,local,a0);
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.playSaFromPlayEffect(forge.game.spellability.SpellAbility)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public boolean willPutCardOnTop(forge.game.card.Card a0) {
            if(getPlayer()!=local){return super.willPutCardOnTop(a0);}
            unsupportedDecision="Unmapped human callback: public boolean forge.ai.PlayerControllerAi.willPutCardOnTop(forge.game.card.Card)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.card.ICardFace chooseSingleCardFace(forge.game.spellability.SpellAbility a0,java.lang.String a1,java.util.function.Predicate<forge.card.ICardFace> a2,java.lang.String a3) {
            if(getPlayer()!=local){return super.chooseSingleCardFace(a0,a1,a2,a3);}
            unsupportedDecision="Unmapped human callback: public forge.card.ICardFace forge.ai.PlayerControllerAi.chooseSingleCardFace(forge.game.spellability.SpellAbility,java.lang.String,java.util.function.Predicate<forge.card.ICardFace>,java.lang.String)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.card.ICardFace chooseSingleCardFace(forge.game.spellability.SpellAbility a0,java.util.List<forge.card.ICardFace> a1,java.lang.String a2) {
            if(getPlayer()!=local){return super.chooseSingleCardFace(a0,a1,a2);}
            unsupportedDecision="Unmapped human callback: public forge.card.ICardFace forge.ai.PlayerControllerAi.chooseSingleCardFace(forge.game.spellability.SpellAbility,java.util.List<forge.card.ICardFace>,java.lang.String)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.PlanarDice choosePDRollToIgnore(java.util.List<forge.game.PlanarDice> a0) {
            if(getPlayer()!=local){return super.choosePDRollToIgnore(a0);}
            unsupportedDecision="Unmapped human callback: public forge.game.PlanarDice forge.ai.PlayerControllerAi.choosePDRollToIgnore(java.util.List<forge.game.PlanarDice>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.ability.effects.RollDiceEffect.DieRollResult chooseRollToSwap(java.util.List<forge.game.ability.effects.RollDiceEffect.DieRollResult> a0) {
            if(getPlayer()!=local){return super.chooseRollToSwap(a0);}
            unsupportedDecision="Unmapped human callback: public forge.game.ability.effects.RollDiceEffect$DieRollResult forge.ai.PlayerControllerAi.chooseRollToSwap(java.util.List<forge.game.ability.effects.RollDiceEffect$DieRollResult>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.card.CardCollection chooseCardsForEffectMultiple(java.util.Map<java.lang.String, forge.game.card.CardCollection> a0,forge.game.spellability.SpellAbility a1,java.lang.String a2,boolean a3) {
            if(getPlayer()!=local){return super.chooseCardsForEffectMultiple(a0,a1,a2,a3);}
            unsupportedDecision="Unmapped human callback: public forge.game.card.CardCollection forge.ai.PlayerControllerAi.chooseCardsForEffectMultiple(java.util.Map<java.lang.String, forge.game.card.CardCollection>,forge.game.spellability.SpellAbility,java.lang.String,boolean)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.card.CardCollection orderAttackers(forge.game.card.Card a0,forge.game.card.CardCollection a1) {
            if(getPlayer()!=local){return super.orderAttackers(a0,a1);}
            unsupportedDecision="Unmapped human callback: public forge.game.card.CardCollection forge.ai.PlayerControllerAi.orderAttackers(forge.game.card.Card,forge.game.card.CardCollection)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.card.CardCollection orderBlocker(forge.game.card.Card a0,forge.game.card.Card a1,forge.game.card.CardCollection a2) {
            if(getPlayer()!=local){return super.orderBlocker(a0,a1,a2);}
            unsupportedDecision="Unmapped human callback: public forge.game.card.CardCollection forge.ai.PlayerControllerAi.orderBlocker(forge.game.card.Card,forge.game.card.Card,forge.game.card.CardCollection)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.card.CardCollection orderBlockers(forge.game.card.Card a0,forge.game.card.CardCollection a1) {
            if(getPlayer()!=local){return super.orderBlockers(a0,a1);}
            unsupportedDecision="Unmapped human callback: public forge.game.card.CardCollection forge.ai.PlayerControllerAi.orderBlockers(forge.game.card.Card,forge.game.card.CardCollection)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.card.CardCollectionView chooseCardsForCost(forge.game.card.CardCollectionView a0,forge.game.spellability.SpellAbility a1,forge.game.cost.CostPartWithList a2,int a3,boolean a4,java.lang.String a5) {
            if(getPlayer()!=local){return super.chooseCardsForCost(a0,a1,a2,a3,a4,a5);}
            unsupportedDecision="Unmapped human callback: public forge.game.card.CardCollectionView forge.ai.PlayerControllerAi.chooseCardsForCost(forge.game.card.CardCollectionView,forge.game.spellability.SpellAbility,forge.game.cost.CostPartWithList,int,boolean,java.lang.String)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.card.CardCollectionView chooseCardsToDelve(int a0,forge.game.card.CardCollection a1) {
            if(getPlayer()!=local){return super.chooseCardsToDelve(a0,a1);}
            unsupportedDecision="Unmapped human callback: public forge.game.card.CardCollectionView forge.ai.PlayerControllerAi.chooseCardsToDelve(int,forge.game.card.CardCollection)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.card.CardCollectionView chooseCardsToDiscardUnlessType(int a0,forge.game.card.CardCollectionView a1,java.lang.String[] a2,forge.game.spellability.SpellAbility a3) {
            if(getPlayer()!=local){return super.chooseCardsToDiscardUnlessType(a0,a1,a2,a3);}
            unsupportedDecision="Unmapped human callback: public forge.game.card.CardCollectionView forge.ai.PlayerControllerAi.chooseCardsToDiscardUnlessType(int,forge.game.card.CardCollectionView,java.lang.String[],forge.game.spellability.SpellAbility)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.card.CardCollectionView chooseCardsToRevealFromHand(int a0,int a1,forge.game.card.CardCollectionView a2) {
            if(getPlayer()!=local){return super.chooseCardsToRevealFromHand(a0,a1,a2);}
            unsupportedDecision="Unmapped human callback: public forge.game.card.CardCollectionView forge.ai.PlayerControllerAi.chooseCardsToRevealFromHand(int,int,forge.game.card.CardCollectionView)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.card.CardCollectionView choosePermanentsToDestroy(forge.game.spellability.SpellAbility a0,int a1,int a2,forge.game.card.CardCollectionView a3,java.lang.String a4) {
            if(getPlayer()!=local){return super.choosePermanentsToDestroy(a0,a1,a2,a3,a4);}
            unsupportedDecision="Unmapped human callback: public forge.game.card.CardCollectionView forge.ai.PlayerControllerAi.choosePermanentsToDestroy(forge.game.spellability.SpellAbility,int,int,forge.game.card.CardCollectionView,java.lang.String)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.card.CardState chooseSingleCardState(forge.game.spellability.SpellAbility a0,java.util.List<forge.game.card.CardState> a1,java.lang.String a2,java.util.Map<java.lang.String, java.lang.Object> a3) {
            if(getPlayer()!=local){return super.chooseSingleCardState(a0,a1,a2,a3);}
            unsupportedDecision="Unmapped human callback: public forge.game.card.CardState forge.ai.PlayerControllerAi.chooseSingleCardState(forge.game.spellability.SpellAbility,java.util.List<forge.game.card.CardState>,java.lang.String,java.util.Map<java.lang.String, java.lang.Object>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.mana.Mana chooseManaFromPool(java.util.List<forge.game.mana.Mana> a0) {
            if(getPlayer()!=local){return super.chooseManaFromPool(a0);}
            if(fullHumanChoices){
                if(a0.isEmpty())return null;
                // Match PlayerControllerHuman's default; the chooser is only
                // requested under its explicit ChooseManaPoolShard control.
                if(actionProbeDepth>0 || !isFullControl(PlayerController.FullControlFlag.ChooseManaPoolShard))return a0.get(0);
                List<forge.game.mana.Mana> offered=new ArrayList<>();var counts=new IdentityHashMap<forge.game.mana.Mana,Integer>();
                for(var mana:a0){if(!counts.containsKey(mana))offered.add(mana);counts.merge(mana,1,Integer::sum);}
                if(offered.isEmpty())return null;if(offered.size()==1)return offered.get(0);
                return optionChoice("Choose mana to spend",offered,1,1,m->{String color=switch(m.getColor()){case 0,32->"Colorless";case 1->"White";case 2->"Blue";case 4->"Black";case 8->"Red";case 16->"Green";default->throw new UnsupportedOperationException("Unmapped mana color");};return color+" mana from "+m.getSourceCard().getName()+(m.isRestricted()?" (restricted)":"")+(m.isSnow()?" (snow)":"")+" — "+counts.get(m)+" available";},null).get(0);
            }
            unsupportedDecision="Unmapped human callback: public forge.game.mana.Mana forge.ai.PlayerControllerAi.chooseManaFromPool(java.util.List<forge.game.mana.Mana>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.player.Player choosePlayerToAssistPayment(forge.util.collect.FCollectionView<forge.game.player.Player> a0,forge.game.spellability.SpellAbility a1,java.lang.String a2,int a3) {
            if(getPlayer()!=local){return super.choosePlayerToAssistPayment(a0,a1,a2,a3);}
            unsupportedDecision="Unmapped human callback: public forge.game.player.Player forge.ai.PlayerControllerAi.choosePlayerToAssistPayment(forge.util.collect.FCollectionView<forge.game.player.Player>,forge.game.spellability.SpellAbility,java.lang.String,int)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.replacement.ReplacementEffect chooseSingleReplacementEffect(java.util.List<forge.game.replacement.ReplacementEffect> a0) {
            if(getPlayer()!=local){return super.chooseSingleReplacementEffect(a0);}
            if(fullHumanChoices){
                if(a0.size()==1)return a0.get(0);
                return sourceOrderChoice("Choose which replacement applies next",a0,e->e.getHostCard(),Object::toString).get(0);
            }
            // Original Human controller returns the sole offered effect before
            // considering remembered order or opening its replacement picker.
            // Competing effects are still an explicit unsupported human choice.
            if(a0.size()==1){String audit="forced-single-replacement:"+a0.get(0).getHostCard().getId();if(!researchCallbackAudit.contains(audit))researchCallbackAudit.add(audit);return a0.get(0);}
            unsupportedDecision="Unmapped human callback: public forge.game.replacement.ReplacementEffect forge.ai.PlayerControllerAi.chooseSingleReplacementEffect(java.util.List<forge.game.replacement.ReplacementEffect>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.spellability.SpellAbility chooseSingleSpellForEffect(java.util.List<forge.game.spellability.SpellAbility> a0,forge.game.spellability.SpellAbility a1,java.lang.String a2,java.util.Map<java.lang.String, java.lang.Object> a3) {
            if(getPlayer()!=local){return super.chooseSingleSpellForEffect(a0,a1,a2,a3);}
            if(fullHumanChoices){if(a0.isEmpty())return null;if(a0.size()==1)return a0.get(0);return optionChoice(a2,a0,1,1,SpellAbility::toString,a1).get(0);}
            unsupportedDecision="Unmapped human callback: public forge.game.spellability.SpellAbility forge.ai.PlayerControllerAi.chooseSingleSpellForEffect(java.util.List<forge.game.spellability.SpellAbility>,forge.game.spellability.SpellAbility,java.lang.String,java.util.Map<java.lang.String, java.lang.Object>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.spellability.TargetChoices chooseNewTargetsFor(forge.game.spellability.SpellAbility a0,java.util.function.Predicate<forge.game.GameObject> a1,boolean a2) {
            if(getPlayer()!=local){return super.chooseNewTargetsFor(a0,a1,a2);}
            if(fullHumanChoices){
                SpellAbility ability=a0 instanceof forge.game.trigger.WrappedAbility wrapper?wrapper.getWrappedAbility():a0;
                if(!ability.usesTargeting())return null;
                if(ability.isDividedAsYouChoose())throw new UnsupportedOperationException("Retargeting a divided allocation needs its original allocation interface");
                if(a2 && !booleanChoice(a0,"Choose new targets for "+ability.getHostCard().getName()+"?","retarget-copy"))return null;
                var previous=ability.getTargets().clone();ability.resetTargets();
                if(selectHumanTargetsForPart(ability,a1,previous.size()))return ability.getTargets();
                ability.setTargets(previous);return null;
            }
            unsupportedDecision="Unmapped human callback: public forge.game.spellability.TargetChoices forge.ai.PlayerControllerAi.chooseNewTargetsFor(forge.game.spellability.SpellAbility,java.util.function.Predicate<forge.game.GameObject>,boolean)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public forge.game.zone.PlayerZone chooseStartingHand(java.util.List<forge.game.zone.PlayerZone> a0) {
            if(getPlayer()!=local){return super.chooseStartingHand(a0);}
            unsupportedDecision="Unmapped human callback: public forge.game.zone.PlayerZone forge.ai.PlayerControllerAi.chooseStartingHand(java.util.List<forge.game.zone.PlayerZone>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public int chooseNumberForCostReduction(forge.game.spellability.SpellAbility a0,int a1,int a2) {
            if(getPlayer()!=local){return super.chooseNumberForCostReduction(a0,a1,a2);}
            unsupportedDecision="Unmapped human callback: public int forge.ai.PlayerControllerAi.chooseNumberForCostReduction(forge.game.spellability.SpellAbility,int,int)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public int chooseNumberForKeywordCost(forge.game.spellability.SpellAbility a0,forge.game.cost.Cost a1,forge.game.keyword.KeywordInterface a2,java.lang.String a3,int a4) {
            if(getPlayer()!=local){return super.chooseNumberForKeywordCost(a0,a1,a2,a3,a4);}
            unsupportedDecision="Unmapped human callback: public int forge.ai.PlayerControllerAi.chooseNumberForKeywordCost(forge.game.spellability.SpellAbility,forge.game.cost.Cost,forge.game.keyword.KeywordInterface,java.lang.String,int)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public int chooseSprocket(forge.game.card.Card a0,java.util.List<java.lang.Integer> a1) {
            if(getPlayer()!=local){return super.chooseSprocket(a0,a1);}
            unsupportedDecision="Unmapped human callback: public int forge.ai.PlayerControllerAi.chooseSprocket(forge.game.card.Card,java.util.List<java.lang.Integer>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.lang.Integer announceRequirements(forge.game.spellability.SpellAbility a0,int a1,int a2,java.lang.String a3) {
            if(getPlayer()!=local){return super.announceRequirements(a0,a1,a2,a3);}
            if(fullHumanChoices){
                if("X".equals(a3) && a0.getPayCosts()!=null){Integer max=a0.getPayCosts().getMaxForNonManaX(a0,getPlayer(),false);if(max!=null)a2=Math.min(a2,max);}
                return a1>a2?null:numberChoice(a0,"Choose "+a3+" for "+a0.getHostCard().getName(),a1,a2);
            }
            unsupportedDecision="Unmapped human callback: public java.lang.Integer forge.ai.PlayerControllerAi.announceRequirements(forge.game.spellability.SpellAbility,int,int,java.lang.String)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.lang.Integer chooseRollToIgnore(java.util.List<java.lang.Integer> a0) {
            if(getPlayer()!=local){return super.chooseRollToIgnore(a0);}
            unsupportedDecision="Unmapped human callback: public java.lang.Integer forge.ai.PlayerControllerAi.chooseRollToIgnore(java.util.List<java.lang.Integer>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.lang.Integer chooseRollToModify(java.util.List<java.lang.Integer> a0) {
            if(getPlayer()!=local){return super.chooseRollToModify(a0);}
            unsupportedDecision="Unmapped human callback: public java.lang.Integer forge.ai.PlayerControllerAi.chooseRollToModify(java.util.List<java.lang.Integer>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.lang.Object vote(forge.game.spellability.SpellAbility a0,java.lang.String a1,java.util.List<java.lang.Object> a2,com.google.common.collect.ListMultimap<java.lang.Object, forge.game.player.Player> a3,forge.game.player.Player a4,boolean a5) {
            if(getPlayer()!=local){return super.vote(a0,a1,a2,a3,a4,a5);}
            unsupportedDecision="Unmapped human callback: public java.lang.Object forge.ai.PlayerControllerAi.vote(forge.game.spellability.SpellAbility,java.lang.String,java.util.List<java.lang.Object>,com.google.common.collect.ListMultimap<java.lang.Object, forge.game.player.Player>,forge.game.player.Player,boolean)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.lang.String chooseCardName(forge.game.spellability.SpellAbility a0,java.util.List<forge.card.ICardFace> a1,java.lang.String a2) {
            if(getPlayer()!=local){return super.chooseCardName(a0,a1,a2);}
            if(fullHumanChoices)return cardNameChoice(a0,a1,a2);
            unsupportedDecision="Unmapped human callback: public java.lang.String forge.ai.PlayerControllerAi.chooseCardName(forge.game.spellability.SpellAbility,java.util.List<forge.card.ICardFace>,java.lang.String)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.lang.String chooseCardName(forge.game.spellability.SpellAbility a0,java.util.function.Predicate<forge.card.ICardFace> a1,java.lang.String a2,java.lang.String a3) {
            if(getPlayer()!=local){return super.chooseCardName(a0,a1,a2,a3);}
            if(fullHumanChoices){
                if(CARD_NAME_FACES.isEmpty())for(var paper:FModel.getMagicDb().getCommonCards().getUniqueCards())for(var face:paper.getRules().getAllFaces())if(CARD_NAME_IDS.containsKey(face.getName()))CARD_NAME_FACES.putIfAbsent(face.getName(),face);
                List<forge.card.ICardFace> faces=new ArrayList<>();for(var face:CARD_NAME_FACES.values())if(a1.test(face))faces.add(face);
                return cardNameChoice(a0,faces,a3==null?a2:a3);
            }
            unsupportedDecision="Unmapped human callback: public java.lang.String forge.ai.PlayerControllerAi.chooseCardName(forge.game.spellability.SpellAbility,java.util.function.Predicate<forge.card.ICardFace>,java.lang.String,java.lang.String)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.lang.String chooseKeywordForPump(java.util.List<java.lang.String> a0,forge.game.spellability.SpellAbility a1,java.lang.String a2,forge.game.card.Card a3) {
            if(getPlayer()!=local){return super.chooseKeywordForPump(a0,a1,a2,a3);}
            unsupportedDecision="Unmapped human callback: public java.lang.String forge.ai.PlayerControllerAi.chooseKeywordForPump(java.util.List<java.lang.String>,forge.game.spellability.SpellAbility,java.lang.String,forge.game.card.Card)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.lang.String chooseRollSwapValue(java.util.List<java.lang.String> a0,java.lang.Integer a1,int a2,int a3) {
            if(getPlayer()!=local){return super.chooseRollSwapValue(a0,a1,a2,a3);}
            unsupportedDecision="Unmapped human callback: public java.lang.String forge.ai.PlayerControllerAi.chooseRollSwapValue(java.util.List<java.lang.String>,java.lang.Integer,int,int)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.lang.String chooseSector(forge.game.card.Card a0,java.lang.String a1,java.util.List<java.lang.String> a2) {
            if(getPlayer()!=local){return super.chooseSector(a0,a1,a2);}
            unsupportedDecision="Unmapped human callback: public java.lang.String forge.ai.PlayerControllerAi.chooseSector(forge.game.card.Card,java.lang.String,java.util.List<java.lang.String>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.lang.String chooseSomeType(java.lang.String a0,forge.game.spellability.SpellAbility a1,java.util.Collection<java.lang.String> a2,boolean a3) {
            if(getPlayer()!=local){return super.chooseSomeType(a0,a1,a2,a3);}
            if(fullHumanChoices){
                String kind=a0.equalsIgnoreCase("Creature")?"SubType":null;
                for(String possible:List.of("SubType","CardType","SuperType")){
                    if(kind!=null)break;
                    JsonObject ids=TYPE_ENUM_IDS.getAsJsonObject(possible);boolean matches=ids!=null;
                    for(String option:a2)if(ids==null || !ids.has(option.toLowerCase(Locale.ROOT)))matches=false;
                    if(matches){kind=possible;break;}
                }
                if(kind==null){JsonObject subtypes=TYPE_ENUM_IDS.getAsJsonObject("SubType");throw new UnsupportedOperationException("Offered type list has no complete original Arena enum binding: "+a0+"; unmapped subtypes="+a2.stream().filter(name->subtypes==null || !subtypes.has(name.toLowerCase(Locale.ROOT))).limit(12).toList());}
                JsonObject context=choiceSource(a1);context.addProperty("typeKind",kind);JsonObject ids=TYPE_ENUM_IDS.getAsJsonObject(kind);
                List<String> offered=new ArrayList<>(),unavailable=new ArrayList<>();for(String name:a2)(ids.has(name.toLowerCase(Locale.ROOT))?offered:unavailable).add(name);
                if(!unavailable.isEmpty()){context.add("typesAbsentFromInstalledArena",JSON.toJsonTree(unavailable));researchCallbackAudit.add("Arena type catalogue excludes: "+unavailable);}
                List<String> selected=selectChoice("type",a0,offered,a3?0:1,1,false,label->{JsonObject option=new JsonObject();option.addProperty("label",label);option.add("nativeTypeId",ids.get(label.toLowerCase(Locale.ROOT)));return option;},context);
                return selected.isEmpty()?null:selected.get(0);
            }
            unsupportedDecision="Unmapped human callback: public java.lang.String forge.ai.PlayerControllerAi.chooseSomeType(java.lang.String,forge.game.spellability.SpellAbility,java.util.Collection<java.lang.String>,boolean)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.List<forge.game.card.Card> chooseCardsForSplice(forge.game.spellability.SpellAbility a0,java.util.List<forge.game.card.Card> a1) {
            if(getPlayer()!=local){return super.chooseCardsForSplice(a0,a1);}
            unsupportedDecision="Unmapped human callback: public java.util.List<forge.game.card.Card> forge.ai.PlayerControllerAi.chooseCardsForSplice(forge.game.spellability.SpellAbility,java.util.List<forge.game.card.Card>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.List<forge.game.card.Card> chooseContraptionsToCrank(java.util.List<forge.game.card.Card> a0) {
            if(getPlayer()!=local){return super.chooseContraptionsToCrank(a0);}
            unsupportedDecision="Unmapped human callback: public java.util.List<forge.game.card.Card> forge.ai.PlayerControllerAi.chooseContraptionsToCrank(java.util.List<forge.game.card.Card>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.List<forge.game.card.Card> enlistAttackers(java.util.List<forge.game.card.Card> a0) {
            if(getPlayer()!=local){return super.enlistAttackers(a0);}
            unsupportedDecision="Unmapped human callback: public java.util.List<forge.game.card.Card> forge.ai.PlayerControllerAi.enlistAttackers(java.util.List<forge.game.card.Card>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.List<forge.game.card.Card> exertAttackers(java.util.List<forge.game.card.Card> a0) {
            if(getPlayer()!=local){return super.exertAttackers(a0);}
            unsupportedDecision="Unmapped human callback: public java.util.List<forge.game.card.Card> forge.ai.PlayerControllerAi.exertAttackers(java.util.List<forge.game.card.Card>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.List<forge.game.cost.CostPart> orderCosts(java.util.List<forge.game.cost.CostPart> a0) {
            if(getPlayer()!=local){return super.orderCosts(a0);}
            if(fullHumanChoices)return new ArrayList<>(a0);
            unsupportedDecision="Unmapped human callback: public java.util.List<forge.game.cost.CostPart> forge.ai.PlayerControllerAi.orderCosts(java.util.List<forge.game.cost.CostPart>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.List<forge.game.spellability.OptionalCostValue> chooseOptionalCosts(forge.game.spellability.SpellAbility a0,java.util.List<forge.game.spellability.OptionalCostValue> a1) {
            if(getPlayer()!=local){return super.chooseOptionalCosts(a0,a1);}
            if(fullHumanChoices)return optionChoice("Choose additional costs for "+a0.getHostCard().getName(),a1,0,a1.size(),Object::toString,a0);
            unsupportedDecision="Unmapped human callback: public java.util.List<forge.game.spellability.OptionalCostValue> forge.ai.PlayerControllerAi.chooseOptionalCosts(forge.game.spellability.SpellAbility,java.util.List<forge.game.spellability.OptionalCostValue>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.List<forge.game.spellability.SpellAbility> chooseSaToActivateFromOpeningHand(java.util.List<forge.game.spellability.SpellAbility> a0) {
            if(getPlayer()!=local){return super.chooseSaToActivateFromOpeningHand(a0);}
            if(fullHumanChoices){
                Map<Integer,SpellAbility> byCard=new LinkedHashMap<>();for(var ability:a0)byCard.putIfAbsent(ability.getHostCard().getId(),ability);
                List<SpellAbility> offered=new ArrayList<>(byCard.values());if(offered.isEmpty())return List.of();
                return optionChoice("Choose opening-hand abilities in activation order",offered,0,offered.size(),a->a.getHostCard().getName(),null);
            }
            unsupportedDecision="Unmapped human callback: public java.util.List<forge.game.spellability.SpellAbility> forge.ai.PlayerControllerAi.chooseSaToActivateFromOpeningHand(java.util.List<forge.game.spellability.SpellAbility>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.List<forge.game.spellability.SpellAbility> orderSimultaneousSa(java.util.List<forge.game.spellability.SpellAbility> a0) {
            if(getPlayer()!=local){return super.orderSimultaneousSa(a0);}
            unsupportedDecision="Unmapped human callback: public java.util.List<forge.game.spellability.SpellAbility> forge.ai.PlayerControllerAi.orderSimultaneousSa(java.util.List<forge.game.spellability.SpellAbility>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.List<forge.item.PaperCard> chooseCardsYouWonToAddToDeck(java.util.List<forge.item.PaperCard> a0) {
            if(getPlayer()!=local){return super.chooseCardsYouWonToAddToDeck(a0);}
            unsupportedDecision="Unmapped human callback: public java.util.List<forge.item.PaperCard> forge.ai.PlayerControllerAi.chooseCardsYouWonToAddToDeck(java.util.List<forge.item.PaperCard>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.List<java.lang.Integer> chooseDiceToReroll(java.util.List<java.lang.Integer> a0) {
            if(getPlayer()!=local){return super.chooseDiceToReroll(a0);}
            unsupportedDecision="Unmapped human callback: public java.util.List<java.lang.Integer> forge.ai.PlayerControllerAi.chooseDiceToReroll(java.util.List<java.lang.Integer>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.Map<forge.game.GameEntity, java.lang.Integer> divideShield(forge.game.card.Card a0,java.util.Map<forge.game.GameEntity, java.lang.Integer> a1,int a2) {
            if(getPlayer()!=local){return super.divideShield(a0,a1,a2);}
            unsupportedDecision="Unmapped human callback: public java.util.Map<forge.game.GameEntity, java.lang.Integer> forge.ai.PlayerControllerAi.divideShield(forge.game.card.Card,java.util.Map<forge.game.GameEntity, java.lang.Integer>,int)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.Map<forge.game.card.Card, forge.card.mana.ManaCostShard> chooseCardsForConvokeOrImprovise(forge.game.spellability.SpellAbility a0,forge.card.mana.ManaCost a1,forge.game.card.CardCollectionView a2,boolean a3,boolean a4,java.lang.Integer a5) {
            if(getPlayer()!=local){return super.chooseCardsForConvokeOrImprovise(a0,a1,a2,a3,a4,a5);}
            if(fullHumanChoices){
                if(actionProbeDepth>0)return super.chooseCardsForConvokeOrImprovise(a0,a1,a2,a3,a4,a5);
                List<Card> offered=new ArrayList<>();for(Card card:a2)offered.add(card);
                int max=a5==null?offered.size():Math.min(offered.size(),a5);
                var chosen=selectChoice("cards-effect","Choose permanents for convoke or improvise",offered,0,max,false,c->{JsonObject o=new JsonObject();o.addProperty("forgeId",c.getId());o.addProperty("entityKind","card");o.addProperty("label",c.getName());o.addProperty("privateToSeat",1);o.addProperty("identityVisible",true);return o;},choiceSource(a0));
                Map<Card,forge.card.mana.ManaCostShard> result=new LinkedHashMap<>();
                var remainder=new forge.game.mana.ManaCostBeingPaid(a1);
                for(Card card:chosen){
                    List<Integer> colors=new ArrayList<>();
                    for(int color:new int[]{0,1,2,4,8,16}){
                        if(color!=0 && (a3 || (card.getColor().getColor()&color)==0))continue;
                        var candidate=new forge.game.mana.ManaCostBeingPaid(remainder);if(candidate.payManaViaConvoke((byte)color)!=null)colors.add(color);
                    }
                    if(colors.isEmpty())throw new IllegalArgumentException("Selected convoke permanent cannot pay any remaining shard");
                    int color=colors.size()==1?colors.get(0):optionChoice("Choose the cost paid by "+card.getName(),colors,1,1,c->Map.of(0,"Generic",1,"White",2,"Blue",4,"Black",8,"Red",16,"Green").get(c),a0).get(0);
                    result.put(card,remainder.payManaViaConvoke((byte)color));
                }
                return result;
            }
            unsupportedDecision="Convoke, improvise or waterbend payment selection is not connected for "+a0.getHostCard().getName();throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public java.util.Map<java.lang.Byte, java.lang.Integer> specifyManaCombo(forge.game.spellability.SpellAbility a0,forge.card.ColorSet a1,int a2,boolean a3) {
            if(getPlayer()!=local){return super.specifyManaCombo(a0,a1,a2,a3);}
            if(fullHumanChoices){
                List<forge.card.MagicColor.Color> available=new ArrayList<>();for(var color:a1.getOrderedColors())if(color!=forge.card.MagicColor.Color.COLORLESS)available.add(color);
                if(a2<0 || a2>0 && available.isEmpty() || a3 && a2>available.size())throw new UnsupportedOperationException("Original mana distribution has unsatisfiable bounds");
                Map<Byte,Integer> result=new LinkedHashMap<>();int remaining=a2;
                while(remaining>0){
                    var color=available.size()==1?available.get(0):chooseColors("Choose a color of mana for "+a0.getHostCard().getName(),a0,1,1,forge.card.ColorSet.fromEnums(available)).iterator().next();
                    int count=a3?1:available.size()==1?remaining:numberChoice(a0,"How much "+color.name().toLowerCase()+" mana?",1,remaining);
                    result.put(color.getColorMask(),count);remaining-=count;available.remove(color);
                }
                return result;
            }
            unsupportedDecision="Unmapped human callback: public java.util.Map<java.lang.Byte, java.lang.Integer> forge.ai.PlayerControllerAi.specifyManaCombo(forge.game.spellability.SpellAbility,forge.card.ColorSet,int,boolean)";throw new UnsupportedOperationException(unsupportedDecision);
        }
        @Override public org.apache.commons.lang3.tuple.Pair<forge.game.spellability.SpellAbilityStackInstance, forge.game.GameObject> chooseTarget(forge.game.spellability.SpellAbility a0,java.util.List<org.apache.commons.lang3.tuple.Pair<forge.game.spellability.SpellAbilityStackInstance, forge.game.GameObject>> a1) {
            if(getPlayer()!=local){return super.chooseTarget(a0,a1);}
            unsupportedDecision="Unmapped human callback: public org.apache.commons.lang3.tuple.Pair<forge.game.spellability.SpellAbilityStackInstance, forge.game.GameObject> forge.ai.PlayerControllerAi.chooseTarget(forge.game.spellability.SpellAbility,java.util.List<org.apache.commons.lang3.tuple.Pair<forge.game.spellability.SpellAbilityStackInstance, forge.game.GameObject>>)";throw new UnsupportedOperationException(unsupportedDecision);
        }
    } // 84 inherited callbacks rejected for human research cases

    static class LocalSeat extends LobbyPlayerAi {
        final boolean humanSeat;
        LocalSeat(String name,boolean humanSeat){super(name,Collections.emptySet());this.humanSeat=humanSeat;setAiProfile("Default");}
        @Override public Player createIngamePlayer(Game g,int id){Player p=new Player(getName(),g,id);p.setFirstController(researchAdmission && humanSeat?new ResearchStrictController(g,p,this):new PassiveController(g,p,this));return p;}
    }
    static String presentationKey(Card c){
        if(fullHumanChoices && c.isEmblem() && c.getEffectSourceAbility()!=null){
            var creator=c.getEffectSourceAbility();
            // A borrowed ability still creates its original emblem. Nicol
            // Bolas gaining Chandra's +2 does not create a Nicol Bolas emblem.
            Card original=creator.getOriginalHost();
            return "emblem:"+(original==null?creator.getHostCard():original).getName();
        }
        if(fullHumanChoices && c.isImmutable() && !c.isEmblem()){
            Set<Integer> seen=new HashSet<>();
            while(c.isImmutable() && !c.isEmblem()){
                if(!seen.add(c.getId()) || seen.size()>16)throw new UnsupportedOperationException("Cyclic effect presentation source");
                Card parent=c.getEffectSource();if(parent==null && c.getEffectSourceAbility()!=null)parent=c.getEffectSourceAbility().getHostCard();
                if(parent==null)break;c=parent;
            }
        }
        if(fullHumanChoices){
            // A nontoken permanent can become a copy of a token. Conversely,
            // a token can copy a printed card: use the active copiable face.
            String image=c.getCurrentState().getImageKey();
            if((image==null || image.isEmpty()) && c.getPaperCard()!=null)image=c.getPaperCard().getImageKey(false);
            if(image==null)image="";
            if(image.startsWith("t:"))return "token:"+image.substring(2).split("\\|",2)[0]+(c.getCurrentStateName()==forge.card.CardStateName.Backside?":Backside":"");
        }
        return c.getName();
    }
    static Map<String,Object> card(Card c) {
        return card(c,null);
    }
    static Map<String,Object> card(Card c,String pendingZone) {
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("forgeId",c.getId());result.put("arenaId",1000+c.getId());result.put("name",c.getName());result.put("zone",pendingZone==null?c.getZone().getZoneType().name():pendingZone);
        result.put("owner",seat(c.getOwner()));result.put("controller",seat(c.getController()));result.put("tapped",c.isTapped());
        result.put("power",c.getNetPower());result.put("toughness",c.getNetToughness());result.put("sick",c.isSick());result.put("damage",c.getDamage());
        result.put("token",c.isToken());result.put("colorMask",(int)c.getColor().getColor());
        if(fullHumanChoices && c.isCopiedSpell())result.put("ephemeralCopy",true);
        if(fullHumanChoices && c.isEmblem())result.put("objectKind","emblem");
        if(!presentationKey(c).equals(c.getName()))result.put("presentationKey",presentationKey(c));
        if(fullHumanChoices){result.put("namedCards",c.getNamedCards());List<Integer> titles=new ArrayList<>();for(String name:c.getNamedCards()){Integer title=CARD_NAME_IDS.get(name);if(title==null)throw new UnsupportedOperationException("Named card has no original Arena title identity: "+name);titles.add(title);}result.put("namedCardTitleIds",titles);}
        if(fullHumanChoices){Set<Integer> abilities=new LinkedHashSet<>();for(SpellAbility a:c.getSpellAbilities())if(a.isActivatedAbility()){int id=nativeAbility(a,false);if(id!=0)abilities.add(id);}result.put("currentAbilityIds",abilities);}
        if(researchAdmission){result.put("currentTypes",c.getType().getCoreTypes().stream().map(Object::toString).toList());result.put("currentSupertypes",c.getType().getSupertypes().stream().map(Object::toString).toList());result.put("currentSubtypes",new ArrayList<>(c.getType().getSubtypes()));}
        result.put("counters",counters(c));result.put("loyalty",c.getCurrentLoyalty());result.put("defense",c.getCurrentDefense());
        if(c.isPlaneswalker())result.put("baseLoyalty",c.getBaseLoyalty());
        keywordPresentation(c,result);
        if(researchAdmission)result.put("rulesKeywords",c.getKeywords().stream().map(k->k.getOriginal()).toList());
        List<String> chosenColors=new ArrayList<>();if(c.hasChosenColor())for(String color:c.getChosenColors())chosenColors.add(color);result.put("chosenColors",chosenColors);
        GameEntity attachment=c.getEntityAttachedTo();
        // Forge may attach a resolving Aura before its as-enters choice, while
        // it still occupies the stack. That provisional relationship is not a
        // battlefield attachment in the native client's state model.
        String attachmentPrefix=c.isInZone(ZoneType.Battlefield)?"attachedTo":
            c.isInZone(ZoneType.Stack) && c.isAura() && game.getStack().isResolving()?"provisionalAttachmentTo":null;
        if(attachment!=null && attachmentPrefix==null)throw new UnsupportedOperationException("Attachment outside battlefield or resolving Aura");
        if(attachment instanceof Card target)result.put(attachmentPrefix+"ForgeId",target.getId());
        else if(attachment instanceof Player target)result.put(attachmentPrefix+"Seat",seat(target));
        else if(attachment!=null)throw new UnsupportedOperationException("Unknown live attachment endpoint");
        result.put("commander",c.isRealCommander());
        if(c.isRealCommander())result.put("commandCasts",c.getOwner().getCommanderCast(c));
        if(c.isRealCommander())result.put("commanderTax",c.isInZone(ZoneType.Command)?2*c.getOwner().getCommanderCast(c):0);
        if(c.isToken() && c.getTokenSpawningAbility()!=null)result.put("sourceForgeId",c.getTokenSpawningAbility().getHostCard().getId());
        List<Integer> currentTargets=new ArrayList<>(spellTargets.getOrDefault(c.getId(),List.of()));
        if(c.isInZone(ZoneType.Stack))for(var entry:game.getStack())if(entry.isSpell() && entry.getSourceCard().getId()==c.getId()){
            currentTargets.clear();for(Card target:entry.getTargetChoices().getTargetCards())currentTargets.add(target.getId());
            for(SpellAbility target:entry.getTargetChoices().getTargetSpells())currentTargets.add(target.getHostCard().getId());break;
        }
        result.put("targetForgeIds",currentTargets);
        Combat combat=game.getPhaseHandler().getCombat();
        result.put("blocked",combat!=null && combat.isBlocked(c));
        GameEntity attacked=combat!=null && combat.isAttacking(c)?combat.getDefenderByAttacker(c):null;
        // Combat.removeFromCombat replaces a departed planeswalker/battle
        // defender with Forge's synthetic Card(-1), named <Nothing>. It is
        // not a card identity and must not become a native attack recipient.
        // The attacker remains in Forge combat; no damage is redirected to
        // that permanent's controller when its presentation link is retired.
        boolean retiredDefender=attacked instanceof Card target && target.getId()==-1 && target.getName().equals("<Nothing>");
        result.put("attackDefenderRemoved",retiredDefender);
        if(retiredDefender)attacked=null;
        result.put("attackTarget",attacked instanceof Player?(seat((Player)attacked)):0);
        result.put("attackTargetForgeId",attacked instanceof Card?((Card)attacked).getId():0);
        List<Integer> blocking=new ArrayList<>();if(combat!=null)for(Card a:combat.getAttackersBlockedBy(c))blocking.add(a.getId());result.put("blocking",blocking);
        return result;
    }
    static LandAbility ability(Card c) {
        LandAbility a = new LandAbility(c,c.getCurrentState());a.setActivatingPlayer(local);return a;
    }
    static List<SpellAbility> humanLandOptions(Card c){
        List<SpellAbility> choices=new ArrayList<>();
        for(var a:c.getAllPossibleAbilities(local,false))if(a.isLandAbility() && a.canPlay())choices.add(a);
        return choices;
    }
    static List<Card> humanActionCards(){
        List<Card> cards=new ArrayList<>();
        for(Card c:game.getCardsInGame()){
            ZoneType z=c.getZone().getZoneType();
            if(Set.of(ZoneType.Hand,ZoneType.Command,ZoneType.Graveyard,ZoneType.Exile).contains(z) || z==ZoneType.Library && c.mayPlayerLook(local))cards.add(c);
        }
        return cards;
    }
    static SpellAbility chooseHumanLandAbility(Card c){
        List<SpellAbility> choices=humanLandOptions(c);if(choices.isEmpty())return null;
        return choices.size()==1?choices.get(0):optionChoice("Choose which land face to play",choices,1,1,a->a.getCardState().getName(),null).get(0);
    }
    static boolean playHumanLand(SpellAbility a){if(!a.canPlay())return false;a.resolve();return true;}
    static List<Object> zone(ZoneType type) {
        List<Object> result=new ArrayList<>();for(Card c:((type==ZoneType.Stack || type==ZoneType.Battlefield || type==ZoneType.Graveyard || type==ZoneType.Command || type==ZoneType.Exile)?game.getCardsIn(type):local.getCardsIn(type))){
            if(fullHumanChoices && type==ZoneType.Exile && c.isFaceDown() && !c.mayPlayerLook(local))continue;
            if(type==ZoneType.Command?c.isRealCommander() || fullHumanChoices && c.isEmblem():type!=ZoneType.Exile || c.isRealCommander() || c.isToken() || ADMITTED_CARDS.contains(c.getName()) || fullHumanChoices && MAPPED_OBJECTS.contains(presentationKey(c)))result.add(card(c));
        }return result;
    }
    static SpellAbility manaAbility(Card c) {
        if (!MANA_COLORS.containsKey(c.getName()) || !c.isInZone(ZoneType.Battlefield) || c.getController()!=local) return null;
        if(c.getManaAbilities().size()!=1)throw new UnsupportedOperationException("Multiple mana abilities require an explicit native choice");
        for (SpellAbility a:c.getManaAbilities()) {a.setActivatingPlayer(local);if(a.canPlay())return a;}
        return null;
    }
    static SpellAbility humanManaAbility(Card card,int nativeId){
        if(!fullHumanChoices)return manaAbility(card);
        if(!card.isInZone(ZoneType.Battlefield) || card.getController()!=local)return null;
        for(SpellAbility a:card.getManaAbilities())if(nativeAbility(a,false)==nativeId){
            a.setActivatingPlayer(local);
            if(a.canPlay() && ComputerUtilCost.canPayCost(a,local,false))return a;
        }
        return null;
    }
    static boolean canPayHumanCosts(SpellAbility ability){
        if(!fullHumanChoices)return ComputerUtilCost.canPayCost(ability,local,false);
        actionProbeDepth++;
        try{return canPayHumanResources(ability);}finally{actionProbeDepth--;}
    }
    static boolean canPayHumanResources(SpellAbility ability){
        if(ability.getPayCosts()==null)return true;
        // ComputerUtilCost also makes strategic AI decisions (including a
        // random refusal to spend a planeswalker's last loyalty). Human action
        // availability must depend on original rules/resources only.
        for(var part:ability.getPayCosts().getCostParts())if(!(part instanceof forge.game.cost.CostPartMana) && !part.canPay(ability,local,false))return false;
        if(!ability.getPayCosts().hasManaCost() || ComputerUtilMana.canPayManaCost(ability.getPayCosts(),ability,local,0,false))return true;
        var mana=ComputerUtilMana.calculateManaCost(ability.getPayCosts(),ability,local,true,0,false);int life=0;
        for(var shard:new ArrayList<>(mana.getUnpaidShards()))if(shard.isPhyrexian()){mana.decreaseShard(shard,1);life+=2;}
        return life>0 && local.canPayLife(life,false,ability) && ComputerUtilMana.canPayManaCost(mana,ability,local,false);
    }
    static SpellAbility castAbility(Card c) {
        if(fullHumanChoices){List<SpellAbility> choices=humanCastOptions(c);return choices.isEmpty()?null:choices.get(0);}
        boolean commander=commanderGame() && c.isRealCommander() && BRAWL_COMMANDERS.contains(c.getName());
        if ((!ADMITTED_CARDS.contains(c.getName()) && !commander) || c.isLand() || (!c.isInZone(ZoneType.Hand) && !c.isInZone(ZoneType.Graveyard) && !(commander && c.isInZone(ZoneType.Command))) || c.getController()!=local)return null;
        for(SpellAbility base:c.getSpellAbilities())if(base.isSpell()){
            base.setActivatingPlayer(local);var choices=new ArrayList<SpellAbility>();choices.add(base);
            if(c.isInZone(ZoneType.Graveyard) || commander && c.isInZone(ZoneType.Command))choices.addAll(GameActionUtil.getAlternativeCosts(base,local,false));
            for(SpellAbility a:choices){a.setActivatingPlayer(local);if(a.canPlay() && canPayHumanCosts(a) && (!a.usesTargeting() || a.getTargetRestrictions().getNumCandidates(a)>0))return a;}
        }
        return null;
    }
    static List<SpellAbility> humanCastOptions(Card c){
        List<SpellAbility> choices=new ArrayList<>();
        boolean admitted=ADMITTED_CARDS.contains(c.getName()) || c.getPaperCard()!=null && ADMITTED_CARDS.contains(c.getPaperCard().getName());
        boolean commander=commanderGame() && c.isRealCommander() && BRAWL_COMMANDERS.contains(c.getName());
        if(!admitted && !commander)return choices;
        for(SpellAbility a:c.getAllPossibleAbilities(local,false))if(a.isSpell()){
            a.setActivatingPlayer(local);if(a.canPlay() && canPayHumanCosts(a) && hasAvailableTargets(a))choices.add(a);
        }
        return choices;
    }
    static SpellAbility chooseHumanCastAbility(Card c){
        List<SpellAbility> choices=probeAction(c,"cast-options",()->humanCastOptions(c));
        if(choices==null || choices.isEmpty())return null;
        return choices.size()==1?choices.get(0):optionChoice("Choose how to cast "+c.getName(),choices,1,1,a->a.getCardState().getName()+": "+a.toString()+" ["+a.getPayCosts()+"]",null).get(0);
    }
    static int nativeAbility(SpellAbility a,boolean triggered){
        // Gained planeswalker abilities retain their source rule identity.
        // Matching the recipient's API first aliases all gained Draw abilities.
        if(fullHumanChoices && a.getOriginalAbility()!=null && a.getOriginalAbility()!=a){
            int original=nativeAbility(a.getOriginalAbility(),triggered);if(original!=0)return original;
        }
        if(fullHumanChoices && a.getOriginalHost()!=null && !presentationKey(a.getOriginalHost()).equals(presentationKey(a.getHostCard()))){
            int original=nativeAbilityFromBinding(a,triggered,ABILITY_BINDINGS.get(presentationKey(a.getOriginalHost())));if(original!=0)return original;
        }
        var binding=ABILITY_BINDINGS.get(presentationKey(a.getHostCard()));
        int id=nativeAbilityFromBinding(a,triggered,binding);
        if(id==0 && fullHumanChoices && a.getOriginalHost()!=null && a.getOriginalHost()!=a.getHostCard())id=nativeAbilityFromBinding(a,triggered,ABILITY_BINDINGS.get(presentationKey(a.getOriginalHost())));
        if(id==0 && fullHumanChoices && a.getGrantorStatic()!=null)id=nativeAbilityFromBinding(a,triggered,ABILITY_BINDINGS.get(presentationKey(a.getGrantorStatic().getHostCard())));
        return id;
    }
    static int nativeAbilityFromBinding(SpellAbility a,boolean triggered,JsonObject binding){
        if(binding==null)return 0;
        if(triggered && a.getTrigger()!=null){
            var triggers=binding.getAsJsonObject("triggerDescriptions");
            String description=a.getTrigger().getParam("TriggerDescription");
            if(triggers!=null && description!=null && triggers.has(description))return triggers.get(description).getAsInt();
            // Forge constructs this delayed trigger from the activated ability's
            // exact SpellDescription (Narset's rebound grant, for example).
            var descriptions=binding.getAsJsonObject("descriptions");
            if("DelayedTrigger".equals(a.getTrigger().getParam("AB")) && descriptions!=null && description!=null && descriptions.has(description))return descriptions.get(description).getAsInt();
            // CardFactoryUtil's pinned Rebound replacement creates this exact
            // delayed Play rule after the granted keyword has left the stack.
            var trigger=a.getTrigger();
            var rule=a instanceof forge.game.trigger.WrappedAbility wrapped?wrapped.getWrappedAbility():a;
            if(binding.has("reboundDelayedTrigger") && "DelayedTrigger".equals(trigger.getParam("DB")) && "Phase".equals(trigger.getParam("Mode")) && "Upkeep".equals(trigger.getParam("Phase")) && "You".equals(trigger.getParam("ValidPlayer")) && "You".equals(trigger.getParam("OptionalDecider")) && "Remembered".equals(trigger.getParam("RememberObjects")) && ("At the beginning of your next upkeep, you may cast "+rule.getCardState().toString()+" without paying its mana cost.").equals(description) && rule.getApi()==forge.game.ability.ApiType.Play)return binding.get("reboundDelayedTrigger").getAsInt();
        }
        var keyword=a.getKeyword();
        if(keyword==null && triggered && a.getTrigger()!=null)keyword=a.getTrigger().getKeyword();
        if(keyword!=null){
            var keywords=binding.getAsJsonObject("keywords");String key=keyword.getKeyword().name().replace("_","");
            if(keywords!=null && keywords.has(key))return keywords.get(key).getAsInt();
        }
        if(triggered && binding.has("trigger"))return binding.get("trigger").getAsInt();
        var descriptions=binding.getAsJsonObject("descriptions");
        if(descriptions!=null){
            if(descriptions.has(a.getDescription()))return descriptions.get(a.getDescription()).getAsInt();
            String description=a.getParam("SpellDescription");
            if(description!=null && descriptions.has(description))return descriptions.get(description).getAsInt();
        }
        var activated=binding.getAsJsonObject("activated");return activated!=null && a.getApi()!=null && activated.has(a.getApi().name())?activated.get(a.getApi().name()).getAsInt():0;
    }
    static SpellAbility activatedAbility(Card c,int nativeId){
        if(!ADMITTED_CARDS.contains(c.getName()) && !(fullHumanChoices && MAPPED_OBJECTS.contains(presentationKey(c))) || c.getController()!=local || !fullHumanChoices && !c.isInZone(ZoneType.Battlefield))return null;
        for(var a:c.getSpellAbilities())if(a.isActivatedAbility() && !a.isManaAbility() && nativeAbility(a,false)==nativeId){a.setActivatingPlayer(local);if(a.canPlay() && canPayHumanCosts(a) && hasAvailableTargets(a))return a;}
        return null;
    }
    static boolean hasAvailableTargets(SpellAbility a){return !a.usesTargeting() || fullHumanChoices && a.getMinTargets()==0 || a.getTargetRestrictions().getNumCandidates(a)>0;}
    static List<Map<String,Object>> manaCost(SpellAbility ability){
        if(ability.getActivatingPlayer()==null)ability.setActivatingPlayer(local);
        if(researchAdmission && !fullHumanChoices && (ability.isAnnouncing("X") || ability.getPayCosts()!=null && ability.getPayCosts().getCostParts().stream().anyMatch(part->part instanceof forge.game.cost.CostPartMana mana && mana.getMana().countX()>0)))throw new UnsupportedOperationException("Choosing X is not connected for "+ability.getHostCard().getName());
        var cost=ComputerUtilMana.calculateManaCost(ability.getPayCosts(),ability,local,true,0,false).toManaCost();
        var result=new ArrayList<Map<String,Object>>();if(cost.getGenericCost()>0)result.add(Map.of("color","Generic","count",cost.getGenericCost()));
        if(fullHumanChoices){
            for(var shard:cost){
                List<String> colors=new ArrayList<>();
                for(String symbol:shard.toString().replace("{","").replace("}","").split("/"))colors.add(switch(symbol){
                    case "W"->"White";case "U"->"Blue";case "B"->"Black";case "R"->"Red";case "G"->"Green";case "C"->"Colorless";case "P"->"Phyrexian";case "2"->"TwoGeneric";case "S"->"Snow";case "X"->"X";default->throw new UnsupportedOperationException("Unmapped source cost symbol "+symbol);
                });
                result.add(Map.of("colors",colors,"count",1));
            }
            return result;
        }
        Map<String,Integer> colors=new LinkedHashMap<>();for(var shard:cost){String color=switch(shard.toString()){case "{W}"->"White";case "{U}"->"Blue";case "{B}"->"Black";case "{R}"->"Red";case "{G}"->"Green";case "{C}"->"Colorless";default->throw new UnsupportedOperationException("Unmapped cost shard "+shard);};colors.merge(color,1,Integer::sum);}
        for(var e:colors.entrySet())result.add(Map.of("color",e.getKey(),"count",e.getValue()));return result;
    }
    static boolean selectHumanTargets(SpellAbility spell){
        if(researchAdmission && spell.getPayCosts()!=null)for(var part:spell.getPayCosts().getCostParts()){
            if(part instanceof forge.game.cost.CostPartMana || part instanceof forge.game.cost.CostTap || part instanceof forge.game.cost.CostSacrifice && part.payCostFromSource())continue;
            unsupportedDecision="Unmapped human payment choice: "+part.getClass().getSimpleName();throw new UnsupportedOperationException(unsupportedDecision);
        }
        // ComputerUtil.playStack pays and stacks an already prepared ability; it
        // does not perform the human casting announcement step. Forge's own
        // PlaySpellAbility calls CharmEffect.makeChoices before target selection.
        // Keep this new path research-only until the native client accepts it.
        if(researchAdmission && spell.getApi()==forge.game.ability.ApiType.Charm){
            if(spell.isAnnouncing("X"))throw new UnsupportedOperationException("Modal X announcement is not mapped");
            if(!forge.game.ability.effects.CharmEffect.makeChoices(spell))return false;
        }
        int depth=0;
        for(SpellAbility part=spell;part!=null;part=part.getSubAbility()){
            if(++depth>64)throw new UnsupportedOperationException("Ability chain exceeds mapped target depth");
            if(!selectHumanTargetsForPart(part))return false;
        }
        return true;
    }
    static boolean selectHumanTargetsForPart(SpellAbility spell){
        return selectHumanTargetsForPart(spell,null,null);
    }
    static boolean selectHumanTargetsForPart(SpellAbility spell,java.util.function.Predicate<forge.game.GameObject> filter,Integer exactCount){
        if(!spell.usesTargeting())return true;
        SpellAbility root=spell.getRootAbility();
        targetSourceContext=choiceSource(root);
        mandatoryTriggerTarget=root.isTrigger() && root.isMandatory();
        targetSourceId=spell.getHostCard().getId();targetSourceAbilityId=nativeAbility(root,root.isTrigger());targetMinimum=spell.getMinTargets();targetMaximum=spell.getMaxTargets();targetCancelled=false;
        if(exactCount!=null)targetMinimum=targetMaximum=exactCount;
        if(targetMaximum==0){spell.resetTargets();return true;}
        if(root.isTrigger() && targetSourceAbilityId==0)throw new UnsupportedOperationException("Unmapped native triggered target ability from "+spell.getHostCard().getName());
        JsonArray options=new JsonArray();
        if(spell.getTargetRestrictions().getZone().equals(List.of(ZoneType.Stack))){
            Map<Integer,SpellAbility> offered=new LinkedHashMap<>();
            for(var entry:game.getStack())if(spell.canTargetSpellAbility(entry.getSpellAbility()) && (filter==null || filter.test(entry.getSpellAbility()))){
                if(!fullHumanChoices && !entry.isSpell())throw new UnsupportedOperationException("Stack ability targeting needs a separate native ability identity");
                SpellAbility target=entry.getSpellAbility();int id=entry.isSpell()?target.getHostCard().getId():-1-entry.getId();offered.put(id,target);
                JsonObject option=new JsonObject();option.addProperty("forgeId",id);option.addProperty("stackInstanceId",entry.getId());option.addProperty("targetKind","spell");options.add(option);
            }
            if(options.size()<targetMinimum)return false;
            if(fullHumanChoices && options.isEmpty() && targetMinimum==0){spell.resetTargets();return true;}
            waitForDecision("targets",options,values->{
                if(values.size()<targetMinimum || values.size()>targetMaximum)throw new IllegalArgumentException("Spell target count outside Forge bounds");
                var previous=spell.getTargets().clone();spell.resetTargets();
                try{
                List<SpellAbility> chosen=new ArrayList<>();Set<Integer> seen=new HashSet<>();
                for(JsonElement value:values){int id=choiceInteger(value.getAsJsonObject(),"forgeId");SpellAbility target=offered.get(id);
                    boolean stillOnStack=false;for(var entry:game.getStack())if(entry.getSpellAbility()==target)stillOnStack=true;
                    if(target==null || !seen.add(id) || !stillOnStack || !spell.canTargetSpellAbility(target) || filter!=null && !filter.test(target))throw new IllegalArgumentException("Forge rejected spell target");chosen.add(target);spell.getTargets().add(target);}
                if(!spell.isTargetNumberValid())throw new IllegalArgumentException("Forge rejected submitted spell target");
                }catch(RuntimeException ex){spell.setTargets(previous);throw ex;}
            });return !targetCancelled && !game.isGameOver() && spell.isTargetNumberValid();
        }
        if(spell.getTargetRestrictions().getZone().contains(ZoneType.Stack))throw new UnsupportedOperationException("Mixed stack/permanent targets require an explicit combined target interface");
        Map<Integer,GameEntity> candidates=new LinkedHashMap<>();
        for(GameEntity target:spell.getTargetRestrictions().getAllCandidates(spell)){
            if(filter!=null && !filter.test(target))continue;
            JsonObject o=new JsonObject();int id;
            if(target instanceof Card card){id=card.getId();o.addProperty("targetKind","card");}
            else if(target instanceof Player player){int seat=seat(player);id=-1000000-seat;o.addProperty("targetKind","player");o.addProperty("targetSeat",seat);}
            else throw new UnsupportedOperationException("Unmapped target entity type");
            candidates.put(id,target);o.addProperty("forgeId",id);options.add(o);
        }
        if(options.size()<targetMinimum)return false;
        if(fullHumanChoices && options.isEmpty() && targetMinimum==0){spell.resetTargets();return true;}
        waitForDecision("targets",options,values->{
            if(values.size()<targetMinimum || values.size()>targetMaximum)throw new IllegalArgumentException("Forge target count is outside its bounds");
            var previous=spell.getTargets().clone();spell.resetTargets();
            try{
            Set<Integer> unique=new HashSet<>();List<GameEntity> chosen=new ArrayList<>();
            for(JsonElement value:values){int id=value.getAsJsonObject().get("forgeId").getAsInt();if(!unique.add(id))throw new IllegalArgumentException("duplicate target");GameEntity entity=candidates.get(id);if(entity==null || !spell.canTarget(entity))throw new IllegalArgumentException("Forge rejected target");chosen.add(entity);spell.getTargets().add(entity);}
            if(!spell.isTargetNumberValid())throw new IllegalArgumentException("Forge rejected submitted targets");
            }catch(RuntimeException ex){spell.setTargets(previous);throw ex;}
        });return !targetCancelled && !game.isGameOver() && spell.isTargetNumberValid();
    }
    static String fidelityGap() {
        if(!unsupportedDecision.isEmpty())return unsupportedDecision;
        for(var entry:game.getStack())if(!entry.isSpell() && !Set.of("Impassioned Orator","Hare Apparent").contains(entry.getSourceCard().getName()) && nativeAbility(entry.getSpellAbility(),entry.isTrigger())==0)return "Unmapped stack ability from "+entry.getSourceCard().getName();
        return "";
    }
    static Card findCard(int id){for(Card c:game.getCardsInGame())if(c.getId()==id)return c;throw new IllegalArgumentException("Unknown Forge card "+id);}

    static void remember(JsonObject request,JsonObject response) throws Exception {
        String id=request.get("id").getAsString();acceptedRequests.put(id,response);requestBodies.put(id,request.deepCopy());
        if(journal!=null){journal.println(new Gson().toJson(Map.of("request",request,"response",response)));journal.flush();}
        write(ipc.resolve("responses").resolve(id+".json"),response);
    }
    static JsonObject response(JsonObject request,boolean accepted,String reason){
        JsonObject r=new JsonObject();r.addProperty("id",request.get("id").getAsString());r.addProperty("session",SESSION);r.addProperty("accepted",accepted);r.addProperty("reason",reason);r.add("state",JSON.toJsonTree(snapshot()));return r;
    }
    // Normal games remain inside Match.startGame on this one owner thread. The
    // controller waits here, then returns a real ability (or null for a pass) to
    // Forge's own priority loop. Acknowledgements are published at its next stable
    // controller boundary, never from a second rules thread.
    static void finishLiveRequests() throws Exception {
        if(!normalGame())return;
        for(JsonObject request:deferredSubmissions){String failure=failedPlays.remove(request.get("id").getAsString());remember(request,response(request,failure==null,failure==null?"Forge reached the next controller boundary":failure));}
        deferredSubmissions.clear();
    }
    // This queue has one human and three bots. Once the human is eliminated,
    // acknowledge their last action at this owner-thread boundary and hold the
    // local session for Return Home. Do not invent a winner among the survivors
    // or run indefinitely without a human controller boundary.
    static void waitForPodExit(){
        try{
            decision=null;retireFile(ipc.resolve("decision.json"));finishLiveRequests();write(ipc.resolve("state.json"),snapshot());
            while(!Files.exists(ipc.resolve("stop.request"))){
                try(var paths=Files.list(ipc.resolve("requests"))){
                    for(Path path:paths.filter(p->p.toString().endsWith(".json")).sorted().toList()){
                        JsonObject request=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
                        String id=request.get("id").getAsString();
                        if(!id.matches("[a-zA-Z0-9_-]{1,80}"))throw new IllegalArgumentException("Invalid request ID");
                        JsonObject cached=acceptedRequests.get(id);
                        if(cached!=null)write(ipc.resolve("responses").resolve(id+".json"),requestBodies.get(id).equals(request)?cached:response(request,false,"request ID reused with different payload"));
                        else{
                            boolean owner=SESSION.equals(request.get("session").getAsString()) && request.get("seat").getAsInt()==1;
                            String op=request.get("op").getAsString();boolean accepted=owner && Set.of("snapshot","concede").contains(op);
                            remember(request,response(request,accepted,accepted?"Local Commander seat eliminated; return Home":"This local Commander seat has been eliminated"));
                        }
                        Files.delete(path);
                    }
                }
                Thread.sleep(25);
            }
            throw new StopRequested();
        }catch(StopRequested ex){throw ex;}catch(Exception ex){throw new RuntimeException(ex);}
    }
    static List<SpellAbility> waitForPriority(){
        try{
            finishLiveRequests();write(ipc.resolve("state.json"),snapshot());
            while(!Files.exists(ipc.resolve("stop.request"))){
                try(var paths=Files.list(ipc.resolve("requests"))){
                    for(Path path:paths.filter(p->p.toString().endsWith(".json")).sorted().toList()){
                        JsonObject request=JsonParser.parseString(Files.readString(path)).getAsJsonObject();String id=request.get("id").getAsString();
                        if(!id.matches("[a-zA-Z0-9_-]{1,80}"))throw new IllegalArgumentException("Invalid request ID");
                        JsonObject cached=acceptedRequests.get(id);
                        if(cached!=null){write(ipc.resolve("responses").resolve(id+".json"),requestBodies.get(id).equals(request)?cached:response(request,false,"request ID reused with different payload"));Files.delete(path);continue;}
                        SpellAbility selected=null;boolean advance=false;
                        try{
                            if(!SESSION.equals(request.get("session").getAsString()))throw new IllegalArgumentException("stale session");
                            if(request.get("seat").getAsInt()!=1)throw new IllegalArgumentException("wrong player");
                            String op=request.get("op").getAsString();
                            if(!op.equals("snapshot") && !op.equals("concede") && !fidelityGap().isEmpty())throw new UnsupportedOperationException(fidelityGap());
                            if(op.equals("snapshot")){remember(request,response(request,true,"snapshot at priority"));}
                            else if(op.equals("concede")){local.concede();priorityChecks.invoke(game.getPhaseHandler());advance=true;}
                            else if(op.equals("pass_priority"))advance=true;
                            else {
                                Card card=findCard(request.get("forgeId").getAsInt());
                                if(op.equals("play_land")){
                                    if(fullHumanChoices){var lands=probeAction(card,"land",()->humanLandOptions(card));if(lands!=null && !lands.isEmpty())selected=lands.get(0);}
                                    else if(card.getController()==local && card.isInZone(ZoneType.Hand) && card.isLand() && ability(card).canPlay())selected=ability(card);
                                }
                                else if(op.equals("activate_mana"))selected=fullHumanChoices?humanManaAbility(card,request.get("abilityId").getAsInt()):manaAbility(card);
                                else if(op.equals("cast_spell"))selected=probeAction(card,"cast",()->{var a=castAbility(card);if(a!=null)manaCost(a);return a;});
                                else if(op.equals("activate_ability")){
                                    if(!request.has("abilityId") || !request.get("abilityId").isJsonPrimitive() || !request.getAsJsonPrimitive("abilityId").isNumber() || !request.get("abilityId").getAsString().matches("[1-9][0-9]{0,8}"))throw new IllegalArgumentException("Activation requires an exact positive integer ability identity");
                                    selected=probeAction(card,"activate",()->activatedAbility(card,request.get("abilityId").getAsInt()));
                                }
                                if(selected==null)throw new IllegalArgumentException("Forge rejected unavailable action at priority");
                                advance=true;
                            }
                        }catch(Exception ex){remember(request,response(request,false,ex.toString()));}
                        Files.delete(path);
                        if(advance){currentRequest=request;deferredSubmissions.add(request.deepCopy());if(commanderPod && local.hasLost())waitForPodExit();return selected==null?null:List.of(selected);}
                    }
                }
                Thread.sleep(25);
            }
            throw new StopRequested();
        }catch(StopRequested ex){throw ex;}catch(Exception ex){throw new RuntimeException(ex);}
    }
    static void publishDecision() throws Exception {
        JsonObject message=new JsonObject();message.addProperty("session",SESSION);message.addProperty("parentRequestId",currentRequest.get("id").getAsString());message.addProperty("token",decision.get("token").getAsString());message.add("state",JSON.toJsonTree(snapshot()));
        write(ipc.resolve("decision.json"),message);write(ipc.resolve("state.json"),snapshot());
    }
    static void waitForDecision(String kind,JsonArray options,Consumer<JsonArray> submit){
        if(actionProbeDepth>0)throw new UnsupportedOperationException("A player choice ("+kind+") is required while checking this action; its availability adapter is not connected");
        try {
            decision=new JsonObject();decision.addProperty("kind",kind);decision.addProperty("seat",1);decision.addProperty("token",UUID.randomUUID().toString());decision.add("options",options);decision.add("assignments",new JsonArray());
            if(kind.equals("choice")){if(sharedChoice==null)throw new IllegalStateException("Missing shared choice contract");decision.add("choice",sharedChoice.deepCopy());}
            if(kind.equals("discard") || kind.startsWith("mulligan"))decision.addProperty("count",discardCount);
            if(kind.equals("legend_rule"))decision.addProperty("count",1);
            if(kind.equals("order_cards")){decision.addProperty("count",options.size());decision.addProperty("destination",orderDecisionZone);decision.addProperty("orderSemantics","movement insertion order; graveyard bottom to top");}
            if(kind.startsWith("mulligan"))decision.addProperty("mulligans",mulligans);
            if(kind.equals("targets")){decision.addProperty("sourceForgeId",targetSourceId);decision.addProperty("sourceAbilityId",targetSourceAbilityId);decision.addProperty("minTargets",targetMinimum);decision.addProperty("maxTargets",targetMaximum);decision.addProperty("canCancel",!mandatoryTriggerTarget);if(targetSourceContext!=null && targetSourceContext.has("pendingCopyObject"))decision.add("pendingCopyObject",targetSourceContext.get("pendingCopyObject").deepCopy());}
            if(kind.equals("assign_damage")){decision.addProperty("sourceForgeId",damageSourceId);decision.addProperty("totalDamage",damageTotal);decision.addProperty("policy","Explicit modern allocation; positive trample-to-player requires lethal on every blocker. Banding and legacy multi-block ordering remain unsupported.");}
            if(kind.equals("commander_return")){decision.addProperty("sourceForgeId",commanderDecisionId);decision.addProperty("fromZone",findCard(commanderDecisionId).getZone().getZoneType().name());decision.addProperty("choiceZone",commanderDecisionZone);}
            finishLiveRequests();
            // A resolving spell may ask several consecutive questions. Publish
            // the previous answer at this stable controller boundary even in a
            // fixture, so the caller can answer the next question without a
            // circular wait for the entire original cast/resolution to finish.
            if(!normalGame()){
                for(JsonObject request:deferredSubmissions)remember(request,response(request,true,"Forge reached the next decision boundary"));
                deferredSubmissions.clear();
            }
            publishDecision();
            if(journal!=null){journal.println(new Gson().toJson(Map.of("event","decision-open","decision",decision)));journal.flush();}
            while(!Files.exists(ipc.resolve("stop.request"))){
                try(var paths=Files.list(ipc.resolve("requests"))){
                    for(Path path:paths.filter(p->p.toString().endsWith(".json")).sorted().toList()){
                        JsonObject request=JsonParser.parseString(Files.readString(path)).getAsJsonObject();String id=request.get("id").getAsString();
                        if(id.equals(currentRequest.get("id").getAsString()))continue;
                        if(!id.matches("[a-zA-Z0-9_-]{1,80}"))throw new IllegalArgumentException("Invalid decision request ID");
                        JsonObject cached=acceptedRequests.get(id);
                        if(cached!=null){write(ipc.resolve("responses").resolve(id+".json"),requestBodies.get(id).equals(request)?cached:response(request,false,"request ID reused with different payload"));Files.delete(path);continue;}
                        boolean done=false;JsonObject reply;
                        try {
                            if(!SESSION.equals(request.get("session").getAsString()))throw new IllegalArgumentException("stale session");
                            if(request.get("seat").getAsInt()!=1)throw new IllegalArgumentException("wrong decision player");
                            String op=request.get("op").getAsString();
                            if(op.equals("snapshot")){reply=response(request,true,"snapshot during decision");}
                            else if(op.equals("concede")){
                                local.concede();priorityChecks.invoke(game.getPhaseHandler());
                                deferredSubmissions.add(request.deepCopy());done=true;reply=null;
                            }
                            else {
                                if(!decision.get("token").getAsString().equals(request.get("decisionToken").getAsString()))throw new IllegalArgumentException("stale decision token");
                                if(op.equals("cancel_targets") && kind.equals("targets")){
                                    if(mandatoryTriggerTarget)throw new IllegalArgumentException("A mandatory triggered target choice cannot be canceled");
                                    targetCancelled=true;deferredSubmissions.add(request.deepCopy());done=true;reply=null;
                                }
                                else if(op.equals("select_"+kind) && !kind.equals("choice") && !kind.equals("assign_damage") && !kind.equals("order_cards")){
                                    JsonArray assignments=kind.equals("discard") || kind.equals("mulligan_bottom")?new JsonArray():decision.getAsJsonArray("assignments").deepCopy();
                                    for(JsonElement value:request.getAsJsonArray("assignments")){
                                        JsonObject chosen=value.getAsJsonObject();int cardId=chosen.get("forgeId").getAsInt();JsonObject offered=null;
                                        for(JsonElement e:options)if(e.getAsJsonObject().get("forgeId").getAsInt()==cardId)offered=e.getAsJsonObject();
                                        if(offered==null)throw new IllegalArgumentException("card was not offered by Forge");
                                        if(kind.equals("attackers")){
                                            int target=chosen.get("targetSeat").getAsInt(),object=chosen.has("targetForgeId")?chosen.get("targetForgeId").getAsInt():0;
                                            boolean legal=target==0 && object==0;
                                            for(JsonElement item:offered.getAsJsonArray("attackTargets")){JsonObject r=item.getAsJsonObject();if(r.get("targetSeat").getAsInt()==target && r.get("targetForgeId").getAsInt()==object)legal=true;}
                                            if(!legal)throw new IllegalArgumentException("invalid attack recipient");
                                        } else if(kind.equals("blockers")){
                                            JsonArray ids=chosen.getAsJsonArray("attackerIds");if(ids.size()>1)throw new UnsupportedOperationException("multiple blocks per vanilla creature unsupported");
                                            for(JsonElement target:ids)if(!offered.getAsJsonArray("attackerIds").contains(target))throw new IllegalArgumentException("illegal blocker pairing");
                                        }
                                        for(int i=assignments.size()-1;i>=0;i--)if(assignments.get(i).getAsJsonObject().get("forgeId").getAsInt()==cardId)assignments.remove(i);
                                        if(!kind.equals("targets") || !chosen.has("selected") || chosen.get("selected").getAsBoolean())assignments.add(chosen.deepCopy());
                                    }
                                    decision.add("assignments",assignments);reply=response(request,true,"updated "+kind+" selection");publishDecision();
                                } else if(op.equals("submit_"+kind)){
                                    if(kind.equals("choice") || kind.equals("mulligan") || kind.equals("starting_player") || kind.equals("assign_damage") || kind.equals("commander_return") || kind.equals("order_cards")){submit.accept(request.getAsJsonArray("assignments"));}
                                    else if(kind.equals("discard") || kind.equals("mulligan_bottom") || kind.equals("legend_rule")){
                                        JsonArray selected=request.has("assignments")?request.getAsJsonArray("assignments"):decision.getAsJsonArray("assignments");
                                        for(JsonElement e:selected)if(!options.asList().stream().anyMatch(o->o.getAsJsonObject().get("forgeId").equals(e.getAsJsonObject().get("forgeId"))))throw new IllegalArgumentException("discard card not offered");
                                        submit.accept(selected);
                                    }else submit.accept(decision.getAsJsonArray("assignments"));
                                    deferredSubmissions.add(request.deepCopy());done=true;reply=null;
                                } else throw new UnsupportedOperationException("Only the pending declaration can be changed now");
                            }
                        }catch(Exception ex){reply=response(request,false,ex.toString());}
                        Files.delete(path);
                        if(done){if(normalGame())currentRequest=request;decision=null;retireFile(ipc.resolve("decision.json"));if(commanderPod && local.hasLost())waitForPodExit();return;}
                        remember(request,reply);
                    }
                }
                Thread.sleep(25);
            }
            if(normalGame())throw new StopRequested();
            throw new IllegalStateException("Stopped during a pending declaration");
        }catch(StopRequested ex){throw ex;}catch(Exception ex){throw new RuntimeException(ex);}
    }
    static Map<String,Object> snapshot() {
        unavailableActions.clear();
        boolean priorityReady=game.getAge()==GameStage.Play && !local.hasLost() && game.getPhaseHandler().getPriorityPlayer()==local && decision==null && !game.isGameOver() && fidelityGap().isEmpty();
        List<Integer> legal=new ArrayList<>();
        if(priorityReady)for(Card c:fullHumanChoices?humanActionCards():local.getCardsIn(ZoneType.Hand))if(fullHumanChoices?!humanLandOptions(c).isEmpty():c.isLand()&&ability(c).canPlay())legal.add(c.getId());
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("session",SESSION);result.put("scenario",scenario);result.put("events",events);result.put("decision",decision);result.put("phase",phaseName());result.put("stage",game.getAge().name());result.put("mulligans",mulligans);
        if(researchAdmission){result.put("keywordPresentationSchema",1);result.put("researchControls",Map.of("strictHumanCallbacks",local.getController() instanceof ResearchStrictController,"auditedAutomaticDecisions",researchCallbackAudit,"effectPresentationOrigins",researchEffectOrigins,"controllerIdentities",seatPlayers.stream().map(p->Map.of("seat",seat(p),"controllerIsAI",p.getController().isAI(),"playerIsAI",p.isAI())).toList()));result.put("researchTrace",researchTrace);}
        result.put("format",commanderMode?"commander-40":arenaBrawl?"arena-brawl":"practice");result.put("startingLifeTotal",local.getStartingLife());result.put("opponentStartingLifeTotal",opponent.getStartingLife());result.put("commanderDamageLimit",commanderMode?21:0);
        List<Map<String,Object>> commanderDamage=new ArrayList<>();for(Player p:seatPlayers)for(var entry:p.getCommanderDamage())commanderDamage.add(Map.of("seat",seat(p),"commanderForgeId",entry.getKey().getId(),"amount",entry.getValue()));result.put("commanderDamage",commanderDamage);result.put("command",zone(ZoneType.Command));result.put("exile",zone(ZoneType.Exile));
        result.put("freeMulliganCount",arenaBrawl || commanderPod?1:0);result.put("players",playerSnapshots());result.put("playerCount",seatPlayers.size());result.put("pod",commanderPod);
        result.put("randomSeed",randomSeed);if(localDeck!=null){result.put("localDeck",localDeck);result.put("opponentDeck",opponentDeck);}
        result.put("startingSeat",startingSeat);result.put("startingPlayerPolicy",startingPlayerPolicy);result.put("opponentKept",opponentKept);result.put("opponentMulligans",opponentMulligans);
        result.put("prioritySeat",seat(game.getPhaseHandler().getPriorityPlayer()));
        result.put("activeSeat",game.getPhaseHandler().getPlayerTurn()==null?(startingSeat==0?1:startingSeat):seat(game.getPhaseHandler().getPlayerTurn()));
        result.put("fidelityGap",fidelityGap());result.put("canPass",priorityReady && fidelityGap().isEmpty());
        result.put("turn",game.getPhaseHandler().getTurn());result.put("gameOver",game.isGameOver());
        result.put("life",local.getLife());result.put("opponentLife",opponent.getLife());
        result.put("playerCounters",seatPlayers.stream().map(p->Map.of("seat",seat(p),"counters",counters(p))).toList());
        result.put("winnerSeat",seatPlayers.stream().filter(Player::hasWon).mapToInt(ForgeLandEngine::seat).findFirst().orElse(0));
        result.put("localLost",local.hasLost());result.put("opponentLost",opponent.hasLost());
        result.put("lossReason",local.hasLost()?local.getOutcome().lossState.name():opponent.hasLost()?opponent.getOutcome().lossState.name():"");
        result.put("landsPlayed",local.getLandsPlayedThisTurn());result.put("maxLandPlays",local.getMaxLandPlays());
        List<Integer> legalCasts=new ArrayList<>();List<Object> castOffers=new ArrayList<>();
        List<Card> castCandidates=new ArrayList<>();
        if(fullHumanChoices)castCandidates.addAll(humanActionCards());else for(ZoneType z:new ZoneType[]{ZoneType.Hand,ZoneType.Command,ZoneType.Graveyard})castCandidates.addAll(local.getCardsIn(z));
        if(priorityReady)for(Card c:castCandidates){
            var offer=probeAction(c,"cast",()->{var a=castAbility(c);return a==null?null:Map.<String,Object>of("forgeId",c.getId(),"manaCost",manaCost(a));});
            if(offer!=null){legalCasts.add(c.getId());castOffers.add(offer);}
        }
        result.put("castOffers",castOffers);
        List<Object> activations=new ArrayList<>();
        if(priorityReady)for(ZoneType z:fullHumanChoices?new ZoneType[]{ZoneType.Battlefield,ZoneType.Hand,ZoneType.Graveyard,ZoneType.Exile,ZoneType.Command}:new ZoneType[]{ZoneType.Battlefield})for(Card c:local.getCardsIn(z))for(var a:c.getSpellAbilities())if(a.isActivatedAbility() && !a.isManaAbility()){
            int nativeId=nativeAbility(a,false);if(nativeId!=0){var offer=probeAction(c,"activate",()->activatedAbility(c,nativeId)==null?null:Map.<String,Object>of("forgeId",c.getId(),"abilityId",nativeId,"api",a.getApi().name(),"manaCost",manaCost(a),"tap",a.getPayCosts().hasTapCost()));if(offer!=null)activations.add(offer);}
        }
        result.put("legalActivations",activations);
        result.put("legalCasts",legalCasts);result.put("stack",zone(ZoneType.Stack));
        result.put("hand",zone(ZoneType.Hand));result.put("battlefield",zone(ZoneType.Battlefield));result.put("graveyard",zone(ZoneType.Graveyard));result.put("legalLands",legal);
        List<Integer> legalMana=new ArrayList<>();
        List<Object> legalManaOffers=new ArrayList<>();
        if(priorityReady)for(Card c:local.getCardsIn(ZoneType.Battlefield)){
            if(fullHumanChoices){
                for(SpellAbility a:c.getManaAbilities()){
                    int nativeId=nativeAbility(a,false);
                    if(nativeId!=0 && probeAction(c,"mana",()->humanManaAbility(c,nativeId))!=null){
                        if(!legalMana.contains(c.getId()))legalMana.add(c.getId());
                        legalManaOffers.add(Map.of("forgeId",c.getId(),"abilityId",nativeId));
                    }
                }
            }else if(probeAction(c,"mana",()->manaAbility(c))!=null)legalMana.add(c.getId());
        }
        if(fullHumanChoices)result.put("legalManaOffers",legalManaOffers);
        result.put("unavailableActions",new ArrayList<>(unavailableActions.values()));
        if(game.isGameOver()){legal.clear();legalCasts.clear();legalMana.clear();}
        Map<Integer,Map<String,Object>> manaLots=new LinkedHashMap<>();
        for(Mana m:local.getManaPool()){
            int id=manaIds.computeIfAbsent(m,k->nextManaId++);var lot=manaLots.get(id);
            if(lot==null){lot=new LinkedHashMap<>();lot.put("id",id);lot.put("color",(int)m.getColor());lot.put("sourceForgeId",m.getSourceCard().getId());lot.put("sourcePresentationKey",presentationKey(m.getSourceCard()));lot.put("count",0);manaLots.put(id,lot);}
            lot.put("count",(int)lot.get("count")+1);
        }
        List<Object> mana=new ArrayList<>(manaLots.values());
        result.put("legalMana",legalMana);result.put("mana",mana);result.put("manaTotal",local.getManaPool().totalMana());
        List<Object> hidden=new ArrayList<>();for(Player p:seatPlayers)for(ZoneType z:new ZoneType[]{ZoneType.Library,ZoneType.Hand})
            if(!p.hasLost() && (p!=local || z!=ZoneType.Hand))for(Card c:p.getCardsIn(z)){
                if(fullHumanChoices && c.mayPlayerLook(local)){
                    var known=card(c);known.put("privateChoice",true);known.put("privateToSeat",1);known.put("visibilityReason","source-look-permission");hidden.add(known);
                }else hidden.add(Map.of("forgeId",c.getId(),"arenaId",1000+c.getId(),"zone",z.name(),"owner",seat(p),"controller",seat(p)));
            }
        if(fullHumanChoices)for(Card c:game.getCardsIn(ZoneType.Exile))if(c.isFaceDown() && !c.mayPlayerLook(local))hidden.add(Map.of("forgeId",c.getId(),"arenaId",1000+c.getId(),"zone","Exile","owner",seat(c.getOwner()),"controller",seat(c.getController())));
        result.put("hidden",hidden);
        List<Object> stackAbilities=new ArrayList<>();List<Integer> stackOrder=new ArrayList<>();
        for(var entry:game.getStack()){
            if(entry.isSpell()){stackOrder.add(entry.getSourceCard().getId());continue;}
            int id=-1-entry.getId();Card source=entry.getSourceCard();int controller=seat(entry.getActivatingPlayer());
            if(fullHumanChoices && source.isImmutable() && !source.isEmblem()){
                Set<Integer> seen=new HashSet<>();
                while(source.isImmutable() && !source.isEmblem()){
                    if(!seen.add(source.getId()) || seen.size()>16)throw new UnsupportedOperationException("Cyclic stack effect source");
                    Card parent=source.getEffectSource();if(parent==null && source.getEffectSourceAbility()!=null)parent=source.getEffectSourceAbility().getHostCard();
                    if(parent==null)break;source=parent;
                }
            }
            Map<String,Object> object=new LinkedHashMap<>();object.put("forgeId",id);object.put("arenaId",200000+entry.getId());object.put("stackInstanceId",entry.getId());object.put("sourceForgeId",source.getId());object.put("name",source.getName());object.put("zone","Stack");object.put("owner",controller);object.put("controller",controller);object.put("objectKind","ability");object.put("triggered",entry.isTrigger());
            if(!presentationKey(source).equals(source.getName()))object.put("presentationKey",presentationKey(source));
            object.put("abilityId",nativeAbility(entry.getSpellAbility(),entry.isTrigger()));
            object.put("targetForgeIds",entry.getTargetChoices().getTargetCards().stream().map(Card::getId).toList());
            List<Integer> targetSeats=new ArrayList<>();for(Player p:entry.getTargetChoices().getTargetPlayers())targetSeats.add(seat(p));object.put("targetSeats",targetSeats);
            stackAbilities.add(object);stackOrder.add(id);
        }
        result.put("stackAbilities",stackAbilities);result.put("stackOrder",stackOrder);
        result.put("scope",normalGame()?"Real Forge Match.startGame, shuffled practice decks, opening hands, London mulligans and full game loop. Starting-player policy: "+startingPlayerPolicy+"; admitted card allowlist only; no constructed deck-legality claim.":aiDuel()?"Seeded six-card hands and 24-card libraries; real Forge AI, phase loop, casts and combat. Admitted card allowlist only; use opening-duel for normal match startup.":"Seeded rules scenario; passive or scripted opponent; admitted card allowlist, native decisions and Forge phase loop. No general cards or normal match startup.");return result;
    }
    static JsonObject handle(JsonObject request) {
        JsonObject response=new JsonObject();response.addProperty("id",request.get("id").getAsString());response.addProperty("session",SESSION);
        boolean accepted=false;String reason="unsupported operation";
        try {
            if(!SESSION.equals(request.get("session").getAsString()))throw new IllegalArgumentException("stale session");
            String op=request.get("op").getAsString();
            if(game.isGameOver() && !op.equals("snapshot"))throw new IllegalStateException("game is over");
            if(researchAdmission && !op.equals("snapshot") && !op.equals("concede") && !fidelityGap().isEmpty())throw new UnsupportedOperationException(fidelityGap());
            if(op.equals("snapshot")){accepted=true;reason="snapshot";}
            else if(op.equals("concede")){
                if(request.get("seat").getAsInt()!=1)throw new IllegalArgumentException("wrong player");
                if(game.isGameOver())throw new IllegalStateException("game is over");
                local.concede();priorityChecks.invoke(game.getPhaseHandler());accepted=local.hasLost() || game.isGameOver();reason="Forge processed local concession";
            }
            else if(op.equals("play_land")) {
                if(request.get("seat").getAsInt()!=1)throw new IllegalArgumentException("wrong player");
                int id=request.get("forgeId").getAsInt();Card selected=null;
                for(Card c:fullHumanChoices?humanActionCards():local.getCardsIn(ZoneType.Hand))if(c.getId()==id)selected=c;
                if(selected==null)reason="card is not in an available land-play zone";
                else if(fullHumanChoices){var land=chooseHumanLandAbility(selected);accepted=land!=null && playHumanLand(land);reason=accepted?"Forge human land play completed":"Forge rejected or canceled land play";}
                else {
                    LandAbility land=ability(selected);
                    if(!selected.isLand()||!land.canPlay())reason="Forge LandAbility.canPlay rejected the action";
                    else {land.resolve();accepted=true;reason="Forge resolved LandAbility";}
                }
            }
            else if(op.equals("cast_spell")) {
                if(request.get("seat").getAsInt()!=1)throw new IllegalArgumentException("wrong player");
                Card selected=null;int id=request.get("forgeId").getAsInt();
                for(Card c:fullHumanChoices?game.getCardsInGame():local.getCardsIn(ZoneType.Hand))if(c.getId()==id)selected=c;
                Card chosenCard=selected;
                SpellAbility spell=chosenCard==null?null:probeAction(chosenCard,"cast",()->{var a=castAbility(chosenCard);if(a!=null)manaCost(a);return a;});
                if(spell==null)reason="Forge rejected unavailable supported creature spell";
                else if(fullHumanChoices){spell=chooseHumanCastAbility(chosenCard);accepted=spell!=null && forge.game.player.PlaySpellAbility.playSpellAbility(local.getController(),local,spell);reason=accepted?"Forge human casting path completed":"Forge human casting path canceled or rejected";}
                else if(!selectHumanTargets(spell)){accepted=targetCancelled;reason=targetCancelled?"Controller canceled pending cast before payment":"Target selection ended without casting";}
                else if(ComputerUtil.playStack(spell,local,game)){game.getPhaseHandler().setPriority(local);accepted=true;reason="Forge paid spell cost and placed supported spell on stack";}
                else reason="Forge could not pay casting cost";
            }
            else if(op.equals("pass_priority")) {
                if(request.get("seat").getAsInt()!=1 || game.getPhaseHandler().getPriorityPlayer()!=local)throw new IllegalArgumentException("wrong priority player");
                if(game.isGameOver())throw new IllegalStateException("game is over");
                if(!fidelityGap().isEmpty())throw new UnsupportedOperationException(fidelityGap());
                List<String> transitions=new ArrayList<>();int steps=0;
                do {
                    game.getPhaseHandler().mainLoopStep();
                    transitions.add(game.getPhaseHandler().getPhase().name()+":"+game.getPhaseHandler().getPriorityPlayer().getName());
                    if(++steps>32)throw new IllegalStateException("priority progression bound exceeded");
                } while(!game.isGameOver() && game.getPhaseHandler().getPriorityPlayer()!=local);
                response.add("phaseTransitions",JSON.toJsonTree(transitions));accepted=true;reason="Forge mainLoopStep processed local pass and passive opponent";
            }
            else if(op.equals("activate_mana")) {
                if(request.get("seat").getAsInt()!=1)throw new IllegalArgumentException("wrong player");
                Card selected=null;int id=request.get("forgeId").getAsInt();
                for(Card c:fullHumanChoices?game.getCardsInGame():local.getCardsIn(ZoneType.Battlefield))if(c.getId()==id)selected=c;
                SpellAbility mana=selected==null?null:fullHumanChoices?humanManaAbility(selected,request.get("abilityId").getAsInt()):manaAbility(selected);
                if(mana==null)reason="Forge rejected unavailable mana ability";
                else if(fullHumanChoices){accepted=forge.game.player.PlaySpellAbility.playSpellAbility(local.getController(),local,mana);reason=accepted?"Forge human mana activation completed":"Forge human mana activation canceled or rejected";}
                else if(ComputerUtil.playNoStack(local,mana,game,false)){accepted=true;reason="Forge paid activation cost and resolved mana ability";}
                else reason="Forge could not pay mana activation cost";
            }
            else if(op.equals("activate_ability") && researchAdmission && scenario.equals("card-family")) {
                if(request.get("seat").getAsInt()!=1)throw new IllegalArgumentException("wrong player");
                if(!request.has("abilityId") || !request.get("abilityId").isJsonPrimitive() || !request.getAsJsonPrimitive("abilityId").isNumber() || !request.get("abilityId").getAsString().matches("[1-9][0-9]{0,8}"))throw new IllegalArgumentException("Activation requires an exact positive integer ability identity");
                Card selected=null;int id=request.get("forgeId").getAsInt();
                for(Card c:fullHumanChoices?game.getCardsInGame():local.getCardsIn(ZoneType.Battlefield))if(c.getId()==id)selected=c;
                Card chosenCard=selected;
                SpellAbility activation=chosenCard==null?null:probeAction(chosenCard,"activate",()->activatedAbility(chosenCard,request.get("abilityId").getAsInt()));
                if(activation==null)reason="Forge rejected unavailable supported activation";
                else if(fullHumanChoices){accepted=forge.game.player.PlaySpellAbility.playSpellAbility(local.getController(),local,activation);reason=accepted?"Forge human activation completed":"Forge human activation canceled or rejected";}
                else if(!selectHumanTargets(activation)){accepted=targetCancelled;reason=targetCancelled?"Controller canceled pending activation before payment":"Target selection ended without activation";}
                else if(ComputerUtil.playStack(activation,local,game)){game.getPhaseHandler().setPriority(local);accepted=true;reason="Forge paid activation cost and placed supported ability on stack";}
                else reason="Forge could not pay activation cost";
            }
            // Present choices only after Forge's own pre-priority SBA/trigger routine.
            // mainLoopStep normally calls this on its next iteration, before consulting a controller.
            if(accepted && !op.equals("snapshot") && !game.isGameOver())priorityChecks.invoke(game.getPhaseHandler());
        }catch(Exception ex){reason=ex.toString();}
        response.addProperty("accepted",accepted);response.addProperty("reason",reason);response.add("state",JSON.toJsonTree(snapshot()));return response;
    }
    public static void main(String[] args) {
        // FModel installs its own uncaught handler. Catch owner-thread failures
        // explicitly so an invalid startup cannot leave AWT helpers alive.
        try { run(args); }
        catch(Throwable error){
            error.printStackTrace();
            try{
                String reason=unsupportedDecision.isEmpty()?error.toString():unsupportedDecision;
                if(ipc!=null)write(ipc.resolve("engine-error.json"),Map.of("session",SESSION,"reason",reason,"recoverable",false));
            }catch(Throwable reportingError){reportingError.printStackTrace();}
            System.exit(1);
        }
    }
    /** Research worker entrypoint; each call must use a fresh bridge classloader. */
    public static void runResearchCase(String[] args) throws Exception {
        JsonObject manifest=JsonParser.parseString(Files.readString(Path.of(args[0]).getParent().resolve("native-lab/bridge-card-manifest.json"))).getAsJsonObject();
        JsonObject fixture=JsonParser.parseString(Files.readString(Path.of(args[1]).resolve("scenario.json"))).getAsJsonObject();
        if(!manifest.has("researchOnly") || !manifest.get("researchOnly").getAsBoolean() || !fixture.get("scenario").getAsString().equals("card-family"))throw new IllegalArgumentException("Warm reuse supports research-only card-family fixtures");
        if(FModel.getMagicDb()==null)throw new IllegalStateException("Research worker did not initialize the shared database");
        warmResearch=true;run(args);
    }
    static void run(String[] args) throws Exception {
        // GuiDesktop initializes AWT helpers. An uncaught owner-thread failure
        // must not leave those helpers alive masquerading as a healthy backend.
        Thread.setDefaultUncaughtExceptionHandler((thread,error)->{error.printStackTrace();System.exit(1);});
        final Path runtime=Path.of(args[0]).toAbsolutePath();ipc=Path.of(args[1]).toAbsolutePath();
        JsonObject manifest=JsonParser.parseString(Files.readString(runtime.getParent().resolve("native-lab/bridge-card-manifest.json"))).getAsJsonObject();
        if(manifest.get("schema").getAsInt()!=1)throw new IllegalArgumentException("Unsupported generated card manifest");
        loadAdmission(manifest);
        researchAdmission=manifest.has("researchOnly") && manifest.get("researchOnly").getAsBoolean() || manifest.has("experimentalAdmission") && manifest.get("experimentalAdmission").getAsBoolean();
        fullHumanChoices=researchAdmission && manifest.has("fullHumanChoices") && manifest.get("fullHumanChoices").getAsBoolean();
        if(Files.exists(ipc.resolve("scenario.json"))){JsonObject config=JsonParser.parseString(Files.readString(ipc.resolve("scenario.json"))).getAsJsonObject();fixtureConfig=config;scenario=config.get("scenario").getAsString();if(config.has("localDeck"))localDeck=config.getAsJsonObject("localDeck");if(config.has("opponentDeck"))opponentDeck=config.getAsJsonObject("opponentDeck");if(config.has("opponentDecks"))podOpponentDecks=config.getAsJsonArray("opponentDecks");if(config.has("randomSeed"))randomSeed=config.get("randomSeed").getAsLong();if(config.has("startingPlayerPolicy"))startingPlayerPolicy=config.get("startingPlayerPolicy").getAsString();}
        if(scenario.equals("card-family") && (!manifest.has("researchOnly") || !manifest.get("researchOnly").getAsBoolean()))throw new IllegalArgumentException("Card-family fixtures require an explicit research-only manifest");
        if(fixtureConfig!=null && (fixtureConfig.has("fixtureAttacker") || fixtureConfig.has("fixtureBlockers")) && (!Set.of("attack-double-blocked","defend").contains(scenario) || !manifest.has("researchOnly") || !manifest.get("researchOnly").getAsBoolean()))throw new IllegalArgumentException("Combat fixture overrides require an explicit research-only combat scenario");
        if(fixtureConfig!=null && fixtureConfig.has("fixtureOpponentBattlefield") && !scenario.equals("card-family"))throw new IllegalArgumentException("Research opponent overrides require the card-family scenario");
        if(fixtureConfig!=null && Set.of("fixtureBattlefield","fixtureBattlefieldReady","fixtureGraveyard","fixtureOpponentGraveyard","fixtureLibrary","fixtureCounters","fixtureOpponentSpell","fixtureOpponentLands","fixtureOpponentHand","fixtureOpponentSpellPlan","fixtureLocalLife","fixtureCommander").stream().anyMatch(fixtureConfig::has) && (!scenario.equals("card-family") || !manifest.has("researchOnly") || !manifest.get("researchOnly").getAsBoolean()))throw new IllegalArgumentException("Initial zone fixtures require an explicit research-only card-family scenario");
        if(fixtureConfig!=null && fixtureConfig.has("fixtureBattlefieldReady") && (!fixtureConfig.get("fixtureBattlefieldReady").isJsonPrimitive() || !fixtureConfig.getAsJsonPrimitive("fixtureBattlefieldReady").isBoolean()))throw new IllegalArgumentException("Initial ready-state fixture must be boolean");
        if(fixtureConfig!=null && (fixtureConfig.has("fixtureActiveSeat") || fixtureConfig.has("fixtureOpponentPolicy"))){
            if(!researchAdmission || !scenario.equals("card-family"))throw new IllegalArgumentException("Starting turn policy requires the research card-family scenario");
            if(fixtureConfig.has("fixtureActiveSeat") && (!fixtureConfig.get("fixtureActiveSeat").isJsonPrimitive() || !fixtureConfig.getAsJsonPrimitive("fixtureActiveSeat").isNumber() || !Set.of("1","2").contains(fixtureConfig.get("fixtureActiveSeat").getAsString())))throw new IllegalArgumentException("Initial active seat must be 1 or 2");
            if(fixtureConfig.has("fixtureOpponentPolicy")){
                String policy=fixtureConfig.get("fixtureOpponentPolicy").getAsString();if(!Set.of("passive","attack-all","block-all").contains(policy))throw new IllegalArgumentException("Unknown research opponent policy");researchOpponentAttackAll=policy.equals("attack-all");researchOpponentBlockAll=policy.equals("block-all");
            }
        }
        arenaBrawl=scenario.equals("brawl-duel");commanderPod=scenario.equals("commander-pod");commanderMode=scenario.equals("commander-duel") || commanderPod;
        if(!Set.of("coin-toss","local-first").contains(startingPlayerPolicy))throw new IllegalArgumentException("Unknown starting-player policy");
        if(!Set.of("starter","attack-open","attack-multi","attack-blocked","defend","duel","mixed-duel","opening-duel","spell-duel","trigger-duel","trigger-orator","trigger-orator-double","hare-chain","blue-duel","blue-bounce","blue-wrong-color","custom-duel","brawl-duel","commander-duel","commander-pod","card-family","counter-ready","counter-ready-white","counter-ready-idle","defend-arrow","lethal-win","defend-lethal","discard","vanilla-costs","defend-ox","attack-swift","attack-double-blocked","draw-ready","draw-wrong-color").contains(scenario))throw new IllegalArgumentException("Unsupported scenario: "+scenario);
        if(scenario.equals("custom-duel") || commanderGame()){validateDeck(localDeck);if(opponentDeck==null)opponentDeck=localDeck.deepCopy();validateDeck(opponentDeck);if(commanderGame()){String format=commanderMode?"commander-40":"arena-brawl";if(!localDeck.has("format") || !opponentDeck.has("format") || !format.equals(localDeck.get("format").getAsString()) || !format.equals(opponentDeck.get("format").getAsString()))throw new IllegalArgumentException("Commander queue and both deck policies must match");}else if(localDeck.has("format") || opponentDeck.has("format"))throw new IllegalArgumentException("Commander decks require their matching scenario");}
        else if(localDeck!=null || opponentDeck!=null)throw new IllegalArgumentException("Imported decks require custom-duel");
        if(commanderPod){
            if(podOpponentDecks==null){podOpponentDecks=new JsonArray();for(int i=0;i<3;i++)podOpponentDecks.add(opponentDeck.deepCopy());}
            if(podOpponentDecks.size()!=3)throw new IllegalArgumentException("Commander pod requires exactly three opponent decks");
            for(JsonElement item:podOpponentDecks){if(!item.isJsonObject())throw new IllegalArgumentException("Pod opponent deck must be an object");validateDeck(item.getAsJsonObject());if(!"commander-40".equals(item.getAsJsonObject().get("format").getAsString()))throw new IllegalArgumentException("Every pod deck must use Commander policy");}
        }else if(podOpponentDecks!=null)throw new IllegalArgumentException("Multiple opponent decks require Commander pod mode");
        Files.createDirectories(ipc.resolve("requests"));Files.createDirectories(ipc.resolve("responses"));
        if(!warmResearch){
            GuiBase.setInterface(new GuiDesktop(){@Override public String getAssetsDir(){return runtime.toString()+File.separator;}});
            FModel.initialize(null,null);
        }
        Set<String> sourceNames=new LinkedHashSet<>(ADMITTED_CARDS);sourceNames.addAll(BRAWL_COMMANDERS);
        for(String name:sourceNames){var paper=Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(name),"Source card missing: "+name);int mask=0;for(String symbol:COLOR_IDENTITIES.get(name))mask|=switch(symbol){case "W"->1;case "U"->2;case "B"->4;case "R"->8;case "G"->16;default->throw new IllegalArgumentException("Unsupported identity");};if(mask!=paper.getRules().getColorIdentity().getColor())throw new IllegalArgumentException("Source color identity differs from admission metadata: "+name);}
        if(randomSeed!=null)forge.util.MyRandom.setRandom(new Random(randomSeed));
        GameRules rules=new GameRules(GameType.Constructed);rules.setPlayForAnte(false);
        if(commanderGame())rules.setAppliedVariants(EnumSet.of(commanderMode?GameType.Commander:GameType.Brawl));
        if(normalGame())rules.setGamesPerMatch(1);
        List<RegisteredPlayer> players=new ArrayList<>();
        for(String name:commanderPod?new String[]{"Local Player","Bot 1","Bot 2","Bot 3"}:new String[]{"Local Player","Opponent"}){
            Deck deck=new Deck("Local vanilla practice deck");
            if(scenario.equals("custom-duel") || commanderGame()){
                JsonObject imported=players.isEmpty()?localDeck:commanderPod?podOpponentDecks.get(players.size()-1).getAsJsonObject():opponentDeck;
                for(JsonElement item:imported.getAsJsonArray("cards")){JsonObject entry=item.getAsJsonObject();String cardName=entry.get("name").getAsString();deck.getMain().add(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(cardName),"Forge card missing: "+cardName),entry.get("count").getAsInt());}
                if(commanderGame())deck.getOrCreate(DeckSection.Commander).add(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(imported.getAsJsonObject("commander").get("name").getAsString())),1);
            }else if(normalGame()){
                String[] names=scenario.equals("blue-duel")?new String[]{"Plains","Island","Savannah Lions","Yoked Ox","Oreskos Swiftclaw","Divine Arrow","Impassioned Orator","Unsummon"}:scenario.equals("trigger-duel")?new String[]{"Plains","Savannah Lions","Yoked Ox","Oreskos Swiftclaw","Divine Arrow","Impassioned Orator"}:scenario.equals("spell-duel")?new String[]{"Plains","Savannah Lions","Yoked Ox","Oreskos Swiftclaw","Divine Arrow"}:new String[]{"Plains","Savannah Lions","Yoked Ox","Oreskos Swiftclaw"};
                for(String cardName:names){int count=scenario.equals("blue-duel")?(cardName.equals("Plains") || cardName.equals("Island")?12:6):cardName.equals("Plains")?24:scenario.equals("trigger-duel")?(cardName.equals("Yoked Ox") || cardName.equals("Divine Arrow")?6:8):scenario.equals("spell-duel")?9:12;deck.getMain().add(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(cardName)),count);}
            }
            RegisteredPlayer registered=commanderGame()?RegisteredPlayer.forVariants(commanderPod?4:2,EnumSet.of(commanderMode?GameType.Commander:GameType.Brawl),deck,Collections.emptyList(),false,Collections.emptyList(),new forge.deck.CardPool()):new RegisteredPlayer(deck);
            players.add(registered.setPlayer(new LocalSeat(name,players.isEmpty())));
        }
        Match match=new Match(rules,players,"Arena local practice");
        game=match.createGame();seatPlayers.clear();seatPlayers.addAll(game.getPlayers());local=seatPlayers.get(0);opponent=seatPlayers.get(1);
        priorityChecks=game.getPhaseHandler().getClass().getDeclaredMethod("checkStateBasedEffects");priorityChecks.setAccessible(true);
        game.subscribeToEvents(new EventRecorder());
        if(normalGame()){
            StaticData.instance().setMulliganRule(MulliganDefs.MulliganRule.London);
            StaticData.instance().setFilteredHandsEnabled(false);
            currentRequest=new JsonObject();currentRequest.addProperty("id","startup");
            try(PrintWriter log=new PrintWriter(Files.newBufferedWriter(ipc.resolve("engine-journal.jsonl")))){
                journal=log;
                try{match.startGame(game);}catch(StopRequested ex){System.exit(0);}
                finishLiveRequests();write(ipc.resolve("state.json"),snapshot());
                journal.println(new Gson().toJson(Map.of("event","normal-game-finished","state",snapshot())));journal.flush();
            }
        }
        if(!normalGame()){
        game.setAge(GameStage.Play);
        for(Player p:game.getPlayers())p.setLife(20,null);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1,local,false,1);
        game.getPhaseHandler().setPriority(local);game.getPhaseHandler().onStackResolved();
        PaperCard printing=Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Plains"));
        for(int i=0;i<2;i++){Card c=Card.fromPaperCard(printing,local);local.getZone(ZoneType.Hand).add(c);}
        Card lion=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Savannah Lions")),local);local.getZone(ZoneType.Hand).add(lion);
        if(!scenario.equals("starter") && !aiDuel() && !scenario.equals("discard") && !scenario.equals("vanilla-costs")){
            Card ready=Card.fromPaperCard(lion.getPaperCard(),local);local.getZone(ZoneType.Battlefield).add(ready);ready.setSickness(false);
            if(scenario.equals("attack-multi"))for(int i=0;i<2;i++){Card extra=Card.fromPaperCard(lion.getPaperCard(),local);local.getZone(ZoneType.Battlefield).add(extra);extra.setSickness(false);}
            if(scenario.contains("blocked") || scenario.startsWith("defend")){
                Card enemy=Card.fromPaperCard(lion.getPaperCard(),opponent);opponent.getZone(ZoneType.Battlefield).add(enemy);enemy.setSickness(false);
                if(scenario.startsWith("defend")){game.getPhaseHandler().devModeSet(PhaseType.MAIN1,opponent,false,2);game.getPhaseHandler().setPriority(local);}
            }
        }
        for(Player p:game.getPlayers())for(int i=0;i<20;i++){Card c=Card.fromPaperCard(printing,p);p.getZone(ZoneType.Library).add(c);}
        if(aiDuel()){
            for(Player p:new Player[]{local,opponent}){
                // Initial fixture construction only; no gameplay zone changes are bypassed.
                p.getZone(ZoneType.Hand).removeAllCards(true);p.getZone(ZoneType.Library).removeAllCards(true);
                for(int i=0;i<6;i++){String name=i<3?"Plains":i==3 || !scenario.equals("mixed-duel")?"Savannah Lions":i==4?"Yoked Ox":"Oreskos Swiftclaw";Card c=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(name)),p);p.getZone(ZoneType.Hand).add(c);}
                String[] sequence=scenario.equals("mixed-duel")?new String[]{"Plains","Savannah Lions","Plains","Oreskos Swiftclaw","Plains","Yoked Ox"}:new String[]{"Plains","Savannah Lions"};
                for(int i=0;i<24;i++){Card c=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(sequence[i%sequence.length])),p);p.getZone(ZoneType.Library).add(c);}
            }
        }
        if(scenario.equals("lethal-win"))opponent.setLife(2,null);
        if(scenario.equals("defend-lethal"))local.setLife(2,null);
        if(scenario.equals("discard"))for(int i=0;i<6;i++)local.getZone(ZoneType.Hand).add(Card.fromPaperCard(printing,local));
        if(scenario.equals("vanilla-costs")){
            local.getZone(ZoneType.Battlefield).add(Card.fromPaperCard(printing,local));
            for(String name:new String[]{"Yoked Ox","Oreskos Swiftclaw"})local.getZone(ZoneType.Hand).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(name)),local));
        }
        if(scenario.equals("defend-ox") || scenario.equals("attack-swift")){
            local.getZone(ZoneType.Battlefield).removeAllCards(true);
            String name=scenario.equals("defend-ox")?"Yoked Ox":"Oreskos Swiftclaw";
            Card ready=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(name)),local);local.getZone(ZoneType.Battlefield).add(ready);ready.setSickness(false);
        }
        if(scenario.equals("defend-arrow")){
            local.getZone(ZoneType.Hand).removeAllCards(true);local.getZone(ZoneType.Hand).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Divine Arrow")),local));
            for(int i=0;i<2;i++)local.getZone(ZoneType.Battlefield).add(Card.fromPaperCard(printing,local));
            Card idle=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Yoked Ox")),opponent);opponent.getZone(ZoneType.Battlefield).add(idle);idle.setSickness(true);
        }
        if(scenario.equals("attack-double-blocked") || scenario.equals("defend") && fixtureConfig!=null && fixtureConfig.has("fixtureAttacker")){
            local.getZone(ZoneType.Hand).removeAllCards(true);local.getZone(ZoneType.Battlefield).removeAllCards(true);opponent.getZone(ZoneType.Battlefield).removeAllCards(true);
            String attackName=fixtureConfig!=null && fixtureConfig.has("fixtureAttacker")?fixtureConfig.get("fixtureAttacker").getAsString():"Oreskos Swiftclaw";
            List<String> blockNames=new ArrayList<>(List.of("Savannah Lions","Yoked Ox"));
            if(fixtureConfig!=null && fixtureConfig.has("fixtureBlockers")){blockNames.clear();for(var name:fixtureConfig.getAsJsonArray("fixtureBlockers"))blockNames.add(name.getAsString());}
            if(!ADMITTED_CARDS.contains(attackName) || blockNames.size()!=2 || blockNames.stream().anyMatch(n->!ADMITTED_CARDS.contains(n)))throw new IllegalArgumentException("Combat fixture needs admitted source identities and two blockers");
            Player attackingPlayer=scenario.equals("defend")?opponent:local,defendingPlayer=scenario.equals("defend")?local:opponent;
            Card attacker=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(attackName)),attackingPlayer);attackingPlayer.getZone(ZoneType.Battlefield).add(attacker);attacker.setSickness(false);
            for(String name:blockNames){Card blocker=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(name)),defendingPlayer);defendingPlayer.getZone(ZoneType.Battlefield).add(blocker);blocker.setSickness(false);}
        }
        if(scenario.equals("draw-ready") || scenario.equals("draw-wrong-color")){
            local.getZone(ZoneType.Hand).removeAllCards(true);local.getZone(ZoneType.Battlefield).removeAllCards(true);local.getZone(ZoneType.Library).removeAllCards(true);opponent.getZone(ZoneType.Battlefield).removeAllCards(true);
            local.getZone(ZoneType.Hand).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Quick Study")),local));
            for(int i=0;i<6;i++)local.getZone(ZoneType.Hand).add(Card.fromPaperCard(printing,local));
            for(String land:new String[]{"Plains","Plains",scenario.equals("draw-ready")?"Island":"Plains"})local.getZone(ZoneType.Battlefield).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(land)),local));
            for(String name:new String[]{"Island","Savannah Lions"})local.getZone(ZoneType.Library).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(name)),local));
        }
        if(scenario.startsWith("counter-ready")){
            local.getZone(ZoneType.Hand).removeAllCards(true);local.getZone(ZoneType.Battlefield).removeAllCards(true);opponent.getZone(ZoneType.Hand).removeAllCards(true);opponent.getZone(ZoneType.Battlefield).removeAllCards(true);
            local.getZone(ZoneType.Hand).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Essence Scatter")),local));
            for(String land:new String[]{"Plains",scenario.equals("counter-ready-white")?"Plains":"Island"})local.getZone(ZoneType.Battlefield).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(land)),local));
            opponent.getZone(ZoneType.Hand).add(Card.fromPaperCard(lion.getPaperCard(),opponent));opponent.getZone(ZoneType.Battlefield).add(Card.fromPaperCard(printing,opponent));
            Card idle=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Yoked Ox")),opponent);opponent.getZone(ZoneType.Battlefield).add(idle);idle.setSickness(false);
            game.getPhaseHandler().devModeSet(PhaseType.MAIN1,opponent,false,2);game.getPhaseHandler().setPriority(opponent);
            if(!scenario.equals("counter-ready-idle")){
                Card casting=opponent.getCardsIn(ZoneType.Hand).getFirst();SpellAbility spell=casting.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();spell.setActivatingPlayer(opponent);
                if(!ComputerUtil.playStack(spell,opponent,game))throw new IllegalStateException("Counter fixture could not pay for its actual creature spell");
            }
            game.getPhaseHandler().setPriority(local);game.getPhaseHandler().onStackResolved();
        }
        if(scenario.equals("blue-bounce") || scenario.equals("blue-wrong-color")){
            local.getZone(ZoneType.Hand).removeAllCards(true);local.getZone(ZoneType.Battlefield).removeAllCards(true);
            for(int i=0;i<2;i++)local.getZone(ZoneType.Hand).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Unsummon")),local));
            for(String land:new String[]{"Plains",scenario.equals("blue-bounce")?"Island":"Plains",scenario.equals("blue-bounce")?"Island":"Plains","Plains"})local.getZone(ZoneType.Battlefield).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(land)),local));
            Card friendly=Card.fromPaperCard(lion.getPaperCard(),local);local.getZone(ZoneType.Battlefield).add(friendly);friendly.setSickness(false);
            Card enemy=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Yoked Ox")),opponent);opponent.getZone(ZoneType.Battlefield).add(enemy);enemy.setSickness(false);
        }
        if(scenario.startsWith("trigger-orator")){
            local.getZone(ZoneType.Hand).removeAllCards(true);local.getZone(ZoneType.Battlefield).removeAllCards(true);
            int count=scenario.equals("trigger-orator-double")?2:1;
            for(int i=0;i<count;i++)local.getZone(ZoneType.Hand).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Impassioned Orator")),local));
            local.getZone(ZoneType.Hand).add(Card.fromPaperCard(lion.getPaperCard(),local));
            for(int i=0;i<count*2+1;i++)local.getZone(ZoneType.Battlefield).add(Card.fromPaperCard(printing,local));
        }
        }
        if(scenario.equals("hare-chain")){
            local.getZone(ZoneType.Hand).removeAllCards(true);local.getZone(ZoneType.Battlefield).removeAllCards(true);
            for(int i=0;i<3;i++)local.getZone(ZoneType.Hand).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Hare Apparent")),local));
            local.getZone(ZoneType.Hand).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Unsummon")),local));
            for(int i=0;i<4;i++)local.getZone(ZoneType.Battlefield).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Island")),local));
            for(int i=0;i<6;i++)local.getZone(ZoneType.Battlefield).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard("Plains")),local));
        }
        if(scenario.equals("card-family")){
            researchOpponentSpellPlan.clear();
            if(fixtureConfig.has("fixtureLocalLife")){int life=choiceInteger(fixtureConfig,"fixtureLocalLife");if(!fullHumanChoices || life<1 || life>200)throw new IllegalArgumentException("Research initial life must be within 1..200");local.setLife(life,null);}
            local.getZone(ZoneType.Hand).removeAllCards(true);local.getZone(ZoneType.Battlefield).removeAllCards(true);opponent.getZone(ZoneType.Battlefield).removeAllCards(true);
            JsonArray hand=fixtureConfig.getAsJsonArray("fixtureHand"),lands=fixtureConfig.getAsJsonArray("fixtureLands");
            if(hand==null || hand.size()>8 || lands==null || lands.size()>100)throw new IllegalArgumentException("Bounded fixture requires at most eight hand cards and 100 lands");
            for(var name:hand){String n=name.getAsString();if(!ADMITTED_CARDS.contains(n))throw new IllegalArgumentException("Fixture card is not in the research policy: "+n);local.getZone(ZoneType.Hand).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(n)),local));}
            for(var name:lands){String n=name.getAsString();if(!MANA_COLORS.containsKey(n))throw new IllegalArgumentException("Fixture land needs a bound native mana ability");Card c=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(n)),local);local.getZone(ZoneType.Battlefield).add(c);}
            if(fixtureConfig.has("fixtureCommander")){
                String name=fixtureConfig.get("fixtureCommander").getAsString();
                if(!fullHumanChoices || !BRAWL_COMMANDERS.contains(name))throw new IllegalArgumentException("Initial commander needs an admitted original commander identity");
                Card c=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(name)),local);c.setCommander(true);local.addCommander(c);local.initCommanderColor(c);local.getZone(ZoneType.Command).add(c);
            }
            if(fixtureConfig.has("fixtureLibrary")){
                JsonArray names=fixtureConfig.getAsJsonArray("fixtureLibrary");if(names.size()>100)throw new IllegalArgumentException("Initial library fixture is bounded to100 cards");
                List<Card> seeded=new ArrayList<>();for(JsonElement value:names){String name=value.getAsString();if(!ADMITTED_CARDS.contains(name))throw new IllegalArgumentException("Unmapped initial library card: "+name);seeded.add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(name)),local));}
                local.getZone(ZoneType.Library).removeAllCards(true);for(Card card:seeded)local.getZone(ZoneType.Library).add(card);
            }
            // Seed only the starting environment. Effects and zone changes after
            // this point must occur through normal Forge actions and rules.
            for(String key:List.of("fixtureBattlefield","fixtureGraveyard","fixtureOpponentGraveyard")){
                JsonArray names=fixtureConfig.getAsJsonArray(key);if(names==null)continue;
                if(names.size()>(key.equals("fixtureBattlefield")?8:40))throw new IllegalArgumentException("Initial zone fixture exceeds its research bound: "+key);
                Player owner=key.equals("fixtureOpponentGraveyard")?opponent:local;
                ZoneType zone=key.equals("fixtureBattlefield")?ZoneType.Battlefield:ZoneType.Graveyard;
                for(var value:names){String n=value.getAsString();if(!ADMITTED_CARDS.contains(n))throw new IllegalArgumentException("Unmapped initial research card: "+n);Card c=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(n)),owner);if(zone==ZoneType.Battlefield && !c.isCreature() && !fullHumanChoices)throw new IllegalArgumentException("Initial research battlefield override supports creatures only");owner.getZone(zone).add(c);if(zone==ZoneType.Battlefield && fixtureConfig.has("fixtureBattlefieldReady") && fixtureConfig.get("fixtureBattlefieldReady").getAsBoolean())c.setSickness(false);}
            }
            JsonArray enemies=fixtureConfig.getAsJsonArray("fixtureOpponentBattlefield");
            if(fixtureConfig.has("fixtureOpponentHand")){
                JsonElement raw=fixtureConfig.get("fixtureOpponentHand");if(!raw.isJsonArray() || raw.getAsJsonArray().size()>8)throw new IllegalArgumentException("Initial opponent hand fixture is bounded to eight cards");
                List<Card> cards=new ArrayList<>();for(JsonElement value:raw.getAsJsonArray()){
                    if(!value.isJsonPrimitive() || !value.getAsJsonPrimitive().isString() || !ADMITTED_CARDS.contains(value.getAsString()))throw new IllegalArgumentException("Unmapped initial opponent hand identity");
                    cards.add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(value.getAsString())),opponent));
                }
                opponent.getZone(ZoneType.Hand).removeAllCards(true);for(Card card:cards)opponent.getZone(ZoneType.Hand).add(card);
            }
            if(fixtureConfig.has("fixtureOpponentSpellPlan")){
                JsonArray plan=fixtureConfig.getAsJsonArray("fixtureOpponentSpellPlan");if(!fullHumanChoices || plan.size()>8)throw new IllegalArgumentException("Scripted opponent research plan must have at most eight spells");
                Map<String,Long> available=new HashMap<>();for(Card c:opponent.getCardsIn(ZoneType.Hand))available.merge(c.getName(),1L,Long::sum);
                for(JsonElement item:plan){String name=item.getAsString();if(available.getOrDefault(name,0L)<1)throw new IllegalArgumentException("Scripted opponent lacks an initial hand card: "+name);available.merge(name,-1L,Long::sum);researchOpponentSpellPlan.addLast(name);}
            }
            if(enemies!=null){
                if(enemies.size()>8)throw new IllegalArgumentException("Research opponent fixture is bounded to eight cards");
                for(var name:enemies){String n=name.getAsString();if(!ADMITTED_CARDS.contains(n))throw new IllegalArgumentException("Unmapped research opponent card");Card c=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(n)),opponent);opponent.getZone(ZoneType.Battlefield).add(c);c.setSickness(false);}
            }
            if(fixtureConfig.has("fixtureCounters")){
                JsonArray values=fixtureConfig.getAsJsonArray("fixtureCounters");if(values.size()>24)throw new IllegalArgumentException("Initial counter fixture is bounded to24 entries");
                Set<String> seeded=new HashSet<>();
                for(JsonElement raw:values){JsonObject value=raw.getAsJsonObject();choiceFields(value,"seat","cardName","occurrence","type","count");
                    int seat=choiceInteger(value,"seat"),occurrence=choiceInteger(value,"occurrence"),count=choiceInteger(value,"count");
                    if((seat!=1 && seat!=2) || occurrence<0 || count<1 || count>99)throw new IllegalArgumentException("Invalid initial counter fixture bounds");
                    CounterType type=CounterEnumType.valueOf(value.get("type").getAsString());Player owner=seat==1?local:opponent;
                    List<Card> targets=new ArrayList<>();for(Card card:owner.getCardsIn(ZoneType.Battlefield))if(card.getName().equals(value.get("cardName").getAsString()))targets.add(card);
                    if(occurrence>=targets.size())throw new IllegalArgumentException("Initial counter fixture has no matching permanent");Card target=targets.get(occurrence);
                    if(!seeded.add(target.getId()+":"+counterKey(type)))throw new IllegalArgumentException("Duplicate initial counter fixture");
                    target.setCounters(type,count);
                }
            }
            if(fixtureConfig.has("fixtureOpponentSpell")){
                String name=fixtureConfig.get("fixtureOpponentSpell").getAsString();if(!ADMITTED_CARDS.contains(name))throw new IllegalArgumentException("Unmapped initial opponent spell");
                JsonArray mana=fixtureConfig.getAsJsonArray("fixtureOpponentLands");if(mana==null || mana.size()>20)throw new IllegalArgumentException("Opponent spell needs bounded initial mana sources");
                for(JsonElement raw:mana){String land=raw.getAsString();if(!Set.of("Plains","Island","Swamp","Mountain","Forest").contains(land))throw new IllegalArgumentException("Opponent spell fixture supports basic mana only");opponent.getZone(ZoneType.Battlefield).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(land)),opponent));}
                Card source=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(name)),opponent);opponent.getZone(ZoneType.Hand).add(source);
                SpellAbility spell=source.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();spell.setActivatingPlayer(opponent);
                game.getPhaseHandler().devModeSet(PhaseType.MAIN1,opponent,false,2);game.getPhaseHandler().setPriority(opponent);
                if(fixtureConfig.has("fixtureOpponentTargets")){
                    JsonArray targets=fixtureConfig.getAsJsonArray("fixtureOpponentTargets");if(!spell.usesTargeting() || targets.size()>8)throw new IllegalArgumentException("Opponent target fixture needs a targeting spell and at most eight targets");
                    spell.resetTargets();
                    for(JsonElement raw:targets){
                        JsonObject target=raw.getAsJsonObject();choiceFields(target,"seat","cardName","occurrence");int seat=choiceInteger(target,"seat"),occurrence=choiceInteger(target,"occurrence");
                        if((seat!=1 && seat!=2) || occurrence<0)throw new IllegalArgumentException("Invalid opponent target fixture selection");
                        List<Card> candidates=new ArrayList<>();for(Card c:(seat==1?local:opponent).getCardsIn(ZoneType.Battlefield))if(c.getName().equals(target.get("cardName").getAsString()))candidates.add(c);
                        if(occurrence>=candidates.size() || !spell.canTarget(candidates.get(occurrence)))throw new IllegalArgumentException("Opponent initial target violates original Forge restrictions");
                        spell.getTargets().add(candidates.get(occurrence));
                    }
                    if(!spell.isTargetNumberValid())throw new IllegalArgumentException("Opponent initial target count violates original Forge restrictions");
                }
                if(!ComputerUtil.playStack(spell,opponent,game))throw new IllegalArgumentException("Initial opponent spell could not really pay its cost");
                game.getPhaseHandler().setPriority(local);game.getPhaseHandler().onStackResolved();
            }
            if(fixtureConfig.has("fixtureActiveSeat") && fixtureConfig.get("fixtureActiveSeat").getAsInt()==2){game.getPhaseHandler().devModeSet(PhaseType.MAIN1,opponent,false,2);game.getPhaseHandler().setPriority(local);game.getPhaseHandler().onStackResolved();}
        }
        write(ipc.resolve("state.json"),snapshot());
        try(PrintWriter log=new PrintWriter(Files.newBufferedWriter(ipc.resolve("engine-journal.jsonl"),StandardOpenOption.CREATE,normalGame()?StandardOpenOption.APPEND:StandardOpenOption.TRUNCATE_EXISTING))) {
            journal=log;
            journal.println(new Gson().toJson(Map.of("event",normalGame()?"terminal-service-ready":"ready","state",snapshot())));journal.flush();
            while(!Files.exists(ipc.resolve("stop.request"))) {
                try(var paths=Files.list(ipc.resolve("requests"))) {
                    for(Path path:paths.filter(p->p.toString().endsWith(".json")).sorted().toList()) {
                        JsonObject request=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
                        String id=request.get("id").getAsString();if(!id.matches("[a-zA-Z0-9_-]{1,80}"))throw new IllegalArgumentException("Invalid request ID");
                        JsonObject response=acceptedRequests.get(id);
                        if(response!=null && !requestBodies.get(id).equals(request)) {
                            response=new JsonObject();response.addProperty("id",id);response.addProperty("session",SESSION);response.addProperty("accepted",false);response.addProperty("reason","request ID reused with different payload");response.add("state",JSON.toJsonTree(snapshot()));
                        }
                        if(response==null){currentRequest=request;response=handle(request);remember(request,response);
                            for(JsonObject submission:deferredSubmissions){boolean conceded=submission.get("op").getAsString().equals("concede") && game.isGameOver() && local.conceded();boolean accepted=conceded || response.get("accepted").getAsBoolean();remember(submission,response(submission,accepted,conceded?"Forge processed local concession":accepted?"Forge completed submitted declaration":response.get("reason").getAsString()));}
                            deferredSubmissions.clear();currentRequest=null;
                        } else write(ipc.resolve("responses").resolve(id+".json"),response);
                        write(ipc.resolve("state.json"),snapshot());Files.delete(path);
                    }
                }
                Thread.sleep(40);
            }
        }
        if(!warmResearch)System.exit(0);
    }
}
