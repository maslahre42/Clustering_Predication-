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
    public static void MapProposalEndpoints(this WebApplication app)
    {
        app.MapGet("/api/proposal", async (HistoryDbContext db, IForecastEngine engine, string asOf, [AsParameters] ProposalRequest request, CancellationToken ct) =>
        {
            if (!HistoricalCutoff.IsValid(asOf))
                return Results.Problem("Use an ISO date (yyyy-MM-dd) for asOf.", statusCode: 400);
            var settings = request.ToSettings();
            var errors = settings.Validate();
            if (errors.Count > 0)
                return Results.Problem(string.Join(" ", errors), statusCode: 400, title: "Invalid operating settings");
            var observations = await db.Observations.AsNoTracking().Through(HistoricalCutoff.Parse(asOf)).ToListAsync(ct);
            var locations = await db.Locations.AsNoTracking().ToListAsync(ct);
            try { return Results.Ok(await engine.RunAsync("proposal", asOf, settings, observations, locations, cancellationToken: ct)); }
            catch (InvalidOperationException ex) { return Results.Problem(ex.Message, statusCode: 503, title: "Python forecast engine unavailable"); }
        });
        app.MapGet("/api/forecast", async (HistoryDbContext db, IForecastEngine engine, string asOf, string locationId, string material,
            int? horizonDays, [AsParameters] ProposalRequest request, CancellationToken ct) =>
        {
            var settings = request.ToSettings();
            if (!HistoricalCutoff.IsValid(asOf) || string.IsNullOrWhiteSpace(locationId) || material is not ("brown" or "green" or "white") ||
                horizonDays is < 1 or > 150 || settings.Validate().Count > 0)
                return Results.Problem("Use a valid date, bin, settings and a horizon of 1–150 days.", statusCode: 400);
            var observations = await db.Observations.AsNoTracking().Through(HistoricalCutoff.Parse(asOf)).ToListAsync(ct);
            try { return Results.Ok(await engine.RunAsync("forecast", asOf, settings, observations, [], locationId, material, horizonDays ?? 60, cancellationToken: ct)); }
            catch (InvalidOperationException ex) { return Results.Problem(ex.Message, statusCode: 503); }
        });
        app.MapGet("/api/simulation", async (HistoryDbContext db, IForecastEngine engine, string asOf, string start, string end,
            int? seed, [AsParameters] ProposalRequest request, CancellationToken ct) =>
        {
            var settings = request.ToSettings();
            var error = SimulationRules.Validate(asOf, start, end, seed ?? 7);
            if (error is not null || settings.Validate().Count > 0)
                return Results.Problem(error ?? string.Join(" ", settings.Validate()), statusCode: 400);
            var observations = await db.Observations.AsNoTracking().Through(HistoricalCutoff.Parse(asOf)).ToListAsync(ct);
            var locations = await db.Locations.AsNoTracking().ToListAsync(ct);
            try { return Results.Ok(await engine.RunAsync("simulation", asOf, settings, observations, locations, start: start, end: end, seed: seed ?? 7, cancellationToken: ct)); }
            catch (InvalidOperationException ex) { return Results.Problem(ex.Message, statusCode: 503); }
        });
    }
}

public static class SimulationRules
{
    public static string? Validate(string asOf, string start, string end, int seed)
    {
        if (!HistoricalCutoff.IsValid(asOf) || !HistoricalCutoff.IsValid(start) || !HistoricalCutoff.IsValid(end)) return "Use ISO calendar dates.";
        if (string.CompareOrdinal(start, end) > 0 || string.CompareOrdinal(end, asOf) > 0) return "Simulation must start before its end and end on or before the history cutoff.";
        if (DateOnly.ParseExact(end, "yyyy-MM-dd").DayNumber - DateOnly.ParseExact(start, "yyyy-MM-dd").DayNumber > 30) return "Choose at most 31 days per simulation.";
        return seed is < 0 or > 1000000 ? "Seed must be between 0 and 1000000." : null;
    }
}
