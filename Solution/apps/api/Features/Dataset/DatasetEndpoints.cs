using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Features.Proposal;
using GarbageCollector.Api.Infrastructure.Persistence;
namespace GarbageCollector.Api.Features.Dataset;

public static class DatasetEndpoints
{
    public static void MapDatasetEndpoints(this WebApplication app)
    {
        app.MapGet("/api/data-range", async (HistoryDbContext db, CancellationToken ct) =>
            Results.Ok(await DatasetDateRange.ReadAsync(db, ct)));
        app.MapPost("/api/dataset-validation", async (IForecastEngine engine, string asOf,
            [Microsoft.AspNetCore.Mvc.FromBody] ProposalDatasetInput input, CancellationToken ct) =>
        {
            if (!HistoricalCutoff.IsValid(asOf)) return Results.Problem("Use an ISO planning date.", statusCode: 400);
            if (string.IsNullOrWhiteSpace(input.Csv) || System.Text.Encoding.UTF8.GetByteCount(input.Csv) > 2_000_000)
                return Results.Problem("Choose a nonempty CSV of at most 2 MB.", statusCode: 400);
            try { return Results.Ok(await engine.RunAsync("dataset", asOf, OperationsSettings.Default, [], [], csv: input.Csv, cancellationToken: ct)); }
            catch (DatasetRejectedException ex) { return Results.Json(new { detail = ex.Message, validation = ex.Validation }, statusCode: 400); }
            catch (InvalidOperationException ex) { return Results.Problem(ex.Message, statusCode: 503, title: "CSV validation unavailable"); }
        });
    }
}
