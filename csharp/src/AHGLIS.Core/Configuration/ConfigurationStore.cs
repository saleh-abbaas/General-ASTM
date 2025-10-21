using System.Text.Json;

namespace AHGLIS.Core.Configuration;

/// <summary>
/// Provides persistence for <see cref="AppConfiguration"/> instances.
/// </summary>
public sealed class ConfigurationStore
{
    private readonly JsonSerializerOptions _serializerOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true,
    };

    /// <summary>
    /// Initializes a new instance of the <see cref="ConfigurationStore"/> class.
    /// </summary>
    /// <param name="configurationPath">The path to the configuration file. When <c>null</c> the default path is used.</param>
    public ConfigurationStore(string? configurationPath = null)
    {
        ConfigurationPath = configurationPath ?? AppConfiguration.DefaultConfigurationPath;
    }

    /// <summary>
    /// Gets the configuration path used by the store.
    /// </summary>
    public string ConfigurationPath { get; }

    /// <summary>
    /// Loads the configuration from disk. When no configuration exists a default instance is returned.
    /// </summary>
    public async Task<AppConfiguration> LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(ConfigurationPath))
        {
            return new AppConfiguration();
        }

        await using var stream = File.OpenRead(ConfigurationPath);
        var configuration = await JsonSerializer.DeserializeAsync<AppConfiguration>(stream, _serializerOptions, cancellationToken);
        return configuration ?? new AppConfiguration();
    }

    /// <summary>
    /// Saves the configuration to disk, ensuring all referenced directories are present.
    /// </summary>
    public async Task SaveAsync(AppConfiguration configuration, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(configuration);

        configuration.EnsureDirectories();
        Directory.CreateDirectory(Path.GetDirectoryName(ConfigurationPath)!);

        await using var stream = File.Create(ConfigurationPath);
        await JsonSerializer.SerializeAsync(stream, configuration, _serializerOptions, cancellationToken);
    }
}
