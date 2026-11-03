using System;
using System.IO;
using System.Diagnostics;
using System.Threading;
using Newtonsoft.Json.Linq;
using ForgeArenaSandbox;

static class SharedReadRecoveryTests
{
    static int checks;
    static void Check(bool ok,string label){if(!ok)throw new Exception(label);checks++;Console.WriteLine("PASS "+label);}
    static JObject Await(AsyncJsonRead reader,string path,int seconds=3)
    {
        var until=Stopwatch.StartNew();
        while(until.Elapsed.TotalSeconds<seconds){if(reader.TryRead(path,out var value))return value;Thread.Sleep(5);}
        throw new Exception("Read did not finish within bound");
    }
    public static void Main(string[] args)
    {
        string root=args[0];Directory.CreateDirectory(root);string path=Path.Combine(root,"response.json");
        File.WriteAllText(path,"{\"id\":\"same-request\",\"session\":\"same-engine\",\"value\":17}");
        int loads=0;
        var read=new AsyncJsonRead(p=>{Interlocked.Increment(ref loads);using var f=new FileStream(p,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete);using var r=new StreamReader(f);return JObject.Parse(r.ReadToEnd());});
        using(var held=new FileStream(path,FileMode.Open,FileAccess.ReadWrite,FileShare.None))
        {
            Check(!read.TryRead(path,out _),"A read starts asynchronously");Thread.Sleep(90);
            var watch=Stopwatch.StartNew();Check(!read.TryRead(path,out _),"A temporary Windows sharing violation keeps the same response pending");
            Check(watch.ElapsedMilliseconds<30,"Retry never blocks the caller thread");
        }
        var result=Await(read,path);Check((string?)result["id"]=="same-request" && (string?)result["session"]=="same-engine" && (int?)result["value"]==17,"Releasing the actual lock adopts the unchanged response");
        Check(loads>=2 && read.Retries>0,"The faulted read is retried without resending an action");read.Forget();
        File.WriteAllText(path,"not JSON");bool rejected=false;
        try{Await(read,path);}catch(Newtonsoft.Json.JsonReaderException){rejected=true;}
        Check(rejected,"Malformed JSON remains an explicit permanent failure");read.Forget();
        File.WriteAllText(path,"{\"value\":19}");var snapshot=new SharedJsonFile(path);
        Check((int?)snapshot.Read()?["value"]==19,"Initial snapshot reads normally");
        Thread.Sleep(20);File.WriteAllText(path,"{\"value\":200}");
        using(var held=new FileStream(path,FileMode.Open,FileAccess.ReadWrite,FileShare.None))
            Check(snapshot.Read()==null,"Locked replacement snapshot is deferred instead of exposing a false fatal error");
        Check((int?)snapshot.Read()?["value"]==200,"Snapshot retries the actual new bytes after lock release");
        read.Forget();bool timedOut=false;var bound=Stopwatch.StartNew();
        using(var held=new FileStream(path,FileMode.Open,FileAccess.ReadWrite,FileShare.None))
            try{Await(read,path);}catch(IOException){timedOut=true;}
        Check(timedOut && bound.Elapsed.TotalSeconds>=.9 && bound.Elapsed.TotalSeconds<2.5,"An enduring sharing lock becomes an explicit bounded failure");read.Forget();
        Thread.Sleep(20);File.WriteAllText(path,"{\"value\":3333}");timedOut=false;bound.Restart();
        using(var held=new FileStream(path,FileMode.Open,FileAccess.ReadWrite,FileShare.None))
        {
            try{while(bound.Elapsed.TotalSeconds<2){snapshot.Read();Thread.Sleep(10);}}catch(IOException){timedOut=true;}
        }
        Check(timedOut && bound.Elapsed.TotalSeconds>=.9 && bound.Elapsed.TotalSeconds<2,"Persistent snapshot access errors are not hidden forever");
        Check((int?)snapshot.Read()?["value"]==3333,"A later successful snapshot clears its failure window");
        var denied=new AsyncJsonRead(_=>throw new UnauthorizedAccessException("injected persistent access denial"));timedOut=false;bound.Restart();
        try{Await(denied,"denied");}catch(UnauthorizedAccessException){timedOut=true;}
        Check(timedOut && bound.Elapsed.TotalSeconds>=.9 && bound.Elapsed.TotalSeconds<2.5,"Persistent access denial is bounded too");denied.Forget();
        var corrupt=new AsyncJsonRead(_=>throw new InvalidDataException("invalid payload"));rejected=false;bound.Restart();
        try{Await(corrupt,"corrupt");}catch(InvalidDataException){rejected=true;}
        Check(rejected && bound.Elapsed.TotalSeconds<.5,"Permanent data failures do not use the IO retry window");corrupt.Forget();
        Console.WriteLine("CHECKS "+checks);
    }
}
