using GarbageCollector.Api.Features.History;
using GarbageCollector.Api.Features.Planning;
using GarbageCollector.Api.Features.Analytics;
using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
namespace GarbageCollector.Api.Tests;

// Relational service tests: each case owns an isolated SQLite in-memory database.
public sealed class HistoryReaderTests : IAsyncLifetime
{
    private readonly SqliteConnection connection = new("Data Source=:memory:");
    private HistoryDbContext db = null!;
    public async Task InitializeAsync()
    {
        await connection.OpenAsync();
        db = new(new DbContextOptionsBuilder<HistoryDbContext>().UseSqlite(connection).Options);
        await db.Database.ExecuteSqlRawAsync("""
            CREATE TABLE raw_data (Location_id TEXT NOT NULL, material_type TEXT NOT NULL, date TEXT NOT NULL, fill_level_perc TEXT NOT NULL);
            INSERT INTO raw_data VALUES
              ('A', 'green', '2026-02-01', '20'),
              ('A', 'brown', '2026-03-01', '80'),
              ('A', 'green', '2026-03-01', '100'),
              ('B', 'white', '2026-03-01', 'unknown'),
              ('A', 'green', '2026-04-01', '40');
            """);
    }
    public async Task DisposeAsync() { await db.DisposeAsync(); await connection.DisposeAsync(); }

    [Fact]
    public async Task CutoffOverridesLaterToDateAndDoesNotChangeSource()
    {
        var result = await HistoryReader.ReadAsync(db, new(AsOf: "2026-03-01", To: "2026-12-31"));
        Assert.Equal(4, result.Total);
        Assert.All(result.Items, row => Assert.True(string.CompareOrdinal(row.Date, "2026-03-01") <= 0));
        Assert.Equal(5, await db.Observations.CountAsync());
    }
    [Fact]
    public async Task CombinesLocationMaterialAndInclusiveDateBounds()
    {
        var result = await HistoryReader.ReadAsync(db, new("A", "green", "2026-03-01", "2026-03-01"));
        Assert.Equal(new HistoryItem("A", "green", "2026-03-01", 100), Assert.Single(result.Items));
        Assert.Equal(1, result.Total);
    }
    [Fact]
    public async Task PaginationIsStableAndTotalCountsAllMatches()
    {
        var first = await HistoryReader.ReadAsync(db, new(AsOf: "2026-03-01", Page: 1, PageSize: 2));
        var next = await HistoryReader.ReadAsync(db, new(AsOf: "2026-03-01", Page: 2, PageSize: 2));
        Assert.Equal(4, first.Total); Assert.Equal(4, next.Total);
        Assert.Equal(new[] { "A:brown", "A:green" }, first.Items.Select(x => $"{x.LocationId}:{x.Material}"));
        Assert.Equal("B", next.Items[0].LocationId);
        Assert.Equal("2026-02-01", next.Items[1].Date);
        Assert.Equal(2, next.Page);
    }
    [Fact]
    public async Task UnknownMeasurementsRemainNullAndAreNotZero()
    {
        var result = await HistoryReader.ReadAsync(db, new(LocationId: "B"));
        Assert.Null(Assert.Single(result.Items).FillLevelPercent);
    }
    [Fact]
    public async Task MissingLocationEarlyDatesAndLargePagesProduceEmptyResults()
    {
        foreach (var filter in new[] { new HistoryFilter(LocationId: "missing"), new(AsOf: "1900-01-01"), new(Page: int.MaxValue, PageSize: 200) })
            Assert.Empty((await HistoryReader.ReadAsync(db, filter)).Items);
    }
    [Fact]
    public async Task InvalidFiltersAreRejectedBeforeReading()
    {
        foreach (var filter in new[] { new HistoryFilter(Material: "plastic"), new(Page: 0), new(PageSize: 201), new(AsOf: "bad-date"), new(From: "2026-04-01", To: "2026-03-01") })
            await Assert.ThrowsAsync<ArgumentException>(() => HistoryReader.ReadAsync(db, filter));
    }
    [Fact]
    public async Task ReturnsExplicitOverflowFlagFromSqlite()
    {
        await db.Database.ExecuteSqlRawAsync("INSERT INTO raw_data VALUES ('C', 'white', '2026-03-01', 'overfull')");
        var result = await HistoryReader.ReadAsync(db, new(LocationId: "C"));
        var item = Assert.Single(result.Items);
        Assert.True(item.IsOverfull); Assert.Null(item.FillLevelPercent);
    }
    [Fact]
    public async Task SortingPrecedesPaginationAndPreservesCutoff()
    {
        var result = await HistoryReader.ReadAsync(db, new(AsOf: "2026-03-01", SortBy: "date", SortDirection: "asc", PageSize: 2));
        Assert.Equal(4, result.Total);
        Assert.Equal(new[] { "2026-02-01", "2026-03-01" }, result.Items.Select(x => x.Date));
        var location = await HistoryReader.ReadAsync(db, new(AsOf: "2026-03-01", SortBy: "location", SortDirection: "desc", PageSize: 1));
        Assert.Equal("B", Assert.Single(location.Items).LocationId);
        var material = await HistoryReader.ReadAsync(db, new(SortBy: "material", SortDirection: "asc", PageSize: 1));
        Assert.Equal("brown", Assert.Single(material.Items).Material);
    }

    [Fact]
    public async Task PartialLocationSearchCombinesWithFiltersAndCountsBeforePaging()
    {
        await db.Database.ExecuteSqlRawAsync("INSERT INTO raw_data VALUES ('SITE-A-01', 'green', '2026-03-01', '60')");
        var result = await HistoryReader.ReadAsync(db, new(Material: "green", AsOf: "2026-03-01", LocationSearch: " A ", PageSize: 1));
        Assert.Equal(3, result.Total);
        Assert.Single(result.Items);
        var exact = await HistoryReader.ReadAsync(db, new(LocationId: "A", LocationSearch: "SITE"));
        Assert.Empty(exact.Items);
    }

    [Theory]
    [InlineData("asc")]
    [InlineData("desc")]
    public async Task FillSortUsesNumbersAndKeepsUnknownLastWithoutChangingOverfull(string direction)
    {
        await db.Database.ExecuteSqlRawAsync("INSERT INTO raw_data VALUES ('C', 'white', '2026-03-01', ' OVERFULL '), ('D', 'white', '2026-03-01', '9')");
        var result = await HistoryReader.ReadAsync(db, new(AsOf: "2026-03-01", SortBy: "fill", SortDirection: direction));
        Assert.Equal("B", result.Items.Last().LocationId);
        var overflow = Assert.Single(result.Items, x => x.IsOverfull);
        Assert.Null(overflow.FillLevelPercent);
        Assert.Equal(direction == "asc" ? new double?[] { 9, 20, 80, 100 } : new double?[] { 100, 80, 20, 9 },
            result.Items.Where(x => x.FillLevelPercent is not null).Select(x => x.FillLevelPercent));
        Assert.Equal("C", result.Items[direction == "asc" ? 4 : 0].LocationId);
    }

    [Theory]
    [InlineData("bad", "asc")]
    [InlineData("date", "bad")]
    public async Task InvalidSortIsRejected(string field, string direction)
    {
        await Assert.ThrowsAsync<ArgumentException>(() => HistoryReader.ReadAsync(db, new(SortBy: field, SortDirection: direction)));
    }

    [Fact]
    public async Task CancellationIsPropagated()
    {
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => HistoryReader.ReadAsync(db, new(), new CancellationToken(true)));
    }
}
