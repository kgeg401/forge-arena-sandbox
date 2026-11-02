using System;
using System.Linq;
using ForgeArenaSandbox;

int checks=0;
void Check(bool value,string label){if(!value)throw new Exception(label);checks++;}
var four=new PodTableLayout(new uint[]{1,2,3,4});
var three=new PodTableLayout(new uint[]{1,2,4});
var two=new PodTableLayout(new uint[]{1,4});
Check(four.CameraHeight>three.CameraHeight && three.CameraHeight>two.CameraHeight,"Camera closes in after each elimination");
Check(four.OpponentScale<three.OpponentScale && three.OpponentScale<two.OpponentScale,"Surviving cards grow");
Check(two.X(4)==0 && two.Has(4) && !two.Has(2),"Remaining original seat is centered without renumbering");
Check(three.X(2)==-three.X(4),"Eliminated middle lane leaves no empty gap");
var ten=new PodTableLayout(Enumerable.Range(1,10).Select(n=>(uint)n).ToArray());
Check(ten.Rows==3 && ten.Opponents.Length==9,"Nine opponents occupy a bounded three-row grid");
Check(ten.Opponents.Select(s=>(ten.X(s),ten.Z(s))).Distinct().Count()==9,"Every opponent has a unique position");
Check(ten.CameraHeight>four.CameraHeight,"Ten-player overview fits the larger table");
foreach(var alive in new[]{new uint[]{1,3,6,9},new uint[]{2,3,7,10},new uint[]{1,10},new uint[]{10}})
{
 var layout=new PodTableLayout(alive);
 Check(layout.Alive.SequenceEqual(alive.OrderBy(s=>s)),"Original seat identities retained");
 Check(layout.CameraHeight<=ten.CameraHeight,"Eliminations never enlarge the ten-player table");
}
Console.WriteLine("{\"passed\":true,\"checks\":"+checks+"}");
