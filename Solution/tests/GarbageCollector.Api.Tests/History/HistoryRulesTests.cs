using GarbageCollector.Api.Features.History;
namespace GarbageCollector.Api.Tests;

public class HistoryRulesTests
{
    [Theory]
    [InlineData(null)] [InlineData("brown")] [InlineData("green")] [InlineData("white")]
    public void AllowsSupportedMaterials(string? material) =>
        Assert.True(HistoryRules.IsValidQuery(material, null, null, null, null));

    [Theory]
    [InlineData("")] [InlineData("plastic")] [InlineData("Green")]
    public void RejectsUnsupportedMaterials(string material) =>
        Assert.False(HistoryRules.IsValidQuery(material, null, null, null, null));

    [Theory]
    [InlineData("2026-02-30")] [InlineData("2026-2-01")] [InlineData("13/11/2026")]
    [InlineData("2026-11-13T00:00:00Z")] [InlineData("")] [InlineData("not-a-date")]
    public void RejectsInvalidDatesInEitherBound(string date)
    {
        Assert.False(HistoryRules.IsValidQuery(null, date, null, null, null));
        Assert.False(HistoryRules.IsValidQuery(null, null, date, null, null));
    }

    [Fact]
    public void AllowsLeapDayAndInclusiveSameDayRange()
    {
        Assert.True(HistoryRules.IsValidQuery(null, "2024-02-29", "2024-02-29", 1, 200));
        Assert.False(HistoryRules.IsValidQuery(null, "2025-02-29", null, 1, 200));
        Assert.False(HistoryRules.IsValidQuery(null, "2026-11-14", "2026-11-13", 1, 50));
    }

    [Theory]
    [InlineData(0, 50)] [InlineData(-1, 50)] [InlineData(1, 0)]
    [InlineData(1, -1)] [InlineData(1, 201)]
    public void RejectsInvalidPagination(int page, int size) =>
        Assert.False(HistoryRules.IsValidQuery(null, null, null, page, size));

    [Theory]
    [InlineData(null, null, 0)] [InlineData(1, 50, 0)] [InlineData(2, null, 50)]
    [InlineData(3, 200, 400)] [InlineData(int.MaxValue, 200, int.MaxValue)]
    public void ComputesOffsetWithoutOverflow(int? page, int? size, int expected) =>
        Assert.Equal(expected, HistoryRules.Offset(page, size));

}
