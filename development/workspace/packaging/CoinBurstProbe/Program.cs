using System;
using System.Collections.Generic;
using ForgeArenaSandbox;

int checks=0;
void Check(bool value){if(!value)throw new Exception("Coin grid failed");checks++;}
foreach(int count in new[]{1,2,5,6,10,20,48})
{
    var positions=new HashSet<(float,float)>();
    for(int index=0;index<count;index++)
    {
        var p=CoinBurstLayout.Point(index,count);
        Check(p.X>.2f&&p.X<.8f&&p.Y>.04f&&p.Y<.52f);
        Check(p.Scale>0&&p.Scale<=1);
        Check(positions.Add((p.X,p.Y)));
    }
}
var first=CoinBurstLayout.Point(0,10);var last=CoinBurstLayout.Point(9,10);
Check(Math.Abs(first.X+last.X-1)<.00001f&&first.Y>last.Y);
foreach(var invalid in new[]{(-1,10),(10,10),(0,0)})
{
    bool rejected=false;
    try{CoinBurstLayout.Point(invalid.Item1,invalid.Item2);}catch(ArgumentOutOfRangeException){rejected=true;}
    Check(rejected);
}
Console.WriteLine($"Passed {checks} coin layout checks");
