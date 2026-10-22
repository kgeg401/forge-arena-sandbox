using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace ForgeArenaSandbox;

// Research only. Uses the game's own card builder offscreen, in bounded batches.
// This checks asset/model availability; it does not execute card rules.
internal static class NativeCardAssetProbe
{
    private static JArray Textures(CDCMetaCardView view)
    {
        var result=new JArray();
        foreach(var renderer in view.GetComponentsInChildren<Renderer>(true))
        {
            var globalBlock=new MaterialPropertyBlock();renderer.GetPropertyBlock(globalBlock);
            var materials=renderer.sharedMaterials;
            for(int index=0;index<materials.Length;index++)
            {
                var material=materials[index];if(material==null)continue;
                var block=new MaterialPropertyBlock();renderer.GetPropertyBlock(block,index);
                foreach(var property in material.GetTexturePropertyNames())
                {
                    // The real renderer overrides the shared MissingArt texture
                    // through property blocks. Inspect the effective texture.
                    var texture=block.GetTexture(property) ?? globalBlock.GetTexture(property) ?? material.GetTexture(property);
                    if(texture!=null)result.Add(new JObject{["renderer"]=renderer.name,["material"]=material.name,["property"]=property,["name"]=texture.name,["width"]=texture.width,["height"]=texture.height});
                }
            }
        }
        return result;
    }
    // Showcase frames can render art through a different material/property.
    // A source art texture is still required; frame/noise textures do not qualify.
    private static bool ArtReady(CDCMetaCardView view)=>Textures(view).Any(t=>((string?)t["name"])?.EndsWith("_AIF",StringComparison.Ordinal)==true && (int)t["width"]!>=128 && (int)t["height"]!>=128);

    public static IEnumerator Run(string root,PAPA papa,Action finished)
    {
        var requestPath=Path.Combine(root,"card-assets.request.json");
        var request=JObject.Parse(File.ReadAllText(requestPath));
        var manifest=JObject.Parse(File.ReadAllText(Path.Combine(root,"bridge-card-manifest.json")));
        if((bool?)manifest["researchOnly"]!=true)throw new InvalidOperationException("Asset probe requires a research-only manifest.");
        var requested=(JArray)request["grpIds"]!;
        if(requested.Count==0 || requested.Count>128 || requested.Distinct(new JTokenEqualityComparer()).Count()!=requested.Count)throw new InvalidDataException("Asset probe needs 1-128 distinct source identities.");
        var allowed=((JObject)manifest["cards"]!).Properties().ToDictionary(p=>(uint)p.Value["grpId"]!,p=>p.Name);
        foreach(var value in requested)if(!allowed.ContainsKey((uint)value))throw new InvalidDataException("Asset probe printing is not in the research manifest.");
        File.Delete(requestPath);
        var rows=new JArray();var live=new List<CDCMetaCardView>();
        var holder=new GameObject("Research native card asset checks");holder.transform.position=new Vector3(10000,10000,10000);
        try
        {
            for(int offset=0;offset<requested.Count;offset+=8)
            {
                var batch=new List<(uint Id,CDCMetaCardView View)>();
                foreach(var value in requested.Skip(offset).Take(8))
                {
                    uint id=(uint)value;
                    try
                    {
                        var data=papa.CardDatabase.CardDataProvider.GetCardPrintingById(id);
                        if(data==null || data.GrpId!=id)throw new InvalidDataException("Native database returned a different printing.");
                        var view=papa.CardViewBuilder.CreateCDCMetaCardView(new GreClient.CardData.CardData(null!,data),holder.transform);
                        live.Add(view);batch.Add((id,view));
                    }
                    catch(Exception error){rows.Add(new JObject{["grpId"]=id,["name"]=allowed[id],["error"]=error.ToString()});}
                }
                float deadline=Time.realtimeSinceStartup+8;
                // Card parts/texture requests update over several Unity frames.
                int frames=0;
                while(Time.realtimeSinceStartup<deadline && (frames<8 || batch.Any(v=>!ArtReady(v.View)))){frames++;yield return null;}
                foreach(var entry in batch)
                {
                    rows.Add(new JObject{["grpId"]=entry.Id,["name"]=allowed[entry.Id],["modelGrpId"]=entry.View.Card.GrpId,["artReady"]=ArtReady(entry.View),["textures"]=Textures(entry.View)});
                    entry.View.Cleanup();UnityEngine.Object.Destroy(entry.View.gameObject);live.Remove(entry.View);
                }
            }
            File.WriteAllText(Path.Combine(root,"card-assets-report.json"),JsonConvert.SerializeObject(new{requestId=(string?)request["requestId"],utc=DateTime.UtcNow,researchOnly=true,cards=rows,scope="Original native card models and art texture availability; not gameplay or complete visual-parity proof."},Formatting.Indented));
        }
        finally
        {
            foreach(var view in live)if(view!=null){view.Cleanup();UnityEngine.Object.Destroy(view.gameObject);}
            UnityEngine.Object.Destroy(holder);finished();
        }
    }
}
