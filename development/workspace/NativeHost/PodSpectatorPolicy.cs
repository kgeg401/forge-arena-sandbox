using System;
using System.Linq;

namespace ForgeArenaSandbox;

// Inspection changes presentation only. Registered seat IDs never change.
internal sealed class PodSpectatorPolicy
{
    internal uint Watched { get; private set; }
    internal uint Pinned { get; private set; }
    internal bool Rail { get; private set; }
    internal bool Following=>Pinned==0;
    private uint[] _alive=new uint[0];
    internal bool Update(uint[] alive,uint active,uint requiredDefenderView=0)
    {
        if(alive.Length>10 || alive.Any(s=>s<1 || s>10) || alive.Distinct().Count()!=alive.Length)throw new ArgumentException("Invalid pod roster");
        bool oldRail=Rail;uint old=Watched;
        _alive=alive.OrderBy(s=>s).ToArray();Rail=_alive.Length>4;
        if(!Rail){Pinned=0;Watched=0;return oldRail || old!=0;}
        if(Pinned!=0 && !_alive.Contains(Pinned))Pinned=0;
        if(requiredDefenderView!=0 && _alive.Contains(requiredDefenderView))Watched=requiredDefenderView;
        else if(Pinned!=0)Watched=Pinned;
        else if(active!=1 && _alive.Contains(active))Watched=active;
        else if(!_alive.Contains(Watched) || Watched==1)Watched=_alive.First(s=>s!=1);
        return oldRail!=Rail || old!=Watched;
    }
    internal void Inspect(uint seat)
    {
        if(!Rail || !_alive.Contains(seat))throw new ArgumentException("Inspect a living player");
        Pinned=seat;Watched=seat;
    }
    internal void Follow()=>Pinned=0;
    internal bool Visible(uint seat)=>!Rail || seat==1 || seat==Watched;
}
