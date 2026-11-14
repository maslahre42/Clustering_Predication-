using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Domain.Locations;
using GarbageCollector.Api.Features.Proposal;
using static GarbageCollector.Api.Tests.ProposalFixtures;
namespace GarbageCollector.Api.Tests;

public class CollectionProposalTests
{
    private static readonly OperationsSettings Settings = OperationsSettings.Default;

    /// <summary>A small town: fast white bins, medium green, slow brown, visited on different rhythms from October to March.</summary>
    private static Observation[] Town()
    {
        var rows = new List<Observation>();
        for (var i = 0; i < 12; i++)
        {
            rows.AddRange(Visits($"L{i:00}", "white", Day("2025-10-20", i), 7 + i % 3, i % 2 == 0 ? "overfull" : "90", 18));
            rows.AddRange(Visits($"L{i:00}", "green", Day("2025-10-20", i), 14, (50 + 3 * i).ToString(), 10));
            rows.AddRange(Visits($"L{i:00}", "brown", Day("2025-10-20", i), 28, "20", 6));
        }
        return [.. rows];
    }
    private static BinLocation[] Places() => Enumerable.Range(0, 12).Select(i =>
        new BinLocation { LocationId = $"L{i:00}", Latitude = 49.12 + 0.005 * i, Longitude = 9.20 + 0.004 * i, IsSynthetic = true }).ToArray();

    private static string Signature(CollectionProposal p) => string.Join(";", p.Bins.Select(b =>
        $"{b.LocationId}:{b.Material}:{b.LastEmptied}:{b.ExpectedFillPercent:F6}:{b.OverflowProbability:F6}:{b.Decision}")) + "#" + ProposalFixtures.Signature(p.Plan);

    [Fact]
    public void EmptyHistoryGivesAnEmptyButDatedProposal()
    {
        var proposal = CollectionProposal.Create([], [], "2026-08-14", Settings);
        Assert.Equal("2026-08-14", proposal.AsOf);
        Assert.Equal("2026-08-17", proposal.PlanDate);   // history through Friday -> plan for Monday
        Assert.Equal("2026-08-18", proposal.WindowEnd);
        Assert.Empty(proposal.Bins);
        Assert.Empty(proposal.Stops);
        Assert.Empty(proposal.Plan.Routes);
        Assert.Equal(0, proposal.Model.Cycles);
    }

    [Theory]
    [InlineData("")] [InlineData("2026-02-30")] [InlineData("14/08/2026")]
    public void InvalidCutoffIsRejected(string asOf) =>
        Assert.Throws<ArgumentException>(() => CollectionProposal.Create([], [], asOf, Settings));

    [Fact]
    public void InvalidSettingsAreRejectedBeforeAnyPlanning() =>
        Assert.Throws<ArgumentException>(() => CollectionProposal.Create(Town(), Places(), "2026-01-15", Settings with { TruckPayloadT = 0 }));

    [Fact]
    public void LaterObservationsNeverChangeAPastProposal()
    {
        var all = Town();
        const string asOf = "2026-01-15";
        var known = all.Where(row => string.CompareOrdinal(row.Date, asOf) <= 0).ToArray();
        Assert.True(known.Length < all.Length);
        var withFuture = CollectionProposal.Create([.. all, Row("NEW", "white", "2026-02-01", "100")], Places(), asOf, Settings);
        var withoutFuture = CollectionProposal.Create(known, Places(), asOf, Settings);
        Assert.Equal(Signature(withoutFuture), Signature(withFuture));
        Assert.Equal(withoutFuture.Model.Cycles, withFuture.Model.Cycles);
        Assert.DoesNotContain(withFuture.Bins, bin => bin.LocationId == "NEW"); // first seen later: not in the inventory yet
    }

    [Fact]
    public void EveryKnownBinIsExplainedAndTheRouteReconciles()
    {
        var proposal = CollectionProposal.Create(Town(), Places(), "2026-01-15", Settings);
        Assert.Equal(36, proposal.Bins.Length);
        Assert.Equal(36, proposal.Bins.Select(b => $"{b.LocationId}:{b.Material}").Distinct().Count());
        Assert.All(proposal.Bins, bin => Assert.Contains(bin.Decision, BinDecision.All));
        var collected = proposal.Bins.Where(b => b.Decision is BinDecision.Due or BinDecision.Neighbour or BinDecision.Optional).ToArray();
        Assert.Equal(collected.Select(b => b.LocationId).Distinct().Order().ToArray(), proposal.Stops.Select(s => s.LocationId).Order().ToArray());
        Assert.Equal(collected.Sum(b => b.WeightKg), proposal.Stops.Sum(s => s.WeightKg), 6);
        var served = proposal.Plan.Routes.SelectMany(r => r.Trips).SelectMany(t => t.Stops);
        Assert.Equal(proposal.Stops.Length, served.Count() + proposal.Plan.Unserved.Count);
        Assert.Equal(36, proposal.Model.Bins);
        Assert.True(proposal.Model.CensoredCycles > 0);
    }

