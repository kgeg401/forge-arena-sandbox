using System;
using System.IO;
using System.IO.MemoryMappedFiles;
using System.ComponentModel;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using ForgeArenaSandbox;

var root=Path.Combine(Path.GetTempPath(),"arena-status-snapshots-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
string path=Path.Combine(root,"deck-host-status.json");int checks=0;
void Check(bool value,string name){if(!value)throw new Exception(name);checks++;}
try
{
    string original="{\"revision\":1,\"padding\":\""+new string('a',4096)+"\"}";
    File.WriteAllText(path,original,new UTF8Encoding(false));
    using(var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete))
    using(var map=MemoryMappedFile.CreateFromFile(file,null,0,MemoryMappedFileAccess.Read,HandleInheritability.None,true))
    using(var view=map.CreateViewAccessor(0,0,MemoryMappedFileAccess.Read))
    {
        bool reproduced=false;
        try{File.WriteAllText(path,"{\"revision\":2}");}catch(IOException error){reproduced=(error.HResult&0xffff)==1224;}
        Check(reproduced,"Original truncating writer reproduces Windows1224 with a mapped reader");
        Check(!StatusJsonFile.TryWrite(path,"{\"revision\":2}"),"Mapped target defers publication without throwing");
        var bytes=new byte[Encoding.UTF8.GetByteCount(original)];view.ReadArray(0,bytes,0,bytes.Length);
        Check(Encoding.UTF8.GetString(bytes)==original,"Mapped reader retains complete original snapshot");
        Check(JsonDocument.Parse(File.ReadAllText(path)).RootElement.GetProperty("revision").GetInt32()==1,"New readers receive the prior complete JSON during deferral");
    }
    Check(StatusJsonFile.TryWrite(path,"{\"revision\":2}"),"Snapshot publishes after the mapped reader closes");
    using(var reader=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite))
    {
        Check(!StatusJsonFile.TryWrite(path,"{\"revision\":3}"),"A reader blocking replacement defers publication without throwing");
        Check(JsonDocument.Parse(File.ReadAllText(path)).RootElement.GetProperty("revision").GetInt32()==2,"Deferred write preserves prior published snapshot");
        Check(Directory.GetFiles(root,"*.snapshot-pending").Length<=1,"Deferred publication retains at most one pending file");
    }
    Check(StatusJsonFile.TryWrite(path,"{\"revision\":4}"),"Next update publishes successfully after reader releases the file");
    Check(JsonDocument.Parse(File.ReadAllText(path)).RootElement.GetProperty("revision").GetInt32()==4,"Latest state wins instead of replaying stale deferred JSON");
    string pending=path+".snapshot-pending";File.WriteAllText(pending,"mapped pending data");
    using(var file=new FileStream(pending,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete))
    using(var map=MemoryMappedFile.CreateFromFile(file,null,0,MemoryMappedFileAccess.Read,HandleInheritability.None,true))
    using(var view=map.CreateViewAccessor(0,0,MemoryMappedFileAccess.Read))
        Check(!StatusJsonFile.TryWrite(path,"{\"revision\":5}"),"Mapped pending writer also defers Windows1224 without a fatal exception");
    bool missing=false;try{StatusJsonFile.TryWrite(Path.Combine(root,"missing","status.json"),"{}");}catch(DirectoryNotFoundException){missing=true;}
    Check(missing,"Unrelated IO failures remain visible");
    File.SetAttributes(path,FileAttributes.ReadOnly);bool denied=false;
    try{StatusJsonFile.TryWrite(path,"{\"revision\":6}");}catch(Win32Exception error){denied=error.NativeErrorCode==5;}
    finally{File.SetAttributes(path,FileAttributes.Normal);}
    Check(denied,"Read-only destination is not silently treated as a transient reader");
    int readCount=0,published=0;using var cancel=new CancellationTokenSource();using var ready=new ManualResetEventSlim();
    var reads=Task.Run(()=>{
        while(!cancel.IsCancellationRequested)
        {
            using var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete);
            using var json=JsonDocument.Parse(file);json.RootElement.GetProperty("revision").GetInt32();Interlocked.Increment(ref readCount);ready.Set();
        }
    });
    try{Check(ready.Wait(5000),"Concurrent reader starts before publication stress");for(int i=10;i<310;i++)if(StatusJsonFile.TryWrite(path,"{\"revision\":"+i+",\"padding\":\""+new string('b',16384)+"\"}"))published++;}
    finally{cancel.Cancel();reads.GetAwaiter().GetResult();}
    Check(readCount>0,"Concurrent readers never observe truncated or malformed JSON");
    Check(StatusJsonFile.TryWrite(path,"{\"revision\":310}"),"Final snapshot publishes after concurrent readers stop");
    Console.WriteLine(JsonSerializer.Serialize(new{passed=true,checks,published,readCount}));
}
finally
{
    if(!string.Equals(Path.GetDirectoryName(Path.GetFullPath(root)),Path.GetFullPath(Path.GetTempPath()).TrimEnd(Path.DirectorySeparatorChar),StringComparison.OrdinalIgnoreCase))throw new IOException("Test cleanup escaped its temporary parent.");
    Directory.Delete(root,true);
}
