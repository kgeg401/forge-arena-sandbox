using System;
using System.Linq;
using Newtonsoft.Json.Linq;
using TMPro;
using Wizards.Mtga;

namespace ForgeArenaSandbox;

// Cosmetic identity controls use the owned notice, input and avatar assets.
internal sealed class NativeProfileMenu
{
    private readonly LocalIdentityLibrary _library;
    private readonly NativeClientDialogs _dialogs;
    private readonly TMP_InputField _nameTemplate;
    private readonly Action<Action> _defer;
    private readonly Action _home;
    private int _page;
    private static readonly string[] Avatars={LocalIdentityLibrary.DefaultAvatar,AvatarIdConstants.Sparky,AvatarIdConstants.NPE_Player};
    public NativeProfileMenu(string root,PAPA papa,NativeClientDialogs dialogs,TMP_InputField nameTemplate,Action<Action> defer,Action home)
    {
        _library=new LocalIdentityLibrary(root,a=>Avatars.Contains(a) && !string.IsNullOrEmpty(ProfileUtilities.GetAvatarBustImagePath(papa.AssetLookupSystem,a)));
        _dialogs=dialogs;_nameTemplate=nameTemplate;_defer=defer;_home=home;
        _page=_library.Profiles.Select(p=>(string)p["id"]!).ToList().IndexOf((string)_library.Current["id"]!);
    }
    private static string AvatarLabel(string id)=>id==LocalIdentityLibrary.DefaultAvatar?"Ajani Goldmane":id==AvatarIdConstants.Sparky?"Sparky":"Tutorial planeswalker";
    private Action Later(Action action)=>()=>_defer(action);
    public void Open()
    {
        var profiles=_library.Profiles;_page=Math.Min(_page,profiles.Count-1);var profile=(JObject)profiles[_page];string id=(string)profile["id"]!;
        _dialogs.Choose("Your profiles ("+(_page+1)+"/"+profiles.Count+")",(string)profile["name"]!+"\n"+AvatarLabel((string)profile["avatar"]!)+((string?)_library.Current["id"]==id?" · active":"")+"\nDecks, collection and packs are shared.",new (string,Action)[]{
            ("New profile",Later(()=>Edit(null))),
            ("Use profile",Later(()=>{_library.Select(id);_home();})),
            ("Edit",Later(()=>Edit(profile))),
            ("Next",Later(()=>{_page=(_page+1)%profiles.Count;Open();})),
            ("Close",Later(_home))});
    }
    private void Edit(JObject? profile)
    {
        string? id=(string?)profile?["id"];string avatar=(string?)profile?["avatar"]??LocalIdentityLibrary.DefaultAvatar;
        _dialogs.Input(id==null?"New local profile":"Rename profile",(string?)profile?["name"]??"",_nameTemplate,name=>_defer(()=>{
            string selected=id??_library.Create(name.Trim(),avatar);if(id!=null)_library.Update(id,name.Trim(),avatar);_page=_library.Profiles.Select(p=>(string)p["id"]!).ToList().IndexOf(selected);PickAvatar(selected);
        }),Later(Open));
    }
    private void PickAvatar(string id)
    {
        var choices=Avatars.Select(a=>(AvatarLabel(a),Later(()=>{var p=(JObject)_library.Profiles.Single(x=>(string?)x["id"]==id);_library.Update(id,(string)p["name"]!,a);_library.Select(id);_home();}))).ToList();
        choices.Add(("Keep current",Later(()=>{_library.Select(id);_home();})));_dialogs.Choose("Choose your avatar","Your name is saved. Choose an avatar, or keep the current one. Cards and decks stay shared.",choices);
    }
}
