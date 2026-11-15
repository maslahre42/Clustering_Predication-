using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Features.Proposal;
using static GarbageCollector.Api.Tests.ProposalFixtures;
namespace GarbageCollector.Api.Tests;

public class NormalDistributionTests
{
    [Theory]
    [InlineData(0, 0.5)] [InlineData(1.959964, 0.975)] [InlineData(-1.959964, 0.025)] [InlineData(1, 0.841345)]
    public void CdfMatchesReferenceValues(double z, double expected) => Assert.Equal(expected, NormalDistribution.Cdf(z), 4);

    [Fact]
    public void CdfIsBoundedAndMonotone()
    {
        Assert.InRange(NormalDistribution.Cdf(-40), 0, 1e-12);
        Assert.InRange(NormalDistribution.Cdf(40), 1 - 1e-12, 1);
        var previous = 0.0;
        for (var z = -6.0; z <= 6.0; z += 0.25)
        {
            var value = NormalDistribution.Cdf(z);
            Assert.True(value >= previous);
            previous = value;
        }
    }
}

public class FillRateModelTests
{
    /// <summary>Twelve cycles of exactly 2 points per day.</summary>
    private static IEnumerable<Observation> SteadyBin(string id = "A", string material = "green", int gap = 10, string fill = "20") =>
        Visits(id, material, "2026-01-01", gap, fill, 13);

    [Fact]
    public void NoHistoryMeansNoForecastInsteadOfAnInventedRate()
    {
        var model = FillRateModel.Fit([]);
        Assert.Null(model.Predict("A", "white", 10));
        Assert.Equal(0, model.CycleCount);
        Assert.Empty(model.MaterialRatePercentPerDay);
    }

    [Fact]
    public void ABinIsEmptyOnTheDayItWasEmptied()
    {
        var forecast = FillRateModel.Fit(Histories(SteadyBin())).Predict("A", "green", 0);
        Assert.NotNull(forecast);
        Assert.Equal(0, forecast!.ExpectedFillPercent);
        Assert.Equal(0, forecast.OverflowProbability);
    }

    [Fact]
    public void ExpectedFillRisesWithTimeAndNeverExceedsOneHundred()
    {
        var model = FillRateModel.Fit(Histories(SteadyBin()));
        double fill = 0, risk = 0;
        for (var days = 1; days <= 400; days += 3)
        {
            var forecast = model.Predict("A", "green", days)!;
            Assert.InRange(forecast.ExpectedFillPercent, fill - 1e-6, 100);
            Assert.InRange(forecast.OverflowProbability, risk - 1e-6, 1);
            fill = forecast.ExpectedFillPercent; risk = forecast.OverflowProbability;
        }
        Assert.InRange(fill, 99, 100);
        Assert.InRange(risk, 0.99, 1);
    }

    [Fact]
    public void RecoversAKnownSteadyRate()
    {
        var model = FillRateModel.Fit(Histories(SteadyBin()));
        Assert.Equal(12, model.CycleCount);
        Assert.Equal(0, model.CensoredCycleCount);
        Assert.InRange(model.MaterialRatePercentPerDay["green"], 1.8, 2.2);
        Assert.InRange(model.Predict("A", "green", 25)!.ExpectedFillPercent, 45, 58);   // 2 points/day for 25 days
        Assert.InRange(model.Predict("A", "green", 25)!.OverflowProbability, 0, 0.1);    // needs 50 days
        Assert.InRange(model.Predict("A", "green", 100)!.OverflowProbability, 0.9, 1);
    }

    [Fact]
    public void ASparseBinBorrowsFromItsGlassType()
    {
        var rows = Enumerable.Range(0, 20).SelectMany(i => Visits($"W{i:00}", "white", "2026-01-01", 10, "30", 8)) // 3 points/day
            .Concat(Visits("SLOW", "white", "2026-01-01", 10, "3", 2));                                           // one cycle at 0.3
        var model = FillRateModel.Fit(Histories(rows));
        var sparse = model.Predict("SLOW", "white", 10)!.ExpectedFillPercent;
        var typical = model.Predict("W00", "white", 10)!.ExpectedFillPercent;
        Assert.InRange(sparse, 3.5, typical - 1); // above its single reading, below the glass-type average
    }

