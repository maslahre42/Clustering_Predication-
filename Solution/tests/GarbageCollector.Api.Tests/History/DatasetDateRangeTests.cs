using GarbageCollector.Api.Features.Dataset;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
namespace GarbageCollector.Api.Tests;

public class DatasetDateRangeTests
{
    [Theory]
    [InlineData("2026-09-30", "2026-10-07")]
    [InlineData("2026-12-29", "2027-01-05")]
    [InlineData("2024-02-25", "2024-03-03")]
    [InlineData("9999-12-31", "9999-12-31")]
    public void AddsSevenCalendarDaysAcrossMonthYearAndLeapBoundaries(string last, string maximum) =>
        Assert.Equal(new DatasetDateRange("2024-01-01", last, maximum), DatasetDateRange.Create("2024-01-01", last));

    [Fact]
    public void EmptyDatasetHasNoSelectableRange() => Assert.Equal(new(null, null, null), DatasetDateRange.Create(null, null));

    [Theory]
    [InlineData(null, "2026-01-01")] [InlineData("bad", "2026-01-01")]
    [InlineData("2026-02-01", "2026-01-01")]
    public void InvalidBoundsAreRejected(string? first, string? last) =>
        Assert.Throws<ArgumentException>(() => DatasetDateRange.Create(first, last));

    [Fact]
    public async Task ReadsGlobalBoundsFromSqliteIncludingEmptyAndUnorderedRows()
    {
        await using var connection = new SqliteConnection("Data Source=:memory:");
        await connection.OpenAsync();
        await using var db = new HistoryDbContext(new DbContextOptionsBuilder<HistoryDbContext>().UseSqlite(connection).Options);
        await db.Database.ExecuteSqlRawAsync("CREATE TABLE raw_data (Location_id TEXT, material_type TEXT, date TEXT, fill_level_perc TEXT)");
        Assert.Equal(new(null, null, null), await DatasetDateRange.ReadAsync(db));
        await db.Database.ExecuteSqlRawAsync("INSERT INTO raw_data VALUES ('A','green','2026-09-30','80'),('B','white','2025-10-17','overfull')");
        Assert.Equal(new("2025-10-17", "2026-09-30", "2026-10-07"), await DatasetDateRange.ReadAsync(db));
    }
}
