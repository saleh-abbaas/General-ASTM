using System.Diagnostics;
using System.ServiceProcess;

namespace AHGLIS.Service;

/// <summary>
/// Provides helper operations for installing and managing the Windows service.
/// </summary>
public static class ServiceInstaller
{
    private const string ServiceName = "AHG LIS Device Listener";
    private const string ServiceDescription = "Bridges ASTM serial data from analysers to AHG LIS text files.";

    /// <summary>
    /// Installs the Windows service and configures it for automatic start.
    /// </summary>
    public static async Task InstallAsync(CancellationToken cancellationToken = default)
    {
        if (IsInstalled())
        {
            return;
        }

        var executablePath = Environment.ProcessPath ?? throw new InvalidOperationException("Cannot determine executable path.");
        var binPath = $"\"{executablePath}\" run";

        await RunProcessAsync("sc.exe", $"create \"{ServiceName}\" binPath= \"{binPath}\" start= auto", cancellationToken);
        await RunProcessAsync("sc.exe", $"description \"{ServiceName}\" \"{ServiceDescription}\"", cancellationToken);
    }

    /// <summary>
    /// Removes the Windows service if it has been installed.
    /// </summary>
    public static async Task UninstallAsync(CancellationToken cancellationToken = default)
    {
        if (!IsInstalled())
        {
            return;
        }

        await StopAsync(TimeSpan.FromSeconds(30));
        await RunProcessAsync("sc.exe", $"delete \"{ServiceName}\"", cancellationToken);
    }

    /// <summary>
    /// Starts the Windows service if it is installed.
    /// </summary>
    public static async Task StartAsync(TimeSpan timeout)
    {
        if (!IsInstalled())
        {
            throw new InvalidOperationException("Service is not installed.");
        }

        using var controller = new ServiceController(ServiceName);
        if (controller.Status == ServiceControllerStatus.Running)
        {
            return;
        }

        controller.Start();
        controller.WaitForStatus(ServiceControllerStatus.Running, timeout);
        await Task.CompletedTask;
    }

    /// <summary>
    /// Stops the Windows service if it is running.
    /// </summary>
    public static async Task StopAsync(TimeSpan timeout)
    {
        if (!IsInstalled())
        {
            return;
        }

        using var controller = new ServiceController(ServiceName);
        if (controller.Status is ServiceControllerStatus.Stopped or ServiceControllerStatus.StopPending)
        {
            controller.WaitForStatus(ServiceControllerStatus.Stopped, timeout);
            return;
        }

        controller.Stop();
        controller.WaitForStatus(ServiceControllerStatus.Stopped, timeout);
        await Task.CompletedTask;
    }

    /// <summary>
    /// Returns the current status of the Windows service, or <c>null</c> when the service is not installed.
    /// </summary>
    public static ServiceControllerStatus? GetStatus()
    {
        if (!IsInstalled())
        {
            return null;
        }

        using var controller = new ServiceController(ServiceName);
        return controller.Status;
    }

    /// <summary>
    /// Determines whether the Windows service is registered on the current machine.
    /// </summary>
    public static bool IsInstalled()
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

    private static async Task RunProcessAsync(string fileName, string arguments, CancellationToken cancellationToken)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            CreateNoWindow = true,
            UseShellExecute = false,
            RedirectStandardError = true,
            RedirectStandardOutput = true,
        };

        using var process = Process.Start(startInfo) ?? throw new InvalidOperationException($"Failed to launch {fileName}.");
        await process.WaitForExitAsync(cancellationToken);

        if (process.ExitCode != 0)
        {
            var output = await process.StandardOutput.ReadToEndAsync(cancellationToken);
            var error = await process.StandardError.ReadToEndAsync(cancellationToken);
            throw new InvalidOperationException($"Command {fileName} {arguments} failed with exit code {process.ExitCode}. Output: {output}. Error: {error}");
        }
    }
}
