using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

// Cosmetic identities share the existing decks, collection and pack receipts.
internal sealed class LocalIdentityLibrary
{
    public const string DefaultAvatar="Avatar_Basic_AjaniGoldmane";
    private readonly string _path;
    private readonly Func<string,bool> _avatarAvailable;
    private JObject _state;
    private bool _persisted;
    public LocalIdentityLibrary(string root,Func<string,bool> avatarAvailable)
    {
        _path=Path.Combine(root,"local-profile","identities.json");_avatarAvailable=avatarAvailable;
        _state=File.Exists(_path)?JObject.Parse(File.ReadAllText(_path)):new JObject{["schema"]=1,["revision"]=0,["activeId"]=Guid.Empty.ToString(),["profiles"]=new JArray(new JObject{["id"]=Guid.Empty.ToString(),["name"]="Local Player",["avatar"]=DefaultAvatar})};
        Validate(_state);_persisted=File.Exists(_path);
    }
    public JArray Profiles=>(JArray)_state["profiles"]!.DeepClone();
    public JObject Current=>(JObject)((JArray)_state["profiles"]!).Single(p=>(string?)p["id"]==(string?)_state["activeId"]).DeepClone();
    private void Validate(JObject state)
    {
        if(state["schema"]?.Type!=JTokenType.Integer || (int)state["schema"]! !=1 || state["revision"]?.Type!=JTokenType.Integer || (long)state["revision"]!<0 || (long)state["revision"]!>=int.MaxValue || !(state["profiles"] is JArray profiles) || profiles.Count<1 || profiles.Count>32)throw new InvalidDataException("Invalid local profiles; existing file preserved.");
        foreach(var profile in profiles)
        {
            if(!(profile is JObject) || profile["id"]?.Type!=JTokenType.String || !Guid.TryParseExact((string?)profile["id"],"D",out _) || profile["name"]?.Type!=JTokenType.String || profile["avatar"]?.Type!=JTokenType.String)throw new InvalidDataException("Invalid local profile fields.");
            string name=(string)profile["name"]!,avatar=(string)profile["avatar"]!;
            if(name!=name.Trim() || name.Length<1 || name.Length>32 || name.Any(c=>char.IsControl(c) || c=='<' || c=='>'))throw new InvalidDataException("Use a profile name of 1–32 characters on one line, without formatting tags.");
            if(!_avatarAvailable(avatar))throw new InvalidDataException("This profile's avatar is unavailable in the installed game.");
        }
        if(profiles.Select(p=>(string)p["id"]!).Distinct(StringComparer.OrdinalIgnoreCase).Count()!=profiles.Count || state["activeId"]?.Type!=JTokenType.String || profiles.Count(p=>(string?)p["id"]==(string?)state["activeId"])!=1)throw new InvalidDataException("Duplicate or missing active local profile.");
        if(profiles.Select(p=>(string)p["name"]!).Distinct(StringComparer.OrdinalIgnoreCase).Count()!=profiles.Count)throw new InvalidDataException("A profile already uses that name. Choose a different name.");
    }
    private void Commit(JObject next)
    {
        next["revision"]=checked((int)_state["revision"]!+1);Validate(next);
        if(File.Exists(_path)){if(!JToken.DeepEquals(JObject.Parse(File.ReadAllText(_path)),_state))throw new InvalidDataException("Profiles changed in another window. Reopen the client before editing them.");}
        else if(_persisted)throw new IOException("The saved profiles file was removed. Reopen the client before editing profiles.");
        LocalDeckLibrary.SaveJsonAtomically(_path,next.ToString(Formatting.Indented));_state=next;_persisted=true;
    }
    public string Create(string name,string avatar)
    {
        var next=(JObject)_state.DeepClone();string id=Guid.NewGuid().ToString();
        ((JArray)next["profiles"]!).Add(new JObject{["id"]=id,["name"]=name,["avatar"]=avatar});next["activeId"]=id;Commit(next);return id;
    }
    public void Update(string id,string name,string avatar)
    {
        var next=(JObject)_state.DeepClone();var profile=((JArray)next["profiles"]!).Single(p=>(string?)p["id"]==id);profile["name"]=name;profile["avatar"]=avatar;Commit(next);
    }
    public void Select(string id)
    {
        var next=(JObject)_state.DeepClone();next["activeId"]=id;Commit(next);
    }
}
