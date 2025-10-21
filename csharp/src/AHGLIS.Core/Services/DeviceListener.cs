using System.IO.Ports;
using System.Text;
using AHGLIS.Core.Logging;
using AHGLIS.Core.Models;
using Microsoft.Extensions.Logging;

namespace AHGLIS.Core.Services;

/// <summary>
/// Listens to a serial port and emits ASTM payloads to disk for a single analyser.
/// </summary>
public sealed class DeviceListener : IAsyncDisposable
{
    private readonly ILogger<DeviceListener> _logger;
    private readonly ServiceLogWriter _serviceLogWriter;
    private readonly TimeSpan _reconnectDelay = TimeSpan.FromSeconds(5);
    private readonly object _lifecycleSync = new();

    private CancellationTokenSource? _cts;
    private Task? _worker;

    /// <summary>
    /// Initializes a new instance of the <see cref="DeviceListener"/> class.
    /// </summary>
    public DeviceListener(DeviceProfile profile, ILogger<DeviceListener> logger, ServiceLogWriter serviceLogWriter)
    {
        Profile = profile ?? throw new ArgumentNullException(nameof(profile));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _serviceLogWriter = serviceLogWriter ?? throw new ArgumentNullException(nameof(serviceLogWriter));
    }

    /// <summary>
    /// Gets the profile represented by the listener.
    /// </summary>
    public DeviceProfile Profile { get; }

    /// <summary>
    /// Starts monitoring the serial port.
    /// </summary>
    public Task StartAsync(CancellationToken cancellationToken)
    {
        lock (_lifecycleSync)
        {
            if (_worker is not null)
            {
                return Task.CompletedTask;
            }

            Directory.CreateDirectory(Profile.OutputDirectory);
            Directory.CreateDirectory(Profile.LogDirectory);

            _cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            _worker = Task.Run(() => RunAsync(_cts.Token), CancellationToken.None);
            return Task.CompletedTask;
        }
    }

    /// <summary>
    /// Stops monitoring the serial port and waits for the background task to complete.
    /// </summary>
    public async Task StopAsync(CancellationToken cancellationToken)
    {
        Task? worker;
        lock (_lifecycleSync)
        {
            if (_worker is null)
            {
                return;
            }

            _cts?.Cancel();
            worker = _worker;
        }

        if (worker is not null)
        {
            if (cancellationToken.CanBeCanceled)
            {
                await Task.WhenAny(worker, Task.Delay(Timeout.Infinite, cancellationToken));
            }
            else
            {
                await worker;
            }
        }

        lock (_lifecycleSync)
        {
            _worker = null;
            _cts?.Dispose();
            _cts = null;
        }
    }

    /// <inheritdoc />
    public async ValueTask DisposeAsync()
    {
        if (_worker is not null)
        {
            await StopAsync(CancellationToken.None);
        }
    }

    private async Task RunAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                using var port = CreatePort();
                port.Open();
                _logger.LogInformation("{Device} connected to {Port} at {BaudRate} baud", Profile.DeviceName, Profile.ComPort, Profile.BaudRate);
                _serviceLogWriter.Info(Profile.DeviceName, $"Connected to {Profile.ComPort} at {Profile.BaudRate} baud");

                await ListenAsync(port, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (UnauthorizedAccessException ex)
            {
                _logger.LogError(ex, "Access to {Port} denied for device {Device}", Profile.ComPort, Profile.DeviceName);
                _serviceLogWriter.Error(Profile.DeviceName, $"Access to {Profile.ComPort} denied", ex);
                await Task.Delay(_reconnectDelay, cancellationToken);
            }
            catch (IOException ex)
            {
                _logger.LogError(ex, "I/O failure on {Port} for device {Device}", Profile.ComPort, Profile.DeviceName);
                _serviceLogWriter.Error(Profile.DeviceName, $"I/O failure on {Profile.ComPort}", ex);
                await Task.Delay(_reconnectDelay, cancellationToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unexpected error for device {Device}", Profile.DeviceName);
                _serviceLogWriter.Error(Profile.DeviceName, "Unexpected error", ex);
                await Task.Delay(_reconnectDelay, cancellationToken);
            }
        }
    }

    private async Task ListenAsync(SerialPort port, CancellationToken cancellationToken)
    {
        using var deviceLog = new StreamWriter(new FileStream(
            Profile.CreateLogPath(DateTime.UtcNow),
            FileMode.Append,
            FileAccess.Write,
            FileShare.Read)) { AutoFlush = true };

        var buffer = new StringBuilder();

        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                var line = port.ReadLine();
                if (line is null)
                {
                    continue;
                }

                if (line.Length == 0)
                {
                    continue;
                }

                buffer.AppendLine(line);

                if (line.EndsWith("ETX") || line.EndsWith("\u0003", StringComparison.Ordinal))
                {
                    await PersistPayloadAsync(buffer.ToString(), deviceLog, cancellationToken);
                    buffer.Clear();
                }
            }
            catch (TimeoutException)
            {
                if (buffer.Length > 0)
                {
                    await PersistPayloadAsync(buffer.ToString(), deviceLog, cancellationToken);
                    buffer.Clear();
                }
            }
        }

        if (buffer.Length > 0)
        {
            await PersistPayloadAsync(buffer.ToString(), deviceLog, cancellationToken);
        }
    }

    private async Task PersistPayloadAsync(string payload, StreamWriter deviceLog, CancellationToken cancellationToken)
    {
        var filePath = Profile.CreatePayloadPath(DateTime.UtcNow);
        await File.WriteAllTextAsync(filePath, payload, cancellationToken);
        await deviceLog.WriteLineAsync(payload);
        await deviceLog.WriteLineAsync(new string('-', 40));

        _logger.LogInformation("Persisted payload for {Device} to {Path}", Profile.DeviceName, filePath);
        _serviceLogWriter.Info(Profile.DeviceName, $"Persisted payload to {filePath}");
    }

    private SerialPort CreatePort()
    {
        return new SerialPort(Profile.ComPort, Profile.BaudRate)
        {
            ReadTimeout = 1000,
            NewLine = "\r",
            DtrEnable = true,
            RtsEnable = true,
            Parity = Parity.None,
            DataBits = 8,
            StopBits = StopBits.One,
            Handshake = Handshake.None,
        };
    }
}
