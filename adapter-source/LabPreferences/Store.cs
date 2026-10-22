using System;
using System.IO;
using System.Collections.Generic;
using System.Globalization;
using Newtonsoft.Json;

namespace ForgeArenaSandbox.LabPreferences;

public static class Store
{
    // The launcher validates this root before resuming the child. Keep the
    // early loader dependency small; the native host validates it again.
    static readonly string PathName=Path.Combine(Environment.GetEnvironmentVariable("FORGE_ARENA_LAB_ROOT")
        ?? @"D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab","local-playerprefs.json");
    static readonly object Sync = new object();
    static Dictionary<string,string> Values = File.Exists(PathName)
        ? JsonConvert.DeserializeObject<Dictionary<string,string>>(File.ReadAllText(PathName)) ?? new Dictionary<string,string>()
        : new Dictionary<string,string>();
    public static string GetString(string key, string fallback) { lock(Sync)return Values.TryGetValue(key,out var value)?value:fallback; }
    public static int GetInt(string key,int fallback) { return int.TryParse(GetString(key,""),NumberStyles.Integer,CultureInfo.InvariantCulture,out var value)?value:fallback; }
    public static float GetFloat(string key,float fallback) { return float.TryParse(GetString(key,""),NumberStyles.Float,CultureInfo.InvariantCulture,out var value)?value:fallback; }
    public static void SetString(string key,string value) { lock(Sync){Values[key]=value;Save();} }
    public static void SetInt(string key,int value) => SetString(key,value.ToString(CultureInfo.InvariantCulture));
    public static void SetFloat(string key,float value) => SetString(key,value.ToString("R",CultureInfo.InvariantCulture));
    public static bool HasKey(string key) { lock(Sync)return Values.ContainsKey(key); }
    public static void DeleteKey(string key) { lock(Sync){Values.Remove(key);Save();} }
    public static void DeleteAll() { lock(Sync){Values.Clear();Save();} }
    public static void Save() { lock(Sync)File.WriteAllText(PathName,JsonConvert.SerializeObject(Values)); }
}
