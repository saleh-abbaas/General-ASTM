using System.ComponentModel.DataAnnotations;

namespace AHGLIS.Core.Models;

/// <summary>
/// Describes a single analyser connection that should be monitored by the service.
/// </summary>
public sealed class DeviceProfile : IEquatable<DeviceProfile>
{
    /// <summary>
    /// Gets or sets a human readable name that uniquely identifies the analyser.
    /// </summary>
    [Required]
    public string DeviceName { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the Windows COM port that exposes the analyser.
    /// </summary>
    [Required]
    public string ComPort { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the serial port baud rate.
    /// </summary>
    [Range(1200, 921600)]
    public int BaudRate { get; set; } = 9600;

    /// <summary>
    /// Gets or sets the directory that will receive ASTM payloads as individual text files.
    /// </summary>
    [Required]
    public string OutputDirectory { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the directory that will host the per-device diagnostic log.
    /// </summary>
    [Required]
    public string LogDirectory { get; set; } = string.Empty;

    /// <summary>
    /// Returns a path that can be used to persist analyser output for the specified timestamp.
    /// </summary>
    public string CreatePayloadPath(DateTime timestampUtc)
    {
        var fileName = $"{Sanitise(DeviceName)}_{timestampUtc:yyyyMMdd_HHmmssfff}.txt";
        return Path.Combine(OutputDirectory, fileName);
    }

    /// <summary>
    /// Returns a path that can be used to persist analyser specific diagnostics.
    /// </summary>
    public string CreateLogPath(DateTime timestampUtc)
    {
        var fileName = $"{Sanitise(DeviceName)}_{timestampUtc:yyyyMMdd}.log";
        return Path.Combine(LogDirectory, fileName);
    }

    /// <inheritdoc />
    public bool Equals(DeviceProfile? other)
    {
        if (other is null)
        {
            return false;
        }

        return string.Equals(DeviceName, other.DeviceName, StringComparison.OrdinalIgnoreCase)
               && string.Equals(ComPort, other.ComPort, StringComparison.OrdinalIgnoreCase)
               && BaudRate == other.BaudRate
               && string.Equals(OutputDirectory, other.OutputDirectory, StringComparison.OrdinalIgnoreCase)
               && string.Equals(LogDirectory, other.LogDirectory, StringComparison.OrdinalIgnoreCase);
    }

    /// <inheritdoc />
    public override bool Equals(object? obj) => Equals(obj as DeviceProfile);

    /// <inheritdoc />
    public override int GetHashCode()
    {
        return HashCode.Combine(
            DeviceName?.ToUpperInvariant(),
            ComPort?.ToUpperInvariant(),
            BaudRate,
            OutputDirectory?.ToUpperInvariant(),
            LogDirectory?.ToUpperInvariant());
    }

    private static string Sanitise(string value)
    {
        var invalid = Path.GetInvalidFileNameChars();
        var result = new char[value.Length];
        for (var i = 0; i < value.Length; i++)
        {
            var current = value[i];
            result[i] = invalid.Contains(current) ? '_' : current;
        }

        return new string(result).Trim('_');
    }
}
