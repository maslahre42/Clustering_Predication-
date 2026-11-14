using GarbageCollector.Api.Features.Planning;
using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Tests;

public class PlanningSnapshotTests
{
    private static Observation Row(string id, string material, string date, string fill) =>
        new() { LocationId = id, Material = material, Date = date, FillLevel = fill };

    [Fact]
    public void EmptyHistoryHasNoInventedDatesOrBins()
    {
        var summary = PlanningSnapshot.Create([], "2026-05-01");
        Assert.Equal(0, summary.ObservationCount);
        Assert.Empty(summary.Bins);
        Assert.Null(summary.FirstDate);
        Assert.Null(summary.LastDate);
    }

    [Fact]
    public void SeparatesBinsByBothLocationAndMaterialAndUsesLatestReading()
    {
        Observation[] rows = [
            Row("B", "brown", "2026-01-01", "80"),
            Row("A", "green", "2026-05-01", "90"),
            Row("A", "brown", "2026-02-01", "100"),
            Row("A", "green", "2026-03-01", "30")
        ];
        var summary = PlanningSnapshot.Create(rows, "2026-05-01");
        Assert.Equal(4, summary.ObservationCount);
        Assert.Equal("2026-01-01", summary.FirstDate);
        Assert.Equal("2026-05-01", summary.LastDate);
        Assert.Equal(3, summary.Bins.Length);
        Assert.Equal(new BinSummary("A", "brown", "2026-02-01", 100, 1), summary.Bins[0]);
        Assert.Equal(new BinSummary("A", "green", "2026-05-01", 90, 2), summary.Bins[1]);
        Assert.Equal(new BinSummary("B", "brown", "2026-01-01", 80, 1), summary.Bins[2]);
        Assert.Equal("B", rows[0].LocationId); // Source data is not reordered or modified.
        Assert.Equal("100", rows[2].FillLevel); // Pre-emptying readings are preserved.
    }

    [Fact]
    public void PastPlanningIgnoresFutureCollectionsAndBinsCompletely()
    {
        Observation[] history = [
            Row("A", "green", "2026-01-01", "30"),
            Row("A", "green", "2026-03-01", "90"),
            Row("A", "green", "2026-05-01", "100"),
            Row("B", "white", "2026-06-01", "100")
        ];
        var snapshot = PlanningSnapshot.Create(history, "2026-03-01");
        Assert.Equal("2026-03-01", snapshot.AsOf);
        Assert.Equal(2, snapshot.ObservationCount);
        Assert.Equal("2026-03-01", snapshot.LastDate);
        Assert.Equal(new BinSummary("A", "green", "2026-03-01", 90, 2), Assert.Single(snapshot.Bins));
        var beforeFirst = PlanningSnapshot.Create(history, "2025-12-31");
        Assert.Empty(beforeFirst.Bins);
        Assert.Equal(0, beforeFirst.ObservationCount);
        Assert.Null(beforeFirst.FirstDate);
        Assert.Null(beforeFirst.LastDate);
        // Replaying a past date must produce the same result after new records are added.
        var earlier = PlanningSnapshot.Create(history[..2], "2026-03-01");
        Assert.Equal(earlier.Bins, snapshot.Bins);
        Assert.Equal(earlier.ObservationCount, snapshot.ObservationCount);
    }

    [Theory]
    [InlineData("")] [InlineData("2026-02-30")] [InlineData("01/03/2026")]
    public void InvalidCutoffIsRejected(string cutoff) =>
        Assert.Throws<ArgumentException>(() => PlanningSnapshot.Create([], cutoff));

    [Fact]
    public void InvalidLatestReadingDoesNotFallBackToOlderValue()
    {
        var summary = PlanningSnapshot.Create([
            Row("A", "white", "2026-01-01", "100"),
            Row("A", "white", "2026-02-01", "unknown")
        ], "2026-05-01");
        var bin = Assert.Single(summary.Bins);
        Assert.Null(bin.LastFillPercent);
        Assert.Equal("2026-02-01", bin.LastCollection);
        Assert.Equal(2, bin.Collections);
    }
}
