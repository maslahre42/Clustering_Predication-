using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
namespace GarbageCollector.Api.Features.Planning;

public static class PlanningEndpoints
{
    public static void MapPlanningEndpoints(this WebApplication app)
    {
        app.MapGet("/api/planning", async (HistoryDbContext db, string asOf, CancellationToken ct) =>
        {
            if (!HistoricalCutoff.IsValid(asOf))
                return Results.Problem("Use an ISO date (yyyy-MM-dd) for asOf.", statusCode: 400);
            var observations = await db.Observations.AsNoTracking()
                .Through(HistoricalCutoff.Parse(asOf)).ToListAsync(ct);
            return Results.Ok(PlanningSnapshot.Create(observations, asOf));
        });
    }
}
