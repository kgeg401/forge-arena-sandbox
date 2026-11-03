using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

internal static class InstalledManifestPlan
{
    public static string[] Select(string downloads,string databaseHash,Action<string> report)
    {
        if(databaseHash==null || databaseHash.Length!=64 || !databaseHash.All(Uri.IsHexDigit))
            throw new InvalidDataException("Missing validated local card-database identity.");
        var selected=new List<(string Path,JArray Assets)>();
        bool foundDatabase=false;
        foreach(var path in Directory.GetFiles(downloads,"Manifest*.mtga").OrderBy(p=>p,StringComparer.Ordinal))
        {
            var assets=JObject.Parse(File.ReadAllText(path))["Assets"] as JArray
                ?? throw new InvalidDataException("Invalid installed manifest: "+Path.GetFileName(path));
            var databases=assets.Where(a=>((string?)a["Name"])?.StartsWith("Raw_CardDatabase_",StringComparison.Ordinal)==true).ToArray();
            if(databases.Length>0)
            {
                bool matches=databases.Any(a=>string.Equals(BitConverter.ToString(Convert.FromBase64String((string?)a["sha256"] ?? "")).Replace("-",""),databaseHash,StringComparison.OrdinalIgnoreCase));
                if(!matches){report("Skipped manifest for another card database: "+Path.GetFileName(path));continue;}
                foundDatabase=true;
            }
            selected.Add((path,assets));
        }
        if(!foundDatabase)throw new InvalidDataException("No installed asset manifest matches the validated card database. Finish the official Arena content download.");
        var bundles=new Dictionary<string,JToken>(StringComparer.Ordinal);
        var owners=new Dictionary<string,string>(StringComparer.Ordinal);
        foreach(var manifest in selected)
        foreach(var asset in manifest.Assets)
        {
            var name=(string?)asset["Name"] ?? throw new InvalidDataException("Installed manifest has an unnamed bundle.");
            if(bundles.TryGetValue(name,out var existing))
            {
                if(!JToken.DeepEquals(existing,asset))throw new InvalidDataException("Conflicting installed bundle metadata: "+name);
                continue;
            }
            bundles.Add(name,asset);
            foreach(var token in asset["IndexedAssets"] as JArray ?? new JArray())
            {
                var indexed=(string?)token ?? throw new InvalidDataException("Installed manifest has an invalid asset path.");
                if(owners.TryGetValue(indexed,out var owner))
                    throw new InvalidDataException("Conflicting installed asset '"+indexed+"' in '"+owner+"' and '"+name+"'. Preserve the files and report this startup error.");
                owners.Add(indexed,name);
            }
        }
        return selected.Select(m=>m.Path).ToArray();
    }
}
