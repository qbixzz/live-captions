// Live Captions launcher ("Live Captions.exe" in the release zip).
//   First run: a setup window installs Python and the packages (uv sync) and downloads the models, then starts the app.
//   Later runs: starts the app (pythonw, no console window) straight away.
//   Drop an audio or video file on the exe to rehearse with it.  "Live Captions.exe --setup" runs the setup again.
//   Unattended setup: --setup --auto [--no-shortcuts]
// Written for the C# 5 compiler that comes with Windows (.NET Framework 4); tools/build_release.ps1 builds it.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("Live Captions")]
[assembly: AssemblyProduct("Live Captions")]
[assembly: AssemblyDescription("Live English captions with a Thai translation")]

static class Launcher
{
    public const string ReadyMarker = @".venv\live-captions-ready.txt";

    [STAThread]
    static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        string dir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        bool forceSetup = Array.IndexOf(args, "--setup") >= 0;
        string sim = null;
        foreach (string a in args)
            if (!a.StartsWith("--") && File.Exists(a)) sim = Path.GetFullPath(a);

        if (!File.Exists(Path.Combine(dir, @"live_captions\__main__.py")))
        {
            Ui.Error("The program files are missing next to Live Captions.exe.\n\n" +
                     "Extract the whole zip to a folder first (right-click the zip, Extract All), then run Live Captions.exe from there.");
            return 1;
        }
        if (forceSetup || !File.Exists(Path.Combine(dir, ReadyMarker)))
        {
            if (!CanWrite(dir))
            {
                Ui.Error("Live Captions cannot write to this folder:\n" + dir + "\n\n" +
                         "Move the folder somewhere of your own, such as Documents, and run it again.");
                return 1;
            }
            SetupForm f = new SetupForm(dir);
            if (Array.IndexOf(args, "--no-shortcuts") >= 0) f.NoShortcuts();
            if (Array.IndexOf(args, "--auto") >= 0) f.Shown += delegate { f.BeginSetup(); };  // unattended (tests)
            Application.Run(f);
            if (!f.Succeeded) return 1;
        }
        return StartApp(dir, sim) ? 0 : 1;
    }

    static bool CanWrite(string dir)
    {
        try
        {
            string p = Path.Combine(dir, ".write-test");
            File.WriteAllText(p, "x");
            File.Delete(p);
            return true;
        }
        catch { return false; }
    }

    static bool StartApp(string dir, string sim)
    {
        string py = Path.Combine(dir, @".venv\Scripts\pythonw.exe");
        string args = "-X utf8 -m live_captions --log logs\\live-captions.log";
        if (sim != null) args += " --sim \"" + sim + "\"";
        ProcessStartInfo psi = new ProcessStartInfo(py, args);
        psi.WorkingDirectory = dir;
        psi.UseShellExecute = false;
        Process p;
        try { p = Process.Start(psi); }
        catch (Exception e)
        {
            Ui.Error("Could not start Live Captions:\n" + e.Message + "\n\nRun the setup again: start \"Live Captions.exe --setup\".");
            return false;
        }
        // A crash while starting shows up within a few seconds; then show the end of the log.
        if (p.WaitForExit(10000) && p.ExitCode != 0)
        {
            string log = Path.Combine(dir, @"logs\live-captions.log");
            string tail = "";
            try
            {
                string[] lines = File.ReadAllLines(log);
                tail = string.Join("\n", lines, Math.Max(0, lines.Length - 12), Math.Min(12, lines.Length));
            }
            catch { }
            Ui.Error("Live Captions stopped while starting.\n\n" + tail + "\n\nThe full log is in " + log);
            return false;
        }
        return true;
    }
}

static class Ui
{
    public static readonly Color Bg = Color.FromArgb(0x0F, 0x12, 0x16);
    public static readonly Color Panel = Color.FromArgb(0x16, 0x1B, 0x22);
    public static readonly Color Fg = Color.FromArgb(0xF4, 0xF6, 0xF8);
    public static readonly Color Muted = Color.FromArgb(0x9A, 0xA6, 0xB2);
    public static readonly Color Accent = Color.FromArgb(0x3D, 0x8B, 0xFD);
    public static readonly Color Ok = Color.FromArgb(0x3F, 0xB9, 0x7F);
    public static readonly Color Err = Color.FromArgb(0xF2, 0x61, 0x5D);

    public static void Error(string msg)
    {
        MessageBox.Show(msg, "Live Captions", MessageBoxButtons.OK, MessageBoxIcon.Warning);
    }
}

class SetupForm : Form
{
    readonly string dir;
    readonly Label status;
    readonly TextBox log;
    readonly ProgressBar bar;
    readonly CheckBox shortcuts;
    readonly Button go, cancel;
    Process current;
    volatile bool cancelled;
    public bool Succeeded;

