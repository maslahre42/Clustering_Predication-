using System.Globalization;
using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Features.Analytics;

public sealed record MaterialCyclePattern(string Material, int NumericCycles, int LowerBoundCycles,
    double? MedianRatePercentPerDay);
public sealed record ReviewBin(string LocationId, string Material, int Collections, int LowCollections,
    int OverfullCollections, string Reason);
public sealed record CollectionPatterns(string? FirstDate, string? LastDate,
    MaterialCyclePattern[] Cycles, int ReviewBinCount, ReviewBin[] ReviewBins)
{
    public MaterialDynamics[] Dynamics { get; init; } = [];

    public static CollectionPatterns Create(IEnumerable<Observation> source, string asOf)
    {
        var cutoff = HistoricalCutoff.Parse(asOf);
        var rows = source.Where(row => cutoff.Includes(row.Date)).ToArray();
        var rates = new Dictionary<string, List<double>>();
        var bounds = new Dictionary<string, int>();
        var review = new List<ReviewBin>();
        foreach (var bin in rows.GroupBy(row => (row.LocationId, row.Material)))
        {
            var visits = bin.GroupBy(row => row.Date).Select(day => day.Last())
                .OrderBy(row => row.Date, StringComparer.Ordinal).ToArray();
            var numeric = rates.TryGetValue(bin.Key.Material, out var existing) ? existing : rates[bin.Key.Material] = [];
            for (var i = 1; i < visits.Length; i++)
            {
                var days = DateOnly.ParseExact(visits[i].Date, "yyyy-MM-dd", CultureInfo.InvariantCulture).DayNumber
                    - DateOnly.ParseExact(visits[i - 1].Date, "yyyy-MM-dd", CultureInfo.InvariantCulture).DayNumber;
                var fill = RecordedFill.Parse(visits[i].FillLevel);
                if (fill.WasOverfull || fill.Percentage == 100)
                    bounds[bin.Key.Material] = bounds.GetValueOrDefault(bin.Key.Material) + 1;
                else if (fill.Percentage is double value && days > 0)
                    numeric.Add(value / days);
                // Every visit resets the bin, including unknown readings. Never difference two fill readings.
            }
            var low = visits.Count(row => RecordedFill.ParsePercentage(row.FillLevel) is <= 30);
            var overfull = visits.Count(row => RecordedFill.IsOverfull(row.FillLevel));
            if (visits.Length >= 3 && (overfull >= 2 || low >= 3 && low * 2 >= visits.Length))
                review.Add(new(bin.Key.LocationId, bin.Key.Material, visits.Length, low, overfull,
                    overfull >= 2 ? "repeated_overfull" : "frequent_low_fill"));
        }
        var cycles = new[] { "brown", "green", "white" }.Select(material => {
            var values = rates.GetValueOrDefault(material, []).Order().ToArray();
            double? median = values.Length == 0 ? null : (values[(values.Length - 1) / 2] + values[values.Length / 2]) / 2;
            return new MaterialCyclePattern(material, values.Length, bounds.GetValueOrDefault(material), median);
        }).ToArray();
        return new(rows.Min(row => row.Date), rows.Max(row => row.Date), cycles, review.Count,
            review.OrderByDescending(bin => bin.Reason == "repeated_overfull")
                .ThenByDescending(bin => bin.Reason == "repeated_overfull" ? bin.OverfullCollections : bin.LowCollections)
                .ThenBy(bin => bin.LocationId, StringComparer.Ordinal).ThenBy(bin => bin.Material, StringComparer.Ordinal)
                .Take(20).ToArray()) { Dynamics = CollectionDynamics.Create(rows, asOf) };
    }
}
