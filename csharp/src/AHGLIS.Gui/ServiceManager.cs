using System.Diagnostics;
using System.ServiceProcess;

namespace AHGLIS.Gui;

/// <summary>
/// Wraps service management logic so the GUI can install, start, and stop the Windows service.
/// </summary>
internal sealed class ServiceManager
{
    private const string ServiceName = "AHG LIS Device Listener";
    private readonly string _serviceExecutablePath;

    public ServiceManager()
    {
        _serviceExecutablePath = Path.Combine(AppContext.BaseDirectory, "AHGLIS.Service.exe");
    }

    public bool ServiceExecutableExists => File.Exists(_serviceExecutablePath);

    public ServiceControllerStatus? GetStatus()
    {
        if (!IsInstalled())
        {
            return null;
        }

        using var controller = new ServiceController(ServiceName);
        return controller.Status;
    }

    public bool IsInstalled()
    {
        try
        {
            using var controller = new ServiceController(ServiceName);
            var _ = controller.Status;
            return true;
        }
        catch (InvalidOperationException)
        {
            return false;
        }
    }

    public Task InstallAsync(CancellationToken cancellationToken)
    {
        EnsureExecutable();
        return RunServiceCommandAsync("install", cancellationToken);
    }

    public Task UninstallAsync(CancellationToken cancellationToken)
    {
        if (!IsInstalled())
        {
            return Task.CompletedTask;
        }

        EnsureExecutable();
        return RunServiceCommandAsync("uninstall", cancellationToken);
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        EnsureExecutable();
        return RunServiceCommandAsync("start", cancellationToken);
    }

    public Task StopAsync(CancellationToken cancellationToken)
    {
        if (!IsInstalled())
        {
            return Task.CompletedTask;
        }

        EnsureExecutable();
        return RunServiceCommandAsync("stop", cancellationToken);
    }

    private void EnsureExecutable()
    {
        if (!ServiceExecutableExists)
        {
            throw new InvalidOperationException($"Unable to locate AHGLIS.Service.exe next to {AppContext.BaseDirectory}.");
        }
    }

    private async Task RunServiceCommandAsync(string command, CancellationToken cancellationToken)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = _serviceExecutablePath,
            Arguments = command,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };

        using var process = Process.Start(startInfo) ?? throw new InvalidOperationException("Unable to start service helper.");
        await process.WaitForExitAsync(cancellationToken);

        if (process.ExitCode != 0)
        {
            var output = await process.StandardOutput.ReadToEndAsync(cancellationToken);
            var error = await process.StandardError.ReadToEndAsync(cancellationToken);
            throw new InvalidOperationException($"Service command '{command}' failed. Output: {output} Error: {error}");
        }
    }
}