    public SetupForm(string dir)
    {
        this.dir = dir;
        Text = "Live Captions setup";
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;
        BackColor = Ui.Bg;
        ForeColor = Ui.Fg;
        Font = new Font("Segoe UI", 9.75f);
        AutoScaleMode = AutoScaleMode.Dpi;
        ClientSize = new Size(760, 540);

        Label title = new Label();
        title.Text = "Set up Live Captions";
        title.Font = new Font("Segoe UI Semibold", 16f);
        title.SetBounds(24, 18, 712, 36);

        Label info = new Label();
        info.Text =
            "Live Captions runs entirely on this computer, so the first start installs what it needs:\n" +
            "  •  Python and its packages, with PyTorch for NVIDIA graphics cards (about 5 GB)\n" +
            "  •  the speech-to-text and translation models (about 5.5 GB)\n" +
            "This takes 10 to 30 minutes, depending on your connection. It happens only once.\n" +
            "You need Windows 10 or 11 and an NVIDIA graphics card with a recent driver.";
        info.ForeColor = Ui.Muted;
        info.SetBounds(24, 60, 712, 100);

        status = new Label();
        status.Text = "Ready to install into " + dir;
        status.AutoEllipsis = true;
        status.SetBounds(24, 166, 712, 22);

        bar = new ProgressBar();
        bar.SetBounds(24, 192, 712, 8);
        bar.Style = ProgressBarStyle.Continuous;
        bar.Maximum = 4;

        log = new TextBox();
        log.Multiline = true;
        log.ReadOnly = true;
        log.ScrollBars = ScrollBars.Vertical;
        log.BackColor = Ui.Panel;
        log.ForeColor = Ui.Muted;
        log.BorderStyle = BorderStyle.None;
        log.Font = new Font("Consolas", 9f);
        log.SetBounds(24, 214, 712, 250);

        shortcuts = new CheckBox();
        shortcuts.Text = "Add Live Captions to the Start menu and the desktop";
        shortcuts.Checked = true;
        shortcuts.SetBounds(24, 482, 420, 26);

        go = new Button();
        go.Text = "Install";
        go.SetBounds(520, 478, 104, 34);
        Style(go, true);
        go.Click += delegate { Begin(); };

        cancel = new Button();
        cancel.Text = "Cancel";
        cancel.SetBounds(632, 478, 104, 34);
        Style(cancel, false);
        cancel.Click += delegate { Cancel(); };

        Controls.AddRange(new Control[] { title, info, status, bar, log, shortcuts, go, cancel });
        AcceptButton = go;
        FormClosing += delegate(object s, FormClosingEventArgs e)
        {
            if (current != null && !cancelled && !Succeeded)
            {
                if (MessageBox.Show("Stop the setup? You can run it again later; finished parts are kept.", "Live Captions",
                                    MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.No) { e.Cancel = true; return; }
                Kill();
            }
        };
    }

    static void Style(Button b, bool primary)
    {
        b.FlatStyle = FlatStyle.Flat;
        b.FlatAppearance.BorderSize = primary ? 0 : 1;
        b.FlatAppearance.BorderColor = Color.FromArgb(0x3A, 0x42, 0x4D);
        b.BackColor = primary ? Ui.Accent : Ui.Panel;
        b.ForeColor = Color.White;
        b.Cursor = Cursors.Hand;
    }

    void Cancel()
    {
        if (current != null && !Succeeded)
        {
            Close();  // asks first, see FormClosing
            return;
        }
        Close();
    }

    void Kill()
    {
        cancelled = true;
        try
        {
            if (current != null && !current.HasExited)
            {
                // the whole tree: uv and the Python it started
                Process.Start(new ProcessStartInfo("taskkill", "/T /F /PID " + current.Id) { CreateNoWindow = true, UseShellExecute = false });
            }
        }
        catch { }
    }

    public void NoShortcuts() { shortcuts.Checked = false; }

    public void BeginSetup() { Begin(); }

    void Begin()
    {
        go.Enabled = false;
        shortcuts.Enabled = false;
        cancelled = false;
        log.Clear();
        bar.Value = 0;
        bool makeShortcuts = shortcuts.Checked;
        Thread t = new Thread(delegate() { Run(makeShortcuts); });
        t.IsBackground = true;
        t.Start();
    }

    void Run(bool makeShortcuts)
    {
        string uv = Path.Combine(dir, @"tools\uv.exe");
        if (!File.Exists(uv)) uv = "uv";
        string py = Path.Combine(dir, @".venv\Scripts\python.exe");
        try
        {
            Step(1, "Installing Python and the packages (about 5 GB the first time)…");
            Exec(uv, "sync --frozen --no-install-project --no-progress");

            Step(2, "Checking the graphics card…");
            int gpu = Exec(py, "-c \"import torch; ok = torch.cuda.is_available(); print('GPU: ' + (torch.cuda.get_device_name(0) if ok else 'no CUDA GPU found')); raise SystemExit(0 if ok else 3)\"", true);
            if (gpu != 0)
                Line("Warning: no NVIDIA GPU could be used. Update the NVIDIA driver (version 570 or newer). The captions will not work without it.");

            Step(3, "Downloading the speech and translation models (about 5.5 GB)…");
            Exec(py, "-X utf8 -u -m live_captions.download --if-missing");

            Step(4, "Finishing…");
            string terms = Path.Combine(dir, "terms.txt");
            if (!File.Exists(terms) && File.Exists(Path.Combine(dir, "terms.example.txt")))
                File.Copy(Path.Combine(dir, "terms.example.txt"), terms);
            File.WriteAllText(Path.Combine(dir, Launcher.ReadyMarker), DateTime.Now.ToString("s"));
            if (makeShortcuts)
            {
                try { MakeShortcuts(); Line("Added Live Captions to the Start menu and the desktop."); }
                catch (Exception e) { Line("Could not add the shortcuts: " + e.Message); }
            }
            Done(true, "Setup finished. Starting Live Captions…");
        }
        catch (Exception e)
        {
            if (cancelled) return;
            Line("");
            Line("Setup stopped: " + e.Message);
            Done(false, "Setup did not finish. Check the messages above, then press Try again; finished parts are kept.");
        }
    }

    int Exec(string exe, string args, bool allowFail = false)
    {
        Line("> " + Path.GetFileName(exe) + " " + args);
        ProcessStartInfo psi = new ProcessStartInfo(exe, args);
        psi.WorkingDirectory = dir;
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;
        psi.StandardOutputEncoding = Encoding.UTF8;
        psi.StandardErrorEncoding = Encoding.UTF8;
        psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
        psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        psi.EnvironmentVariables["HF_HUB_DISABLE_PROGRESS_BARS"] = "1";
        psi.EnvironmentVariables["UV_LINK_MODE"] = "copy";
        psi.EnvironmentVariables["NO_COLOR"] = "1";
        Process p = new Process();
        p.StartInfo = psi;
        p.OutputDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null) Line(e.Data); };
        p.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null) Line(e.Data); };
        try { p.Start(); }
        catch (Exception e) { throw new Exception("could not run " + exe + ": " + e.Message); }
        current = p;
        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
        p.WaitForExit();
        current = null;
        if (cancelled) throw new Exception("cancelled");
        if (p.ExitCode != 0 && !allowFail) throw new Exception(Path.GetFileName(exe) + " ended with code " + p.ExitCode);
        return p.ExitCode;
    }

    void MakeShortcuts()
    {
        string exe = Application.ExecutablePath;
        string[] places = {
            Environment.GetFolderPath(Environment.SpecialFolder.Programs),
            Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory)
        };
        Type t = Type.GetTypeFromProgID("WScript.Shell");
        object shell = Activator.CreateInstance(t);
        foreach (string place in places)
        {
            object lnk = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell,
                                        new object[] { Path.Combine(place, "Live Captions.lnk") });
            Type lt = lnk.GetType();
            lt.InvokeMember("TargetPath", BindingFlags.SetProperty, null, lnk, new object[] { exe });
            lt.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, lnk, new object[] { dir });
            lt.InvokeMember("IconLocation", BindingFlags.SetProperty, null, lnk, new object[] { exe + ",0" });
            lt.InvokeMember("Description", BindingFlags.SetProperty, null, lnk, new object[] { "Live English captions with a Thai translation" });
            lt.InvokeMember("Save", BindingFlags.InvokeMethod, null, lnk, null);
        }
    }

    // ---- UI updates from the worker thread
    void Ui_(Action a)
    {
        if (IsDisposed) return;
        try { BeginInvoke(a); } catch { }
    }

    void Step(int n, string text)
    {
        Ui_(delegate { status.Text = "Step " + n + " of 4: " + text; status.ForeColor = Ui.Fg; bar.Value = n - 1; });
        Line("");
        Line("== " + text);
    }

    void Line(string text)
    {
        Ui_(delegate
        {
            if (log.TextLength > 200000) log.Text = log.Text.Substring(100000);
            log.AppendText(text + Environment.NewLine);
        });
    }

    void Done(bool ok, string text)
    {
        Ui_(delegate
        {
            status.Text = text;
            status.ForeColor = ok ? Ui.Ok : Ui.Err;
            if (ok)
            {
                bar.Value = bar.Maximum;
                Succeeded = true;
                System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
                timer.Interval = 1200;
                timer.Tick += delegate { timer.Stop(); Close(); };
                timer.Start();
            }
            else
            {
                go.Text = "Try again";
                go.Enabled = true;
            }
        });
    }
}
