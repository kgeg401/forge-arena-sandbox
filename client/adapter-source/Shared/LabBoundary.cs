using System;
using System.IO;

namespace ForgeArenaSandbox;

// Shared by the launcher, early preference patcher and native host. Portable
// installs may relocate, but must stay independent of the owned retail tree.
internal static class LabBoundary
{
    internal const string RootVariable="FORGE_ARENA_LAB_ROOT";
    internal static string ExpectedRoot => Path.GetFullPath(Environment.GetEnvironmentVariable(RootVariable)
        ?? @"D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab").TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar);
    internal static string Validate(string requested,bool inspectAncestors=false)
    {
        string root=Path.GetFullPath(requested).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar);
        if(!string.Equals(root,ExpectedRoot,StringComparison.OrdinalIgnoreCase)
            || !string.Equals(Path.GetFileName(root),"native-lab",StringComparison.OrdinalIgnoreCase)
            || !File.Exists(Path.Combine(root,"sandbox-lab.json")))
            throw new InvalidOperationException("Only the configured independent native-lab may run.");
        string sourceMarker=Path.Combine(root,"sandbox-source.txt");
        if(!File.Exists(sourceMarker) && !string.Equals(root,@"D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab",StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Portable labs require their recorded source-install marker.");
        // Legacy lab identity is retained for existing shortcuts. Every new
        // portable install writes its exact source before it can launch.
        string source=File.Exists(sourceMarker)?Path.GetFullPath(File.ReadAllText(sourceMarker).Trim()):@"D:\GAMES\MTGA";
        if(IsWithin(root,source)||IsWithin(source,root))throw new InvalidOperationException("The sandbox and retail installation must be separate trees.");
        // Only the launcher can inspect ancestors: the AppContainer correctly
        // has no read permission outside its own lab. Do not widen that ACL.
        for(var directory=new DirectoryInfo(root);directory!=null;directory=inspectAncestors?directory.Parent:null)
            if((directory.Attributes&FileAttributes.ReparsePoint)!=0)throw new InvalidOperationException("Sandbox roots cannot traverse junctions or symbolic links.");
        return root;
    }
    internal static bool IsWithin(string child,string parent)
    {
        parent=Path.GetFullPath(parent).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar);
        child=Path.GetFullPath(child).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar);
        return string.Equals(child,parent,StringComparison.OrdinalIgnoreCase)||child.StartsWith(parent+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase);
    }
}
