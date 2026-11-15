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
        app.MapGet("/api/fill-state", async (HistoryDbContext db, IForecastEngine engine, string asOf, CancellationToken ct) =>
        {
            if (!HistoricalCutoff.IsValid(asOf))
                return Results.Problem("Use an ISO date (yyyy-MM-dd) for asOf.", statusCode: 400);
            var observations = await db.Observations.AsNoTracking().Through(HistoricalCutoff.Parse(asOf)).ToListAsync(ct);
            try { return Results.Ok(await engine.RunAsync("state", asOf, OperationsSettings.Default, observations, [], cancellationToken: ct)); }
            catch (DatasetRejectedException ex) { return Results.Json(new { detail = ex.Message, validation = ex.Validation }, statusCode: 400); }
            catch (InvalidOperationException ex) { return Results.Problem(ex.Message, statusCode: 503, title: "Selected-day fill estimates unavailable"); }
        });
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
            catch (DatasetRejectedException ex) { return Results.Json(new { detail = ex.Message, validation = ex.Validation }, statusCode: 400); }
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
            catch (DatasetRejectedException ex) { return Results.Json(new { detail = ex.Message, validation = ex.Validation }, statusCode: 400); }
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
            catch (DatasetRejectedException ex) { return Results.Json(new { detail = ex.Message, validation = ex.Validation }, statusCode: 400); }
            catch (InvalidOperationException ex) { return Results.Problem(ex.Message, statusCode: 503); }
        });
        // Uploaded data is scoped to this request; it never changes the source SQLite dataset.
        foreach (var action in new[] { "proposal", "forecast", "simulation" })
        {
            var operation = action;
            app.MapPost($"/api/{action}", async (IForecastEngine engine,
                [Microsoft.AspNetCore.Mvc.FromBody] ProposalDatasetInput input,
                string asOf, [AsParameters] ProposalRequest request, string? locationId, string? material,
                int? horizonDays, string? start, string? end, int? seed, CancellationToken ct) =>
            {
                var settings = request.ToSettings();
                if (!HistoricalCutoff.IsValid(asOf) || settings.Validate().Count > 0)
                    return Results.Problem("Use a valid cutoff and operating settings.", statusCode: 400);
                if (string.IsNullOrWhiteSpace(input.Csv) || System.Text.Encoding.UTF8.GetByteCount(input.Csv) > 2_000_000)
                    return Results.Problem("Upload a nonempty CSV of at most 2 MB.", statusCode: 400);
                if (operation == "simulation" && SimulationRules.Validate(asOf, start ?? "", end ?? "", seed ?? 7) is string error)
                    return Results.Problem(error, statusCode: 400);
                if (operation == "forecast" && (string.IsNullOrWhiteSpace(locationId) || material is not ("brown" or "green" or "white") || horizonDays is < 1 or > 150))
                    return Results.Problem("Choose a container, material and forecast horizon of 1–150 days.", statusCode: 400);
                try
                {
                    return Results.Ok(await engine.RunAsync(operation, asOf, settings, [], [], locationId, material,
                        horizonDays ?? 60, start, end, seed ?? 7, ct, input.Csv));
                }
                catch (DatasetRejectedException ex) { return Results.Json(new { detail = ex.Message, validation = ex.Validation }, statusCode: 400); }
                catch (InvalidOperationException ex) { return Results.Problem(ex.Message, statusCode: 503); }
            });
        }
    }
}

public sealed record ProposalDatasetInput(string Csv);

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
