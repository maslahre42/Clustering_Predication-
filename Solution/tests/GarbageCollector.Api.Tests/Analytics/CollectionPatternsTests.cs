using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Features.Analytics;
namespace GarbageCollector.Api.Tests;

public class CollectionPatternsTests
{
    private static Observation Row(string id, string material, string date, string fill) =>
        new() { LocationId = id, Material = material, Date = date, FillLevel = fill };

    [Fact]
    public void RatesUseFillSincePreviousEmptyingAndRetainUnknownResetsAndZero()
    {
        Observation[] rows = [Row("A", "brown", "2026-01-01", "90"), Row("A", "brown", "2026-01-11", "20"),
            Row("A", "brown", "2026-01-16", "unknown"), Row("A", "brown", "2026-01-21", "30"),
            Row("A", "brown", "2026-01-26", "0"), Row("A", "brown", "2026-01-31", "100"),
            Row("A", "brown", "2026-02-05", "overfull"), Row("B", "brown", "2026-01-01", "50"),
            Row("A", "green", "2026-01-01", "50")];
        var result = CollectionPatterns.Create(rows, "2026-02-05");
        var brown = result.Cycles.Single(row => row.Material == "brown");
        Assert.Equal(3, brown.NumericCycles); // 20/10, 30/5, 0/5
        Assert.Equal(2, brown.MedianRatePercentPerDay);
        Assert.Equal(2, brown.LowerBoundCycles);
        Assert.Null(result.Cycles.Single(row => row.Material == "green").MedianRatePercentPerDay);
    }

    [Fact]
    public void ReviewRulesRequireEvidenceAndKeepOverfullSeparateFromNumericFull()
    {
        var rows = new List<Observation>();
        foreach (var (id, fills) in new[] {
            ("overflow", new[] { "overfull", "100", "overfull" }),
            ("low", new[] { "10", "20", "30", "90" }),
            ("sparse", new[] { "overfull", "overfull" }),
            ("full", new[] { "100", "100", "100" }),
            ("few-low", new[] { "10", "20", "unknown" }) })
            rows.AddRange(fills.Select((fill, i) => Row(id, "white", $"2026-01-{i + 1:00}", fill)));
        var result = CollectionPatterns.Create(rows, "2026-01-31");
        Assert.Equal(2, result.ReviewBinCount);
        Assert.Equal("repeated_overfull", result.ReviewBins[0].Reason);
        Assert.Equal(2, result.ReviewBins[0].OverfullCollections);
        Assert.Equal("frequent_low_fill", result.ReviewBins[1].Reason);
        Assert.Equal(3, result.ReviewBins[1].LowCollections);
    }

    [Fact]
    public void EmptyAndFutureRowsDoNotSupplyPatternsOrChangeHistoricalEvidence()
    {
        var empty = CollectionPatterns.Create([], "2026-01-01");
        Assert.Null(empty.FirstDate); Assert.Null(empty.LastDate); Assert.Empty(empty.ReviewBins);
        Assert.All(empty.Cycles, cycle => Assert.Null(cycle.MedianRatePercentPerDay));
        Observation[] before = [Row("A", "brown", "2026-01-01", "10"), Row("A", "brown", "2026-01-11", "20")];
        var first = CollectionAnalytics.Create(before, "2026-01-11");
        var later = CollectionAnalytics.Create([.. before, Row("A", "brown", "2026-02-01", "overfull"),
            Row("new", "white", "2026-02-01", "100")], "2026-01-11");
        Assert.Equal(first.Patterns.Cycles, later.Patterns.Cycles);
        Assert.Equal(first.Patterns.ReviewBins, later.Patterns.ReviewBins);
        Assert.Equal(first.Patterns.FirstDate, later.Patterns.FirstDate);
        Assert.Equal(first.Patterns.LastDate, later.Patterns.LastDate);
        var month = Assert.Single(later.Months);
        Assert.Equal(2, month.Collections); Assert.Equal(15, month.MeanNumericFill);
    }

    [Fact]
    public void ReviewIsBoundedAndStableForTiedBins()
    {
        var rows = Enumerable.Range(0, 25).SelectMany(i => Enumerable.Range(1, 3)
            .Select(day => Row($"A{i:00}", "brown", $"2026-01-{day:00}", "10"))).ToArray();
        var result = CollectionPatterns.Create(rows.Reverse(), "2026-01-31");
        Assert.Equal(25, result.ReviewBinCount); Assert.Equal(20, result.ReviewBins.Length);
        Assert.Equal("A00", result.ReviewBins[0].LocationId); Assert.Equal("A19", result.ReviewBins[^1].LocationId);
    }
}
