using GarbageCollector.Api.Features.History;

namespace GarbageCollector.Api.Tests;

public sealed class HistoryFillOrderingTests
{
    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public void UnknownStaysLastAndOverfullRetainsItsCategory(bool ascending)
    {
        HistoryItem[] items = [
            new("unknown", "white", "2026-03-01", null),
            new("full", "brown", "2026-03-01", 100),
            new("overfull", "green", "2026-03-01", null, true),
            new("empty", "white", "2026-03-01", 0),
        ];
        var result = HistoryFillOrdering.Apply(items, ascending).ToArray();
        Assert.Equal("unknown", result.Last().LocationId);
        Assert.Equal(ascending ? "empty" : "overfull", result.First().LocationId);
        Assert.Null(Assert.Single(result, row => row.IsOverfull).FillLevelPercent);
        Assert.Equal("unknown", items.First().LocationId);
    }

    [Fact]
    public void EqualReadingsUseDateLocationAndMaterialForStablePaging()
    {
        HistoryItem[] items = [
            new("B", "white", "2026-03-01", 50),
            new("A", "green", "2026-03-01", 50),
            new("A", "brown", "2026-03-01", 50),
            new("A", "brown", "2026-02-01", 50),
        ];
        var result = HistoryFillOrdering.Apply(items, true).ToArray();
        Assert.Equal(new[] { "A:brown", "A:green", "B:white", "A:brown" }, result.Select(row => $"{row.LocationId}:{row.Material}"));
        Assert.Equal("2026-02-01", result.Last().Date);
        Assert.Empty(HistoryFillOrdering.Apply([], true));
    }
}
