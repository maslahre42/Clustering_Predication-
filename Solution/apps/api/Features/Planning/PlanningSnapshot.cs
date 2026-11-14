using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Features.Planning;

public sealed record BinSummary(string LocationId, string Material, string LastCollection,
    double? LastFillPercent, int Collections, bool LastIsOverfull = false);
public sealed record PlanningSnapshot(string AsOf, int ObservationCount, string? FirstDate, string? LastDate, BinSummary[] Bins)
{
    public static PlanningSnapshot Create(IReadOnlyCollection<Observation> source, string asOf)
    {
        var cutoff = HistoricalCutoff.Parse(asOf);
        var observations = source.Where(x => cutoff.Includes(x.Date)).ToArray();
        var bins = observations.GroupBy(x => new { x.LocationId, x.Material })
            .OrderBy(g => g.Key.LocationId, StringComparer.Ordinal)
            .ThenBy(g => g.Key.Material, StringComparer.Ordinal)
            .Select(g => {
                var latest = g.OrderByDescending(x => x.Date, StringComparer.Ordinal).First();
                return new BinSummary(g.Key.LocationId, g.Key.Material, latest.Date,
                    RecordedFill.ParsePercentage(latest.FillLevel), g.Count(), RecordedFill.IsOverfull(latest.FillLevel));
            }).ToArray();
        var dates = observations.Select(x => x.Date).Order(StringComparer.Ordinal).ToArray();
        return new(asOf, observations.Length, dates.FirstOrDefault(), dates.LastOrDefault(), bins);
    }
}
