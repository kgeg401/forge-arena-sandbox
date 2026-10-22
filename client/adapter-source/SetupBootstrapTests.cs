using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using ForgeArenaSetup;

class FakeHost:ISetupHost {
    public Queue<string> Probes=new Queue<string>();
    public List<string> Events=new List<string>();
    public bool BadHash,Offline;
    public int ExitCode;
    public string FindPython(){Events.Add("probe");return Probes.Dequeue();}
    public Task<string> Download(){Events.Add("download");if(Offline)throw new InvalidOperationException("offline");return Task.FromResult("official-installer.exe");}
    public void Verify(string path){Events.Add("verify");if(BadHash)throw new InvalidOperationException("bad hash");}
    public int Install(string path){Events.Add("install");return ExitCode;}
    public void Launch(string python){Events.Add("launch:"+python);}
    public void Status(string message){}
}
class BootstrapTests {
    static int checks;
    static void Check(string label,bool ok){if(!ok)throw new Exception(label);checks++;Console.WriteLine("PASS "+label);}
    static void Reject(string label,FakeHost host){try{SetupFlow.Run(host).GetAwaiter().GetResult();throw new Exception("Accepted failure");}catch(InvalidOperationException){Check(label,true);}}
    public static int Main(){
        var existing=new FakeHost();existing.Probes.Enqueue("existing-python.exe");
        var reused=SetupFlow.Run(existing).GetAwaiter().GetResult();
        Check("Working Python is reused without a download",String.Join(",",existing.Events)=="probe,launch:existing-python.exe" && !(bool)reused["pythonInstalled"]);
        var missing=new FakeHost();missing.Probes.Enqueue(null);missing.Probes.Enqueue("installed-python.exe");
        var installed=SetupFlow.Run(missing).GetAwaiter().GetResult();
        Check("Missing runtime downloads, verifies, installs, reprobes and continues",String.Join(",",missing.Events)=="probe,download,verify,install,probe,launch:installed-python.exe" && (bool)installed["pythonInstalled"]);
        var bad=new FakeHost{BadHash=true};bad.Probes.Enqueue(null);Reject("Corrupt download blocks installation",bad);Check("No installer or app runs after hash rejection",!bad.Events.Contains("install") && bad.Events.Count==3);
        var offline=new FakeHost{Offline=true};offline.Probes.Enqueue(null);Reject("Offline download stops before installing",offline);Check("Offline path does not launch setup",offline.Events.Count==2);
        var cancelled=new FakeHost{ExitCode=1602};cancelled.Probes.Enqueue(null);Reject("Cancelled Python install does not launch sandbox setup",cancelled);Check("Cancellation does not claim success",!cancelled.Events.Exists(e=>e.StartsWith("launch:")));
        var broken=new FakeHost();broken.Probes.Enqueue(null);broken.Probes.Enqueue(null);Reject("Installer success still requires a working runtime",broken);
        var reboot=new FakeHost{ExitCode=3010};reboot.Probes.Enqueue(null);reboot.Probes.Enqueue(null);Reject("Restart-needed install without runtime stops clearly",reboot);
        var ready=new FakeHost{ExitCode=3010};ready.Probes.Enqueue(null);ready.Probes.Enqueue("ready-python.exe");Check("Restart code permits continuation only with successful probe",(bool)SetupFlow.Run(ready).GetAwaiter().GetResult()["setupStarted"]);
        Check("Python installs for current user without system PATH changes",PythonRelease.Arguments.Contains("InstallAllUsers=0") && PythonRelease.Arguments.Contains("PrependPath=0") && PythonRelease.Arguments.Contains("AppendPath=0"));
        Check("Tcl/Tk and per-user launcher are requested",PythonRelease.Arguments.Contains("Include_tcltk=1") && PythonRelease.Arguments.Contains("Include_launcher=1") && PythonRelease.Arguments.Contains("InstallLauncherAllUsers=0"));
        Check("Installer progress is visible and reboot is suppressed",PythonRelease.Arguments.Contains("/passive") && PythonRelease.Arguments.Contains("/norestart"));
        Check("Official installer URL and digest are pinned",PythonRelease.Url.StartsWith("https://www.python.org/ftp/python/") && PythonRelease.Sha256.Length==64);
        Console.WriteLine("CHECKS "+checks);return 0;
    }
}
