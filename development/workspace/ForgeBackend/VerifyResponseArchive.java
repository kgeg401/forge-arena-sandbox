import com.google.gson.*;
import java.nio.file.*;
import java.util.*;

/** Bounded archive contracts; real gameplay is verified separately. */
public final class VerifyResponseArchive {
    static int checks;
    static void check(String label,boolean ok){if(!ok)throw new AssertionError(label);checks++;System.out.println(label);}
    interface Operation {void run() throws Exception;}
    static void reject(String label,Operation operation) throws Exception {
        try{operation.run();}catch(java.io.IOException|IllegalArgumentException expected){check(label,true);return;}
        throw new AssertionError(label+" unexpectedly accepted");
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);Files.createDirectory(root);
        var archive=new ForgeLandEngine.ResponseArchive(()->root);
        check("Unknown IDs have no archived replay",archive.get("unknown")==null);
        JsonObject original=JsonParser.parseString("{\"id\":\"first\",\"accepted\":true,\"reason\":null,\"state\":{\"name\":\"\u00c6ther \u2022\",\"life\":40,\"values\":[1,2.5,false]}}").getAsJsonObject();
        JsonObject expected=original.deepCopy();archive.put("first",original);original.addProperty("accepted",false);
        check("Exact typed Unicode reply survives independently of caller mutation",expected.equals(archive.get("first")));
        for(int i=0;i<64;i++){
            var reply=new JsonObject();reply.addProperty("id","later"+i);reply.addProperty("state",("board"+i).repeat(20000));archive.put("later"+i,reply);
        }
        check("Historical answer remains exact after many later requests",expected.equals(archive.get("first")));
        check("The memory index retains only fixed-size integrity receipts",archive.hashes.size()==65 && archive.hashes.values().stream().allMatch(v->v.length==32));
        archive.put("Case",expected);archive.put("case",original);
        check("Case-sensitive request IDs remain independent on Windows",!archive.path("Case").equals(archive.path("case")) && archive.get("Case").equals(expected) && archive.get("case").equals(original));
        Path file=archive.path("first");byte[] bytes=Files.readAllBytes(file);byte[] tampered=bytes.clone();tampered[tampered.length/2]^=1;Files.write(file,tampered);
        reject("Tampered reply is rejected before decompression",()->archive.get("first"));Files.write(file,bytes);
        Files.delete(file);reject("Missing completed answer fails instead of becoming a new action",()->archive.get("first"));Files.write(file,bytes);
        check("Restored original archive replays the exact original answer",expected.equals(archive.get("first")));
        reject("Path traversal ID is rejected",()->archive.get("../escape"));
        reject("Oversized ID is rejected",()->archive.put("a".repeat(81),expected));
        Path regular=root.resolve("regular.json");ForgeLandEngine.write(regular,expected);
        check("Ordinary atomic JSON writer preserves its existing UTF-8/null contract",JsonParser.parseString(Files.readString(regular)).equals(JsonParser.parseString(ForgeLandEngine.JSON.toJson(expected))));
        System.out.println("PASS "+checks+" archive contracts; not gameplay proof");
    }
}
