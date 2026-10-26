using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using GreClient.Rules;
using Newtonsoft.Json.Linq;
using Wotc.Mtga.Cards.Database;
using Wotc.Mtgo.Gre.External.Messaging;

/// <summary>Original pure choice translation/selector only. No workflow is
/// constructed/applied, no Unity scene, assets, device or window is created.</summary>
internal static class NativeChoicePresentation
{
    public static JObject Verify(SelectNRequest request,MtgGameState state)
    {
        if(request.IdType!=IdType.PromptParameterIndex || request.ReqPrompt.Parameters.Any(p=>p.Type!=ParameterType.NonLocalizedString))throw new NotSupportedException("Pure headless choice check supports explicitly bound string options only");
        var core=Assembly.Load(new AssemblyName("Core"));var translatorType=core.GetType("Wotc.Mtga.DuelScene.Interactions.SelectN.DynamicListTranslation",true)!;
        var constructor=translatorType.GetConstructors().Single(c=>c.GetParameters().Length==4);var providerType=constructor.GetParameters()[2].ParameterType;
        var referenceType=providerType.GetProperty("LatestGameState")!.PropertyType;
        if(!referenceType.IsGenericType || referenceType.GetGenericTypeDefinition().FullName!="Wotc.Mtga.DuelScene.ObservableReference`1" || referenceType.GetGenericArguments()[0]!=typeof(MtgGameState))throw new NotSupportedException("Owned UI game-state wrapper changed");
        var stateReference=Activator.CreateInstance(referenceType)!;referenceType.GetProperty("Value")!.SetValue(stateReference,state);
        var provider=DispatchProxy.Create(providerType,typeof(HeadlessStateProviderProxy));((HeadlessStateProviderProxy)provider).StateReference=stateReference;
        var translator=constructor.Invoke(new object?[]{null,NullCardDatabaseAdapter.Default,provider,null});
        var options=translatorType.GetMethod("Translate")!.Invoke(translator,new object[]{request})!;var optionsType=options.GetType();
        var map=(IReadOnlyDictionary<string,uint>)optionsType.GetField("ChoiceToIdMap")!.GetValue(options)!;
        var sorted=(IReadOnlyList<string>)optionsType.GetField("SortedChoices")!.GetValue(options)!;
        var expected=request.ReqPrompt.Parameters.Select(p=>p.StringValue).ToArray();
        if(map.Count!=expected.Length || expected.Where((text,index)=>!map.TryGetValue(text,out uint id) || id!=request.UnfilteredIds[index]).Any() || !sorted.SequenceEqual(expected.OrderBy(t=>t)))throw new InvalidOperationException("Original native choice translation differs from explicit source-bound labels or response identities");
        var selector=core.GetType("Wotc.Mtga.DuelScene.Interactions.SelectN.ChoiceSelectionTranslation",true)!;
        bool promptButtons=(bool)selector.GetMethod("UsePromptButtonWorkflow")!.Invoke(null,new object[]{options,request})!;
        return new JObject{["labels"]=new JArray(sorted),["nativeIds"]=new JArray(sorted.Select(label=>map[label])),["originalPromptButtonsSelected"]=promptButtons,["rendererStarted"]=false};
    }
}

public class HeadlessStateProviderProxy : DispatchProxy
{
    public object? StateReference;
    protected override object? Invoke(MethodInfo? method,object?[]? args)
    {
        if(method?.Name=="get_LatestGameState")return StateReference;
        throw new NotSupportedException("Pure choice translation requested unexpected game-state access: "+method?.Name);
    }
}