    [Fact]
    public void UnknownBinUsesItsGlassTypeAndUnknownGlassTypeUsesAllBins()
    {
        var rows = Enumerable.Range(0, 6).SelectMany(i => Visits($"W{i}", "white", "2026-01-01", 10, "40", 8))
            .Concat(Enumerable.Range(0, 6).SelectMany(i => Visits($"B{i}", "brown", "2026-01-01", 10, "10", 8)));
        var model = FillRateModel.Fit(Histories(rows));
        var white = model.Predict("NEW", "white", 10)!.ExpectedFillPercent;
        var brown = model.Predict("NEW", "brown", 10)!.ExpectedFillPercent;
        var other = model.Predict("NEW", "blue", 10)!.ExpectedFillPercent;
        Assert.True(white > brown * 2);
        Assert.InRange(other, brown, white);
        Assert.True(model.MaterialRatePercentPerDay["white"] > model.MaterialRatePercentPerDay["brown"]);
    }

    [Fact]
    public void FullReadingsPushTheRateAboveTheirLowerBound()
    {
        // Half of the cycles end full after ten days: the true rate was at least 10 points/day in those.
        var rows = Enumerable.Range(0, 10).SelectMany(i => Visits($"F{i}", "white", "2026-01-01", 10, "100", 6))
            .Concat(Enumerable.Range(0, 10).SelectMany(i => Visits($"N{i}", "white", "2026-01-01", 10, "80", 6)));
        var model = FillRateModel.Fit(Histories(rows));
        Assert.Equal(50, model.CensoredCycleCount);
        var naive = Math.Exp((Math.Log(10) + Math.Log(8)) / 2);
        Assert.True(model.MaterialRatePercentPerDay["white"] > naive);
        Assert.True(model.Predict("F0", "white", 9)!.OverflowProbability > model.Predict("N0", "white", 9)!.OverflowProbability);
    }

    [Fact]
    public void AllFullHistoryStaysFinite()
    {
        var model = FillRateModel.Fit(Histories(Visits("A", "white", "2026-01-01", 10, "overfull", 10)));
        var rate = model.MaterialRatePercentPerDay["white"];
        Assert.InRange(rate, 10, 500);
        Assert.InRange(model.Predict("A", "white", 10)!.OverflowProbability, 0.5, 1);
    }

    [Fact]
    public void FitDoesNotDependOnInputOrder()
    {
        var rows = Enumerable.Range(0, 8).SelectMany(i => Visits($"W{i}", i % 2 == 0 ? "white" : "brown", "2026-01-01", 7 + i, (20 + 10 * i).ToString(), 6)).ToArray();
        var forward = FillRateModel.Fit(Histories(rows));
        var backward = FillRateModel.Fit(Enumerable.Reverse(Histories(Enumerable.Reverse(rows))).ToArray());
        foreach (var id in new[] { "W0", "W3", "W7" })
        {
            Assert.Equal(forward.Predict(id, "white", 12)!.ExpectedFillPercent, backward.Predict(id, "white", 12)!.ExpectedFillPercent, 9);
            Assert.Equal(forward.Predict(id, "brown", 12)!.OverflowProbability, backward.Predict(id, "brown", 12)!.OverflowProbability, 9);
        }
        Assert.Equal(forward.Sigma, backward.Sigma, 9);
    }

    [Fact]
    public void LowerThresholdIsReachedAtLeastAsOftenAsOverflow()
    {
        var model = FillRateModel.Fit(Histories(SteadyBin()));
        Assert.True(model.Predict("A", "green", 40, threshold: 70)!.OverflowProbability >= model.Predict("A", "green", 40)!.OverflowProbability);
    }
}
