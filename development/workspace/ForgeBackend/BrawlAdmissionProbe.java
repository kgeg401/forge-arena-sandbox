import com.google.gson.*;
import java.nio.file.*;
import java.util.*;

/** Production admission tests only; never initializes a match or changes policy. */
public final class BrawlAdmissionProbe {
 static int checks;
 static void invalid(String label,JsonObject deck){
  try{ForgeLandEngine.validateDeck(deck);throw new AssertionError("Accepted "+label);}
  catch(IllegalArgumentException expected){checks++;}
 }
 public static void main(String[] args)throws Exception{
  var manifest=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
  var good=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
  ForgeLandEngine.loadAdmission(manifest);ForgeLandEngine.validateDeck(good);checks++;
  if(ForgeLandEngine.ADMITTED_CARDS.contains("Isamaru, Hound of Konda") || !ForgeLandEngine.BRAWL_COMMANDERS.contains("Isamaru, Hound of Konda"))throw new AssertionError("Commander leaked into ordinary admission");checks++;
  for(String issue:List.of("98main","100main","two-commanders","string-commander-count","missing-commander","missing-format","unknown-format","unverified-commander","off-color","repeated-nonbasic")){
   var bad=good.deepCopy();var commander=bad.getAsJsonObject("commander");var main=bad.getAsJsonArray("cards");
   switch(issue){
    case "98main" -> main.get(0).getAsJsonObject().addProperty("count",92);
    case "100main" -> main.get(0).getAsJsonObject().addProperty("count",94);
    case "two-commanders" -> commander.addProperty("count",2);
    case "string-commander-count" -> commander.addProperty("count","1");
    case "missing-commander" -> bad.remove("commander");
    case "missing-format" -> bad.remove("format");
    case "unknown-format" -> bad.addProperty("format","commander");
    case "unverified-commander" -> commander.addProperty("name","Krenko, Mob Boss");
    case "off-color" -> main.get(0).getAsJsonObject().addProperty("name","Island");
    case "repeated-nonbasic" -> {main.get(0).getAsJsonObject().addProperty("count",92);main.get(1).getAsJsonObject().addProperty("count",2);}
   }
   invalid(issue,bad);
  }
  var malformed=manifest.deepCopy();malformed.getAsJsonObject("cards").getAsJsonObject("Isamaru, Hound of Konda").addProperty("commanderAdmitted","true");
  Set<String> before=new HashSet<>(ForgeLandEngine.BRAWL_COMMANDERS);
  try{ForgeLandEngine.loadAdmission(malformed);throw new AssertionError("Coerced commander admission");}catch(IllegalArgumentException expected){checks++;}
  if(!before.equals(ForgeLandEngine.BRAWL_COMMANDERS))throw new AssertionError("Failed load mutated commander admission");checks++;
  System.out.println("Brawl admission checks passed: "+checks);
 }
}
