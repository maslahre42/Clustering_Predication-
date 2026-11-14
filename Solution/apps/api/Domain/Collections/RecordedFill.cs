using System.Globalization;
namespace GarbageCollector.Api.Domain.Collections;

/// <summary>Overflow is a category, not an imputed numeric percentage.</summary>
public readonly record struct RecordedFill(double? Percentage, bool WasOverfull)
{
    public static RecordedFill Parse(string? raw) => new(ParsePercentage(raw), IsOverfull(raw));

    public static bool IsOverfull(string? raw) =>
        string.Equals(raw?.Trim(), "overfull", StringComparison.OrdinalIgnoreCase);

    public static double? ParsePercentage(string? raw) =>
        double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var value) && value >= 0 && value <= 100
            ? value : null;
}
