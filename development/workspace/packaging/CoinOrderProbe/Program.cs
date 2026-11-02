using System;using System.Collections.Generic;using System.Linq;using System.IO;using System.Runtime.Loader;using System.Runtime.Serialization;using System.Reflection;using GreClient.Rules;using Wotc.Mtga.DuelScene;using Wotc.Mtga.DuelScene.UXEvents;
class Program {
 static readonly List<string> Log=new();static int life=40,checks;
 static void Check(bool ok,string name){if(!ok)throw new Exception(name);checks++;}
 static void Main(string[] args){AssemblyLoadContext.Default.Resolving+=(_,n)=>{var p=Path.Combine(args[0],n.Name+".dll");return File.Exists(p)?AssemblyLoadContext.Default.LoadFromAssemblyPath(p):null;};Run();}
 [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
 static void Run(){
 var type=Assembly.LoadFrom(Path.Combine(AppContext.BaseDirectory,"NativeHost.dll")).GetType("ForgeArenaSandbox.NativeCoinFlipOrder")!;
 var sort=type.GetMethod("RevealBeforeConsequences",BindingFlags.Static|BindingFlags.NonPublic)!;
 void Order(List<UXEvent> events)=>sort.Invoke(null,new object[]{events});
 var model=new MtgGameState();var controller=new Playback();
 for(int count=0;count<=2;count++){
  Log.Clear();life=40;var effects=new UXEvent[]{new GameStatePlaybackCommencedUXEvent(model,controller),new Effect("draw"),new Effect("damage"),new Effect("counter"),new GameStatePlaybackCompletedUXEvent(model,controller)};
  var events=effects.ToList();for(int i=0;i<count;i++)events.Insert(3,Flip.Make("coin"+i));var before=events.Where(e=>e is not ChooseRandomUXEvent_CoinFlip).ToArray();var coins=events.OfType<ChooseRandomUXEvent_CoinFlip>().ToArray();Order(events);
  Check(events.Where(e=>e is not ChooseRandomUXEvent_CoinFlip).SequenceEqual(before),"unrelated event order");Check(events.Take(count).SequenceEqual(coins),"all flips first in original order");
  using var queue=new UXEventQueue();queue.EnqueuePending(events);queue.Update(.1f);
  if(count>0){Check(life==40&&!Log.Contains("draw")&&!Log.Contains("damage")&&!Log.Contains("counter"),"consequences withheld during first flip");for(int n=0;n<4;n++)queue.Update(.1f);Check(life==40,"native blocking holds model state");}
  for(int n=0;n<40&&queue.IsRunning;n++)queue.Update(.1f);
  Check(!queue.IsRunning,"native queue completes");Check(life==34&&Log.Count(x=>x=="draw")==1&&Log.Count(x=>x=="damage")==1&&Log.Count(x=>x=="counter")==1,"consequences once");
  if(count>0)Check(Log.FindLastIndex(x=>x.StartsWith("coin")&&x.EndsWith("-complete"))<Log.IndexOf("state-commenced"),"coin complete before life/model/draw/counter");
 }
 Console.WriteLine($"Passed {checks} checks using original UXEventQueue blocking/playback events");}
 sealed class Playback:IGameStatePlaybackController{public void StartPlayback(MtgGameState state){life=34;Log.Add("state-commenced");}public void CompletePlayback(MtgGameState state){Log.Add("state-complete");}}
 sealed class Effect:UXEvent{readonly string name;public Effect(string n)=>name=n;public override void Execute(){Log.Add(name);Complete();}}
 sealed class Flip:ChooseRandomUXEvent_CoinFlip{
  string label="";float left;
  private Flip():base(0,0,Array.Empty<bool>(),null!,default){}
  public static Flip Make(string label){var f=(Flip)FormatterServices.GetUninitializedObject(typeof(Flip));f.label=label;return f;}
  public override void Execute(){left=1;Log.Add(label+"-start");}
  public override void Update(float dt){left-=dt;if(left<=0){Log.Add(label+"-complete");Complete();}}
 }
}
