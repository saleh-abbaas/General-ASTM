using AHGLIS.Core.Configuration;
using AHGLIS.Core.Logging;
using AHGLIS.Core.Services;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace AHGLIS.Service;

/// <summary>
/// Windows service host that orchestrates analyser listeners based on the user configuration.
/// </summary>
public sealed class DeviceListenerHostedService : IHostedService, IDisposable
{
    private readonly ConfigurationStore _configurationStore;
    private readonly DeviceListenerOrchestrator _orchestrator;
    private readonly ServiceLogWriter _serviceLogWriter;
    private readonly ILogger<DeviceListenerHostedService> _logger;
    private readonly SemaphoreSlim _reloadLock = new(1, 1);

    private FileSystemWatcher? _watcher;

    /// <summary>
    /// Initializes a new instance of the <see cref="DeviceListenerHostedService"/> class.
    /// </summary>
    public DeviceListenerHostedService(
        ConfigurationStore configurationStore,
        DeviceListenerOrchestrator orchestrator,
        ServiceLogWriter serviceLogWriter,
        ILogger<DeviceListenerHostedService> logger)
    {
        _configurationStore = configurationStore;
        _orchestrator = orchestrator;
        _serviceLogWriter = serviceLogWriter;
        _logger = logger;
    }

    /// <inheritdoc />
    public async Task StartAsync(CancellationToken cancellationToken)
    {
        await ReloadAsync(cancellationToken);
        InitialiseWatcher();
    }

    /// <inheritdoc />
    public async Task StopAsync(CancellationToken cancellationToken)
    {
        _watcher?.Dispose();
        _watcher = null;
        await _orchestrator.StopAllAsync(cancellationToken);
    }

    /// <inheritdoc />
    public void Dispose()
    {
        _watcher?.Dispose();
        _reloadLock.Dispose();
    }

    private async Task ReloadAsync(CancellationToken cancellationToken)
    {
        await _reloadLock.WaitAsync(cancellationToken);
        try
        {
            var configuration = await _configurationStore.LoadAsync(cancellationToken);
            configuration.EnsureDirectories();
            _serviceLogWriter.UpdateLogDirectory(configuration.ServiceLogDirectory);
            await _orchestrator.ApplyAsync(configuration, cancellationToken);
            _logger.LogInformation("Configuration loaded with {Count} device(s)", configuration.Devices.Count);
            _serviceLogWriter.Info("Service", $"Configuration loaded with {configuration.Devices.Count} device(s)");
        }
        finally
        {
            _reloadLock.Release();
        }
    }

    private void InitialiseWatcher()
    {
        var directory = Path.GetDirectoryName(_configurationStore.ConfigurationPath);
        if (string.IsNullOrEmpty(directory))
        {
            return;
        }

        Directory.CreateDirectory(directory);

        _watcher = new FileSystemWatcher(directory, Path.GetFileName(_configurationStore.ConfigurationPath))
        {
            NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite | NotifyFilters.Size,
            EnableRaisingEvents = true,
        };

        _watcher.Changed += HandleConfigurationChanged;
        _watcher.Created += HandleConfigurationChanged;
        _watcher.Renamed += HandleConfigurationChanged;
    }

    private void HandleConfigurationChanged(object sender, FileSystemEventArgs e)
    {
        _ = Task.Run(async () =>
        {
            try
            {
                await Task.Delay(TimeSpan.FromMilliseconds(250));
                await ReloadAsync(CancellationToken.None);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to reload configuration");
                _serviceLogWriter.Error("Service", "Failed to reload configuration", ex);
            }
        });
    }
}
