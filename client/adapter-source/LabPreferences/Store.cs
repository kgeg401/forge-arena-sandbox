using System;
using System.IO;
using System.Collections.Generic;
using System.Globalization;
using Newtonsoft.Json;
using System.Runtime.InteropServices;
using System.ComponentModel;
using System.Text;

namespace ForgeArenaSandbox.LabPreferences;

public static class Store
{
    // The launcher validates this root before resuming the child. Keep the
    // early loader dependency small; the native host validates it again.
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern bool MoveFileEx(string source,string destination,uint flags);
    static readonly string LabRoot=Environment.GetEnvironmentVariable("FORGE_ARENA_LAB_ROOT")
        ?? @"D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab";
    static readonly string PathName=Path.Combine(LabRoot,"local-profile","playerprefs.json");
    static readonly string PreviousPath=Path.Combine(LabRoot,"local-playerprefs.json");
    static readonly object Sync = new object();
    static Dictionary<string,string> Values=ReadExisting();
    static Dictionary<string,string> ReadExisting()
    {
        string path=File.Exists(PathName)?PathName:PreviousPath;
        return File.Exists(path)?JsonConvert.DeserializeObject<Dictionary<string,string>>(File.ReadAllText(path))
            ?? throw new InvalidDataException("Invalid saved local preferences; original file preserved."):new Dictionary<string,string>();
    }
    public static string GetString(string key, string fallback) { lock(Sync)return Values.TryGetValue(key,out var value)?value:fallback; }
    public static int GetInt(string key,int fallback) { return int.TryParse(GetString(key,""),NumberStyles.Integer,CultureInfo.InvariantCulture,out var value)?value:fallback; }
    public static float GetFloat(string key,float fallback) { return float.TryParse(GetString(key,""),NumberStyles.Float,CultureInfo.InvariantCulture,out var value)?value:fallback; }
    public static void SetString(string key,string value) { lock(Sync){Values[key]=value;Save();} }
    public static void SetInt(string key,int value) => SetString(key,value.ToString(CultureInfo.InvariantCulture));
    public static void SetFloat(string key,float value) => SetString(key,value.ToString("R",CultureInfo.InvariantCulture));
    public static bool HasKey(string key) { lock(Sync)return Values.ContainsKey(key); }
    public static void DeleteKey(string key) { lock(Sync){Values.Remove(key);Save();} }
    public static void DeleteAll() { lock(Sync){Values.Clear();Save();} }
    public static void Save()
    {
        lock(Sync)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(PathName)!);
            string pending=PathName+".pending";
            byte[] bytes=new UTF8Encoding(false).GetBytes(JsonConvert.SerializeObject(Values));
            using(var stream=new FileStream(pending,FileMode.Create,FileAccess.Write,FileShare.None))
            {stream.Write(bytes,0,bytes.Length);stream.Flush(true);}
            if(File.Exists(PathName))File.Copy(PathName,PathName+".bak",true);
            // Retain the legacy preference file. The first successful save
            // migrates its values into the profile covered by update backups.
            for(int attempt=0;;attempt++)
            {
                if(MoveFileEx(pending,PathName,9))return;
                int error=Marshal.GetLastWin32Error();
                if(attempt>=11 || (error!=5 && error!=32 && error!=33))throw new Win32Exception(error);
                System.Threading.Thread.Sleep(10);
            }
        }
    }
}
