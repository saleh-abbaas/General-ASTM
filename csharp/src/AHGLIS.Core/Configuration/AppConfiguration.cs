using AHGLIS.Core.Models;

namespace AHGLIS.Core.Configuration;

/// <summary>
/// Represents all persisted settings required by the AHG LIS Project components.
/// </summary>
public sealed class AppConfiguration
{
    /// <summary>
    /// Gets the default root directory used to store configuration and service data.
    /// </summary>
    public static string DefaultRoot { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
        "AHG LIS Project");

    /// <summary>
    /// Gets the default configuration path persisted on disk.
    /// </summary>
    public static string DefaultConfigurationPath { get; } = Path.Combine(DefaultRoot, "ahg-lis.settings.json");

    /// <summary>
    /// Gets or sets the directory that will contain service level diagnostics.
    /// </summary>
    public string ServiceLogDirectory { get; set; } = Path.Combine(DefaultRoot, "ServiceLogs");

    /// <summary>
    /// Gets or sets all configured analyser profiles.
    /// </summary>
    public List<DeviceProfile> Devices { get; set; } = new();

    /// <summary>
    /// Ensures that all directories referenced by the configuration exist on disk.
    /// </summary>
    public void EnsureDirectories()
    {
        Directory.CreateDirectory(DefaultRoot);
        if (!string.IsNullOrWhiteSpace(ServiceLogDirectory))
        {
            Directory.CreateDirectory(ServiceLogDirectory);
        }

        foreach (var device in Devices)
        {
            if (!string.IsNullOrWhiteSpace(device.OutputDirectory))
            {
                Directory.CreateDirectory(device.OutputDirectory);
            }

            if (!string.IsNullOrWhiteSpace(device.LogDirectory))
            {
                Directory.CreateDirectory(device.LogDirectory);
            }
        }
    }
}
