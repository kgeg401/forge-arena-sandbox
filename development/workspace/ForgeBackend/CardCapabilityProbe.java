import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;
import com.google.gson.*;
import forge.*;
import forge.ai.*;
import forge.card.CardStateName;
import forge.deck.Deck;
import forge.game.*;
import forge.game.card.*;
import forge.game.player.*;
import forge.game.spellability.SpellAbility;
import forge.game.CardTraitBase;
import forge.gui.GuiBase;
import forge.item.PaperCard;
import forge.model.FModel;

/** Construction/trait inventory only. Never calls resolve or claims gameplay. */
public final class CardCapabilityProbe {
    static final Gson JSON=new GsonBuilder().create();
    static Map<String,Object> trait(CardTraitBase trait,String kind){
        var row=new LinkedHashMap<String,Object>();row.put("kind",kind);
        // Preserve rules parameters, not human descriptions or AI hints.
        var params=new TreeMap<String,String>();
        trait.getMapParams().forEach((k,v)->{if(!k.endsWith("Description") && !k.startsWith("AI"))params.put(k,v);});
        row.put("params",params);
        if(trait instanceof SpellAbility sa){row.put("api",sa.getApi()==null?null:sa.getApi().name());row.put("spell",sa.isSpell());row.put("mana",sa.isManaAbility());
            if(sa.getSubAbility()!=null)row.put("subAbility",trait(sa.getSubAbility(),"subAbility"));}
        return row;
    }
    public static void main(String[] args)throws Exception{
        Thread.setDefaultUncaughtExceptionHandler((thread,error)->{error.printStackTrace();System.exit(1);});
        Path runtime=Path.of(args[0]),input=Path.of(args[1]),output=Path.of(args[2]);
        GuiBase.setInterface(new GuiDesktop(){@Override public String getAssetsDir(){return runtime.toString()+File.separator;}});
        FModel.initialize(null,null);
        var rules=new GameRules(GameType.Constructed);rules.setPlayForAnte(false);
        var players=new ArrayList<RegisteredPlayer>();
        for(String n:List.of("Probe","Opponent"))players.add(new RegisteredPlayer(new Deck(n)).setPlayer(new LobbyPlayerAi(n,Collections.emptySet())));
        Game game=new Match(rules,players,"Construction audit - no game started").createGame();
        Player owner=game.getPlayers().get(0);
        var data=JsonParser.parseString(Files.readString(input)).getAsJsonObject();
        int count=0,failed=0;
        try(var writer=Files.newBufferedWriter(output)){
            for(var item:data.getAsJsonArray("scripts")){
                var script=item.getAsJsonObject();var result=new LinkedHashMap<String,Object>();
                result.put("script",script.get("script").getAsString());result.put("sha256",script.get("sha256").getAsString());
                PrintStream stdout=System.out,stderr=System.err;
                var diagnostics=new ByteArrayOutputStream();var capture=new PrintStream(diagnostics,true,java.nio.charset.StandardCharsets.UTF_8);
                try{
                    System.setOut(capture);System.setErr(capture);
                    var names=script.getAsJsonArray("names");String query=names.get(0).getAsString();
                    PaperCard paper=FModel.getMagicDb().getCommonCards().getCard(query);
                    if(paper==null && names.size()>1){var joined=new ArrayList<String>();for(var n:names)joined.add(n.getAsString());paper=FModel.getMagicDb().getCommonCards().getCard(String.join(" // ",joined));}
                    if(paper==null)throw new IllegalArgumentException("Forge CardDb has no printing for candidate");
                    result.put("forgeName",paper.getName());
                    Card card=Card.fromPaperCard(paper,owner);
                    var faces=new ArrayList<Object>();
                    for(CardStateName state:card.getStates()){
                        if(state==CardStateName.FaceDown)continue;
                        CardState face=card.getState(state);var row=new LinkedHashMap<String,Object>();
                        row.put("state",state.name());row.put("name",face.getName());row.put("types",face.getType().toString());row.put("mana",face.getManaCost().toString());
                        var traits=new ArrayList<Object>();
                        for(var sa:face.getSpellAbilities())traits.add(trait(sa,"ability"));
                        for(var t:face.getTriggers())traits.add(trait(t,"trigger"));
                        for(var r:face.getReplacementEffects())traits.add(trait(r,"replacement"));
                        for(var s:face.getStaticAbilities())traits.add(trait(s,"static"));
                        row.put("traits",traits);faces.add(row);
                    }
                    result.put("faces",faces);result.put("status","constructed-not-playtested");
                }catch(Exception|LinkageError ex){result.put("status","construction-failed");result.put("error",ex.toString());failed++;}
                finally{System.setOut(stdout);System.setErr(stderr);capture.close();}
                String warning=diagnostics.toString(java.nio.charset.StandardCharsets.UTF_8).strip();
                if(!warning.isEmpty()){result.put("diagnostics",warning.substring(0,Math.min(8192,warning.length())));if(!result.get("status").equals("construction-failed"))result.put("status","constructed-with-diagnostics");}
                writer.write(JSON.toJson(result));writer.newLine();writer.flush();
                if(++count%500==0)System.out.println("Constructed "+count+" candidates; failures="+failed);
            }
        }
        // Inventory actual installed controller callbacks, including inherited
        // AI decisions. No guessing from script words alone.
        var callbacks=new ArrayList<Object>();
        Class<?> bridge=Class.forName("ForgeLandEngine$PassiveController");
        for(Method m:PlayerControllerAi.class.getMethods()){
            String n=m.getName();if(!n.matches("(choose|confirm|order|arrange|pay|applyMana|announce|specify|divide|exert|enlist|willPut|vote|playTrigger|playSaFrom).*"))continue;
            var row=new LinkedHashMap<String,Object>();row.put("signature",m.toGenericString());row.put("name",n);
            row.put("implementedBy",bridge.getMethod(n,m.getParameterTypes()).getDeclaringClass().getName());callbacks.add(row);
        }
        Files.writeString(output.resolveSibling("controller-callbacks.json"),new GsonBuilder().setPrettyPrinting().create().toJson(callbacks));
        System.out.println("Finished "+count+" candidate scripts; failures="+failed+". Construction only; no gameplay executed.");
        System.exit(0);
    }
}
