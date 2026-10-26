import java.lang.reflect.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Inventory outside the named choice guard. This is a gap audit, not closure. */
public final class AuditResearchControllerInheritance {
    public static void main(String[] args)throws Exception{
        Class<?> controller=Class.forName("ForgeLandEngine$ResearchStrictController",false,AuditResearchControllerInheritance.class.getClassLoader());
        Set<String> candidates=Set.of("getAbilityToPlay","getCostDecisionMaker","helpPayForAssistSpell","acceptsDrawOffer","sideboard","cheatShuffle");
        Set<String> flags=Set.of("isAI","isGuiPlayer","canPlayUnlimitedLands","isOrderedZone");
        List<Map<String,Object>> rows=new ArrayList<>();
        for(Method method:controller.getMethods()){
            if(method.isBridge() || method.isSynthetic() || Modifier.isStatic(method.getModifiers()) || !candidates.contains(method.getName()) && !flags.contains(method.getName()))continue;
            String owner=method.getDeclaringClass().getName();
            rows.add(Map.of("signature",method.toGenericString(),"implementedBy",owner,"inheritedAiImplementation",owner.equals("forge.ai.PlayerControllerAi"),"category",flags.contains(method.getName())?"engine-identity-or-zone-flag":"outside-current-named-choice-guard","requiresSourceAndReachabilityReview",true));
        }
        rows.sort(Comparator.comparing(r->r.get("signature").toString()));
        System.out.println(new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("schema",1,"completeHumanControllerParity",false,"entries",rows,"scope","Additional inherited public entry points and identity flags. This audit neither executes them nor proves they are reachable in covered scenarios. Named choice tests do not establish exhaustive human-controller closure.")));
    }
}