    [Fact]
    public void ABinThatIsAlwaysFullAfterAWeekIsDueAndGetsATruck()
    {
        var rows = Visits("HOT", "white", "2026-01-05", 7, "overfull", 12).Concat(Visits("COLD", "brown", "2026-01-05", 28, "10", 4)).ToArray();
        var last = rows.Where(r => r.LocationId == "HOT").Max(r => r.Date)!;
        var proposal = CollectionProposal.Create(rows, [], Day(last, 13), Settings);
        var hot = proposal.Bins.Single(b => b.LocationId == "HOT");
        Assert.Equal(BinDecision.Due, hot.Decision);
        Assert.Equal(last, hot.LastEmptied);
        Assert.InRange(hot.OverflowProbability!.Value, 0.7, 1);
        Assert.Equal(BinDecision.Skipped, proposal.Bins.Single(b => b.LocationId == "COLD").Decision);
        Assert.Equal("HOT", Assert.Single(Assert.Single(proposal.Plan.Routes).Trips).Stops.Single());
        Assert.Equal(1, proposal.Plan.Totals.Trucks);
    }

    [Fact]
    public void DaysSinceEmptyingAreCountedToThePlanDate()
    {
        var proposal = CollectionProposal.Create(Visits("A", "white", "2026-08-03", 7, "50", 2).ToArray(), [], "2026-08-14", Settings);
        var bin = Assert.Single(proposal.Bins);
        Assert.Equal("2026-08-10", bin.LastEmptied);
        Assert.Equal(7, bin.DaysSinceEmptied); // emptied Monday 10th, planned for Monday 17th
    }

    [Fact]
    public void OperatingNumbersChangeThePlan()
    {
        var normal = CollectionProposal.Create(Town(), Places(), "2026-01-15", Settings);
        var cautious = CollectionProposal.Create(Town(), Places(), "2026-01-15", Settings with { MustProbability = 0.2 });
        var smallTruck = CollectionProposal.Create(Town(), Places(), "2026-01-15", Settings with { TruckPayloadT = 2 });
        Assert.True(normal.Plan.Totals.Stops > 0);
        Assert.True(cautious.Bins.Count(b => b.Decision == BinDecision.Due) > normal.Bins.Count(b => b.Decision == BinDecision.Due));
        Assert.True(smallTruck.Plan.Totals.Trips > normal.Plan.Totals.Trips);
        Assert.Equal(2.0, smallTruck.Settings.TruckPayloadT);
    }

    [Fact]
    public void AssumptionsAndModelAreDeclared()
    {
        var proposal = CollectionProposal.Create(Town(), Places(), "2026-01-15", Settings);
        Assert.NotEmpty(proposal.Assumptions);
        Assert.Contains(proposal.Assumptions, text => text.Contains("density", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(proposal.Assumptions, text => text.Contains("before", StringComparison.OrdinalIgnoreCase));
        Assert.True(proposal.Model.MaterialRatePercentPerDay["white"] > proposal.Model.MaterialRatePercentPerDay["brown"]);
    }

    [Fact]
    public void ProposalIsValidJsonWithoutInfiniteOrDerivedNumbers()
    {
        // Unknown truck volume is an infinite limit internally; it must never reach the API response.
        var options = new System.Text.Json.JsonSerializerOptions(System.Text.Json.JsonSerializerDefaults.Web);
        var json = System.Text.Json.JsonSerializer.Serialize(CollectionProposal.Create(Town(), Places(), "2026-01-15", Settings), options);
        Assert.Contains("\"planDate\":\"2026-01-16\"", json);
        Assert.Contains("\"truckVolumeM3\":0", json);
        Assert.DoesNotContain(new[] { "truckVolumeL", "truckPayloadKg", "Infinity", "NaN" }, name => json.Contains(name));
        var empty = System.Text.Json.JsonSerializer.Serialize(CollectionProposal.Create([], [], "2026-01-15", Settings), options);
        Assert.Contains("\"distanceKm\":null", empty);
    }
}
