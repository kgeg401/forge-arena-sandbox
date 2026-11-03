using System;
using System.IO;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

namespace ForgeArenaSandbox;

// Reconstructible snapshots only. Durable profiles and one-shot commands must
// keep their own commit/acknowledgement contracts.
internal static class StatusJsonFile
{
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    private static extern bool MoveFileEx(string source,string destination,uint flags);

    private static bool Busy(int code)=>code==32 || code==33 || code==1224;
    private static bool WritableFile(string path)=>File.Exists(path) && (File.GetAttributes(path)&FileAttributes.ReadOnly)==0;
    private static bool Busy(IOException error)
    {
        if(Busy(error.HResult&0xffff))return true;
        // Mono reports an unmapped Win32 code using the generic IO HRESULT.
        foreach(int code in new[]{32,33,1224})if(error.Message.StartsWith("Win32 IO returned "+code+".",StringComparison.Ordinal))return true;
        return false;
    }

    public static bool TryWrite(string path,string json)
    {
        // One Unity-thread writer per snapshot; retain at most one pending file.
        string pending=path+".snapshot-pending";
        try
        {
            File.WriteAllText(pending,json,new UTF8Encoding(false));
            if(MoveFileEx(pending,path,1))return true;
            int error=Marshal.GetLastWin32Error();
            // Windows may report access denied for replacing a mapped target,
            // even when its reader permits deletion. Do not treat read-only
            // files as a transient lock.
            if(Busy(error) || error==5 && WritableFile(path))return false;
            throw new Win32Exception(error,"Could not publish snapshot: "+path);
        }
        catch(IOException error) when(Busy(error)){return false;}
        finally
        {
            try{if(File.Exists(pending))File.Delete(pending);}
            catch(IOException error) when(Busy(error)){}
            catch(UnauthorizedAccessException) when(WritableFile(pending)){}
        }
    }
}
