using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace ForgeArenaSandbox;

internal static class SharedAttachmentProtocol
{
    public static JArray Persistent(JObject state,Func<int,int> cardId)
    {
        var result=new JArray();
        foreach(var card in new[]{"hand","battlefield","stack","graveyard","command","exile"}.SelectMany(k=>(JArray?)state[k]??new JArray()))
        {
            bool toCard=card["attachedToForgeId"]!=null,toPlayer=card["attachedToSeat"]!=null;if(!toCard && !toPlayer)continue;
            if(toCard && toPlayer || (string?)card["zone"]!="Battlefield")throw new NotSupportedException("Unmapped attachment outside the battlefield or with ambiguous target");
            int forge=(int)card["forgeId"]!;if(forge<1 || forge>=500000)throw new InvalidDataException("Attachment annotation identity bound exceeded");
            int source=cardId(forge),target=toCard?cardId((int)card["attachedToForgeId"]!):(int)card["attachedToSeat"]!;
            if(source==target || target<1 || toPlayer && target!=1 && target!=2)throw new InvalidDataException("Invalid native attachment endpoint");
            result.Add(new JObject{["id"]=1_500_000+forge,["affectorId"]=source,["affectedIds"]=new JArray(target),["type"]=new JArray("AnnotationType_Attachment")});
        }
        return result;
    }
    public static JArray CreatedEvents(JObject state,long afterEventId,Func<int,int> cardId,ref int annotationId)
    {
        var result=new JArray();
        foreach(var e in ((JArray?)state["events"]??new JArray()).Where(e=>(long)e["id"]!>afterEventId && (string?)e["kind"]=="attachment-change"))
        {
            if(e["toForgeId"]==null && e["toSeat"]==null)continue;
            int source=cardId((int)e["sourceForgeId"]!),target=e["toForgeId"]!=null?cardId((int)e["toForgeId"]!):(int)e["toSeat"]!;
            result.Add(new JObject{["id"]=annotationId++,["affectorId"]=source,["affectedIds"]=new JArray(target),["type"]=new JArray("AnnotationType_AttachmentCreated")});
        }
        return result;
    }
}
