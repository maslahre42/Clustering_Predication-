using GarbageCollector.Api.Features.Analytics;
using GarbageCollector.Api.Features.Dataset;
using GarbageCollector.Api.Features.Locations;
using GarbageCollector.Api.Features.History;
using GarbageCollector.Api.Features.Planning;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
namespace GarbageCollector.Api.Api;

public static class EndpointRegistration
{
    public static void MapApplicationEndpoints(this WebApplication app)
    {
        app.MapOpenApi();
        app.MapGet("/api/health", async (HistoryDbContext db, CancellationToken ct) => {
            await db.Locations.AsNoTracking().Take(1).ToListAsync(ct);
            await db.Observations.AsNoTracking().Take(1).ToListAsync(ct);
            return Results.Ok(new { status = "healthy" });
        });
        app.MapDatasetEndpoints();
        app.MapLocationEndpoints();
        app.MapHistoryEndpoints();
        app.MapPlanningEndpoints();
        app.MapAnalyticsEndpoints();
    }
}
