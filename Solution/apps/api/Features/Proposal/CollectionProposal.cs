using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Domain.Locations;
namespace GarbageCollector.Api.Features.Proposal;

public sealed record ModelSummary(int Bins, int Cycles, int CensoredCycles, double Sigma, double Tau,
    IReadOnlyDictionary<string, double> MaterialRatePercentPerDay);

/// <summary>
/// Forecast, selection and routes for the first collection day after the history cutoff.
/// Only observations through <see cref="AsOf"/> are used, so a past proposal never changes when later data arrives.
/// </summary>
public sealed record CollectionProposal(string AsOf, string PlanDate, string WindowEnd, OperationsSettings Settings,
    ModelSummary Model, BinAssessment[] Bins, SiteStop[] Stops, RoutePlan Plan, string[] Assumptions)
{
    private const string IsoDate = "yyyy-MM-dd";

    public static CollectionProposal Create(IReadOnlyCollection<Observation> source, IReadOnlyCollection<BinLocation> locations,
        string asOf, OperationsSettings settings)
    {
        var cutoff = HistoricalCutoff.Parse(asOf);
        var errors = settings.Validate();
        if (errors.Count > 0) throw new ArgumentException(string.Join(" ", errors), nameof(settings));

        var planDate = CollectionCalendar.NextWorkingDay(DateOnly.ParseExact(asOf, IsoDate), settings);
        var windowEnd = CollectionCalendar.WindowEnd(planDate, settings);
        var histories = FillingCycles.Build(source, cutoff);
        var model = FillRateModel.Fit(histories);

        var risks = histories.Select(bin =>
        {
            var emptied = DateOnly.ParseExact(bin.LastEmptied, IsoDate);
            var onPlanDate = model.Predict(bin.LocationId, bin.Material, planDate.DayNumber - emptied.DayNumber);
            var byWindowEnd = model.Predict(bin.LocationId, bin.Material, windowEnd.DayNumber - emptied.DayNumber);
            return new BinRisk(bin.LocationId, bin.Material, bin.LastEmptied, planDate.DayNumber - emptied.DayNumber,
                onPlanDate?.ExpectedFillPercent, byWindowEnd?.OverflowProbability);
        }).ToArray();
        var bins = CollectionPolicy.Decide(risks, settings);
        var coordinates = locations.GroupBy(location => location.LocationId, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => (group.First().Latitude, group.First().Longitude), StringComparer.Ordinal);
        var stops = CollectionPolicy.Stops(bins, coordinates);
        var plan = RoutePlanner.Plan(stops, settings);

        return new(asOf, planDate.ToString(IsoDate), windowEnd.ToString(IsoDate), settings,
            new(histories.Count, model.CycleCount, model.CensoredCycleCount, model.Sigma, model.Tau, model.MaterialRatePercentPerDay),
            bins, stops, plan, DeclaredAssumptions(settings));
    }

    private static string[] DeclaredAssumptions(OperationsSettings settings) =>
    [
        "A reading is taken before the bin is emptied, and every recorded visit empties it.",
        "Full and overfull readings count as 'at least 100%'; no overflow amount is invented.",
        "Glass density is an assumption until weighbridge data exists; it turns fill level into weight.",
        settings.TruckVolumeM3 > 0 ? "Truck volume is a configured assumption." : "Truck volume is unknown, so only the weight limit per load applies.",
        settings.FixedTravelMin > 0
            ? "Every drive takes the same fixed time; no distance is reported."
            : "Driving uses straight-line distance times a detour factor, not road navigation. Site coordinates may be synthetic.",
        "Yard and unloading-site positions are placeholders.",
        "No seasonal or holiday effect is fitted yet: the history covers less than one year.",
        "Routes come from a constructive heuristic: feasible and frugal with trucks, not a proven optimum.",
    ];
}
