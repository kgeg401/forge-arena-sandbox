using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using HarmonyLib;
using Newtonsoft.Json.Linq;
using UnityEngine;
using Wotc.Mtga.Cards.Database;

namespace ForgeArenaSandbox;

// Locally cached illustrations use the original material/texture loader paths.
internal static class NativePaperArt
{
    private static readonly Dictionary<string,Texture2D> Textures=new Dictionary<string,Texture2D>(StringComparer.Ordinal);
    private static readonly Dictionary<uint,string> Artists=new Dictionary<uint,string>();
    public static string Artist(uint id)=>Artists.TryGetValue(id,out var value)?value:"Paper card — art unavailable";
    public static void Install(string root,JObject manifest,Harmony harmony)
    {
        string cache=Path.Combine(root,"paper-art"),index=Path.Combine(cache,"index.json");
        if(!File.Exists(index))return;
        var source=JObject.Parse(File.ReadAllText(index));
        if((int?)source["schema"]!=1)throw new InvalidDataException("Unknown paper artwork cache schema");
        var allowed=((JObject)manifest["cards"]!).Properties().Where(p=>(bool?)p.Value["paperOnly"]==true).ToDictionary(p=>(uint)p.Value["grpId"]!,p=>p.Name);
        long total=0;
        foreach(var entry in (JArray)source["cards"]!)
        {
            uint id=(uint)entry["grpId"]!;
            if(!allowed.TryGetValue(id,out var name) || name!=(string?)entry["name"] || Artists.ContainsKey(id))throw new InvalidDataException("Paper artwork identity mismatch");
            string path=Path.Combine(cache,id+".jpg");
            if(!File.Exists(path))continue;
            long bytes=new FileInfo(path).Length;total+=bytes;
            if(bytes>4*1024*1024 || total>64*1024*1024)throw new InvalidDataException("Paper artwork cache exceeds its size limit");
            var content=File.ReadAllBytes(path);
            using(var hash=SHA256.Create())if(BitConverter.ToString(hash.ComputeHash(content)).Replace("-","").ToLowerInvariant()!=(string?)entry["sha256"])throw new InvalidDataException("Paper artwork checksum mismatch: "+name);
            var texture=new Texture2D(2,2,TextureFormat.RGB24,false);
            if(!ImageConversion.LoadImage(texture,content,true) || texture.width<128 || texture.height<128 || texture.width>4096 || texture.height>4096)
            {UnityEngine.Object.Destroy(texture);throw new InvalidDataException("Invalid paper artwork image: "+name);}
            texture.name=id+"_AIF";texture.wrapMode=TextureWrapMode.Clamp;texture.filterMode=FilterMode.Bilinear;
            Textures.Add(CardArtUtil.GetArtPath(id.ToString()),texture);Artists.Add(id,(string)entry["artist"]!);
        }
        harmony.Patch(AccessTools.Method(typeof(CardArtTextureLoader),"GetCardArtPath"),prefix:new HarmonyMethod(typeof(NativePaperArt),nameof(ArtPath)));
        harmony.Patch(AccessTools.Method(typeof(CardArtTextureLoader),"AcquireCardArt"),prefix:new HarmonyMethod(typeof(NativePaperArt),nameof(Acquire)));
        harmony.Patch(AccessTools.Method(typeof(AltReferencedMaterialAndBlock),"SetMainTexture",new[]{typeof(string)}),prefix:new HarmonyMethod(typeof(NativePaperArt),nameof(MainTexture)));
        harmony.Patch(AccessTools.Method(typeof(AltReferencedMaterialAndBlock),"SetTexture",new[]{typeof(string),typeof(string)}),prefix:new HarmonyMethod(typeof(NativePaperArt),nameof(TextureProperty)));
    }
    private static bool ArtPath(string originalAssetPath,ref string __result)
    {if(originalAssetPath==null || !Textures.ContainsKey(originalAssetPath))return true;__result=originalAssetPath;return false;}
    private static bool Acquire(string assetPath,ref Texture2D __result)
    {if(assetPath==null || !Textures.TryGetValue(assetPath,out var texture))return true;__result=texture;return false;}
    private static bool MainTexture(AltReferencedMaterialAndBlock __instance,string texturePath)
    {if(texturePath==null || !Textures.TryGetValue(texturePath,out var texture))return true;__instance.SetMainTexture(texture);return false;}
    private static bool TextureProperty(AltReferencedMaterialAndBlock __instance,string property,string texturePath)
    {if(texturePath==null || !Textures.TryGetValue(texturePath,out var texture))return true;__instance.MatBlock.SetTexture(property,texture);return false;}
}
