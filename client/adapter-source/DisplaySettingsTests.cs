using System;
using System.IO;

internal static class DisplaySettingsTests
{
    public static int Main(string[] args)
    {
        var root=Path.GetFullPath(args[0]);Directory.CreateDirectory(Path.Combine(root,"local-profile"));
        var path=Path.Combine(root,"local-profile","display.json");int checks=0;
        void Check(bool value,string label){if(!value)throw new Exception(label);checks++;Console.WriteLine("PASS "+label);}
        var defaults=DisplaySettings.Read(root);Check(defaults.Arguments=="-screen-fullscreen 0 -screen-width 1280 -screen-height 720","Fresh profile uses bounded windowed defaults");
        void Write(string text)=>File.WriteAllText(path,text);
        Write("{\"schema\":1,\"width\":1600,\"height\":900,\"fullScreenMode\":3}");
        Check(DisplaySettings.Read(root).Arguments=="-screen-fullscreen 0 -screen-width 1600 -screen-height 900","Saved window size reaches launch arguments");
        Write("{\"schema\":1,\"width\":2560,\"height\":1440,\"fullScreenMode\":1}");
        Check(DisplaySettings.Read(root).Arguments.EndsWith("-window-mode borderless"),"Borderless fullscreen is retained");
        Write("{\"schema\":1,\"width\":1920,\"height\":1080,\"fullScreenMode\":0}");
        Check(DisplaySettings.Read(root).Arguments.EndsWith("-window-mode exclusive"),"Exclusive fullscreen is retained");
        foreach(var invalid in new[]{"{", "{}", "{\"schema\":2,\"width\":1280,\"height\":720,\"fullScreenMode\":3}","{\"schema\":1,\"width\":0,\"height\":720,\"fullScreenMode\":3}","{\"schema\":1,\"width\":1280,\"height\":200000,\"fullScreenMode\":3}","{\"schema\":1,\"width\":1280,\"height\":720,\"fullScreenMode\":2}","{\"schema\":1,\"width\":\"1280 -logFile elsewhere\",\"height\":720,\"fullScreenMode\":3}"})
        {
            Write(invalid);bool rejected=false;try{DisplaySettings.Read(root);}catch(InvalidDataException){rejected=true;}
            Check(rejected && File.ReadAllText(path)==invalid,"Invalid saved setting is rejected without changing its bytes");
        }
        Console.WriteLine("CHECKS "+checks);return 0;
    }
}
