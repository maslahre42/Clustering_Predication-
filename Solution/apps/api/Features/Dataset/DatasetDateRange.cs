using System.Globalization;
using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
namespace GarbageCollector.Api.Features.Dataset;

/// <summary>Global navigation metadata, independent of the selected historical cutoff.</summary>
public sealed record DatasetDateRange(string? FirstDate, string? LastDate, string? MaxPlanningDate)
{
    public const int PlanningHorizonDays = 7;
    public static DatasetDateRange Create(string? first, string? last)
    {
        if (first is null && last is null) return new(null, null, null);
        if (!HistoricalCutoff.IsValid(first) || !HistoricalCutoff.IsValid(last) || string.CompareOrdinal(first, last) > 0)
            throw new ArgumentException("The database date range must contain valid ordered ISO dates.");
        var finalDate = DateOnly.ParseExact(last!, "yyyy-MM-dd", CultureInfo.InvariantCulture);
        var limit = DateOnly.FromDayNumber(Math.Min(DateOnly.MaxValue.DayNumber, finalDate.DayNumber + PlanningHorizonDays));
        return new(first, last, limit.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
    }

    public static async Task<DatasetDateRange> ReadAsync(HistoryDbContext db, CancellationToken ct = default)
    {
        var bounds = await db.Observations.AsNoTracking().GroupBy(_ => 1)
            .Select(rows => new { First = rows.Min(row => row.Date), Last = rows.Max(row => row.Date) })
            .SingleOrDefaultAsync(ct);
        return Create(bounds?.First, bounds?.Last);
    }
}
