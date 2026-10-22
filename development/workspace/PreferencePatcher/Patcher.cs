using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;
using ForgeArenaSandbox.LabPreferences;

namespace ForgeArenaSandbox.PreferencePatcher;

// In-memory patch of a lab process only; retail DLLs on disk are not rewritten.
public static class Patcher
{
    public static IEnumerable<string> TargetDLLs => new[] { "UnityEngine.CoreModule.dll", "Core.dll" };
    public static void Patch(AssemblyDefinition assembly)
    {
        var root = Environment.GetEnvironmentVariable("FORGE_ARENA_LAB_ROOT") ?? @"D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab";
        if (!File.Exists(System.IO.Path.Combine(root,"sandbox-lab.json")))throw new InvalidOperationException("Missing lab marker.");
        if (!System.IO.Path.GetFullPath(assembly.MainModule.FileName).StartsWith(root+System.IO.Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Refusing to patch an assembly outside the lab.");
        // A direct double-click of the private MTGA.exe must not fall through
        // into normal startup. Exit this child before any game assembly runs.
        if(!IsolationToken.HasZeroCapabilities())
        {
            File.WriteAllText(Path.Combine(root,"isolation-required.txt"),"Use the sandbox shortcuts. The private executable requires a zero-capability AppContainer.");
            Environment.Exit(78);
            throw new InvalidOperationException("Zero-capability AppContainer required before patching.");
        }
        if (assembly.Name.Name=="Core")
        {
            // The lab does not use crash upload, analytics, Steam services, or Unity services.
            // Preserve file-system and prompt setup. No authentication methods are patched.
            var config=assembly.MainModule.Types.Single(t=>t.FullName=="Wotc.Mtga.Client.InitConfig");
            var factory=config.Methods.Single(m=>m.Name=="GetBootstrapConfig");
            var constructor=config.Methods.Single(m=>m.IsConstructor && !m.IsStatic);
            factory.Body=new MethodBody(factory);
            var code=factory.Body.GetILProcessor();
            code.Emit(OpCodes.Ldc_I4_1);code.Emit(OpCodes.Ldc_I4_1);
            for(var i=0;i<4;i++)code.Emit(OpCodes.Ldc_I4_0);
            code.Emit(OpCodes.Newobj,constructor);code.Emit(OpCodes.Ret);
            return;
        }
        var type=assembly.MainModule.Types.Single(t=>t.FullName=="UnityEngine.PlayerPrefs");
        var replacements=typeof(Store).GetMethods(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Static);
        var count=0;
        foreach(var method in type.Methods)
        {
            var replacement=replacements.SingleOrDefault(r=>r.Name==method.Name &&
                r.GetParameters().Select(p=>p.ParameterType.FullName).SequenceEqual(method.Parameters.Select(p=>p.ParameterType.FullName)));
            if(replacement==null)continue;
            method.ImplAttributes=MethodImplAttributes.IL|MethodImplAttributes.Managed;
            method.Body=new MethodBody(method);
            var il=method.Body.GetILProcessor();
            for(var i=0;i<method.Parameters.Count;i++)il.Emit(OpCodes.Ldarg,method.Parameters[i]);
            il.Emit(OpCodes.Call,assembly.MainModule.ImportReference(replacement));il.Emit(OpCodes.Ret);count++;
        }
        File.WriteAllText(System.IO.Path.Combine(root,"preference-patch-count.txt"),count.ToString());
        if(count!=10)throw new InvalidOperationException("Unexpected PlayerPrefs API count: "+count);
    }
}
