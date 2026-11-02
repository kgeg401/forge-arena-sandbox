using System;
using System.Linq;

namespace ForgeArenaSandbox;

// Stable seat IDs stay in the rules; only surviving seats occupy table slots.
internal sealed class PodTableLayout
{
    internal readonly uint[] Alive, Opponents;
    internal int Rows=>Math.Max(1,(Opponents.Length+2)/3);
    internal float OpponentScale=>Opponents.Length<=1?.90f:Opponents.Length==2?.74f:Rows==1?.57f:Rows==2?.43f:.34f;
    internal float LocalScale=>Opponents.Length<=1?1f:Opponents.Length==2?.94f:.88f;
    internal float CameraHeight=>Opponents.Length<=1?50.5f:Opponents.Length==2?60f:70f+(Rows-1)*15f;
    internal float CameraDepth=>Opponents.Length<=1?19f:Opponents.Length==2?24f:29f-(Rows-1)*6f;
    internal float HalfWidth=>Opponents.Length<=1?27.5f:Opponents.Length==2?14.3f:9.8f;
    internal PodTableLayout(uint[] alive)
    {
        if(alive.Length>10 || alive.Distinct().Count()!=alive.Length || alive.Any(s=>s<1 || s>10))throw new ArgumentException("Invalid visible pod roster");
        Alive=alive.OrderBy(s=>s).ToArray();Opponents=Alive.Where(s=>s!=1).ToArray();
    }
    internal bool Has(uint seat)=>Array.IndexOf(Alive,seat)>=0;
    internal int Slot(uint seat)=>Array.IndexOf(Opponents,seat);
    internal float X(uint seat)
    {
        int slot=Slot(seat);if(seat==1)return 0;if(slot<0)return 200+seat*60;
        int columns=Math.Min(3,Opponents.Length-(slot/3)*3),column=slot%3;
        float spacing=Opponents.Length==2?26f:21f;
        return ((columns-1)*.5f-column)*spacing;
    }
    internal float Z(uint seat)=>seat==1?(Opponents.Length<=1?0:Opponents.Length==2?3:6):-1-Math.Max(0,Slot(seat)/3)*12f;
}
