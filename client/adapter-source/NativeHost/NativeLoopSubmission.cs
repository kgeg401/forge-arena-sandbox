using System;
using System.Linq;
using System.Reflection;
using GreClient.Rules;
using Wotc.Mtgo.Gre.External.Messaging;

namespace ForgeArenaSandbox;

internal static class NativeLoopSubmission
{
    internal static BaseUserRequest? Request(object? workflow)
    {
        for(var type=workflow?.GetType();type!=null;type=type.BaseType)
        {
            var field=type.GetField("_request",BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.DeclaredOnly);
            if(field!=null)return field.GetValue(workflow) as BaseUserRequest;
        }
        return null;
    }
    internal static void Submit(BaseUserRequest request,ClientToGREMessage recorded)
    {
        if(request.OnSubmit==null)throw new InvalidOperationException("The native request is already submitted.");
        if(recorded.Type==ClientMessageType.PerformActionResp && request is ActionsAvailableRequest actions)
        {
            var old=recorded.PerformActionResp.Actions.Single();
            var current=actions.Actions.SingleOrDefault(a=>a.ActionType==old.ActionType && a.InstanceId==old.InstanceId && a.GrpId==old.GrpId && a.AbilityGrpId==old.AbilityGrpId);
            if(current==null)throw new InvalidOperationException("The recorded action is no longer offered or affordable.");
            if(!current.ManaCost.SequenceEqual(old.ManaCost))throw new InvalidOperationException("The recorded mana cost changed.");
            if(current.ActionType==ActionType.Pass)actions.SubmitPass();else actions.SubmitAction(current,false);return;
        }
        if(recorded.Type==ClientMessageType.SelectNresp && request is SelectNRequest select)
        {
            var ids=recorded.SelectNResp.Ids.ToArray();
            if(ids.Length<select.MinSel || ids.Length>select.MaxSel || ids.Any(id=>!select.Ids.Contains(id)))throw new InvalidOperationException("The recorded color choice is no longer offered.");
            select.SubmitSelection(ids);return;
        }
        if(recorded.Type==ClientMessageType.SelectTargetsResp && request is SelectTargetsRequest targets)
        {
            var old=recorded.SelectTargetsResp.Target;var group=targets.TargetSelections.Single(s=>s.TargetIdx==old.TargetIdx);var chosen=old.Targets.Single();
            var current=group.Targets.SingleOrDefault(t=>t.TargetInstanceId==chosen.TargetInstanceId)?.Clone()??throw new InvalidOperationException("The recorded target is no longer legal.");
            current.LegalAction=chosen.LegalAction;targets.UpdateTarget(current,group.TargetIdx);return;
        }
        if(recorded.Type==ClientMessageType.SubmitTargetsReq && request is SelectTargetsRequest submit){submit.SubmitTargets();return;}
        throw new InvalidOperationException("This native choice cannot be repeated automatically.");
    }
}
