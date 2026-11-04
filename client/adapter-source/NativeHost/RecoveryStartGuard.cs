using System;
using System.IO;
using System.Security.Cryptography;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;
internal static class RecoveryStartGuard
{
    internal static bool Allows(string root,string ipc,string session,JObject state)
    {
        try
        {
            if((string?)state["session"]!=session || (bool?)state["gameOver"]==true || !string.IsNullOrEmpty((string?)state["fidelityGap"]) || state["decision"] is not JObject && !((bool?)state["canPass"]==true && (int?)state["prioritySeat"]==1))return false;
            var status=JObject.Parse(File.ReadAllText(Path.Combine(root,"client-service-status.json")));
            if((bool?)status["recovered"]!=true || (string?)status["phase"]!="ready" || (string?)status["engineSession"]!=session || !Guid.TryParse((string?)status["requestId"],out var id) || id.ToString()!=(string?)status["requestId"])return false;
            var receipt=JObject.Parse(File.ReadAllText(Path.Combine(root,"match-recovery-consumed-"+id+".json")));
            var expiry=receipt["expires"];if(expiry==null || expiry.Type!=JTokenType.Integer && expiry.Type!=JTokenType.Float)return false;
            double expires=(double)expiry;
            if((int?)receipt["schema"]!=1 || (string?)receipt["clientSession"]!=(string?)status["session"] || (string?)receipt["engineSession"]!=session || double.IsNaN(expires) || double.IsInfinity(expires) || expires<DateTimeOffset.UtcNow.ToUnixTimeSeconds() || !string.Equals(Path.GetFullPath((string)receipt["ipc"]!),Path.GetFullPath(ipc),StringComparison.OrdinalIgnoreCase))return false;
            using(var file=new FileStream(Path.Combine(ipc,"state.json"),FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete))
            using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(file)).Replace("-","").ToLowerInvariant()==(string?)receipt["stateSha256"];
        }
        catch(Exception error) when(error is IOException || error is UnauthorizedAccessException || error is ArgumentException || error is Newtonsoft.Json.JsonException){return false;}
    }
}
