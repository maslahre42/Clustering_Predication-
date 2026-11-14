using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
namespace GarbageCollector.Api.Features.Analytics;

public static class AnalyticsEndpoints
{
    public static void MapAnalyticsEndpoints(this WebApplication app) =>
        app.MapGet("/api/analytics", async (HistoryDbContext db, string asOf, CancellationToken ct) => {
            if (!HistoricalCutoff.IsValid(asOf))
                return Results.Problem("Use an ISO date (yyyy-MM-dd) for asOf.", statusCode: 400);
            var rows = await db.Observations.AsNoTracking().Through(HistoricalCutoff.Parse(asOf)).ToArrayAsync(ct);
            return Results.Ok(CollectionAnalytics.Create(rows, asOf));
        });
}
