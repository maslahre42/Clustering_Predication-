using System.Globalization;
using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Features.Proposal;

/// <summary>One filling period between two visits. <see cref="Censored"/> means the bin was full: the true rate was at least this.</summary>
public sealed record FillingCycle(string End, int GapDays, double Fill, bool Censored)
{
    public double LogRate => Math.Log(Fill / GapDays);
}

public sealed record BinHistory(string LocationId, string Material, string LastEmptied, IReadOnlyList<FillingCycle> Cycles)
{
    public string Key => $"{LocationId}:{Material}";
}

/// <summary>
/// Turns visit readings into filling cycles. A reading is taken before the bin is emptied and every visit empties it,
/// so the fill at a visit is what accumulated since the previous visit. Differences between readings mean nothing.
/// </summary>
public static class FillingCycles
{
    /// <summary>Keeps the logarithm finite for a bin recorded as empty.</summary>
    public const double MinimumFill = 2.5;

    public static IReadOnlyList<BinHistory> Build(IReadOnlyCollection<Observation> source, HistoricalCutoff cutoff) =>
        source.Where(row => cutoff.Includes(row.Date) && Parse(row.Date) is not null)
            .GroupBy(row => (row.LocationId, row.Material))
            .OrderBy(group => group.Key.LocationId, StringComparer.Ordinal).ThenBy(group => group.Key.Material, StringComparer.Ordinal)
            .Select(group =>
            {
                // One visit per day; the last recorded row of a day wins.
                var visits = group.GroupBy(row => row.Date).Select(day => day.Last())
                    .OrderBy(row => row.Date, StringComparer.Ordinal).ToArray();
                var cycles = new List<FillingCycle>();
                for (var i = 1; i < visits.Length; i++)
                {
                    var fill = RecordedFill.Parse(visits[i].FillLevel);
                    if (fill.Percentage is null && !fill.WasOverfull) continue; // unknown reading: emptied, but no rate
                    var gap = Math.Max(1, Parse(visits[i].Date)!.Value.DayNumber - Parse(visits[i - 1].Date)!.Value.DayNumber);
                    var censored = fill.WasOverfull || fill.Percentage >= 100;
                    cycles.Add(new(visits[i].Date, gap, censored ? 100 : Math.Max(fill.Percentage!.Value, MinimumFill), censored));
                }
                return new BinHistory(group.Key.LocationId, group.Key.Material, visits[^1].Date, cycles);
            }).ToArray();

    internal static DateOnly? Parse(string date) =>
        DateOnly.TryParseExact(date, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var value) ? value : null;
}
