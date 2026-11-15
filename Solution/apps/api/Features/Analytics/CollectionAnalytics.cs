using System.Globalization;
using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Features.Analytics;

public sealed record FillDistribution(int Low0To30, int MidAbove30Below70, int High70Below100, int Full100, int Overfull, int Unknown);
public sealed record MaterialAnalytics(string Material, int Collections, int NumericReadings, int OverfullCount,
    int UnknownCount, double? MeanNumericFill, double? MedianIntervalDays, int IntervalCount, FillDistribution Distribution);
public sealed record MonthlyAnalytics(string Month, string Material, int Collections, int OverfullCount, int NumericReadings, double? MeanNumericFill);
public sealed record CollectionAnalytics(string AsOf, int TotalCollections, int KnownBins, int BinsWithFewerThan3Readings,
    int OverfullCount, MaterialAnalytics[] Materials, MonthlyAnalytics[] Months, CollectionPatterns Patterns)
{
    public static CollectionAnalytics Create(IReadOnlyCollection<Observation> source, string asOf)
    {
        var cutoff = HistoricalCutoff.Parse(asOf);
        var rows = source.Where(x => cutoff.Includes(x.Date)).ToArray();
        var bins = rows.GroupBy(x => new { x.LocationId, x.Material }).ToArray();
        var materials = new[] { "brown", "green", "white" }.Select(material => {
            var readings = rows.Where(x => x.Material == material).ToArray();
            var numbers = readings.Select(x => RecordedFill.ParsePercentage(x.FillLevel)).OfType<double>().ToArray();
            var overfull = readings.Count(x => RecordedFill.IsOverfull(x.FillLevel));
            var unknown = readings.Length - numbers.Length - overfull;
            var intervals = bins.Where(b => b.Key.Material == material).SelectMany(b => {
                var dates = b.Select(x => DateOnly.ParseExact(x.Date, "yyyy-MM-dd", CultureInfo.InvariantCulture))
                    .Distinct().Order().ToArray();
                return dates.Skip(1).Select((date, i) => date.DayNumber - dates[i].DayNumber);
            }).Order().ToArray();
            double? median = intervals.Length == 0 ? null : intervals.Length % 2 == 1
                ? intervals[intervals.Length / 2] : (intervals[intervals.Length / 2 - 1] + intervals[intervals.Length / 2]) / 2.0;
            return new MaterialAnalytics(material, readings.Length, numbers.Length, overfull, unknown,
                numbers.Length == 0 ? null : numbers.Average(), median, intervals.Length,
                new(numbers.Count(n => n <= 30), numbers.Count(n => n > 30 && n < 70),
                    numbers.Count(n => n >= 70 && n < 100), numbers.Count(n => n == 100), overfull, unknown));
        }).ToArray();
        var months = rows.GroupBy(x => new { Month = x.Date[..7], x.Material })
            .OrderBy(g => g.Key.Month).ThenBy(g => g.Key.Material).Select(g => {
                var numbers = g.Select(x => RecordedFill.ParsePercentage(x.FillLevel)).OfType<double>().ToArray();
                return new MonthlyAnalytics(g.Key.Month, g.Key.Material, g.Count(),
                    g.Count(x => RecordedFill.IsOverfull(x.FillLevel)), numbers.Length,
                    numbers.Length == 0 ? null : numbers.Average());
            }).ToArray();
        return new(asOf, rows.Length, bins.Length, bins.Count(b => b.Count() < 3),
            rows.Count(x => RecordedFill.IsOverfull(x.FillLevel)), materials, months, CollectionPatterns.Create(rows, asOf));
    }
}
