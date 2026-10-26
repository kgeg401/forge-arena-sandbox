// Authored setup bootstrap. Uses Windows' .NET Framework, never Python to
// install Python. Official installer arguments: docs.python.org/3.13/using/windows.html.
using System;
using System.IO;
using System.Net;
using System.Linq;
using System.Text;
using System.Drawing;
using System.Diagnostics;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using Microsoft.Win32;

namespace ForgeArenaSetup {
    public static class PythonRelease {
        public const string Version="3.13.17";
        public const string Url="https://www.python.org/ftp/python/3.13.17/python-3.13.17-amd64.exe";
        // Published SHA-256: python.org/downloads/release/python-31317/.
        public const string Sha256="5da012101ba2e17113a9a1cd901e9ce1441086f2b7ecb5de06ec94163899a190";
        public const string Arguments="/passive /norestart InstallAllUsers=0 InstallLauncherAllUsers=0 Include_launcher=1 Include_tcltk=1 Include_exe=1 Include_lib=1 Include_dev=1 Include_test=0 Include_doc=0 Include_pip=0 PrependPath=0 AppendPath=0 AssociateFiles=0 Shortcuts=0";
        public static string Hash(string path) {
            using(var file=File.OpenRead(path)) using(var h=SHA256.Create())
                return BitConverter.ToString(h.ComputeHash(file)).Replace("-","").ToLowerInvariant();
        }
        public static void Verify(string path) {
            if(!File.Exists(path) || new FileInfo(path).Length>64L*1024*1024 || Hash(path)!=Sha256)
                throw new InvalidOperationException("Python download failed its SHA-256 check. No installer was run. Please retry Setup.exe.");
        }
    }

    public interface ISetupHost {
        string FindPython();
        Task<string> Download();
        void Verify(string path);
        int Install(string path);
        void Launch(string python);
        void Status(string message);
    }

    public static class SetupFlow {
        public static async Task<Dictionary<string,object>> Run(ISetupHost host) {
            host.Status("Checking for 64-bit Python with working Tcl/Tk...");
            string python=await Task.Run(()=>host.FindPython());
            bool installed=false;
            int? exitCode=null;
            if(python==null) {
                host.Status("Python is missing or lacks Tcl/Tk. Downloading the official Python installer...");
                string installer=await host.Download();
                host.Verify(installer);
                host.Status("Installing Python for this Windows user. Please wait...");
                exitCode=await Task.Run(()=>host.Install(installer));
                if(exitCode!=0 && exitCode!=3010)
                    throw new InvalidOperationException("Python setup did not finish (code "+exitCode+"). No sandbox was installed. You can retry Setup.exe.");
                python=await Task.Run(()=>host.FindPython());
                if(python==null)throw new InvalidOperationException(exitCode==3010 ? "Python setup needs a Windows restart. Restart, then run Setup.exe again." : "Python setup finished, but 64-bit Python with Tcl/Tk is still unavailable. See the setup log.");
                installed=true;
            }
            host.Status("Python is ready. Opening sandbox setup...");
            host.Launch(python);
            return new Dictionary<string,object>{{"python",python},{"pythonInstalled",installed},{"installerExitCode",exitCode},{"setupStarted",true}};
        }
    }

