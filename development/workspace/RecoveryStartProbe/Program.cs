using System;using System.IO;using System.Security.Cryptography;using Newtonsoft.Json.Linq;using ForgeArenaSandbox;
var root=Path.Combine(Path.GetTempPath(),"forge-recovery-"+Guid.NewGuid());Directory.CreateDirectory(root);var ipc=Path.Combine(root,"ipc");Directory.CreateDirectory(ipc);
string session=Guid.NewGuid().ToString(),client=Guid.NewGuid().ToString(),id=Guid.NewGuid().ToString();string receiptPath=Path.Combine(root,"match-recovery-consumed-"+id+".json");int checks=0;
JObject state=null!,status=null!,receipt=null!;
void SaveState(){File.WriteAllText(Path.Combine(ipc,"state.json"),state.ToString());receipt["stateSha256"]=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Path.Combine(ipc,"state.json")))).ToLowerInvariant();}
void Reset(){state=new JObject{["session"]=session,["gameOver"]=false,["fidelityGap"]="",["canPass"]=true,["prioritySeat"]=1};status=new JObject{["recovered"]=true,["phase"]="ready",["session"]=client,["engineSession"]=session,["requestId"]=id};receipt=new JObject{["schema"]=1,["clientSession"]=client,["engineSession"]=session,["expires"]=DateTimeOffset.UtcNow.ToUnixTimeSeconds()+300,["ipc"]=ipc};SaveState();}
void Check(string label,Action change,bool expected){Reset();change();File.WriteAllText(Path.Combine(root,"client-service-status.json"),status.ToString());File.WriteAllText(receiptPath,receipt.ToString());if(RecoveryStartGuard.Allows(root,ipc,session,state)!=expected)throw new Exception(label);checks++;}
try{
Check("verified local priority",()=>{},true);
Check("verified explicit choice",()=>{state["canPass"]=false;state["decision"]=new JObject{["kind"]="choice"};SaveState();},true);
Check("wrong local priority",()=>{state["prioritySeat"]=2;SaveState();},false);
Check("no input boundary",()=>{state["canPass"]=false;SaveState();},false);
Check("finished game",()=>{state["gameOver"]=true;SaveState();},false);
Check("rules gap",()=>{state["fidelityGap"]="unmapped";SaveState();},false);
Check("expired",()=>receipt["expires"]=0,false);
Check("null expiry",()=>receipt["expires"]=null,false);
Check("absent expiry",()=>receipt.Remove("expires"),false);
Check("wrong client",()=>receipt["clientSession"]=Guid.NewGuid().ToString(),false);
Check("wrong game",()=>receipt["engineSession"]=Guid.NewGuid().ToString(),false);
Check("wrong IPC",()=>receipt["ipc"]=root,false);
Check("changed snapshot",()=>File.AppendAllText(Path.Combine(ipc,"state.json")," "),false);
Check("not recovered",()=>status["recovered"]=false,false);
Check("already playing",()=>status["phase"]="playing",false);
Check("request path escape",()=>status["requestId"]="../escape",false);
void LiveResume(){status.Remove("recovered");status["liveResumeSha256"]=receipt["stateSha256"];File.WriteAllText(Path.Combine(root,"client-session.json"),new JObject{["session"]=client}.ToString());}
Check("live resume verifies the active client and position",LiveResume,true);
Check("live resume rejects changed position",()=>{LiveResume();File.AppendAllText(Path.Combine(ipc,"state.json")," ");},false);
Check("live resume rejects a different client",()=>{LiveResume();status["session"]=Guid.NewGuid().ToString();},false);
Console.WriteLine(new JObject{["passed"]=true,["checks"]=checks});
}finally{Directory.Delete(root,true);}
