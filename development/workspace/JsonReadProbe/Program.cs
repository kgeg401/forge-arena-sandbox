using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using Newtonsoft.Json.Linq;
using ForgeArenaSandbox;

internal static class Program
{
    static int checks;
    static void Check(bool value,string label){if(!value)throw new Exception(label);checks++;Console.WriteLine("PASS "+label);}
    static void Until(Func<bool> ready){if(!SpinWait.SpinUntil(ready,TimeSpan.FromSeconds(5)))throw new TimeoutException("Bounded background read did not finish");}
    static void Main()
    {
        ThreadPool.GetMinThreads(out int workers,out int io);ThreadPool.SetMinThreads(Math.Max(workers,4),io);
        int caller=Environment.CurrentManagedThreadId,thread=caller,loads=0;
        using var entered=new ManualResetEventSlim();using var release=new ManualResetEventSlim();
        var first=new JObject{{"id","first"}};
        var reader=new AsyncJsonRead(_=>{Interlocked.Increment(ref loads);thread=Environment.CurrentManagedThreadId;entered.Set();release.Wait();return first;});
        var clock=Stopwatch.StartNew();
        try
        {
            Check(!reader.TryRead("one",out _),"An unfinished read returns without waiting for its bytes");
            Check(clock.ElapsedMilliseconds<1000,"A blocked loader does not block the caller");
            Until(()=>entered.IsSet);
            bool stillPending=true;
            for(int i=0;i<20;i++)stillPending&=!reader.TryRead("one",out _);
            Check(stillPending,"Repeated polling retains the same unfinished read");
            Check(loads==1 && thread!=caller,"Exactly one loader runs off the calling thread");
        }
        finally{release.Set();}
        JObject? result=null;Until(()=>reader.TryRead("one",out result));
        Check(ReferenceEquals(first,result),"Completion hands the exact parsed object to its owner");reader.Forget();

        using var oldEntered=new ManualResetEventSlim();using var oldRelease=new ManualResetEventSlim();
        var newer=new JObject{{"id","newer"}};
        var switching=new AsyncJsonRead(path=>{if(path=="old"){oldEntered.Set();oldRelease.Wait();throw new FormatException("retired read");}return newer;});
        try
        {
            Check(!switching.TryRead("old",out _),"A superseded operation begins independently");Until(()=>oldEntered.IsSet);
            Until(()=>switching.TryRead("new",out result));
            Check(ReferenceEquals(newer,result),"A newer request cannot consume the old request's result");
            switching.Forget();oldRelease.Set();
            Until(()=>switching.TryRead("new",out result));
            Check(ReferenceEquals(newer,result),"An obsolete read failure cannot become the new request's failure");
        }
        finally{oldRelease.Set();switching.Forget();}

        int fresh=0;var reusing=new AsyncJsonRead(_=>new JObject{{"generation",Interlocked.Increment(ref fresh)}});
        Until(()=>reusing.TryRead("same",out result));Check((int)result!["generation"]! == 1,"First generation is loaded");
        reusing.Forget();Until(()=>reusing.TryRead("same",out result));Check((int)result!["generation"]! == 2,"Retiring a request also invalidates the same path");reusing.Forget();

        var invalid=new AsyncJsonRead(_=>JObject.Parse("not JSON"));bool propagated=false;
        Until(()=>{try{invalid.TryRead("bad",out _);return false;}catch(Newtonsoft.Json.JsonReaderException){propagated=true;return true;}});
        Check(propagated,"A current malformed response fails on the polling owner instead of disappearing");invalid.Forget();
        string directory=Path.Combine(Path.GetTempPath(),"forge-response-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(directory);
        string published=Path.Combine(directory,"response.json"),retired=Path.Combine(directory,"retired.json");int prepared=0;
        var armed=new AsyncJsonRead(path=>{Interlocked.Increment(ref prepared);return JObject.Parse(File.ReadAllText(path));});
        try
        {
            armed.Begin(retired);Thread.Sleep(30);Check(prepared==0,"An armed read never opens an unpublished response");
            armed.Begin(published);File.WriteAllText(retired,"{\"id\":\"stale\"}");Thread.Sleep(30);
            Check(prepared==0,"Retiring an unpublished response stops its waiter");
            File.WriteAllText(published,"{\"id\":\"prepared\"}");Until(()=>Volatile.Read(ref prepared)==1);Thread.Sleep(30);
            Check(armed.TryRead(published,out result) && (string?)result["id"]=="prepared","A prearmed response is parsed before its first UI poll");
            armed.Forget();armed.Begin(Path.Combine(directory,"never.json"));armed.Forget();
            Check(prepared==1,"Closing a pending request does not load or replay anything");
        }
        finally{armed.Forget();Directory.Delete(directory,true);}
        Console.WriteLine($"{checks} asynchronous response ownership checks passed");
    }
}
