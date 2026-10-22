import com.google.gson.*;
import java.util.Set;

/** Own admission-boundary regression; never initializes or resolves a game. */
public final class AdmissionProbe {
    public static void main(String[] args){
        var source=JsonParser.parseString("{\"admissionSchema\":1,\"cards\":{\"Plains\":{\"admitted\":true,\"token\":false},\"Unverified Candidate\":{\"admitted\":false,\"candidate\":true,\"token\":false},\"Rabbit Token\":{\"admitted\":false,\"token\":true}}}").getAsJsonObject();
        ForgeLandEngine.loadAdmission(source);
        if(!ForgeLandEngine.ADMITTED_CARDS.equals(Set.of("Plains")))throw new AssertionError("Candidate or token entered primary admission");
        int rejected=0;
        for(String mode:new String[]{"missing-schema","missing-flag","coerced-flag","coerced-token"}){
            var invalid=source.deepCopy();
            if(mode.equals("missing-schema"))invalid.remove("admissionSchema");
            else if(mode.equals("missing-flag"))invalid.getAsJsonObject("cards").getAsJsonObject("Plains").remove("admitted");
            else if(mode.equals("coerced-flag"))invalid.getAsJsonObject("cards").getAsJsonObject("Unverified Candidate").addProperty("admitted","true");
            else invalid.getAsJsonObject("cards").getAsJsonObject("Unverified Candidate").addProperty("token","false");
            try{ForgeLandEngine.loadAdmission(invalid);throw new AssertionError("Malformed admission accepted: "+mode);}
            catch(IllegalArgumentException expected){rejected++;}
            if(!ForgeLandEngine.ADMITTED_CARDS.equals(Set.of("Plains")))throw new AssertionError("Failed admission changed the prior allowlist");
        }
        System.out.println("Admission checks passed: candidate/token exclusion; "+rejected+" malformed policies rejected without changing admission");
    }
}
