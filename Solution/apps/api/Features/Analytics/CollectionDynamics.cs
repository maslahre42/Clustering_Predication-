using System.Globalization;
using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Features.Analytics;

public sealed record HistogramBucket(double Lower, double Upper, int Count, bool IsTail = false);
public sealed record CycleDistribution(int Count, double Minimum, double Q1, double Median, double Q3,
    double Maximum, HistogramBucket[] Buckets);
public sealed record FillingTimePoint(int Days, int Cycles, double Share);
public sealed record BinDynamics(string LocationId, string Material, int Collections, int Intervals,
    int NumericCycles, int LowerBoundCycles, int UnknownCycles, int ZeroFillCycles,
    double? MedianIntervalDays, double? MedianRatePercentPerDay, double? MedianDaysToFull);
public sealed record MaterialDynamics(string Material, int Collections, int Bins, int Intervals,
    int NumericCycles, int LowerBoundCycles, int UnknownCycles, int ZeroFillCycles,
    CycleDistribution? Cadence, CycleDistribution? Rates, CycleDistribution? FillingTimes,
    FillingTimePoint[] FillingCurve, BinDynamics[] FastestBins, BinDynamics[] SlowestBins);

/// <summary>Descriptive cycle evidence. All visits reset a bin; full readings remain lower bounds.</summary>
public static class CollectionDynamics
{
    public static MaterialDynamics[] Create(IEnumerable<Observation> source, string asOf)
    {
        var cutoff = HistoricalCutoff.Parse(asOf);
        var bins = source.Where(row => cutoff.Includes(row.Date))
            .GroupBy(row => (row.LocationId, row.Material)).Select(group => {
                var visits = group.GroupBy(row => row.Date).Select(day => day.Last()).OrderBy(row => row.Date, StringComparer.Ordinal).ToArray();
                var gaps = new List<double>(); var rates = new List<double>(); var times = new List<double>();
                var bounds = 0; var unknown = 0; var zeros = 0;
                for (var i = 1; i < visits.Length; i++)
                {
                    var days = DateOnly.ParseExact(visits[i].Date, "yyyy-MM-dd", CultureInfo.InvariantCulture).DayNumber
                        - DateOnly.ParseExact(visits[i - 1].Date, "yyyy-MM-dd", CultureInfo.InvariantCulture).DayNumber;
                    if (days <= 0) continue;
                    gaps.Add(days);
                    var fill = RecordedFill.Parse(visits[i].FillLevel);
                    if (fill.WasOverfull || fill.Percentage == 100) { bounds++; continue; }
                    if (fill.Percentage is not double value) { unknown++; continue; }
                    rates.Add(value / days);
                    if (value > 0) times.Add(100.0 * days / value); else zeros++;
                }
                return new { group.Key.LocationId, group.Key.Material, Visits = visits.Length, Gaps = gaps, Rates = rates, Times = times, Bounds = bounds, Unknown = unknown, Zeros = zeros };
            }).ToArray();
        return new[] { "brown", "green", "white" }.Select(material => {
            var selected = bins.Where(bin => bin.Material == material).ToArray();
            var times = selected.SelectMany(bin => bin.Times).Order().ToArray();
            // Rank only bins with at least three positive ordinary cycles; no exact times from censored cycles.
            var ranked = selected.Where(bin => bin.Times.Count >= 3).Select(bin => new BinDynamics(bin.LocationId, material,
                bin.Visits, bin.Gaps.Count, bin.Rates.Count, bin.Bounds, bin.Unknown, bin.Zeros,
                Median(bin.Gaps), Median(bin.Rates), Median(bin.Times))).ToArray();
            return new MaterialDynamics(material, selected.Sum(bin => bin.Visits), selected.Length, selected.Sum(bin => bin.Gaps.Count),
                selected.Sum(bin => bin.Rates.Count), selected.Sum(bin => bin.Bounds), selected.Sum(bin => bin.Unknown), selected.Sum(bin => bin.Zeros),
                Distribution(selected.SelectMany(bin => bin.Gaps)), Distribution(selected.SelectMany(bin => bin.Rates)), Distribution(times),
                Enumerable.Range(0, 91).Select(day => { var count = times.Count(value => value <= day); return new FillingTimePoint(day, count, times.Length == 0 ? 0 : (double)count / times.Length); }).ToArray(),
                ranked.OrderBy(bin => bin.MedianDaysToFull).ThenBy(bin => bin.LocationId, StringComparer.Ordinal).Take(10).ToArray(),
                ranked.OrderByDescending(bin => bin.MedianDaysToFull).ThenBy(bin => bin.LocationId, StringComparer.Ordinal).Take(10).ToArray());
        }).ToArray();
    }

    private static double Quantile(double[] sorted, double q)
    {
        var index = (sorted.Length - 1) * q; var lower = (int)Math.Floor(index); var upper = (int)Math.Ceiling(index);
        return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower);
    }
    private static double? Median(IEnumerable<double> values)
    {
        var sorted = values.Order().ToArray(); return sorted.Length == 0 ? null : Quantile(sorted, .5);
    }
    private static CycleDistribution? Distribution(IEnumerable<double> values)
    {
        var sorted = values.Order().ToArray();
        if (sorted.Length == 0) return null;
        var cap = Math.Max(Quantile(sorted, .95), 1);
        var width = cap / 7;
        var counts = new int[8];
        foreach (var value in sorted) counts[value > cap ? 7 : Math.Min(6, (int)(value / width))]++;
        return new(sorted.Length, sorted[0], Quantile(sorted, .25), Quantile(sorted, .5), Quantile(sorted, .75), sorted[^1],
            Enumerable.Range(0, 8).Select(i => new HistogramBucket(i * width, i == 7 ? Math.Max(cap, sorted[^1]) : (i + 1) * width, counts[i], i == 7)).ToArray());
    }
}
