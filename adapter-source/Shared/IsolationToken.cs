using System;
using System.Runtime.InteropServices;

namespace ForgeArenaSandbox;

// No Unity dependency: usable by the early preloader before client startup.
internal static class IsolationToken
{
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr process,uint access,out IntPtr token);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool GetTokenInformation(IntPtr token,int info,IntPtr buffer,int length,out int needed);
    internal static bool HasZeroCapabilities()
    {
        if(!OpenProcessToken(GetCurrentProcess(),8,out var token))return false;
        try
        {
            var value=Marshal.AllocHGlobal(4);
            try{if(!GetTokenInformation(token,29,value,4,out _)||Marshal.ReadInt32(value)!=1)return false;}
            finally{Marshal.FreeHGlobal(value);}
            GetTokenInformation(token,30,IntPtr.Zero,0,out var size);
            if(size<=0)return false;
            var caps=Marshal.AllocHGlobal(size);
            try{return GetTokenInformation(token,30,caps,size,out _)&&Marshal.ReadInt32(caps)==0;}
            finally{Marshal.FreeHGlobal(caps);}
        }
        finally{CloseHandle(token);}
    }
}
