using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using ForgeArenaSandbox;

internal static class ProfileIdentityTests
{
    public static void Main(string[] args)
    {
        string root=Path.GetFullPath(args[0]);Directory.CreateDirectory(Path.Combine(root,"local-profile"));
        string dir=Path.Combine(root,"local-profile"),path=Path.Combine(dir,"identities.json");
        foreach(string name in new[]{"decks.json","packs.json","play-selection.json","display.json"})File.WriteAllText(Path.Combine(dir,name),"preserve "+name);
        int checks=0;void Check(bool value){if(!value)throw new Exception("Check "+(checks+1));checks++;}
        LocalIdentityLibrary Open()=>new LocalIdentityLibrary(root,a=>a==LocalIdentityLibrary.DefaultAvatar || a=="Avatar_Basic_Sparky");
        var store=Open();Check(!File.Exists(path) && (string?)store.Current["name"]=="Local Player");
        string id=store.Create("Æther tester","Avatar_Basic_Sparky");Check((string?)Open().Current["id"]==id && Open().Profiles.Count==2);
        store.Update(id,"Second name",LocalIdentityLibrary.DefaultAvatar);Check((string?)Open().Current["name"]=="Second name");
        store.Select(Guid.Empty.ToString());Check((string?)Open().Current["id"]==Guid.Empty.ToString());
        string before=File.ReadAllText(path);
        foreach(var candidate in new[]{("",LocalIdentityLibrary.DefaultAvatar),(" leading",LocalIdentityLibrary.DefaultAvatar),("line\nbreak",LocalIdentityLibrary.DefaultAvatar),("<b>markup</b>",LocalIdentityLibrary.DefaultAvatar),(new string('x',33),LocalIdentityLibrary.DefaultAvatar),("local player",LocalIdentityLibrary.DefaultAvatar),("Bad avatar","unknown")})
        {
            try{store.Create(candidate.Item1,candidate.Item2);throw new Exception("Accepted invalid identity");}catch(InvalidDataException error){if(candidate.Item1=="local player")Check(error.Message.Contains("already uses"));}
            Check(File.ReadAllText(path)==before && store.Profiles.Count==2);
        }
        try{store.Select(Guid.NewGuid().ToString());throw new Exception("Accepted missing profile");}catch(InvalidDataException){}Check(File.ReadAllText(path)==before);
        File.SetAttributes(path,FileAttributes.ReadOnly);
        try{store.Create("Read only",LocalIdentityLibrary.DefaultAvatar);throw new Exception("Accepted read-only write");}catch(UnauthorizedAccessException){}finally{File.SetAttributes(path,FileAttributes.Normal);}
        Check(File.ReadAllText(path)==before && store.Profiles.Count==2);
        foreach(string name in new[]{"decks.json","packs.json","play-selection.json","display.json"})Check(File.ReadAllText(Path.Combine(dir,name))=="preserve "+name);
        var stale=Open();store.Update(id,"Newer write",LocalIdentityLibrary.DefaultAvatar);string latest=File.ReadAllText(path);
        try{stale.Select(id);throw new Exception("Accepted stale writer");}catch(InvalidDataException){}Check(File.ReadAllText(path)==latest);
        File.WriteAllText(path,"{\"schema\":9}");try{Open();throw new Exception("Accepted invalid schema");}catch(InvalidDataException){}Check(File.ReadAllText(path)=="{\"schema\":9}");
        Console.WriteLine("PASS "+checks+" cosmetic profile storage contracts");
    }
}
