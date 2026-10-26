import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;
import java.nio.file.*;
import java.security.*;
import java.util.jar.*;

/** Reject a Forge update that adds an inherited AI choice to the research player. */
public final class VerifyResearchCallbackSurface {
    public static void main(String[] args)throws Exception{
        Class<?> strict=Class.forName("ForgeLandEngine$ResearchStrictController",false,VerifyResearchCallbackSurface.class.getClassLoader());
        JsonObject audit=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        Path jar=Path.of(forge.game.player.PlayerController.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        String parentSha;
        try(JarFile zip=new JarFile(jar.toFile())){parentSha=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(zip.getInputStream(zip.getJarEntry("forge/game/player/PlayerController.class")).readAllBytes()));}
        if(!audit.get("parentControllerClassSha256").getAsString().equals(parentSha))throw new IllegalArgumentException("Unreviewed parent-controller bytecode; audit its final delegators first");
        Set<String> helpers=new HashSet<>(),seen=new HashSet<>();
        for(JsonElement e:audit.getAsJsonArray("delegators"))helpers.add(e.getAsJsonObject().get("signature").getAsString());
        List<Map<String,Object>> rows=new ArrayList<>();boolean passed=true;
        for(Method m:strict.getMethods()){
            if(m.isBridge() || m.isSynthetic() || Modifier.isStatic(m.getModifiers()))continue;
            if(!m.getName().matches("(choose|confirm|order|arrange|pay|applyMana|announce|specify|divide|exert|enlist|willPut|vote|playTrigger|playSaFrom).*") && !m.getName().equals("reveal"))continue;
            String implementation=m.getDeclaringClass().getName();
            boolean mapped=implementation.equals("ForgeLandEngine$PassiveController"),blocked=implementation.equals("ForgeLandEngine$ResearchStrictController");
            boolean headless=implementation.equals("ForgeLandEngine$HeadlessChoiceController");
            boolean delegated=Modifier.isFinal(m.getModifiers()) && implementation.equals("forge.game.player.PlayerController") && helpers.contains(m.toGenericString());
            if(delegated)seen.add(m.toGenericString());
            rows.add(Map.of("signature",m.toGenericString(),"implementedBy",implementation,"mapped",mapped,"headlessSharedChoice",headless,"nativeChoiceAcceptancePending",headless,"rejectsUnmappedHumanChoice",blocked,"auditedDelegationToGuard",delegated));
            if(!mapped && !headless && !blocked && !delegated)passed=false;
        }
        if(!seen.equals(helpers))passed=false;
        rows.sort(Comparator.comparing(r->r.get("signature").toString()));
        System.out.println(new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("passed",passed,"callbacks",rows.size(),"details",rows,"parentControllerClassSha256",parentSha,"scope","Pinned public choice callback surface only; this is not gameplay evidence or an exhaustive proof of all future engine behavior.")));
        if(!passed)System.exit(1);
    }
}
