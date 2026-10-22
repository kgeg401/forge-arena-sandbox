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
    static Player opponent;
    static JsonObject currentRequest;
    static JsonObject decision;
    static int discardCount;
    static final List<JsonObject> deferredSubmissions = new ArrayList<>();
    static PrintWriter journal;
    static String scenario="starter";
    static final Set<String> ADMITTED_CARDS=new LinkedHashSet<>();
    static final Set<String> BRAWL_COMMANDERS=new LinkedHashSet<>();
    static final Map<String,String> CARD_COLORS=new LinkedHashMap<>();
    static final Map<String,String> MANA_COLORS=new LinkedHashMap<>();
    static final Map<String,Set<String>> COLOR_IDENTITIES=new LinkedHashMap<>();
    static final Map<String,JsonObject> ABILITY_BINDINGS=new LinkedHashMap<>();
    static boolean arenaBrawl;
    static String unsupportedDecision="";
    static void loadAdmission(JsonObject manifest){
        if(!manifest.has("admissionSchema") || manifest.get("admissionSchema").getAsInt()!=1)throw new IllegalArgumentException("Regenerate runtime card admission metadata for this engine");
        var next=new LinkedHashSet<String>();var commanders=new LinkedHashSet<String>();var colors=new LinkedHashMap<String,String>();var identities=new LinkedHashMap<String,Set<String>>();var bindings=new LinkedHashMap<String,JsonObject>();
        for(var entry:manifest.getAsJsonObject("cards").entrySet()){
            var card=entry.getValue().getAsJsonObject();
            if(!card.has("admitted") || !card.get("admitted").isJsonPrimitive() || !card.getAsJsonPrimitive("admitted").isBoolean())throw new IllegalArgumentException("Card admission must be explicit boolean: "+entry.getKey());
            if(!card.has("token") || !card.get("token").isJsonPrimitive() || !card.getAsJsonPrimitive("token").isBoolean())throw new IllegalArgumentException("Token identity must be an explicit boolean: "+entry.getKey());
            if(card.get("admitted").getAsBoolean() && !card.get("token").getAsBoolean())next.add(entry.getKey());
            if(card.has("commanderAdmitted")){
                if(!card.get("commanderAdmitted").isJsonPrimitive() || !card.getAsJsonPrimitive("commanderAdmitted").isBoolean())throw new IllegalArgumentException("Commander admission must be boolean");
                if(card.get("commanderAdmitted").getAsBoolean()){
                    if(card.get("token").getAsBoolean() || !card.getAsJsonArray("supertypes").contains(new JsonPrimitive("Legendary")))throw new IllegalArgumentException("Commander requires a legendary primary mapping");
                    commanders.add(entry.getKey());
                }
            }
            if(card.has("color"))colors.put(entry.getKey(),card.get("color").getAsString());
            Set<String> identity=new LinkedHashSet<>();if(card.has("colorIdentity"))for(var c:card.getAsJsonArray("colorIdentity")){String value=c.getAsString();if(!Set.of("W","U","B","R","G").contains(value))throw new IllegalArgumentException("Unknown color identity symbol");identity.add(value);}identities.put(entry.getKey(),identity);
            if(card.has("abilityBindings"))bindings.put(entry.getKey(),card.getAsJsonObject("abilityBindings").deepCopy());
        }
        MANA_COLORS.clear();
        for(var entry:manifest.getAsJsonObject("cards").entrySet())if(entry.getValue().getAsJsonObject().has("manaColor"))MANA_COLORS.put(entry.getKey(),entry.getValue().getAsJsonObject().get("manaColor").getAsString());
        ADMITTED_CARDS.clear();ADMITTED_CARDS.addAll(next);
        BRAWL_COMMANDERS.clear();BRAWL_COMMANDERS.addAll(commanders);CARD_COLORS.clear();CARD_COLORS.putAll(colors);
        COLOR_IDENTITIES.clear();COLOR_IDENTITIES.putAll(identities);ABILITY_BINDINGS.clear();ABILITY_BINDINGS.putAll(bindings);
    }
    static JsonObject localDeck,opponentDeck;
    static JsonObject fixtureConfig;
    static boolean normalGame(){return scenario.equals("opening-duel") || scenario.equals("spell-duel") || scenario.equals("trigger-duel") || scenario.equals("blue-duel") || scenario.equals("custom-duel") || scenario.equals("brawl-duel");}
    static void validateDeck(JsonObject deck){
        if(deck==null || !deck.has("cards") || !deck.get("cards").isJsonArray())throw new IllegalArgumentException("Imported deck requires a cards array");
        boolean brawl=deck.has("format") && deck.get("format").getAsString().equals("arena-brawl");
        if(deck.has("format") && !brawl)throw new IllegalArgumentException("Unknown imported deck format");
        String commander="";
        if(brawl){
            if(!deck.has("commander") || !deck.get("commander").isJsonObject())throw new IllegalArgumentException("Brawl requires one commander object");
            var c=deck.getAsJsonObject("commander");commander=c.get("name").getAsString();
            if(!BRAWL_COMMANDERS.contains(commander) || !c.get("count").isJsonPrimitive() || !c.getAsJsonPrimitive("count").isNumber() || !c.get("count").getAsString().equals("1"))throw new IllegalArgumentException("Unverified or invalid Brawl commander");
        }else if(deck.has("commander"))throw new IllegalArgumentException("Commander requires arena-brawl format");
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
    static int damageSourceId,damageTotal;
    static int commanderDecisionId;
    static String commanderDecisionZone;
    static final Map<Integer,List<Integer>> spellTargets=new HashMap<>();
    static final Map<String,String> failedPlays=new HashMap<>();
    static class StopRequested extends RuntimeException {}
    static String phaseName(){return game.getPhaseHandler().getPhase()==null?"PREGAME":game.getPhaseHandler().getPhase().name();}
    static final List<Map<String,Object>> events=new ArrayList<>();static long eventId;
    static void event(Map<String,Object> values){Map<String,Object> e=new LinkedHashMap<>(values);e.put("id",++eventId);e.put("phase",phaseName());events.add(e);if(events.size()>2048)events.remove(0);}
    public static class EventRecorder {
        @Subscribe public void sacrificed(GameEventCardSacrificed e){event(Map.of("kind","sacrificed","sourceForgeId",e.card().getId()));}
        @Subscribe public void zoneChanged(GameEventCardChangeZone e){
            var top=game.getStack().peek();
            if(e.from()==null || e.to()==null || e.from().zoneType()!=ZoneType.Stack || e.to().zoneType()!=ZoneType.Graveyard || !game.getStack().isResolving() || top==null || !top.getSourceCard().getName().equals("Essence Scatter"))return;
            for(SpellAbility target:top.getTargetChoices().getTargetSpells())if(target.getHostCard().getId()==e.card().getId())event(Map.of("kind","countered","sourceForgeId",top.getSourceCard().getId(),"targetForgeId",e.card().getId()));
        }
        @Subscribe public void lifeChanged(GameEventPlayerLivesChanged e){
            if(e.newLives()<=e.oldLives())return;
            var top=game.getStack().peek();
            int source=game.getStack().isResolving() && top!=null?(top.isSpell()?top.getSourceCard().getId():-1-top.getId()):0;
            event(Map.of("kind","life-gain","targetSeat",e.player().getId()==local.getId()?1:2,"amount",e.newLives()-e.oldLives(),"sourceStackForgeId",source));
        }
        @Subscribe public void spellCast(GameEventSpellAbilityCast e){
            List<Integer> targets=new ArrayList<>();if(e.si()!=null && e.si().getTargetCards()!=null)for(CardView c:e.si().getTargetCards())targets.add(c.getId());
            spellTargets.put(e.sa().getHostCard().getId(),List.copyOf(targets));
        }
        @Subscribe public void playerDamage(GameEventPlayerDamaged e){event(Map.of("kind","damage","sourceForgeId",e.source().getId(),"targetSeat",e.target().getId()==local.getId()?1:2,"amount",e.amount(),"combat",e.combat()));}
        @Subscribe public void cardDamage(GameEventCardDamaged e){
            // Installed card-damage events omit a combat flag. In this admitted
            // slice only Divine Arrow can deal noncombat damage; the three
            // vanilla creatures have no damage abilities.
            boolean combat=!e.source().getName().equals("Divine Arrow");
            event(Map.of("kind","damage","sourceForgeId",e.source().getId(),"targetForgeId",e.card().getId(),"amount",e.amount(),"combat",combat));
        }
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
    static class PassiveController extends PlayerControllerAi {
        private Boolean bufferedKeep;
        PassiveController(Game g,Player p,LobbyPlayer l){super(g,p,l);}
        @Override public boolean confirmAction(SpellAbility sa,PlayerActionConfirmMode mode,String message,List<String> options,Card host,Map<String,Object> params){
            Card card=sa==null?host:sa.getHostCard();
            if(arenaBrawl && getPlayer()==local && mode==PlayerActionConfirmMode.ChangeZoneToAltDestination && card!=null && card.isRealCommander() && card.getOwner()==local){
                return chooseCommanderReturn(card,card.getZone().getZoneType());
            }
            if(arenaBrawl && getPlayer()==local){unsupportedDecision="Unmapped human Brawl confirmation: "+mode+" / "+message;throw new UnsupportedOperationException(unsupportedDecision);}
            return super.confirmAction(sa,mode,message,options,host,params);
        }
        @Override public boolean confirmReplacementEffect(forge.game.replacement.ReplacementEffect effect,SpellAbility sa,GameEntity affected,String question){
            if(arenaBrawl && getPlayer()==local && affected instanceof Card card && card.isRealCommander() && card.getOwner()==local){
                Object original=sa==null?null:sa.getReplacingObject(forge.game.ability.AbilityKey.OriginalParams);
                Object destination=original instanceof Map<?,?> params?params.get(forge.game.ability.AbilityKey.Destination):null;
                if(sa!=null && "Command".equals(sa.getParam("Destination")) && "ReplacedCard".equals(sa.getParam("Defined")) && (destination==ZoneType.Hand || destination==ZoneType.Library))return chooseCommanderReturn(card,(ZoneType)destination);
                unsupportedDecision="Unmapped human commander replacement: "+question;throw new UnsupportedOperationException(unsupportedDecision);
            }
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
            if(getPlayer()==local && normalGame())return waitForPriority();
            return aiDuel() && getPlayer()!=local?super.chooseSpellAbilityToPlay():null;
        }
        @Override public boolean playChosenSpellAbility(SpellAbility chosen){
            if(getPlayer()!=local || !normalGame())return super.playChosenSpellAbility(chosen);
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
            if(getPlayer()!=local){Player chosen=super.chooseStartingPlayer(firstGame);startingSeat=chosen==local?1:2;return chosen;}
            JsonArray options=new JsonArray();for(int seat:new int[]{1,2}){JsonObject o=new JsonObject();o.addProperty("startingSeat",seat);options.add(o);}
            waitForDecision("starting_player",options,values->{
                if(values.size()!=1)throw new IllegalArgumentException("Choose exactly one starting seat");
                int seat=values.get(0).getAsJsonObject().get("startingSeat").getAsInt();if(seat!=1 && seat!=2)throw new IllegalArgumentException("Starting seat was not offered");startingSeat=seat;
            });return startingSeat==2?opponent:local;
        }
        @Override public boolean mulliganKeepHand(Player first,int cardsToReturn){
            if(getPlayer()!=local){boolean keep=super.mulliganKeepHand(first,cardsToReturn);opponentKept=keep;opponentMulligans=cardsToReturn;return keep;}
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
                keep[0]=accepted;if(!keep[0])mulligans++;
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
        @Override public void declareAttackers(Player p,Combat combat){
            if(p!=local){
                if(aiDuel()){super.declareAttackers(p,combat);return;}
                if(scenario.startsWith("defend"))for(Card c:p.getCreaturesInPlay())if(CombatUtil.canAttack(c,local))combat.addAttacker(c,local);
                return;
            }
            JsonArray options=new JsonArray();
            for(Card c:p.getCreaturesInPlay())if(CombatUtil.canAttack(c,p.getSingleOpponent())){
                JsonObject option=new JsonObject();option.addProperty("forgeId",c.getId());option.addProperty("targetSeat",2);options.add(option);
            }
            waitForDecision("attackers",options,assignments->{
                combat.clearAttackers();
                for(JsonElement e:assignments){JsonObject a=e.getAsJsonObject();if(a.get("targetSeat").getAsInt()!=0)combat.addAttacker(findCard(a.get("forgeId").getAsInt()),p.getSingleOpponent());}
                if(!CombatUtil.validateAttackers(combat)){combat.clearAttackers();throw new IllegalArgumentException("Forge rejected the complete attacker declaration");}
            });
        }
        @Override public void declareBlockers(Player p,Combat combat){
            if(p!=local){
                if(aiDuel()){super.declareBlockers(p,combat);return;}
                if(scenario.contains("blocked"))for(Card c:p.getCreaturesInPlay())for(Card a:combat.getAttackers())if(CombatUtil.canBlock(a,c,combat)){combat.addBlocker(a,c);break;}
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
            // Damage assignment is a capability, not a whitelist of creature
            // names. Keywords with different allocation rules remain explicit gaps.
            if(source.hasKeyword("Trample") || source.hasKeyword("Deathtouch") || source.hasKeyword("Banding"))throw new UnsupportedOperationException("Unmapped keyword combat damage allocation");
            if(recipients.size()<=1){Map<Card,Integer> forced=new LinkedHashMap<>();forced.put(recipients.isEmpty()?null:recipients.get(0),total);return forced;}
            if(!overrideOrder)throw new UnsupportedOperationException("Unmapped ordered combat damage choice");
            damageSourceId=source.getId();damageTotal=total;
            Map<Card,Integer> suggested=super.assignCombatDamage(source,recipients,remaining,total,defender,overrideOrder);
            JsonArray options=new JsonArray();Map<Integer,Card> offered=new LinkedHashMap<>();
            for(Card card:recipients){offered.put(card.getId(),card);JsonObject option=new JsonObject();option.addProperty("forgeId",card.getId());option.addProperty("lethalDamage",Math.max(0,card.getNetToughness()-card.getDamage()));option.addProperty("assignedDamage",suggested.getOrDefault(card,0));options.add(option);}
            Map<Card,Integer> result=new LinkedHashMap<>();
            waitForDecision("assign_damage",options,values->{
                if(values.size()!=offered.size())throw new IllegalArgumentException("Assign damage to every offered recipient, including zero allocations");
                Map<Card,Integer> selected=new LinkedHashMap<>();int sum=0;
                for(JsonElement value:values){JsonObject entry=value.getAsJsonObject();Card card=offered.get(entry.get("forgeId").getAsInt());JsonElement amount=entry.get("amount");
                    if(card==null || selected.containsKey(card))throw new IllegalArgumentException("Duplicate or unoffered damage recipient");
                    if(amount==null || !amount.isJsonPrimitive() || !amount.getAsJsonPrimitive().isNumber() || !amount.getAsString().matches("[0-9]+"))throw new IllegalArgumentException("Damage must be a nonnegative integer");
                    int count=Integer.parseInt(amount.getAsString());if(count<0 || count>total)throw new IllegalArgumentException("Damage exceeds the source total");sum+=count;selected.put(card,count);
                }
                if(sum!=total)throw new IllegalArgumentException("All combat damage must be assigned exactly once");
                result.clear();result.putAll(selected);
            });return result;
        }
    }
    static class LocalSeat extends LobbyPlayerAi {
        LocalSeat(String name){super(name,Collections.emptySet());setAiProfile("Default");}
        @Override public Player createIngamePlayer(Game g,int id){Player p=new Player(getName(),g,id);p.setFirstController(new PassiveController(g,p,this));return p;}
    }
    static Map<String,Object> card(Card c) {
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("forgeId",c.getId());result.put("arenaId",1000+c.getId());result.put("name",c.getName());result.put("zone",c.getZone().getZoneType().name());
        result.put("owner",c.getOwner()==local?1:2);result.put("controller",c.getController()==local?1:2);result.put("tapped",c.isTapped());
        result.put("power",c.getNetPower());result.put("toughness",c.getNetToughness());result.put("sick",c.isSick());result.put("damage",c.getDamage());
        result.put("token",c.isToken());result.put("colorMask",(int)c.getColor().getColor());
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
        result.put("attackTarget",combat!=null && combat.isAttacking(c)?(combat.getDefenderByAttacker(c)==local?1:2):0);
        List<Integer> blocking=new ArrayList<>();if(combat!=null)for(Card a:combat.getAttackersBlockedBy(c))blocking.add(a.getId());result.put("blocking",blocking);
        return result;
    }
    static LandAbility ability(Card c) {
        LandAbility a = new LandAbility(c,c.getCurrentState());a.setActivatingPlayer(local);return a;
    }
    static List<Object> zone(ZoneType type) {
        List<Object> result=new ArrayList<>();for(Card c:((type==ZoneType.Stack || type==ZoneType.Battlefield || type==ZoneType.Graveyard || type==ZoneType.Command || type==ZoneType.Exile)?game.getCardsIn(type):local.getCardsIn(type)))if(type==ZoneType.Command?c.isRealCommander():type!=ZoneType.Exile || c.isRealCommander() || c.isToken() || ADMITTED_CARDS.contains(c.getName()))result.add(card(c));return result;
    }
    static SpellAbility manaAbility(Card c) {
        if (!MANA_COLORS.containsKey(c.getName()) || !c.isInZone(ZoneType.Battlefield) || c.getController()!=local) return null;
        if(c.getManaAbilities().size()!=1)throw new UnsupportedOperationException("Multiple mana abilities require an explicit native choice");
        for (SpellAbility a:c.getManaAbilities()) {a.setActivatingPlayer(local);if(a.canPlay())return a;}
        return null;
    }
    static SpellAbility castAbility(Card c) {
        boolean commander=arenaBrawl && c.isRealCommander() && BRAWL_COMMANDERS.contains(c.getName());
        if ((!ADMITTED_CARDS.contains(c.getName()) && !commander) || c.isLand() || (!c.isInZone(ZoneType.Hand) && !c.isInZone(ZoneType.Graveyard) && !(commander && c.isInZone(ZoneType.Command))) || c.getController()!=local)return null;
        for(SpellAbility base:c.getSpellAbilities())if(base.isSpell()){
            base.setActivatingPlayer(local);var choices=new ArrayList<SpellAbility>();choices.add(base);
            if(c.isInZone(ZoneType.Graveyard) || commander && c.isInZone(ZoneType.Command))choices.addAll(GameActionUtil.getAlternativeCosts(base,local,false));
            for(SpellAbility a:choices){a.setActivatingPlayer(local);if(a.canPlay() && ComputerUtilCost.canPayCost(a,local,false) && (!a.usesTargeting() || a.getTargetRestrictions().getNumCandidates(a)>0))return a;}
        }
        return null;
    }
    static int nativeAbility(SpellAbility a,boolean triggered){
        var binding=ABILITY_BINDINGS.get(a.getHostCard().getName());
        if(binding==null)return 0;
        if(triggered && binding.has("trigger"))return binding.get("trigger").getAsInt();
        var activated=binding.getAsJsonObject("activated");return activated!=null && a.getApi()!=null && activated.has(a.getApi().name())?activated.get(a.getApi().name()).getAsInt():0;
    }
    static SpellAbility activatedAbility(Card c,int nativeId){
        if(!ADMITTED_CARDS.contains(c.getName()) || c.getController()!=local || !c.isInZone(ZoneType.Battlefield))return null;
        for(var a:c.getSpellAbilities())if(a.isActivatedAbility() && !a.isManaAbility() && nativeAbility(a,false)==nativeId){a.setActivatingPlayer(local);if(a.canPlay() && ComputerUtilCost.canPayCost(a,local,false) && (!a.usesTargeting() || a.getTargetRestrictions().getNumCandidates(a)>0))return a;}
        return null;
    }
    static List<Map<String,Object>> manaCost(SpellAbility ability){
        var cost=ComputerUtilMana.calculateManaCost(ability.getPayCosts(),ability,local,true,0,false).toManaCost();
        var result=new ArrayList<Map<String,Object>>();if(cost.getGenericCost()>0)result.add(Map.of("color","Generic","count",cost.getGenericCost()));
        Map<String,Integer> colors=new LinkedHashMap<>();for(var shard:cost){String color=switch(shard.toString()){case "{W}"->"White";case "{U}"->"Blue";case "{B}"->"Black";case "{R}"->"Red";case "{G}"->"Green";case "{C}"->"Colorless";default->throw new UnsupportedOperationException("Unmapped cost shard "+shard);};colors.merge(color,1,Integer::sum);}
        for(var e:colors.entrySet())result.add(Map.of("color",e.getKey(),"count",e.getValue()));return result;
    }
    static boolean selectHumanTargets(SpellAbility spell){
        if(!spell.usesTargeting())return true;
        targetSourceId=spell.getHostCard().getId();targetSourceAbilityId=nativeAbility(spell,false);targetMinimum=spell.getMinTargets();targetMaximum=spell.getMaxTargets();targetCancelled=false;
        JsonArray options=new JsonArray();
        if(spell.getHostCard().getName().equals("Essence Scatter")){
            Map<Integer,SpellAbility> offered=new LinkedHashMap<>();
            for(var entry:game.getStack())if(entry.isSpell() && spell.canTargetSpellAbility(entry.getSpellAbility())){
                SpellAbility target=entry.getSpellAbility();int id=target.getHostCard().getId();offered.put(id,target);
                JsonObject option=new JsonObject();option.addProperty("forgeId",id);option.addProperty("stackInstanceId",entry.getId());option.addProperty("targetKind","spell");options.add(option);
            }
            waitForDecision("targets",options,values->{
                if(values.size()!=1)throw new IllegalArgumentException("Choose one actual creature spell");
                int id=values.get(0).getAsJsonObject().get("forgeId").getAsInt();SpellAbility target=offered.get(id);
                boolean stillOnStack=false;for(var entry:game.getStack())if(entry.getSpellAbility()==target)stillOnStack=true;
                if(target==null || !stillOnStack || !spell.canTargetSpellAbility(target))throw new IllegalArgumentException("Forge rejected spell target");
                spell.resetTargets();spell.getTargets().add(target);
                if(!spell.isTargetNumberValid())throw new IllegalArgumentException("Forge rejected submitted spell target");
            });return !targetCancelled && !game.isGameOver() && spell.isTargetNumberValid();
        }
        Map<Integer,GameEntity> candidates=new LinkedHashMap<>();
        for(GameEntity target:spell.getTargetRestrictions().getAllCandidates(spell)){
            JsonObject o=new JsonObject();int id;
            if(target instanceof Card card){id=card.getId();o.addProperty("targetKind","card");}
            else if(target instanceof Player player){int seat=player==local?1:2;id=-1000000-seat;o.addProperty("targetKind","player");o.addProperty("targetSeat",seat);}
            else throw new UnsupportedOperationException("Unmapped target entity type");
            candidates.put(id,target);o.addProperty("forgeId",id);options.add(o);
        }
        waitForDecision("targets",options,values->{
            if(values.size()<targetMinimum || values.size()>targetMaximum)throw new IllegalArgumentException("Forge target count is outside its bounds");
            Set<Integer> unique=new HashSet<>();List<GameEntity> chosen=new ArrayList<>();
            for(JsonElement value:values){int id=value.getAsJsonObject().get("forgeId").getAsInt();if(!unique.add(id))throw new IllegalArgumentException("duplicate target");GameEntity entity=candidates.get(id);if(entity==null || !spell.canTarget(entity))throw new IllegalArgumentException("Forge rejected target");chosen.add(entity);}
            spell.resetTargets();for(GameEntity entity:chosen)spell.getTargets().add(entity);
            if(!spell.isTargetNumberValid())throw new IllegalArgumentException("Forge rejected submitted targets");
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
                                if(op.equals("play_land") && card.getController()==local && card.isInZone(ZoneType.Hand) && card.isLand() && ability(card).canPlay())selected=ability(card);
                                else if(op.equals("activate_mana"))selected=manaAbility(card);
                                else if(op.equals("cast_spell"))selected=castAbility(card);
                                else if(op.equals("activate_ability")){
                                    if(!request.has("abilityId") || !request.get("abilityId").isJsonPrimitive() || !request.getAsJsonPrimitive("abilityId").isNumber() || !request.get("abilityId").getAsString().matches("[1-9][0-9]{0,8}"))throw new IllegalArgumentException("Activation requires an exact positive integer ability identity");
                                    selected=activatedAbility(card,request.get("abilityId").getAsInt());
                                }
                                if(selected==null)throw new IllegalArgumentException("Forge rejected unavailable action at priority");
                                advance=true;
                            }
                        }catch(Exception ex){remember(request,response(request,false,ex.toString()));}
                        Files.delete(path);
                        if(advance){currentRequest=request;deferredSubmissions.add(request.deepCopy());return selected==null?null:List.of(selected);}
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
        try {
            decision=new JsonObject();decision.addProperty("kind",kind);decision.addProperty("seat",1);decision.addProperty("token",UUID.randomUUID().toString());decision.add("options",options);decision.add("assignments",new JsonArray());
            if(kind.equals("discard") || kind.startsWith("mulligan"))decision.addProperty("count",discardCount);
            if(kind.equals("legend_rule"))decision.addProperty("count",1);
            if(kind.startsWith("mulligan"))decision.addProperty("mulligans",mulligans);
            if(kind.equals("targets")){decision.addProperty("sourceForgeId",targetSourceId);decision.addProperty("sourceAbilityId",targetSourceAbilityId);decision.addProperty("minTargets",targetMinimum);decision.addProperty("maxTargets",targetMaximum);}
            if(kind.equals("assign_damage")){decision.addProperty("sourceForgeId",damageSourceId);decision.addProperty("totalDamage",damageTotal);decision.addProperty("policy","Installed Forge unordered vanilla combat; no trample, deathtouch, replacements or legacy damage order");}
            if(kind.equals("commander_return")){decision.addProperty("sourceForgeId",commanderDecisionId);decision.addProperty("fromZone",findCard(commanderDecisionId).getZone().getZoneType().name());decision.addProperty("choiceZone",commanderDecisionZone);}
            finishLiveRequests();
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
                                    targetCancelled=true;deferredSubmissions.add(request.deepCopy());done=true;reply=null;
                                }
                                else if(op.equals("select_"+kind) && !kind.equals("assign_damage")){
                                    JsonArray assignments=kind.equals("discard") || kind.equals("mulligan_bottom")?new JsonArray():decision.getAsJsonArray("assignments").deepCopy();
                                    for(JsonElement value:request.getAsJsonArray("assignments")){
                                        JsonObject chosen=value.getAsJsonObject();int cardId=chosen.get("forgeId").getAsInt();JsonObject offered=null;
                                        for(JsonElement e:options)if(e.getAsJsonObject().get("forgeId").getAsInt()==cardId)offered=e.getAsJsonObject();
                                        if(offered==null)throw new IllegalArgumentException("card was not offered by Forge");
                                        if(kind.equals("attackers")){
                                            int target=chosen.get("targetSeat").getAsInt();if(target!=0 && target!=offered.get("targetSeat").getAsInt())throw new IllegalArgumentException("invalid attack recipient");
                                        } else if(kind.equals("blockers")){
                                            JsonArray ids=chosen.getAsJsonArray("attackerIds");if(ids.size()>1)throw new UnsupportedOperationException("multiple blocks per vanilla creature unsupported");
                                            for(JsonElement target:ids)if(!offered.getAsJsonArray("attackerIds").contains(target))throw new IllegalArgumentException("illegal blocker pairing");
                                        }
                                        for(int i=assignments.size()-1;i>=0;i--)if(assignments.get(i).getAsJsonObject().get("forgeId").getAsInt()==cardId)assignments.remove(i);
                                        if(!kind.equals("targets") || !chosen.has("selected") || chosen.get("selected").getAsBoolean())assignments.add(chosen.deepCopy());
                                    }
                                    decision.add("assignments",assignments);reply=response(request,true,"updated "+kind+" selection");publishDecision();
                                } else if(op.equals("submit_"+kind)){
                                    if(kind.equals("mulligan") || kind.equals("starting_player") || kind.equals("assign_damage") || kind.equals("commander_return")){submit.accept(request.getAsJsonArray("assignments"));}
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
                        if(done){if(normalGame())currentRequest=request;decision=null;retireFile(ipc.resolve("decision.json"));return;}
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
        boolean priorityReady=game.getAge()==GameStage.Play && game.getPhaseHandler().getPriorityPlayer()==local && decision==null && !game.isGameOver() && fidelityGap().isEmpty();
        List<Integer> legal=new ArrayList<>();
        if(priorityReady)for(Card c:local.getCardsIn(ZoneType.Hand))if(c.isLand()&&ability(c).canPlay())legal.add(c.getId());
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("session",SESSION);result.put("scenario",scenario);result.put("events",events);result.put("decision",decision);result.put("phase",phaseName());result.put("stage",game.getAge().name());result.put("mulligans",mulligans);
        result.put("format",arenaBrawl?"arena-brawl":"practice");result.put("command",zone(ZoneType.Command));result.put("exile",zone(ZoneType.Exile));
        result.put("freeMulliganCount",arenaBrawl?1:0);
        result.put("randomSeed",randomSeed);if(localDeck!=null){result.put("localDeck",localDeck);result.put("opponentDeck",opponentDeck);}
        result.put("startingSeat",startingSeat);result.put("startingPlayerPolicy",startingPlayerPolicy);result.put("opponentKept",opponentKept);result.put("opponentMulligans",opponentMulligans);
        result.put("prioritySeat",game.getPhaseHandler().getPriorityPlayer()==null?0:game.getPhaseHandler().getPriorityPlayer()==local?1:2);
        result.put("activeSeat",game.getPhaseHandler().getPlayerTurn()==null?(startingSeat==0?1:startingSeat):game.getPhaseHandler().getPlayerTurn()==local?1:2);
        result.put("fidelityGap",fidelityGap());result.put("canPass",priorityReady && fidelityGap().isEmpty());
        result.put("turn",game.getPhaseHandler().getTurn());result.put("gameOver",game.isGameOver());
        result.put("life",local.getLife());result.put("opponentLife",opponent.getLife());
        result.put("winnerSeat",local.hasWon()?1:opponent.hasWon()?2:0);
        result.put("localLost",local.hasLost());result.put("opponentLost",opponent.hasLost());
        result.put("lossReason",local.hasLost()?local.getOutcome().lossState.name():opponent.hasLost()?opponent.getOutcome().lossState.name():"");
        result.put("landsPlayed",local.getLandsPlayedThisTurn());result.put("maxLandPlays",local.getMaxLandPlays());
        List<Integer> legalCasts=new ArrayList<>();List<Object> castOffers=new ArrayList<>();
        if(priorityReady)for(ZoneType z:new ZoneType[]{ZoneType.Hand,ZoneType.Command,ZoneType.Graveyard})for(Card c:local.getCardsIn(z)){var a=castAbility(c);if(a!=null){legalCasts.add(c.getId());castOffers.add(Map.of("forgeId",c.getId(),"manaCost",manaCost(a)));}}
        result.put("castOffers",castOffers);
        List<Object> activations=new ArrayList<>();
        if(priorityReady)for(Card c:local.getCardsIn(ZoneType.Battlefield))for(var a:c.getSpellAbilities())if(a.isActivatedAbility() && !a.isManaAbility()){
            int nativeId=nativeAbility(a,false);if(nativeId!=0 && activatedAbility(c,nativeId)!=null)activations.add(Map.of("forgeId",c.getId(),"abilityId",nativeId,"api",a.getApi().name(),"manaCost",manaCost(a),"tap",a.getPayCosts().hasTapCost()));
        }
        result.put("legalActivations",activations);
        result.put("legalCasts",legalCasts);result.put("stack",zone(ZoneType.Stack));
        result.put("hand",zone(ZoneType.Hand));result.put("battlefield",zone(ZoneType.Battlefield));result.put("graveyard",zone(ZoneType.Graveyard));result.put("legalLands",legal);
        List<Integer> legalMana=new ArrayList<>();
        if(priorityReady)for(Card c:local.getCardsIn(ZoneType.Battlefield))if(manaAbility(c)!=null)legalMana.add(c.getId());
        if(game.isGameOver()){legal.clear();legalCasts.clear();legalMana.clear();}
        List<Object> mana=new ArrayList<>();
        for(Mana m:local.getManaPool())mana.add(Map.of("id",manaIds.computeIfAbsent(m,k->nextManaId++),"color",(int)m.getColor(),"sourceForgeId",m.getSourceCard().getId()));
        result.put("legalMana",legalMana);result.put("mana",mana);result.put("manaTotal",local.getManaPool().totalMana());
        List<Object> hidden=new ArrayList<>();for(Player p:new Player[]{local,opponent})for(ZoneType z:new ZoneType[]{ZoneType.Library,ZoneType.Hand})
            if(p!=local || z!=ZoneType.Hand)for(Card c:p.getCardsIn(z))hidden.add(Map.of("forgeId",c.getId(),"arenaId",1000+c.getId(),"zone",z.name(),"owner",p==local?1:2,"controller",p==local?1:2));
        result.put("hidden",hidden);
        List<Object> stackAbilities=new ArrayList<>();List<Integer> stackOrder=new ArrayList<>();
        for(var entry:game.getStack()){
            if(entry.isSpell()){stackOrder.add(entry.getSourceCard().getId());continue;}
            int id=-1-entry.getId();Card source=entry.getSourceCard();int controller=entry.getActivatingPlayer()==local?1:2;
            Map<String,Object> object=new LinkedHashMap<>();object.put("forgeId",id);object.put("arenaId",200000+entry.getId());object.put("stackInstanceId",entry.getId());object.put("sourceForgeId",source.getId());object.put("name",source.getName());object.put("zone","Stack");object.put("owner",controller);object.put("controller",controller);object.put("objectKind","ability");object.put("triggered",entry.isTrigger());
            object.put("abilityId",nativeAbility(entry.getSpellAbility(),entry.isTrigger()));
            object.put("targetForgeIds",entry.getTargetChoices().getTargetCards().stream().map(Card::getId).toList());
            List<Integer> targetSeats=new ArrayList<>();for(Player p:entry.getTargetChoices().getTargetPlayers())targetSeats.add(p==local?1:2);object.put("targetSeats",targetSeats);
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
            if(op.equals("snapshot")){accepted=true;reason="snapshot";}
            else if(op.equals("concede")){
                if(request.get("seat").getAsInt()!=1)throw new IllegalArgumentException("wrong player");
                if(game.isGameOver())throw new IllegalStateException("game is over");
                local.concede();priorityChecks.invoke(game.getPhaseHandler());accepted=game.isGameOver();reason="Forge processed local concession";
            }
            else if(op.equals("play_land")) {
                if(request.get("seat").getAsInt()!=1)throw new IllegalArgumentException("wrong player");
                int id=request.get("forgeId").getAsInt();Card selected=null;
                for(Card c:local.getCardsIn(ZoneType.Hand))if(c.getId()==id)selected=c;
                if(selected==null)reason="card is not in the local hand";
                else {
                    LandAbility land=ability(selected);
                    if(!selected.isLand()||!land.canPlay())reason="Forge LandAbility.canPlay rejected the action";
                    else {land.resolve();accepted=true;reason="Forge resolved LandAbility";}
                }
            }
            else if(op.equals("cast_spell")) {
                if(request.get("seat").getAsInt()!=1)throw new IllegalArgumentException("wrong player");
                Card selected=null;int id=request.get("forgeId").getAsInt();
                for(Card c:local.getCardsIn(ZoneType.Hand))if(c.getId()==id)selected=c;
                SpellAbility spell=selected==null?null:castAbility(selected);
                if(spell==null)reason="Forge rejected unavailable supported creature spell";
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
                for(Card c:local.getCardsIn(ZoneType.Battlefield))if(c.getId()==id)selected=c;
                SpellAbility mana=selected==null?null:manaAbility(selected);
                if(mana==null)reason="Forge rejected unavailable mana ability";
                else if(ComputerUtil.playNoStack(local,mana,game,false)){accepted=true;reason="Forge paid activation cost and resolved mana ability";}
                else reason="Forge could not pay mana activation cost";
            }
            // Present choices only after Forge's own pre-priority SBA/trigger routine.
            // mainLoopStep normally calls this on its next iteration, before consulting a controller.
            if(accepted && !op.equals("snapshot") && !game.isGameOver())priorityChecks.invoke(game.getPhaseHandler());
        }catch(Exception ex){reason=ex.toString();}
        response.addProperty("accepted",accepted);response.addProperty("reason",reason);response.add("state",JSON.toJsonTree(snapshot()));return response;
    }
    public static void main(String[] args) throws Exception {
        // GuiDesktop initializes AWT helpers. An uncaught owner-thread failure
        // must not leave those helpers alive masquerading as a healthy backend.
        Thread.setDefaultUncaughtExceptionHandler((thread,error)->{error.printStackTrace();System.exit(1);});
        final Path runtime=Path.of(args[0]).toAbsolutePath();ipc=Path.of(args[1]).toAbsolutePath();
        JsonObject manifest=JsonParser.parseString(Files.readString(runtime.getParent().resolve("native-lab/bridge-card-manifest.json"))).getAsJsonObject();
        if(manifest.get("schema").getAsInt()!=1)throw new IllegalArgumentException("Unsupported generated card manifest");
        loadAdmission(manifest);
        if(Files.exists(ipc.resolve("scenario.json"))){JsonObject config=JsonParser.parseString(Files.readString(ipc.resolve("scenario.json"))).getAsJsonObject();fixtureConfig=config;scenario=config.get("scenario").getAsString();if(config.has("localDeck"))localDeck=config.getAsJsonObject("localDeck");if(config.has("opponentDeck"))opponentDeck=config.getAsJsonObject("opponentDeck");if(config.has("randomSeed"))randomSeed=config.get("randomSeed").getAsLong();if(config.has("startingPlayerPolicy"))startingPlayerPolicy=config.get("startingPlayerPolicy").getAsString();}
        if(scenario.equals("card-family") && (!manifest.has("researchOnly") || !manifest.get("researchOnly").getAsBoolean()))throw new IllegalArgumentException("Card-family fixtures require an explicit research-only manifest");
        if(fixtureConfig!=null && (fixtureConfig.has("fixtureAttacker") || fixtureConfig.has("fixtureBlockers")) && (!Set.of("attack-double-blocked","defend").contains(scenario) || !manifest.has("researchOnly") || !manifest.get("researchOnly").getAsBoolean()))throw new IllegalArgumentException("Combat fixture overrides require an explicit research-only combat scenario");
        if(fixtureConfig!=null && fixtureConfig.has("fixtureOpponentBattlefield") && !scenario.equals("card-family"))throw new IllegalArgumentException("Research opponent overrides require the card-family scenario");
        arenaBrawl=scenario.equals("brawl-duel");
        if(!Set.of("coin-toss","local-first").contains(startingPlayerPolicy))throw new IllegalArgumentException("Unknown starting-player policy");
        if(!Set.of("starter","attack-open","attack-multi","attack-blocked","defend","duel","mixed-duel","opening-duel","spell-duel","trigger-duel","trigger-orator","trigger-orator-double","hare-chain","blue-duel","blue-bounce","blue-wrong-color","custom-duel","brawl-duel","card-family","counter-ready","counter-ready-white","counter-ready-idle","defend-arrow","lethal-win","defend-lethal","discard","vanilla-costs","defend-ox","attack-swift","attack-double-blocked","draw-ready","draw-wrong-color").contains(scenario))throw new IllegalArgumentException("Unsupported scenario: "+scenario);
        if(scenario.equals("custom-duel") || arenaBrawl){validateDeck(localDeck);if(opponentDeck==null)opponentDeck=localDeck.deepCopy();validateDeck(opponentDeck);if(arenaBrawl && (!localDeck.has("format") || !opponentDeck.has("format")))throw new IllegalArgumentException("Brawl requires two Brawl deck policies");if(!arenaBrawl && (localDeck.has("format") || opponentDeck.has("format")))throw new IllegalArgumentException("Brawl decks require the Brawl scenario");}
        else if(localDeck!=null || opponentDeck!=null)throw new IllegalArgumentException("Imported decks require custom-duel");
        Files.createDirectories(ipc.resolve("requests"));Files.createDirectories(ipc.resolve("responses"));
        GuiBase.setInterface(new GuiDesktop(){@Override public String getAssetsDir(){return runtime.toString()+File.separator;}});
        FModel.initialize(null,null);
        Set<String> sourceNames=new LinkedHashSet<>(ADMITTED_CARDS);sourceNames.addAll(BRAWL_COMMANDERS);
        for(String name:sourceNames){var paper=Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(name),"Source card missing: "+name);int mask=0;for(String symbol:COLOR_IDENTITIES.get(name))mask|=switch(symbol){case "W"->1;case "U"->2;case "B"->4;case "R"->8;case "G"->16;default->throw new IllegalArgumentException("Unsupported identity");};if(mask!=paper.getRules().getColorIdentity().getColor())throw new IllegalArgumentException("Source color identity differs from admission metadata: "+name);}
        if(randomSeed!=null)forge.util.MyRandom.setRandom(new Random(randomSeed));
        GameRules rules=new GameRules(GameType.Constructed);rules.setPlayForAnte(false);
        if(arenaBrawl)rules.setAppliedVariants(EnumSet.of(GameType.Brawl));
        if(normalGame())rules.setGamesPerMatch(1);
        List<RegisteredPlayer> players=new ArrayList<>();
        for(String name:new String[]{"Local Player","Opponent"}){
            Deck deck=new Deck("Local vanilla practice deck");
            if(scenario.equals("custom-duel") || arenaBrawl){
                JsonObject imported=players.isEmpty()?localDeck:opponentDeck;
                for(JsonElement item:imported.getAsJsonArray("cards")){JsonObject entry=item.getAsJsonObject();String cardName=entry.get("name").getAsString();deck.getMain().add(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(cardName),"Forge card missing: "+cardName),entry.get("count").getAsInt());}
                if(arenaBrawl)deck.getOrCreate(DeckSection.Commander).add(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(imported.getAsJsonObject("commander").get("name").getAsString())),1);
            }else if(normalGame()){
                String[] names=scenario.equals("blue-duel")?new String[]{"Plains","Island","Savannah Lions","Yoked Ox","Oreskos Swiftclaw","Divine Arrow","Impassioned Orator","Unsummon"}:scenario.equals("trigger-duel")?new String[]{"Plains","Savannah Lions","Yoked Ox","Oreskos Swiftclaw","Divine Arrow","Impassioned Orator"}:scenario.equals("spell-duel")?new String[]{"Plains","Savannah Lions","Yoked Ox","Oreskos Swiftclaw","Divine Arrow"}:new String[]{"Plains","Savannah Lions","Yoked Ox","Oreskos Swiftclaw"};
                for(String cardName:names){int count=scenario.equals("blue-duel")?(cardName.equals("Plains") || cardName.equals("Island")?12:6):cardName.equals("Plains")?24:scenario.equals("trigger-duel")?(cardName.equals("Yoked Ox") || cardName.equals("Divine Arrow")?6:8):scenario.equals("spell-duel")?9:12;deck.getMain().add(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(cardName)),count);}
            }
            RegisteredPlayer registered=arenaBrawl?RegisteredPlayer.forVariants(2,EnumSet.of(GameType.Brawl),deck,Collections.emptyList(),false,Collections.emptyList(),new forge.deck.CardPool()):new RegisteredPlayer(deck);
            players.add(registered.setPlayer(new LocalSeat(name)));
        }
        Match match=new Match(rules,players,"Arena local practice");
        game=match.createGame();local=game.getPlayers().get(0);opponent=game.getPlayers().get(1);
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
            local.getZone(ZoneType.Hand).removeAllCards(true);local.getZone(ZoneType.Battlefield).removeAllCards(true);opponent.getZone(ZoneType.Battlefield).removeAllCards(true);
            JsonArray hand=fixtureConfig.getAsJsonArray("fixtureHand"),lands=fixtureConfig.getAsJsonArray("fixtureLands");
            if(hand==null || hand.size()>8 || lands==null || lands.size()>100)throw new IllegalArgumentException("Bounded fixture requires at most eight hand cards and 100 lands");
            for(var name:hand){String n=name.getAsString();if(!ADMITTED_CARDS.contains(n))throw new IllegalArgumentException("Fixture card is not in the research policy: "+n);local.getZone(ZoneType.Hand).add(Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(n)),local));}
            for(var name:lands){String n=name.getAsString();if(!MANA_COLORS.containsKey(n))throw new IllegalArgumentException("Fixture land needs a bound native mana ability");Card c=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(n)),local);local.getZone(ZoneType.Battlefield).add(c);}
            JsonArray enemies=fixtureConfig.getAsJsonArray("fixtureOpponentBattlefield");
            if(enemies!=null){
                if(enemies.size()>8)throw new IllegalArgumentException("Research opponent fixture is bounded to eight cards");
                for(var name:enemies){String n=name.getAsString();if(!ADMITTED_CARDS.contains(n))throw new IllegalArgumentException("Unmapped research opponent card");Card c=Card.fromPaperCard(Objects.requireNonNull(FModel.getMagicDb().getCommonCards().getCard(n)),opponent);opponent.getZone(ZoneType.Battlefield).add(c);c.setSickness(false);}
            }
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
                            for(JsonObject submission:deferredSubmissions){boolean conceded=submission.get("op").getAsString().equals("concede") && game.isGameOver() && local.conceded();remember(submission,response(submission,conceded || response.get("accepted").getAsBoolean(),conceded?"Forge processed local concession":"Forge completed submitted declaration"));}
                            deferredSubmissions.clear();currentRequest=null;
                        } else write(ipc.resolve("responses").resolve(id+".json"),response);
                        write(ipc.resolve("state.json"),snapshot());Files.delete(path);
                    }
                }
                Thread.sleep(40);
            }
        }
        System.exit(0);
    }
}
