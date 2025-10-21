using System.Text;

namespace AHGLIS.Core.Logging;

/// <summary>
/// Provides lightweight file logging that can be shared by the Windows service and the GUI application.
/// </summary>
public sealed class ServiceLogWriter
{
    private string _logDirectory;
    private readonly object _sync = new();

    /// <summary>
    /// Initializes a new instance of the <see cref="ServiceLogWriter"/> class.
    /// </summary>
    /// <param name="logDirectory">The destination directory for log files.</param>
    public ServiceLogWriter(string logDirectory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(logDirectory);
        _logDirectory = logDirectory;
    }

    /// <summary>
    /// Updates the log directory at runtime. The directory is created on demand when the next message is written.
    /// </summary>
    /// <param name="logDirectory">The new log directory.</param>
    public void UpdateLogDirectory(string logDirectory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(logDirectory);
        _logDirectory = logDirectory;
    }

    /// <summary>
    /// Writes an informational message to the service log.
    /// </summary>
    public void Info(string source, string message) => Write("INFO", source, message, null);

    /// <summary>
    /// Writes a warning message to the service log.
    /// </summary>
    public void Warn(string source, string message) => Write("WARN", source, message, null);

    /// <summary>
    /// Writes an error message to the service log.
    /// </summary>
    public void Error(string source, string message, Exception? exception = null) => Write("ERROR", source, message, exception);

    private void Write(string level, string source, string message, Exception? exception)
    {
        var directory = _logDirectory;
        Directory.CreateDirectory(directory);
        var filePath = Path.Combine(directory, $"AHGLIS-Service-{DateTime.UtcNow:yyyyMMdd}.log");
        var builder = new StringBuilder();
        builder.Append(DateTime.UtcNow.ToString("O"));
        builder.Append(' ');
        builder.Append(level);
        builder.Append(' ');
        builder.Append(source);
        builder.Append(" :: ");
        builder.AppendLine(message);

        if (exception is not null)
        {
            builder.AppendLine(exception.ToString());
        }

        lock (_sync)
        {
            File.AppendAllText(filePath, builder.ToString());
        }
    }
}
