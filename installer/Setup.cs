using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Windows.Forms;

internal static class Setup
{
    private static bool Verify(Stream stream)
    {
        using (SHA256 sha = SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").Equals(SetupInfo.Hash, StringComparison.OrdinalIgnoreCase);
    }

    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length == 1 && args[0] == "--verify")
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Lume.Payload.msi"))
                return stream != null && Verify(stream) ? 0 : 4;
        }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        if (!Environment.Is64BitOperatingSystem)
        {
            MessageBox.Show("O Lume requer Windows 10 ou 11 de 64 bits.", "Lume", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return 1;
        }
        using (Welcome form = new Welcome())
        {
            Application.Run(form);
            return form.ExitCode;
        }
    }

    private sealed class Welcome : Form
    {
        internal int ExitCode;
        private readonly Label status;
        private readonly BackgroundWorker worker = new BackgroundWorker();
        private readonly string folder = Path.Combine(Path.GetTempPath(), "Lume-Setup-" + Guid.NewGuid().ToString("N"));

        internal Welcome()
        {
            Text = "Lume — Instalação";
            ClientSize = new Size(560, 240);
            BackColor = Color.FromArgb(250, 249, 245);
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            AutoScaleMode = AutoScaleMode.Dpi;
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Lume.Icon.ico"))
                if (stream != null) Icon = new Icon(stream);
            Controls.Add(new Label { Text = "Lume", Font = new Font("Georgia", 30), ForeColor = Color.FromArgb(37, 37, 34), Location = new Point(32, 26), AutoSize = true });
            status = new Label { Text = "Preparando seu espaço para as palavras…", Font = new Font("Segoe UI", 11), ForeColor = Color.FromArgb(108, 106, 100), Location = new Point(36, 98), Size = new Size(490, 50) };
            Controls.Add(status);
            Controls.Add(new ProgressBar { Location = new Point(36, 164), Size = new Size(488, 8), Style = ProgressBarStyle.Marquee });
            Controls.Add(new Label { Text = "O assistente de instalação será aberto em instantes.", Font = new Font("Segoe UI", 9), ForeColor = Color.FromArgb(108, 106, 100), Location = new Point(36, 190), AutoSize = true });
            worker.DoWork += Install;
            worker.RunWorkerCompleted += Complete;
            Shown += delegate { worker.RunWorkerAsync(); };
            FormClosing += delegate(object sender, FormClosingEventArgs e) { if (worker.IsBusy) e.Cancel = true; };
        }

        private void Install(object sender, DoWorkEventArgs e)
        {
            Directory.CreateDirectory(folder);
            string msi = Path.Combine(folder, "Lume.msi");
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Lume.Payload.msi"))
            {
                if (stream == null || !Verify(stream)) throw new InvalidDataException("O instalador está incompleto ou corrompido. Baixe novamente pela página oficial.");
                stream.Position = 0;
                using (FileStream file = new FileStream(msi, FileMode.CreateNew, FileAccess.Write, FileShare.None)) stream.CopyTo(file);
            }
            ProcessStartInfo start = new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, "msiexec.exe"), "/i \"" + msi + "\" /norestart");
            start.UseShellExecute = false;
            using (Process process = Process.Start(start))
            {
                BeginInvoke((Action)delegate { Hide(); });
                process.WaitForExit();
                e.Result = process.ExitCode;
            }
        }

        private void Complete(object sender, RunWorkerCompletedEventArgs e)
        {
            try
            {
                string msi = Path.Combine(folder, "Lume.msi");
                if (File.Exists(msi)) File.Delete(msi);
                if (Directory.Exists(folder)) Directory.Delete(folder);
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            ExitCode = e.Error == null ? (int)e.Result : 1;
            if (e.Error != null || (ExitCode != 0 && ExitCode != 1602 && ExitCode != 3010))
            {
                Show();
                MessageBox.Show(this, e.Error == null ? "Não foi possível concluir a instalação (código " + ExitCode + "). Feche o aplicativo e tente novamente." : e.Error.Message, "Lume", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            Close();
        }
    }
}
