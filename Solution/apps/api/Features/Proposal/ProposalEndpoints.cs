using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
namespace GarbageCollector.Api.Features.Proposal;

public static class ProposalEndpoints
{
    /// <summary>
    /// Forecast, selection and routes for the first collection day after <c>asOf</c>.
    /// Operating numbers are optional query values; missing ones keep their defaults.
    /// </summary>
    public static void MapProposalEndpoints(this WebApplication app) =>
        app.MapGet("/api/proposal", async (HistoryDbContext db, string asOf, [AsParameters] ProposalRequest request, CancellationToken ct) =>
        {
            if (!HistoricalCutoff.IsValid(asOf))
                return Results.Problem("Use an ISO date (yyyy-MM-dd) for asOf.", statusCode: 400);
            var settings = request.ToSettings();
            var errors = settings.Validate();
            if (errors.Count > 0)
                return Results.Problem(string.Join(" ", errors), statusCode: 400, title: "Invalid operating settings");
            var observations = await db.Observations.AsNoTracking().Through(HistoricalCutoff.Parse(asOf)).ToListAsync(ct);
            var locations = await db.Locations.AsNoTracking().ToListAsync(ct);
            return Results.Ok(CollectionProposal.Create(observations, locations, asOf, settings));
        });
}
