using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
namespace GarbageCollector.Api.Features.Locations;

public static class LocationEndpoints
{
    public static void MapLocationEndpoints(this WebApplication app) =>
        app.MapGet("/api/locations", async (HistoryDbContext db, CancellationToken ct) =>
            Results.Ok(await db.Locations.AsNoTracking().OrderBy(location => location.LocationId).ToListAsync(ct)));
}
