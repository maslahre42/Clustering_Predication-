using GarbageCollector.Api.Infrastructure.Persistence;
namespace GarbageCollector.Api.Features.Dataset;

public static class DatasetEndpoints
{
    public static void MapDatasetEndpoints(this WebApplication app) =>
        app.MapGet("/api/data-range", async (HistoryDbContext db, CancellationToken ct) =>
            Results.Ok(await DatasetDateRange.ReadAsync(db, ct)));
}
