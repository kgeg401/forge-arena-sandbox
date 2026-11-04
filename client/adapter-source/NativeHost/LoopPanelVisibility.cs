namespace ForgeArenaSandbox;

internal sealed class LoopPanelVisibility
{
    private bool _first=true,_wasRunning;
    internal bool Collapsed {get;private set;}
    internal void Observe(bool running,int requested)
    {
        if(running){Collapsed=false;_wasRunning=true;}
        else if(_wasRunning || _first && requested>0){Collapsed=true;_wasRunning=false;}
        _first=false;
    }
    internal void Open()=>Collapsed=false;
    internal void Close()=>Collapsed=true;
}
