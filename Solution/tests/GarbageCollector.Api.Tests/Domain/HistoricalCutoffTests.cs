using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Tests;
public class HistoricalCutoffTests
{
    [Theory]
    [InlineData("2024-02-29", true)] [InlineData("2026-02-29", false)]
    [InlineData("2026-3-01", false)] [InlineData("2026-03-01T10:00:00Z", false)]
    [InlineData("", false)] [InlineData(null, false)]
    public void ValidatesExactServiceDates(string? value, bool expected) => Assert.Equal(expected, HistoricalCutoff.IsValid(value));

    [Fact]
    public void BoundaryIsInclusiveAndRejectsLaterDates()
    {
        var cutoff = HistoricalCutoff.Parse("2026-03-01");
        Assert.True(cutoff.Includes("2026-02-28"));
        Assert.True(cutoff.Includes("2026-03-01"));
        Assert.False(cutoff.Includes("2026-03-02"));
        Assert.Throws<ArgumentException>(() => HistoricalCutoff.Parse("bad"));
    }
}
