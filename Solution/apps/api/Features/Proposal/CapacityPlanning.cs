using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;

namespace GarbageCollector.Api.Features.Proposal;

public sealed record ContainerCounts(int Brown = 1, int Green = 1, int White = 1)
{
    [System.Text.Json.Serialization.JsonIgnore]
    public bool Valid => new[] { Brown, Green, White }.All(n => n is >= 1 and <= 20);
}
public sealed record ContainerCountOverride(string LocationId, string Material, int BaselineCount, int AlternativeCount);
public sealed record SiteContainerLimit(string LocationId, int MaxContainers);
public sealed record CapacityScenarioRequest
{
    public bool Optimize { get; init; }
    public int OptimizationWeeks { get; init; } = 4;
    public double TargetFillPercent { get; init; } = 90;
    public int MaxContainersPerType { get; init; } = 3;
    public int MaxContainersPerSite { get; init; } = 9;
    public int MinIntervalDays { get; init; } = 1;
    public int MaxIntervalDays { get; init; } = 28;
    public SiteContainerLimit[]? SiteLimits { get; init; } = [];
    public int Days { get; init; } = 28;
    public int BaselineIntervalDays { get; init; } = 7;
    public int AlternativeIntervalDays { get; init; } = 14;
    public ContainerCounts? BaselineContainers { get; init; } = new();
    public ContainerCounts? AlternativeContainers { get; init; } = new();
    public ContainerCountOverride[]? Overrides { get; init; } = [];
    public double ContainerCostPerMonthEuro { get; init; }
    public string? Csv { get; init; }
    public string? Validate()
    {
        if (Optimize && (OptimizationWeeks is < 1 or > 8 || !double.IsFinite(TargetFillPercent) || TargetFillPercent is < 50 or > 100 ||
            MaxContainersPerType is < 1 or > 20 || MaxContainersPerSite is < 1 or > 60 || MinIntervalDays is < 1 or > 56 || MaxIntervalDays is < 1 or > 56 ||
            MinIntervalDays > Math.Min(MaxIntervalDays, OptimizationWeeks * 7))) return "Use a 1–8 week cycle, 50–100% fill target, valid container bounds and 1–56 day intervals within the cycle.";
        if (SiteLimits is null || SiteLimits.Length > 500 || SiteLimits.Any(r => r is null || string.IsNullOrWhiteSpace(r.LocationId) || r.MaxContainers is < 1 or > 60) || SiteLimits.Select(r => r.LocationId).Distinct().Count() != SiteLimits.Length)
            return "Use unique site limits with 1–60 total containers.";
        if (Days is < 7 or > 31 || BaselineIntervalDays is < 1 or > 28 || AlternativeIntervalDays is < 1 or > 28)
            return "Choose 7–31 scenario days and collection intervals of 1–28 calendar days.";
        if (BaselineContainers?.Valid != true || AlternativeContainers?.Valid != true)
            return "Specify 1–20 containers per site and glass type for both scenarios.";
        if (!double.IsFinite(ContainerCostPerMonthEuro) || ContainerCostPerMonthEuro is < 0 or > 10000)
            return "Container monthly cost must be between 0 and 10000 euros.";
        if (Overrides is null || Overrides.Length > 1500 || Overrides.Any(r => r is null || string.IsNullOrWhiteSpace(r.LocationId) || r.Material is not ("brown" or "green" or "white") || r.BaselineCount is < 1 or > 20 || r.AlternativeCount is < 1 or > 20))
            return "Use valid site/material overrides with counts of 1–20.";
        if (Overrides.Select(r => (r.LocationId, r.Material)).Distinct().Count() != Overrides.Length)
            return "Each site/material override must be unique.";
        if (Csv is not null && (string.IsNullOrWhiteSpace(Csv) || System.Text.Encoding.UTF8.GetByteCount(Csv) > 2_000_000))
            return "Upload a nonempty CSV of at most 2 MB.";
        return null;
    }
}

public static class CapacityPlanningEndpoints
{
    public static void MapCapacityPlanning(this WebApplication app)
    {
        app.MapPost("/api/capacity-scenario", async (HistoryDbContext db, IForecastEngine engine, string asOf,
            [Microsoft.AspNetCore.Mvc.FromBody] CapacityScenarioRequest input,
            [AsParameters] ProposalRequest request, CancellationToken ct) =>
        {
            if (!HistoricalCutoff.IsValid(asOf)) return Results.Problem("Use an ISO history cutoff.", statusCode: 400);
            var settings = request.ToSettings();
            if (input.Validate() is string error) return Results.Problem(error, statusCode: 400);
            if (settings.Validate().Count > 0) return Results.Problem("Use valid operating settings.", statusCode: 400);
            var observations = input.Csv is null ? await db.Observations.AsNoTracking().Through(HistoricalCutoff.Parse(asOf)).ToListAsync(ct) : [];
            var locations = input.Csv is null ? await db.Locations.AsNoTracking().ToListAsync(ct) : [];
            try
            {
                return Results.Ok(await engine.RunAsync("capacity", asOf, settings, observations, locations,
                    cancellationToken: ct, csv: input.Csv, capacityScenario: input with { Csv = null }));
            }
            catch (DatasetRejectedException ex) { return Results.Json(new { detail = ex.Message, validation = ex.Validation }, statusCode: 400); }
            catch (InvalidOperationException ex) { return Results.Problem(ex.Message, statusCode: 503); }
        });
    }
}
