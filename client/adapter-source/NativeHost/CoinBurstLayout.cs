using System;

namespace ForgeArenaSandbox;

internal static class CoinBurstLayout
{
    internal static (float X,float Y,float Scale) Point(int index,int count)
    {
        if(count<1 || index<0 || index>=count)throw new ArgumentOutOfRangeException();
        int columns=Math.Min(5,count),rows=1+(count-1)/columns,row=index/columns;
        int rowColumns=Math.Min(columns,count-row*columns);
        float x=.5f+(index%columns+.5f-rowColumns*.5f)*(.56f/columns);
        float y=.28f+((rows-1)*.5f-row)*Math.Min(.18f,.45f/rows);
        return(x,y,Math.Min(1f,Math.Min(4f/columns,2f/rows)));
    }
}
