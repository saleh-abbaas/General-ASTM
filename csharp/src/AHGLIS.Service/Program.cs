using AHGLIS.Core.Configuration;
using AHGLIS.Core.Logging;
using AHGLIS.Core.Services;
using AHGLIS.Service;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var cancellationToken = CancellationToken.None;

if (args.Length > 0)
{
    switch (args[0].ToLowerInvariant())
    {
        case "install":
            await ServiceInstaller.InstallAsync(cancellationToken);
            Console.WriteLine("Service installed successfully.");
            return;
        case "uninstall":
            await ServiceInstaller.UninstallAsync(cancellationToken);
            Console.WriteLine("Service removed successfully.");
            return;
        case "start":
            await ServiceInstaller.StartAsync(TimeSpan.FromSeconds(30));
            Console.WriteLine("Service started successfully.");
            return;
        case "stop":
            await ServiceInstaller.StopAsync(TimeSpan.FromSeconds(30));
            Console.WriteLine("Service stopped successfully.");
            return;
        case "status":
            var status = ServiceInstaller.GetStatus();
            Console.WriteLine(status?.ToString() ?? "Service is not installed.");
            return;
        case "run":
            break;
        default:
            Console.WriteLine("Unknown command. Supported commands: install, uninstall, start, stop, status, run.");
            return;
    }
}

var host = Host.CreateDefaultBuilder(args)
    .UseWindowsService(options => options.ServiceName = "AHG LIS Device Listener")
    .ConfigureLogging(builder =>
    {
        builder.ClearProviders();
        builder.AddSimpleConsole(options =>
        {
            options.SingleLine = true;
            options.TimestampFormat = "yyyy-MM-dd HH:mm:ss ";
        });
    })
    .ConfigureServices(services =>
    {
        services.AddSingleton<ConfigurationStore>();
        services.AddSingleton<ServiceLogWriter>(sp =>
        {
            var configuration = sp.GetRequiredService<ConfigurationStore>()
                .LoadAsync()
                .GetAwaiter()
                .GetResult();
            return new ServiceLogWriter(configuration.ServiceLogDirectory);
        });
        services.AddSingleton<DeviceListenerOrchestrator>();
        services.AddHostedService<DeviceListenerHostedService>();
    })
    .Build();

await host.RunAsync();
