import java.lang.reflect.*;
import java.util.*;

/** Emit rejecting overrides for the pinned public human-choice callback surface.
 * Signatures come from installed Forge; no original implementation is copied.
 */
public final class GenerateResearchController {
    static String type(Type t){return t.getTypeName().replace('$','.');}
    public static void main(String[] args)throws Exception{
        Class<?> bridge=Class.forName("ForgeLandEngine$PassiveController",false,GenerateResearchController.class.getClassLoader());
        List<Method> methods=new ArrayList<>(Arrays.asList(bridge.getMethods()));methods.sort(Comparator.comparing(Method::toGenericString));
        System.out.println("    static class ResearchStrictController extends PassiveController {");
        System.out.println("        ResearchStrictController(forge.game.Game g,forge.game.player.Player p,forge.LobbyPlayer l){super(g,p,l);}");
        int count=0;
        for(Method m:methods){
            if(m.getDeclaringClass()==bridge || Modifier.isFinal(m.getModifiers()) || Modifier.isStatic(m.getModifiers()) || m.isBridge() || m.isSynthetic())continue;
            if(!m.getName().matches("(choose|confirm|order|arrange|pay|applyMana|announce|specify|divide|exert|enlist|willPut|vote|playTrigger|playSaFrom).*"))continue;
            List<String> generics=new ArrayList<>();
            for(TypeVariable<Method> t:m.getTypeParameters()){
                List<String> bounds=new ArrayList<>();for(Type b:t.getBounds())if(b!=Object.class)bounds.add(type(b));
                generics.add(t.getName()+(bounds.isEmpty()?"":" extends "+String.join(" & ",bounds)));
            }
            List<String> parameters=new ArrayList<>(),names=new ArrayList<>();Type[] types=m.getGenericParameterTypes();
            for(int i=0;i<types.length;i++){parameters.add(type(types[i])+" a"+i);names.add("a"+i);}
            String signature=m.toGenericString().replace("\\","\\\\").replace("\"","\\\"");
            System.out.println("        @Override public "+(generics.isEmpty()?"":"<"+String.join(",",generics)+"> ")+type(m.getGenericReturnType())+" "+m.getName()+"("+String.join(",",parameters)+") {");
            System.out.println("            if(getPlayer()!=local){"+(m.getReturnType()==Void.TYPE?"":"return ")+"super."+m.getName()+"("+String.join(",",names)+");"+(m.getReturnType()==Void.TYPE?"return;":"")+"}");
            System.out.println("            unsupportedDecision=\"Unmapped human callback: "+signature+"\";throw new UnsupportedOperationException(unsupportedDecision);");
            System.out.println("        }");count++;
        }
        System.out.println("    } // "+count+" inherited callbacks rejected for human research cases");
    }
}
