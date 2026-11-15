using GarbageCollector.Api.Features.Analytics;
using GarbageCollector.Api.Features.Planning;
using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Tests;

public class CollectionAnalyticsTests
{
    [Fact]
    public void MonthlyDashboardCountsDistinctDaysAndExactFillBoundariesBeforeCutoff()
    {
        Observation[] rows = [
            Row("A", "white", "2026-01-01", "100"), Row("B", "white", "2026-01-01", "overfull"),
            Row("A", "white", "2026-01-02", "bad"), Row("A", "brown", "2026-01-01", "39"),
            Row("B", "brown", "2026-01-01", "40"), Row("A", "white", "2026-01-03", "100")
        ];
        var result = CollectionAnalytics.Create(rows, "2026-01-02");
        var white = result.Months.Single(m => m.Material == "white");
        Assert.Equal(3, white.Collections); Assert.Equal(2, white.ActiveDays);
        Assert.Equal(2, white.FullOrOverfullCount); Assert.Equal(0, white.PrematureCount);
        var brown = result.Months.Single(m => m.Material == "brown");
        Assert.Equal(1, brown.ActiveDays); Assert.Equal(1, brown.PrematureCount);
    }
    private static Observation Row(string id, string color, string date, string fill) => new() { LocationId = id, Material = color, Date = date, FillLevel = fill };
    [Theory]
    [InlineData("overfull", true)] [InlineData(" OverFull ", true)] [InlineData("100", false)]
    [InlineData("110", false)] [InlineData(null, false)] [InlineData("unknown", false)]
    public void OverflowIsAnExplicitCategory(string? raw, bool expected)
    {
        Assert.Equal(expected, RecordedFill.IsOverfull(raw));
        if (expected) Assert.Null(RecordedFill.ParsePercentage(raw));
    }
    [Fact]
    public void LatestOverflowIsPreservedWithoutInventingAPercentage()
    {
        var result = PlanningSnapshot.Create([Row("A", "white", "2026-01-01", "50"), Row("A", "white", "2026-02-01", "overfull")], "2026-02-01");
        var bin = Assert.Single(result.Bins);
        Assert.True(bin.LastIsOverfull); Assert.Null(bin.LastFillPercent);
    }
    [Fact]
    public void CountsEveryCollectionAndKeepsCategoriesSeparate()
    {
        var rows = new[] { "0", "30", "40", "60", "70", "90", "100", "overfull", "bad" }
            .Select((fill, i) => Row(i.ToString(), "brown", "2026-01-01", fill)).ToArray();
        var result = CollectionAnalytics.Create(rows, "2026-01-01");
        var brown = result.Materials.Single(m => m.Material == "brown");
        Assert.Equal(9, result.TotalCollections);
        Assert.Equal(new FillDistribution(2, 2, 2, 1, 1, 1), brown.Distribution);
        Assert.Equal(7, brown.NumericReadings); Assert.Equal(1, brown.OverfullCount); Assert.Equal(1, brown.UnknownCount);
        Assert.Equal(390.0 / 7, brown.MeanNumericFill);
        Assert.Equal(1, result.OverfullCount);
    }
    [Fact]
    public void IntervalsUseEveryCollectionAndSeparateLocationsAndGlassTypes()
    {
        Observation[] rows = [
            Row("A", "brown", "2026-01-01", "30"), Row("A", "brown", "2026-01-11", "60"),
            Row("A", "brown", "2026-01-31", "overfull"), Row("A", "brown", "2026-03-01", "100"),
            Row("A", "green", "2026-01-01", "10"), Row("B", "brown", "2026-01-01", "10")
        ];
        var result = CollectionAnalytics.Create(rows, "2026-01-31");
        var brown = result.Materials.Single(m => m.Material == "brown");
        Assert.Equal(2, brown.IntervalCount); Assert.Equal(15, brown.MedianIntervalDays);
        Assert.Null(result.Materials.Single(m => m.Material == "green").MedianIntervalDays);
        Assert.Equal(5, result.TotalCollections); Assert.Equal(3, result.KnownBins); Assert.Equal(2, result.BinsWithFewerThan3Readings);
        Assert.All(result.Months, m => Assert.Equal("2026-01", m.Month));
    }
    [Fact]
    public void HistoricalSummaryIsUnchangedByLaterRecords()
    {
        Observation[] before = [Row("A", "white", "2026-01-01", "overfull")];
        var first = CollectionAnalytics.Create(before, "2026-01-01");
        var later = CollectionAnalytics.Create([.. before, Row("B", "brown", "2026-02-01", "10")], "2026-01-01");
        Assert.Equal(first.Materials, later.Materials); Assert.Equal(first.Months, later.Months);
        Assert.Equal(first.TotalCollections, later.TotalCollections); Assert.Equal(first.KnownBins, later.KnownBins);
    }
    [Fact]
    public void EmptyAndOnlyOverfullGroupsHaveNoInventedNumericAverage()
    {
        var empty = CollectionAnalytics.Create([], "2026-01-01");
        Assert.Equal(0, empty.TotalCollections); Assert.Empty(empty.Months);
        Assert.All(empty.Materials, m => { Assert.Null(m.MeanNumericFill); Assert.Null(m.MedianIntervalDays); });
        var overfull = CollectionAnalytics.Create([Row("A", "white", "2026-01-01", "overfull")], "2026-01-01");
        Assert.Null(overfull.Materials.Single(m => m.Material == "white").MeanNumericFill);
    }
    [Theory]
    [InlineData("")] [InlineData("2026-02-30")] [InlineData("01/02/2026")]
    public void RejectsInvalidCutoffs(string date) => Assert.Throws<ArgumentException>(() => CollectionAnalytics.Create([], date));
}
