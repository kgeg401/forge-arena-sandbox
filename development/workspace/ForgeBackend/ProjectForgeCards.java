import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import forge.*;
import forge.deck.*;
import forge.game.*;
import forge.game.card.*;
import forge.game.player.*;
import forge.game.spellability.*;
import forge.model.*;
import forge.gui.*;
import forge.GuiDesktop;

public class ProjectForgeCards {
    static Map<String,Object> ability(SpellAbility a){
        Map<String,Object> r=new LinkedHashMap<>();r.put("api",a.getApi()==null?"":a.getApi().name());r.put("description",a.getDescription());r.put("spell",a.isSpell());r.put("activated",a.isActivatedAbility());r.put("mana",a.isManaAbility());r.put("params",a.getMapParams());r.put("costs",a.getPayCosts()==null?"":a.getPayCosts().toString());
        if(a.getApi()==forge.game.ability.ApiType.Charm && a.hasParam("Choices")){
            var modes=new ArrayList<Object>();for(String key:a.getParam("Choices").split(",")){var mode=forge.game.ability.AbilityFactory.getAbility(a.getHostCard().getSVar(key),a.getHostCard());mode.setActivatingPlayer(a.getActivatingPlayer());modes.add(Map.of("sourceSVar",key,"description",mode.toString(),"params",mode.getMapParams()));}r.put("modes",modes);
        }
        r.put("costParts",a.getPayCosts()==null?List.of():a.getPayCosts().getCostParts().stream().map(p->p.getClass().getSimpleName()).toList());
        return r;
    }
    static Map<String,Object> card(Card card){
        var original=card.getCurrentState();Map<String,Object> r=new LinkedHashMap<>();
        r.put("name",card.getName());r.put("colorMask",(int)original.getColor().getColor());r.put("coreTypes",original.getType().getCoreTypes().stream().map(Object::toString).sorted().toList());r.put("subtypes",original.getType().getSubtypes().stream().sorted().toList());r.put("power",original.getBasePowerString());r.put("toughness",original.getBaseToughnessString());r.put("keywords",original.getIntrinsicKeywords().stream().map(k->k.getOriginal()).sorted().toList());r.put("imageKey",card.getPaperCard().getImageKey(false));
        r.put("abilities",card.getSpellAbilities().stream().map(ProjectForgeCards::ability).toList());r.put("triggers",card.getTriggers().stream().map(t->t.getMapParams()).toList());var latent=new ArrayList<Object>();for(var entry:card.getSVars().entrySet())if(entry.getValue().startsWith("AB$")){try{var a=forge.game.ability.AbilityFactory.getAbility(entry.getValue(),card);a.setActivatingPlayer(card.getOwner());var row=ability(a);row.put("sourceSVar",entry.getKey());latent.add(row);}catch(Exception ex){latent.add(Map.of("sourceSVar",entry.getKey(),"error",ex.toString()));}}r.put("latentAbilities",latent);
        var latentTriggers=new ArrayList<Object>();for(var entry:card.getSVars().entrySet())if(entry.getValue().startsWith("DB$ ImmediateTrigger") || entry.getValue().startsWith("DB$ DelayedTrigger")){
            var params=new LinkedHashMap<String,String>();for(String field:entry.getValue().split("\\|")){String[] pair=field.split("\\$",2);if(pair.length==2)params.put(pair[0].trim(),pair[1].trim());}
            // DelayedTriggerEffect promotes SpellDescription to the eventual
            // TriggerDescription. Mana Drain uses this form for its mana trigger.
            if("DelayedTrigger".equals(params.get("DB")) && !params.containsKey("TriggerDescription") && params.containsKey("SpellDescription"))params.put("TriggerDescription",params.get("SpellDescription"));
            if(params.containsKey("TriggerDescription")){params.put("sourceSVar",entry.getKey());if(params.containsKey("Execute"))params.put("executeRule",card.getSVar(params.get("Execute")));latentTriggers.add(params);}
        }r.put("latentTriggers",latentTriggers);
        var emblems=new ArrayList<Object>();for(var a:card.getSpellAbilities())if(a.hasParam("Name") && a.getParam("Name").startsWith("Emblem")){
            var row=new LinkedHashMap<String,Object>();row.put("sourceAbilityDescription",a.getDescription());row.put("name",a.getParam("Name"));row.put("params",a.getMapParams());var triggers=new ArrayList<Object>();
            if(a.hasParam("Triggers"))for(String key:a.getParam("Triggers").split(","))triggers.add(forge.game.trigger.TriggerHandler.parseTrigger(card.getSVar(key),card,false).getMapParams());
            row.put("triggers",triggers);var statics=new ArrayList<String>();if(a.hasParam("StaticAbilities"))for(String key:a.getParam("StaticAbilities").split(","))statics.add(card.getSVar(key));row.put("statics",statics);emblems.add(row);
        }r.put("emblems",emblems);
        r.put("oracle",card.getPaperCard().getRules().getMainPart().getOracleText());
        return r;
    }
    public static void main(String[] args)throws Exception {
        run(args);System.exit(0);
    }
    static void run(String[] args)throws Exception {
        Path runtime=Path.of(args[0]),scope=Path.of(args[1]),out=Path.of(args[2]);
        GuiBase.setInterface(new GuiDesktop(){@Override public String getAssetsDir(){return runtime.toString()+java.io.File.separator;}});
        FModel.initialize(null,null);var input=JsonParser.parseString(Files.readString(scope)).getAsJsonObject();
        var players=new ArrayList<RegisteredPlayer>();players.add(new RegisteredPlayer(new Deck("Research only")).setPlayer(new ForgeLandEngine.LocalSeat("Local Player")));players.add(new RegisteredPlayer(new Deck("Research only")).setPlayer(new ForgeLandEngine.LocalSeat("Opponent")));
        Game game=new Match(new GameRules(GameType.Constructed),players,"Data projection only").createGame();Player player=game.getPlayers().get(0);
        var cards=new LinkedHashMap<String,Object>();var tokens=new LinkedHashMap<String,Object>();Set<String> names=new TreeSet<>();
        for(var value:input.getAsJsonArray("cards")){
            var row=value.getAsJsonObject();String name=row.get("name").getAsString();var paper=FModel.getMagicDb().getCommonCards().getCard(name);
            Card c=Card.fromPaperCard(paper,player);for(var a:c.getSpellAbilities())a.setActivatingPlayer(player);cards.put(name,card(c));
            if(c.hasState(forge.card.CardStateName.Backside)){c.setState(forge.card.CardStateName.Backside,false);for(var a:c.getSpellAbilities())a.setActivatingPlayer(player);var face=card(c);face.put("parentName",name);face.put("facePresentation",true);cards.put(c.getName(),face);}
            for(var token:row.getAsJsonArray("tokens"))names.add(token.getAsString().trim());
        }
        if(input.has("observedTokenScripts"))for(var token:input.getAsJsonArray("observedTokenScripts"))names.add(token.getAsString());
        for(String name:names){var paper=FModel.getMagicDb().getAllTokens().getToken(name);if(paper==null){tokens.put(name,Map.of("missing",true));continue;}Card token=Card.fromPaperCard(paper,player);tokens.put(name,card(token));if(token.hasState(forge.card.CardStateName.Backside)){token.setState(forge.card.CardStateName.Backside,false);var face=card(token);face.put("parentTokenScript",name);tokens.put(name+":Backside",face);}}
        Files.writeString(out,new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("cards",cards,"tokens",tokens)));
    }
}

