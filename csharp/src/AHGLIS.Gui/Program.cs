using System.Windows.Forms;
using AHGLIS.Core.Configuration;
using AHGLIS.Core.Logging;

namespace AHGLIS.Gui;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        Application.SetHighDpiMode(HighDpiMode.SystemAware);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        var configurationStore = new ConfigurationStore();
        var configuration = configurationStore.LoadAsync().GetAwaiter().GetResult();
        var serviceLogWriter = new ServiceLogWriter(configuration.ServiceLogDirectory);

        using var mainForm = new MainForm(configurationStore, serviceLogWriter);
        Application.Run(mainForm);
    }
}
