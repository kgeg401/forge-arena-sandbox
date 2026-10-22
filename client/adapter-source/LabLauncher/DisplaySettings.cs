using System;
using System.IO;
using System.Collections.Generic;
using System.Text.Json;

// Only numeric display settings become command-line arguments. This profile is
// separate from Unity's native registry preferences and moves with the client.
internal sealed class DisplaySettings
{
    public int Width {get;private set;}=1280;
    public int Height {get;private set;}=720;
    public int FullScreenMode {get;private set;}=3;
    public bool FullScreen=>FullScreenMode!=3;
    public string Arguments=>$"-screen-fullscreen {(FullScreen?1:0)} -screen-width {Width} -screen-height {Height}"+
        (FullScreen?" -window-mode "+(FullScreenMode==0?"exclusive":"borderless"):"");
    public static DisplaySettings Read(string lab)
    {
        var path=Path.Combine(lab,"local-profile","display.json");
        if(!File.Exists(path))return new DisplaySettings();
        try
        {
            using var document=JsonDocument.Parse(File.ReadAllText(path));var value=document.RootElement;
            int schema=value.GetProperty("schema").GetInt32(),width=value.GetProperty("width").GetInt32(),height=value.GetProperty("height").GetInt32(),mode=value.GetProperty("fullScreenMode").GetInt32();
            if(schema!=1 || width<640 || width>16384 || height<360 || height>16384 || (mode!=0 && mode!=1 && mode!=3))throw new FormatException("Unsupported display values.");
            return new DisplaySettings{Width=width,Height=height,FullScreenMode=mode};
        }
        catch(Exception ex)when(ex is JsonException || ex is InvalidOperationException || ex is KeyNotFoundException || ex is FormatException || ex is OverflowException)
        {throw new InvalidDataException("Saved sandbox display settings are invalid. Preserve display.json and restore its .bak copy to recover.",ex);}
    }
}
