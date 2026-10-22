using System;
using System.Runtime.InteropServices;

namespace ForgeArenaSandbox;

internal static class NativeClientWindow
{
    private delegate bool Visit(IntPtr window,IntPtr context);
    [DllImport("user32.dll")] private static extern bool EnumWindows(Visit visit,IntPtr context);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window,out uint process);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] private static extern bool SetWindowText(IntPtr window,string text);
    [DllImport("kernel32.dll")] private static extern uint GetCurrentProcessId();
    public static bool SetTitle(string version)
    {
        uint own=GetCurrentProcessId();bool changed=false;
        EnumWindows((window,_)=>{
            GetWindowThreadProcessId(window,out var process);
            if(process!=own || !IsWindowVisible(window))return true;
            changed=SetWindowText(window,"Forge Arena Sandbox"+(string.IsNullOrWhiteSpace(version)?"":" — "+version));
            return !changed;
        },IntPtr.Zero);
        return changed;
    }
}
