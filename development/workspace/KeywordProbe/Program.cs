using System;
using System.IO;
using System.Linq;
using ForgeArenaSandbox;
using Newtonsoft.Json.Linq;

var bindings=JObject.Parse("{'haste':9,'protection from white':185,'protection from blue':186,'protection from black':187,'protection from red':188,'protection from green':189}");
int count=0;
void Check(string label,bool ok){if(!ok)throw new Exception(label);count++;Console.WriteLine(label);}
void Reject(string label,Action f){try{f();}catch(NotSupportedException){Check(label,true);return;}catch(InvalidDataException){Check(label,true);return;}throw new Exception(label+" unexpectedly accepted");}
JObject State(string keyword,int layer=7)=>new(){["battlefield"]=new JArray(new JObject{["forgeId"]=3,["name"]="Controlled contract input",["keywordGrants"]=new JArray(new JObject{["keyword"]=keyword,["sourceForgeId"]=2,["layerId"]=layer,["timestamp"]=42})})};
JArray Encode(JObject state)=>SharedKeywordProtocol.Persistent(state,id=>1000+id,bindings,new JObject());
int[] Ids(JToken annotation)=>((JArray)annotation["details"]!).Single(d=>(string?)d["key"]=="grpid")["valueInt32"]!.Values<int>().ToArray();
var compound=Encode(State("Protection from each color"));
Check("Five original literal protections share one native annotation",compound.Count==1 && Ids(compound[0]).SequenceEqual(new[]{185,186,187,188,189}));
Check("Source, target, annotation identity and layer are retained",(uint)compound[0]["id"]! ==3_000_000_007u && (int)compound[0]["affectorId"]! ==1002 && compound[0]["affectedIds"]!.Values<int>().SequenceEqual(new[]{1003}) && (int)((JArray)compound[0]["details"]!).Single(d=>(string?)d["key"]=="effect_id")["valueInt32"]![0]! ==7);
Check("Unchanged active effect keeps byte-equivalent persistent identity",JToken.DeepEquals(compound,Encode(State("Protection from each color"))));
Check("An expired effect retires the whole compound annotation",Encode(new JObject()).Count==0);
var literal=Encode(State("Haste",8));Check("Ordinary literal grant retains its single original identity",Ids(literal[0]).SequenceEqual(new[]{9}) && (uint)literal[0]["id"]! ==3_000_000_008u);
var removal=new JObject{["keywords"]=new JArray("Protection from each color")};
Check("Removing the compound removes the same five abilities",SharedKeywordProtocol.RemovedAbilities(new JObject(),removal,bindings,new JObject()).SequenceEqual(new[]{185,186,187,188,189}));
var missing=(JObject)bindings.DeepClone();missing.Remove("protection from blue");
Reject("Missing one actual color identity fails instead of giving partial protection",()=>SharedKeywordProtocol.Abilities("Protection from each color",missing));
Reject("A different unsupported compound remains an explicit gap",()=>Encode(State("Protection from everything")));
Reject("Invalid zero layer remains rejected",()=>Encode(State("Protection from each color",0)));
Reject("Oversized layer remains rejected",()=>Encode(State("Protection from each color",100001)));
Console.WriteLine("PASS "+count+" bounded keyword contracts; not gameplay proof");
