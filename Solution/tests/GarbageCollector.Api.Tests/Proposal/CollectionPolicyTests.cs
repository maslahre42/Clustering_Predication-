using GarbageCollector.Api.Features.Proposal;
namespace GarbageCollector.Api.Tests;

public class CollectionPolicyTests
{
    private static readonly OperationsSettings Settings = OperationsSettings.Default; // must 0.70, neighbour 0.12 / 40%, optional 0.40
    private static BinRisk Bin(string site, string material, double? fill, double? risk) =>
        new(site, material, "2026-08-01", 16, fill, risk);
    private static string Decision(IEnumerable<BinAssessment> bins, string site, string material) =>
        bins.Single(b => b.LocationId == site && b.Material == material).Decision;

    [Fact]
    public void HighOverflowRiskMakesABinDueAndBoundaryIsInclusive()
    {
        var result = CollectionPolicy.Decide([Bin("A", "white", 90, 0.70), Bin("B", "white", 90, 0.6999)], Settings);
        Assert.Equal(BinDecision.Due, Decision(result, "A", "white"));
        Assert.NotEqual(BinDecision.Due, Decision(result, "B", "white"));
    }

    [Fact]
    public void NeighboursAtAVisitedSiteAreEmptiedWhenWorthIt()
    {
        var result = CollectionPolicy.Decide([
            Bin("A", "white", 95, 0.9), Bin("A", "green", 40, 0.01), Bin("A", "brown", 10, 0.12), Bin("A", "blue", 39.9, 0.11)], Settings);
        Assert.Equal(BinDecision.Due, Decision(result, "A", "white"));
        Assert.Equal(BinDecision.Neighbour, Decision(result, "A", "green"));  // fill threshold
        Assert.Equal(BinDecision.Neighbour, Decision(result, "A", "brown"));  // risk threshold
        Assert.Equal(BinDecision.Skipped, Decision(result, "A", "blue"));
    }

    [Fact]
    public void SiteWithoutADueBinIsOnlyOptionalWhenItCarriesRealRisk()
    {
        var result = CollectionPolicy.Decide([
            Bin("RISKY", "white", 70, 0.40), Bin("RISKY", "green", 45, 0.05), Bin("RISKY", "brown", 5, 0.0),
            Bin("CALM", "white", 60, 0.39), Bin("CALM", "green", 50, 0.2)], Settings);
        Assert.Equal(BinDecision.Optional, Decision(result, "RISKY", "white"));
        Assert.Equal(BinDecision.Optional, Decision(result, "RISKY", "green"));
        Assert.Equal(BinDecision.Skipped, Decision(result, "RISKY", "brown"));
        Assert.Equal(BinDecision.Skipped, Decision(result, "CALM", "white"));
        Assert.Equal(BinDecision.Skipped, Decision(result, "CALM", "green"));
    }

    [Fact]
    public void BinWithoutForecastIsLabelledNotGuessed()
    {
        var result = CollectionPolicy.Decide([Bin("A", "white", null, null), Bin("A", "green", 95, 0.9)], Settings);
        var bin = result.Single(b => b.Material == "white");
        Assert.Equal(BinDecision.NoForecast, bin.Decision);
        Assert.Equal(0, bin.WeightKg);
        Assert.Null(bin.ExpectedFillPercent);
    }

    [Fact]
    public void EveryBinGetsExactlyOneDecisionInInputOrder()
    {
        BinRisk[] bins = [Bin("B", "white", 10, 0.0), Bin("A", "white", 99, 0.99), Bin("A", "green", 50, 0.3)];
        var result = CollectionPolicy.Decide(bins, Settings);
        Assert.Equal(bins.Select(b => b.LocationId + b.Material).ToArray(), result.Select(b => b.LocationId + b.Material).ToArray());
        Assert.All(result, b => Assert.Contains(b.Decision, BinDecision.All));
    }

    [Fact]
    public void DemandIsFillTimesContainerVolumeTimesDensity()
    {
        var result = CollectionPolicy.Decide([Bin("A", "white", 80, 0.9), Bin("A", "green", 50, 0.0), Bin("A", "brown", 20, 0.0)], Settings);
        var white = result.Single(b => b.Material == "white");
        Assert.Equal(2400, white.VolumeL, 6);  // 80% of 3 m³
        Assert.Equal(840, white.WeightKg, 6);  // × 350 kg/m³
        Assert.Equal(0, result.Single(b => b.Material == "brown").WeightKg); // skipped bins carry no demand

        var stop = Assert.Single(CollectionPolicy.Stops(result, new Dictionary<string, (double, double)> { ["A"] = (49.1, 9.2) }));
        Assert.Equal("A", stop.LocationId);
        Assert.True(stop.Mandatory);
        Assert.Equal(2, stop.Bins);
        Assert.Equal(3900, stop.VolumeL, 6);
        Assert.Equal(1365, stop.WeightKg, 6);
        Assert.Equal(0.9, stop.Risk);
        Assert.Equal(49.1, stop.Latitude);
        Assert.Equal(new[] { "green", "white" }, stop.Materials.ToArray());
    }

    [Fact]
    public void DensityAndContainerSizeAreConfigurable()
    {
        var heavy = Settings with { ContainerVolumeM3 = 2, GlassDensityKgM3 = 500 };
        var bin = Assert.Single(CollectionPolicy.Decide([Bin("A", "white", 100, 0.9)], heavy));
        Assert.Equal(2000, bin.VolumeL, 6);
        Assert.Equal(1000, bin.WeightKg, 6);
    }

    [Fact]
    public void StopsSeparateMandatoryFromOptionalAndKeepUnknownCoordinatesUnknown()
    {
        var result = CollectionPolicy.Decide([Bin("M", "white", 95, 0.9), Bin("O", "white", 70, 0.5), Bin("S", "white", 5, 0.0)], Settings);
        var stops = CollectionPolicy.Stops(result, new Dictionary<string, (double, double)>());
        Assert.Equal(new[] { "M", "O" }, stops.Select(s => s.LocationId).ToArray());
        Assert.True(stops[0].Mandatory);
        Assert.False(stops[1].Mandatory);
        Assert.Null(stops[0].Latitude);
        Assert.Null(stops[0].Longitude);
    }

    [Fact]
    public void LowerRiskToleranceSelectsMore()
    {
        BinRisk[] bins = [Bin("A", "white", 80, 0.5), Bin("B", "white", 85, 0.65), Bin("C", "white", 95, 0.8)];
        int Due(double must) => CollectionPolicy.Decide(bins, Settings with { MustProbability = must }).Count(b => b.Decision == BinDecision.Due);
        Assert.Equal(1, Due(0.70));
        Assert.Equal(3, Due(0.50));
    }
}
