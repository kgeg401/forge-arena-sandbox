using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Text.Json;

// Windows AppContainer with zero capabilities. No firewall edits or elevation.
// A suspended child is checked before its first instruction runs.
internal static class Program
{
    const string Profile = "Codex.ForgeArenaSandbox.LocalLab";
    [StructLayout(LayoutKind.Sequential)] struct SecurityCaps { public IntPtr Sid, Capabilities; public uint Count, Reserved; }
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] struct StartupInfo
    {
        public uint cb; public string? reserved, desktop, title; public uint x,y,width,height,xCount,yCount,fill,flags;
        public ushort show, reservedCount; public IntPtr reservedBytes, stdin, stdout, stderr;
    }
    [StructLayout(LayoutKind.Sequential)] struct StartupInfoEx { public StartupInfo info; public IntPtr attributes; }
    [StructLayout(LayoutKind.Sequential)] struct ProcessInfo { public IntPtr process, thread; public uint pid, tid; }
    [DllImport("userenv.dll",CharSet=CharSet.Unicode)] static extern int CreateAppContainerProfile(string name,string display,string description,IntPtr caps,uint count,out IntPtr sid);
    [DllImport("userenv.dll",CharSet=CharSet.Unicode)] static extern int DeriveAppContainerSidFromAppContainerName(string name,out IntPtr sid);
    [DllImport("advapi32.dll")] static extern IntPtr FreeSid(IntPtr sid);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool InitializeProcThreadAttributeList(IntPtr list,int count,uint flags,ref IntPtr size);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool UpdateProcThreadAttribute(IntPtr list,uint flags,IntPtr attribute,IntPtr value,IntPtr size,IntPtr previous,IntPtr result);
    [DllImport("kernel32.dll")] static extern void DeleteProcThreadAttributeList(IntPtr list);
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool CreateProcessW(string app,StringBuilder command,IntPtr procAttrs,IntPtr threadAttrs,bool inherit,uint flags,IntPtr environment,string cwd,ref StartupInfoEx info,out ProcessInfo process);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr process,uint access,out IntPtr token);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool GetTokenInformation(IntPtr token,int info,IntPtr buffer,int length,out int needed);
    [DllImport("kernel32.dll")] static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll")] static extern bool TerminateProcess(IntPtr process,uint code);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);

    static void Main(string[] args)
    {
        if (args.Length!=1) throw new ArgumentException("Supply the exact native-lab directory.");
        var lab=ForgeArenaSandbox.LabBoundary.Validate(args[0],true);
        // The early loader/PlayerPrefs patch runs before the native host.
        // Give all three the same validated root through the child environment.
        Environment.SetEnvironmentVariable(ForgeArenaSandbox.LabBoundary.RootVariable,lab);
        var display=DisplaySettings.Read(lab);
        var hr=CreateAppContainerProfile(Profile,Profile,"Private offline Arena rendering test",IntPtr.Zero,0,out var sid);
        if(hr<0) Marshal.ThrowExceptionForHR(DeriveAppContainerSidFromAppContainerName(Profile,out sid));
        var sidText=new SecurityIdentifier(sid).Value;
        var directory=new DirectoryInfo(lab);
        var acl=directory.GetAccessControl();
        acl.AddAccessRule(new FileSystemAccessRule(new SecurityIdentifier(sid),FileSystemRights.Modify,
            InheritanceFlags.ContainerInherit|InheritanceFlags.ObjectInherit,PropagationFlags.None,AccessControlType.Allow));
        directory.SetAccessControl(acl);
        // Low-integrity writes are confined to this lab tree, never the installed game.
        var labelMarker=Path.Combine(lab,"isolation-label-ready.txt");
        if(!File.Exists(labelMarker) || File.ReadAllText(labelMarker)!=sidText)
        {
        var label=System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("icacls.exe")
        { ArgumentList={lab,"/setintegritylevel","(OI)(CI)L","/T","/Q"}, UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true });
        label!.StandardOutput.ReadToEnd(); var labelError=label.StandardError.ReadToEnd(); label.WaitForExit();
        if(label.ExitCode!=0)throw new Exception("Could not label the lab for isolated writes: "+labelError);
        File.WriteAllText(labelMarker,sidText);
        }
        var size=IntPtr.Zero; InitializeProcThreadAttributeList(IntPtr.Zero,1,0,ref size);
        var attrs=Marshal.AllocHGlobal(size); var capMemory=Marshal.AllocHGlobal(Marshal.SizeOf<SecurityCaps>());
        ProcessInfo pi=default;
        try
        {
            if(!InitializeProcThreadAttributeList(attrs,1,0,ref size))throw new Win32Exception();
            Marshal.StructureToPtr(new SecurityCaps{Sid=sid},capMemory,false);
            if(!UpdateProcThreadAttribute(attrs,0,(IntPtr)0x20009,capMemory,(IntPtr)Marshal.SizeOf<SecurityCaps>(),IntPtr.Zero,IntPtr.Zero))throw new Win32Exception();
            var startup=new StartupInfoEx{info=new StartupInfo{cb=(uint)Marshal.SizeOf<StartupInfoEx>(),desktop=@"winsta0\default"},attributes=attrs};
            var exe=Path.Combine(lab,"MTGA.exe"); var log=Path.Combine(lab,"unity-lab.log");
            var command=new StringBuilder($"\"{exe}\" {display.Arguments} -logFile \"{log}\"");
            if(!CreateProcessW(exe,command,IntPtr.Zero,IntPtr.Zero,false,0x00080004,IntPtr.Zero,lab,ref startup,out pi))throw new Win32Exception();
            if(!OpenProcessToken(pi.process,8,out var token))throw new Win32Exception();
            try
            {
                var value=Marshal.AllocHGlobal(4);
                try { if(!GetTokenInformation(token,29,value,4,out _) || Marshal.ReadInt32(value)!=1)throw new Exception("Child is not an AppContainer."); }
                finally{Marshal.FreeHGlobal(value);}
                GetTokenInformation(token,30,IntPtr.Zero,0,out var capSize);
                var capabilities=Marshal.AllocHGlobal(capSize);
                try { if(!GetTokenInformation(token,30,capabilities,capSize,out _) || Marshal.ReadInt32(capabilities)!=0)throw new Exception("Unexpected child capabilities."); }
                finally{Marshal.FreeHGlobal(capabilities);}
            }
            finally{CloseHandle(token);}
            var receipt=new { pid=pi.pid, executable=exe, appContainer=true, capabilityCount=0, packageSid=sidText, networkCapability=false, display=new{width=display.Width,height=display.Height,fullScreenMode=display.FullScreenMode},utc=DateTime.UtcNow };
            File.WriteAllText(Path.Combine(lab,"launch-receipt.json"),JsonSerializer.Serialize(receipt,new JsonSerializerOptions{WriteIndented=true}));
            if(ResumeThread(pi.thread)==uint.MaxValue)throw new Win32Exception();
            Console.WriteLine(JsonSerializer.Serialize(receipt));
        }
        catch { if(pi.process!=IntPtr.Zero)TerminateProcess(pi.process,1);throw; }
        finally
        {
            if(pi.thread!=IntPtr.Zero)CloseHandle(pi.thread);if(pi.process!=IntPtr.Zero)CloseHandle(pi.process);
            DeleteProcThreadAttributeList(attrs);Marshal.FreeHGlobal(attrs);Marshal.FreeHGlobal(capMemory);FreeSid(sid);
        }
    }
}
