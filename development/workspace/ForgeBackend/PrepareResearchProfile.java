import java.nio.file.*;
import java.util.*;
import com.google.gson.Gson;
import forge.gui.GuiBase;
import forge.GuiDesktop;
import forge.localinstance.properties.ForgeConstants;

/** Materialize owned Forge profile directories once, before parallel tests. */
public final class PrepareResearchProfile {
    public static void main(String[] args)throws Exception{
        if(args.length!=1)throw new IllegalArgumentException("Private research asset root required");
        Path root=Path.of(args[0]).toRealPath();
        var manifest=com.google.gson.JsonParser.parseString(Files.readString(root.getParent().resolve("native-lab/bridge-card-manifest.json"))).getAsJsonObject();
        if(!manifest.has("researchOnly") || !manifest.get("researchOnly").getAsBoolean() || Files.exists(root.getParent().resolve("native-lab/MTGA.exe")))throw new IllegalArgumentException("Only an isolated research runtime may be prepared");
        Properties profile=new Properties();try(var stream=Files.newInputStream(root.resolve("forge.profile.properties"))){profile.load(stream);}
        // Validate explicit profile overrides before Forge's static initializer
        // can materialize user/cache directories. Never accept retail defaults.
        if(!profile.containsKey("userDir") || !profile.containsKey("cacheDir"))throw new IllegalArgumentException("Private user and cache directories must be explicit");
        for(String key:List.of("userDir","cacheDir","cardPicsDir","decksDir","decksConstructedDir"))if(profile.containsKey(key)){
            Path path=Path.of(profile.getProperty(key)).toAbsolutePath().normalize();
            if(!path.startsWith(root) || path.equals(root))throw new IllegalArgumentException("Profile override escapes private research root: "+key);
        }
        GuiBase.setInterface(new GuiDesktop(){@Override public String getAssetsDir(){return root.toString()+java.io.File.separator;}});
        List<Path> paths=new ArrayList<>();
        for(String value:ForgeConstants.PROFILE_DIRS){
            Path path=Path.of(value).toAbsolutePath().normalize();
            if(!path.startsWith(root) || path.equals(root))throw new IllegalArgumentException("Profile path escapes private research root: "+path);
            paths.add(path);
        }
        for(Path path:paths)Files.createDirectories(path);
        System.out.println(new Gson().toJson(Map.of("prepared",true,"scope","Directory preparation only; no FModel, rules match or rendered application initialized","directories",paths.stream().map(Path::toString).toList())));
    }
}
