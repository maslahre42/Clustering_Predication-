using GarbageCollector.Api.Infrastructure.Persistence;
namespace GarbageCollector.Api.Features.History;

public static class HistoryEndpoints
{
    public static void MapHistoryEndpoints(this WebApplication app)
    {
        app.MapGet("/api/history", async (HistoryDbContext db, string? locationId, string? material,
            string? from, string? to, string? asOf, int? page, int? pageSize, string? sortBy, string? sortDirection, string? locationSearch, CancellationToken ct) =>
        {
            if (!HistoryRules.IsValidSort(sortBy, sortDirection) || !HistoryRules.IsValidQuery(material, from, to, page, pageSize) ||
                !HistoryRules.IsValidQuery(null, asOf, null, null, null))
                return Results.Problem("Use a valid material, ISO dates (yyyy-MM-dd), page >= 1 and pageSize between 1 and 200; sortBy date/location/material/fill and sortDirection asc/desc.", statusCode: 400);
            return Results.Ok(await HistoryReader.ReadAsync(db,
                new HistoryFilter(locationId, material, from, to, asOf, page, pageSize, sortBy, sortDirection, locationSearch), ct));
        });
    }
}
