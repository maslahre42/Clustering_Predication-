namespace GarbageCollector.Api.Features.Proposal;

public static class BinDecision
{
    /// <summary>Likely to overflow before the next collection day: its site must be visited.</summary>
    public const string Due = "due";
    /// <summary>Not urgent, but the truck is at this site anyway and the bin is worth emptying.</summary>
    public const string Neighbour = "neighbour";
    /// <summary>Some risk, nothing urgent at the site: collected only if a truck has spare time.</summary>
    public const string Optional = "optional";
    public const string Skipped = "skipped";
    public const string NoForecast = "no_forecast";
    public static readonly IReadOnlyList<string> All = [Due, Neighbour, Optional, Skipped, NoForecast];
    public static bool IsCollected(string decision) => decision is Due or Neighbour or Optional;
}

/// <summary>Forecast for one bin: expected fill on the plan date and overflow probability by the end of the window.</summary>
public sealed record BinRisk(string LocationId, string Material, string LastEmptied, int DaysSinceEmptied,
    double? ExpectedFillPercent, double? OverflowProbability);

public sealed record BinAssessment(string LocationId, string Material, string LastEmptied, int DaysSinceEmptied,
    double? ExpectedFillPercent, double? OverflowProbability, string Decision, double VolumeL, double WeightKg);

/// <summary>One physical stop: all selected glass types of a location. Coordinates stay unknown when none are stored.</summary>
public sealed record SiteStop(string LocationId, bool Mandatory, double Risk, int Bins, double VolumeL, double WeightKg,
    double? Latitude, double? Longitude, IReadOnlyList<string> Materials);

/// <summary>Which bins should be emptied on the plan date, and why. Every bin gets exactly one decision.</summary>
public static class CollectionPolicy
{
    public static BinAssessment[] Decide(IReadOnlyCollection<BinRisk> bins, OperationsSettings settings)
    {
        var siteRisk = bins.GroupBy(bin => bin.LocationId, StringComparer.Ordinal)
            .ToDictionary(site => site.Key, site => site.Max(bin => bin.OverflowProbability ?? 0), StringComparer.Ordinal);
        return bins.Select(bin =>
        {
            var decision = Classify(bin, siteRisk[bin.LocationId], settings);
            var volume = BinDecision.IsCollected(decision)
                ? Math.Clamp(bin.ExpectedFillPercent!.Value, 0, 100) / 100 * settings.ContainerVolumeL : 0;
            return new BinAssessment(bin.LocationId, bin.Material, bin.LastEmptied, bin.DaysSinceEmptied,
                bin.ExpectedFillPercent, bin.OverflowProbability, decision, volume, volume / 1000 * settings.GlassDensityKgM3);
        }).ToArray();
    }

    private static string Classify(BinRisk bin, double siteRisk, OperationsSettings settings)
    {
        if (bin.ExpectedFillPercent is not { } fill || bin.OverflowProbability is not { } risk) return BinDecision.NoForecast;
        if (risk >= settings.MustProbability) return BinDecision.Due;
        var worthIt = risk >= settings.NeighbourProbability || fill >= settings.NeighbourFillPercent;
        if (!worthIt) return BinDecision.Skipped;
        if (siteRisk >= settings.MustProbability) return BinDecision.Neighbour;
        return siteRisk >= settings.OptionalProbability ? BinDecision.Optional : BinDecision.Skipped;
    }

    public static SiteStop[] Stops(IReadOnlyCollection<BinAssessment> bins, IReadOnlyDictionary<string, (double Latitude, double Longitude)> coordinates) =>
        bins.Where(bin => BinDecision.IsCollected(bin.Decision))
            .GroupBy(bin => bin.LocationId, StringComparer.Ordinal)
            .OrderBy(site => site.Key, StringComparer.Ordinal)
            .Select(site =>
            {
                (double Latitude, double Longitude)? place = coordinates.TryGetValue(site.Key, out var found) ? found : null;
                return new SiteStop(site.Key, site.Any(bin => bin.Decision == BinDecision.Due),
                    site.Max(bin => bin.OverflowProbability ?? 0), site.Count(), site.Sum(bin => bin.VolumeL), site.Sum(bin => bin.WeightKg),
                    place?.Latitude, place?.Longitude, site.Select(bin => bin.Material).Order(StringComparer.Ordinal).ToArray());
            }).ToArray();
}