    public class WindowsSetupHost:ISetupHost {
        readonly string root,logDirectory;
        readonly Action<string> show;
        public WindowsSetupHost(string root,string logDirectory,Action<string> status) { this.root=root;this.logDirectory=logDirectory;show=status; }
        public void Status(string text) { show(text); }
        public static IEnumerable<string> Candidates() {
            // Registry and direct paths avoid depending on py.exe or launching
            // Windows Store aliases when Python is absent.
            var found=new List<string>();
            foreach(var hive in new[]{RegistryHive.CurrentUser,RegistryHive.LocalMachine})
                foreach(var view in new[]{RegistryView.Registry64,RegistryView.Registry32}) {
                    using(var baseKey=RegistryKey.OpenBaseKey(hive,view))
                    using(var core=baseKey.OpenSubKey(@"Software\Python\PythonCore")) {
                        if(core==null)continue;
                        foreach(string version in core.GetSubKeyNames())
                            using(var key=core.OpenSubKey(version+@"\InstallPath")) {
                                if(key==null)continue;
                                string exe=key.GetValue("ExecutablePath") as string;
                                string folder=key.GetValue("") as string;
                                if(!String.IsNullOrEmpty(exe))found.Add(exe);
                                if(!String.IsNullOrEmpty(folder))found.Add(Path.Combine(folder,"python.exe"));
                            }
                    }
                }
            foreach(string folder in (Environment.GetEnvironmentVariable("PATH")??"").Split(Path.PathSeparator)) {
                string clean=folder.Trim().Trim('"');
                if(clean.Length>0 && clean.IndexOf("WindowsApps",StringComparison.OrdinalIgnoreCase)<0)found.Add(Path.Combine(clean,"python.exe"));
            }
            for(int minor=15;minor>=10;minor--)found.Add(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Programs","Python","Python3"+minor,"python.exe"));
            return found.Distinct(StringComparer.OrdinalIgnoreCase).Where(File.Exists);
        }
        public static string Probe(string exe) {
            const string code="import sys,struct,tkinter; assert sys.version_info>=(3,10) and struct.calcsize('P')==8; w=tkinter.Tk(); w.withdraw(); w.update_idletasks(); w.destroy(); print(sys.executable)";
            try {
                using(var p=new Process()) {
                    p.StartInfo=new ProcessStartInfo(exe,"-I -B -c \""+code+"\""){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
                    p.Start();var stdout=p.StandardOutput.ReadToEndAsync();var stderr=p.StandardError.ReadToEndAsync();
                    if(!p.WaitForExit(10000)){p.Kill();return null;}
                    string result=stdout.Result.Trim();
                    return p.ExitCode==0 && File.Exists(result) ? result : null;
                }
            } catch(System.ComponentModel.Win32Exception){return null;}
              catch(InvalidOperationException){return null;}
        }
        public string FindPython() {
            foreach(string exe in Candidates()) { string result=Probe(exe);if(result!=null)return result; }
            return null;
        }
        public async Task<string> Download() {
            string folder=Path.Combine(Path.GetTempPath(),"ForgeArenaSandbox-Setup",Guid.NewGuid().ToString("N"));Directory.CreateDirectory(folder);
            string target=Path.Combine(folder,"python-"+PythonRelease.Version+"-amd64.exe");
            ServicePointManager.SecurityProtocol=SecurityProtocolType.Tls12;
            using(var web=new WebClient()) {
                web.Headers[HttpRequestHeader.UserAgent]="ForgeArenaSandbox-Setup";
                web.DownloadProgressChanged+=(s,e)=>{
                    if(e.BytesReceived>64L*1024*1024)web.CancelAsync();
                    show("Downloading official Python: "+(e.BytesReceived/1024/1024)+" MB");
                };
                await web.DownloadFileTaskAsync(new Uri(PythonRelease.Url),target);
            }
            return target;
        }
        public void Verify(string path) { PythonRelease.Verify(path); }
        public int Install(string path) {
            using(var p=Process.Start(new ProcessStartInfo(path,PythonRelease.Arguments+" /log \""+Path.Combine(logDirectory,"python-installer.log")+"\""){UseShellExecute=false})) {p.WaitForExit();return p.ExitCode;}
        }
        public void Launch(string python) {
            var start=new ProcessStartInfo(python,"-B \""+Path.Combine(root,"setup_client.py")+"\""){UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=root};
            start.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"]="1";
            Process.Start(start);
        }
    }

    public class SetupWindow:Form {
        readonly Label status=new Label();
        readonly string root,logs;
        bool busy=true;
        public int ExitCode=1;
        public SetupWindow(string root,string logs) {
            this.root=root;this.logs=logs;
            Text="Forge Arena Sandbox setup";ClientSize=new Size(580,165);StartPosition=FormStartPosition.CenterScreen;FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;
            Font=new Font("Segoe UI",10);
            var title=new Label{Text="Preparing sandbox setup",Left=20,Top=20,Width=540,Height=32,Font=new Font("Segoe UI",16,FontStyle.Bold)};
            status.SetBounds(20,68,540,65);Controls.Add(title);Controls.Add(status);
            FormClosing+=(s,e)=>{if(busy)e.Cancel=true;};
            Shown+=Start;
        }
        async void Start(object sender,EventArgs e) {
            try {
                var result=await SetupFlow.Run(new WindowsSetupHost(root,logs,message=>status.Text=message));
                result["utc"]=DateTime.UtcNow.ToString("o");result["pythonDownloadUrl"]=PythonRelease.Url;
                Program.Report(Path.Combine(logs,"bootstrap-result.json"),result);
                ExitCode=0;busy=false;Close();
            } catch(Exception error) {
                Program.Report(Path.Combine(logs,"bootstrap-error.json"),new Dictionary<string,object>{{"error",error.ToString()}});
                busy=false;MessageBox.Show(this,error.Message+"\n\nDetails: "+logs,"Setup stopped",MessageBoxButtons.OK,MessageBoxIcon.Error);Close();
            }
        }
    }

    public static class Program {
        public static void Report(string path,object value) {File.WriteAllText(path,new JavaScriptSerializer().Serialize(value),new UTF8Encoding(false));}
        [STAThread] public static int Main(string[] args) {
            string root=AppDomain.CurrentDomain.BaseDirectory;
            string logs=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"ForgeArenaSandbox","setup-logs",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss-fff")+"-"+Guid.NewGuid().ToString("N").Substring(0,6));Directory.CreateDirectory(logs);
            try {
                if(!Environment.Is64BitOperatingSystem)throw new InvalidOperationException("The sandbox requires 64-bit Windows.");
                if(args.Length>0) {
                    if(args.Length!=2 || (args[0]!="--probe-only" && args[0]!="--download-only"))throw new ArgumentException("Supported diagnostics: --probe-only <report.json> or --download-only <report.json>");
                    var host=new WindowsSetupHost(root,logs,message=>{});
                    if(args[0]=="--probe-only")Report(args[1],new {python=host.FindPython(),probeOnly=true});
                    else {
                        string file=host.Download().GetAwaiter().GetResult();host.Verify(file);
                        Report(args[1],new {installer=file,sha256=PythonRelease.Hash(file),installerExecuted=false,source=PythonRelease.Url});
                    }
                    return 0;
                }
                if(!File.Exists(Path.Combine(root,"setup_client.py")))throw new InvalidOperationException("Extract the entire sandbox ZIP before running Setup.exe.");
                Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
                using(var window=new SetupWindow(root,logs)){Application.Run(window);return window.ExitCode;}
            } catch(Exception error) {
                Report(Path.Combine(logs,"bootstrap-error.json"),new {error=error.ToString()});
                if(args.Length==0)MessageBox.Show(error.Message+"\nDetails: "+logs,"Setup stopped");return 1;
            }
        }
    }
}
