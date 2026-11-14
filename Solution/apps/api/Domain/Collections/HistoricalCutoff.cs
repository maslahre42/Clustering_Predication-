using System.Globalization;
namespace GarbageCollector.Api.Domain.Collections;

/// <summary>An inclusive service-day boundary, never an inferred collection timestamp.</summary>
public readonly record struct HistoricalCutoff
{
    public string Value { get; }
    private HistoricalCutoff(string value) => Value = value;

    public static bool IsValid(string? value) => !string.IsNullOrEmpty(value) &&
        DateOnly.TryParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out _);

    public static HistoricalCutoff Parse(string value) => IsValid(value)
        ? new(value) : throw new ArgumentException("Use an ISO date (yyyy-MM-dd).", nameof(value));

    public bool Includes(string observationDate) => string.CompareOrdinal(observationDate, Value) <= 0;
}
