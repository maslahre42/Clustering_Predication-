using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Features.Proposal;
namespace GarbageCollector.Api.Tests;

/// <summary>Shared builders for the forecast, policy and routing tests.</summary>
internal static class ProposalFixtures
{
    public static Observation Row(string id, string material, string date, string fill) =>
        new() { LocationId = id, Material = material, Date = date, FillLevel = fill };

    public static string Day(string start, int offset) =>
        DateOnly.ParseExact(start, "yyyy-MM-dd").AddDays(offset).ToString("yyyy-MM-dd");

    /// <summary>Visits every <paramref name="gapDays"/> days, each recording the same pre-emptying fill.</summary>
    public static IEnumerable<Observation> Visits(string id, string material, string start, int gapDays, string fill, int count) =>
        Enumerable.Range(0, count).Select(i => Row(id, material, Day(start, i * gapDays), fill));

    public static IReadOnlyList<BinHistory> Histories(IEnumerable<Observation> rows, string asOf = "2030-01-01") =>
        FillingCycles.Build(rows.ToArray(), HistoricalCutoff.Parse(asOf));

    public static SiteStop Stop(string id, double kg, int bins = 1, bool mandatory = true, double risk = 0.9,
        double? latitude = 49.15, double? longitude = 9.22, double? liters = null) =>
        new(id, mandatory, risk, bins, liters ?? kg / 0.35, kg, latitude, longitude, ["white"]);

    public static string Signature(RoutePlan plan) => string.Join(" | ",
        plan.Routes.Select(r => $"T{r.Truck}:" + string.Join("/", r.Trips.Select(t => string.Join(",", t.Stops))))
            .Concat(plan.Unserved.Select(u => $"U:{u.LocationId}:{u.Reason}")));
}
