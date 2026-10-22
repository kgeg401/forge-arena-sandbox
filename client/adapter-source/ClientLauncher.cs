// Authored, version-independent Windows entry point. No game code or assets.
using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Drawing;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Web.Script.Serialization;

namespace ForgeArenaClient {
    internal static class Launcher {
        [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr h);
        [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr h,int command);
        private static readonly JavaScriptSerializer Json=new JavaScriptSerializer();
        private static bool Focus(string root) {
            string target=Path.GetFullPath(Path.Combine(root,"data","native-lab","MTGA.exe"));
            foreach(var p in Process.GetProcessesByName("MTGA"))using(p)try {
                if(String.Equals(p.MainModule.FileName,target,StringComparison.OrdinalIgnoreCase) && p.MainWindowHandle!=IntPtr.Zero){ShowWindow(p.MainWindowHandle,9);SetForegroundWindow(p.MainWindowHandle);return true;}
            } catch(System.ComponentModel.Win32Exception){} catch(InvalidOperationException){}
            return false;
        }
        private static string Key(string root) {
            using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(root.ToUpperInvariant()))).Replace("-","");
        }
        [STAThread] public static int Main(string[] args) {
            Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
            string root=AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
            if(args.Contains("--version")){Console.WriteLine("Forge Arena Sandbox launcher 1");return 0;}
            if(!File.Exists(Path.Combine(root,"sandbox-install.json"))){MessageBox.Show("Install the sandbox with Setup.exe first. Open Forge Arena Sandbox from the installed folder afterward.","Forge Arena Sandbox",MessageBoxButtons.OK,MessageBoxIcon.Information);return 1;}
            bool owner;
            using(var mutex=new Mutex(true,"Local\\ForgeArenaSandbox.Client."+Key(root),out owner)) {
                if(!owner){Focus(root);return 0;}
                try {
                    if(Focus(root))return 0;
                    var config=Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(root,"sandbox-install.json")));
                    string python=(string)config["python"];
                    if(!File.Exists(python))throw new InvalidOperationException("The installed Python runtime is missing. Run Setup.exe to repair the prerequisites.");
                    Application.Run(new LaunchWindow(root,python));return LaunchWindow.ExitCode;
                } catch(Exception ex){MessageBox.Show(ex.Message,"Sandbox could not start",MessageBoxButtons.OK,MessageBoxIcon.Error);return 1;}
                finally{mutex.ReleaseMutex();}
            }
        }
    }
    internal sealed class LaunchWindow : Form {
        public static int ExitCode=0;
        private readonly string root,python;
        private readonly Label status;
        private readonly ProgressBar progress;
        public LaunchWindow(string folder,string interpreter) {
            root=folder;python=interpreter;
            Text="Forge Arena Sandbox";ClientSize=new Size(540,210);StartPosition=FormStartPosition.CenterScreen;
            FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;MinimizeBox=true;ControlBox=false;
            BackColor=Color.FromArgb(24,27,34);ForeColor=Color.FromArgb(239,240,243);Font=new Font("Segoe UI",10);
            var title=new Label{Text="Forge Arena Sandbox",Font=new Font("Segoe UI",23,FontStyle.Bold),AutoSize=true,Location=new Point(26,24)};Controls.Add(title);
            var subtitle=new Label{Text="Local play  ·  Forge bot matches",AutoSize=true,ForeColor=Color.FromArgb(182,190,204),Location=new Point(29,72)};Controls.Add(subtitle);
            status=new Label{Text="Checking the installed client…",AutoSize=false,Size=new Size(482,38),Location=new Point(29,108)};Controls.Add(status);
            progress=new ProgressBar{Style=ProgressBarStyle.Marquee,MarqueeAnimationSpeed=25,Size=new Size(482,8),Location=new Point(29,163)};Controls.Add(progress);
            Shown+=async delegate {await StartClient();};
        }
        private void Status(string message) {
            if(IsDisposed)return;
            BeginInvoke((Action)(()=>status.Text=message.Length>150?message.Substring(0,150):message));
        }
        private async Task StartClient() {
            string logPath=null;
            try {
                Directory.CreateDirectory(Path.Combine(root,"logs"));
                logPath=Path.Combine(root,"logs","launcher-"+DateTime.Now.ToString("yyyyMMdd-HHmmss-fff")+".log");
                string bootstrap=Path.Combine(root,"client_bootstrap.py");
                if(!File.Exists(bootstrap))throw new InvalidOperationException("The installed launcher is incomplete. Run Setup.exe again.");
                using(var log=new StreamWriter(logPath,false,Encoding.UTF8))using(var process=new Process()) {
                    process.StartInfo=new ProcessStartInfo(python,"-B \""+bootstrap+"\" hub --no-window"){WorkingDirectory=root,UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8};
                    process.StartInfo.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"]="1";
                    process.StartInfo.EnvironmentVariables["PYTHONIOENCODING"]="utf-8";
                    process.OutputDataReceived+=(s,e)=>{if(e.Data!=null){lock(log){log.WriteLine(e.Data);log.Flush();}if(!e.Data.TrimStart().StartsWith("{") && e.Data.EndsWith("…"))Status(e.Data);}};
                    process.ErrorDataReceived+=(s,e)=>{if(e.Data!=null)lock(log){log.WriteLine(e.Data);log.Flush();}};
                    process.Start();process.BeginOutputReadLine();process.BeginErrorReadLine();
                    await Task.Run(()=>process.WaitForExit());ExitCode=process.ExitCode;
                    if(ExitCode!=0)throw new InvalidOperationException("The client could not finish starting. Your saved decks and collection were preserved.\n\nDetails: "+logPath);
                }
                Close();
            } catch(Exception ex){ExitCode=1;progress.Style=ProgressBarStyle.Continuous;MessageBox.Show(this,ex.Message,"Sandbox could not start",MessageBoxButtons.OK,MessageBoxIcon.Error);Close();}
        }
    }
}
