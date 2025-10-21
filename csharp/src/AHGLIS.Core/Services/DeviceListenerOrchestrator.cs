using AHGLIS.Core.Configuration;
using AHGLIS.Core.Logging;
using AHGLIS.Core.Models;
using Microsoft.Extensions.Logging;

namespace AHGLIS.Core.Services;

/// <summary>
/// Manages the lifecycle of <see cref="DeviceListener"/> instances based on the persisted configuration.
/// </summary>
public sealed class DeviceListenerOrchestrator : IAsyncDisposable
{
    private readonly ILoggerFactory _loggerFactory;
    private readonly ServiceLogWriter _serviceLogWriter;
    private readonly Dictionary<string, DeviceListener> _listeners = new(StringComparer.OrdinalIgnoreCase);

    /// <summary>
    /// Initializes a new instance of the <see cref="DeviceListenerOrchestrator"/> class.
    /// </summary>
    public DeviceListenerOrchestrator(ILoggerFactory loggerFactory, ServiceLogWriter serviceLogWriter)
    {
        _loggerFactory = loggerFactory ?? throw new ArgumentNullException(nameof(loggerFactory));
        _serviceLogWriter = serviceLogWriter ?? throw new ArgumentNullException(nameof(serviceLogWriter));
    }

    /// <summary>
    /// Applies the supplied configuration, adding, updating, or removing listeners as required.
    /// </summary>
    public async Task ApplyAsync(AppConfiguration configuration, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(configuration);

        configuration.EnsureDirectories();

        var desired = configuration.Devices.ToDictionary(d => d.DeviceName, StringComparer.OrdinalIgnoreCase);
        var existingKeys = _listeners.Keys.ToList();

        foreach (var key in existingKeys)
        {
            if (!desired.ContainsKey(key))
            {
                await RemoveAsync(key, cancellationToken);
            }
        }

        foreach (var profile in desired.Values)
        {
            if (_listeners.TryGetValue(profile.DeviceName, out var listener))
            {
                if (!listener.Profile.Equals(profile))
                {
                    await RemoveAsync(profile.DeviceName, cancellationToken);
                    await AddAsync(profile, cancellationToken);
                }
            }
            else
            {
                await AddAsync(profile, cancellationToken);
            }
        }
    }

    /// <summary>
    /// Stops all listeners.
    /// </summary>
    public async Task StopAllAsync(CancellationToken cancellationToken = default)
    {
        var keys = _listeners.Keys.ToList();
        foreach (var key in keys)
        {
            await RemoveAsync(key, cancellationToken);
        }
    }

    /// <inheritdoc />
    public async ValueTask DisposeAsync()
    {
        await StopAllAsync();
    }

    private async Task AddAsync(DeviceProfile profile, CancellationToken cancellationToken)
    {
        var listener = new DeviceListener(profile, _loggerFactory.CreateLogger<DeviceListener>(), _serviceLogWriter);
        await listener.StartAsync(cancellationToken);
        _listeners[profile.DeviceName] = listener;
        _serviceLogWriter.Info(profile.DeviceName, "Device listener started");
    }

    private async Task RemoveAsync(string deviceName, CancellationToken cancellationToken)
    {
        if (_listeners.TryGetValue(deviceName, out var listener))
        {
            await listener.StopAsync(cancellationToken);
            await listener.DisposeAsync();
            _listeners.Remove(deviceName);
            _serviceLogWriter.Warn(deviceName, "Device listener stopped");
        }
    }
}
