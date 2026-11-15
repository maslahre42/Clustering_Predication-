using System.Text.Json;
using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Domain.Locations;
using GarbageCollector.Api.Features.Proposal;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace GarbageCollector.Api.Tests;

public class ProposalEndpointTests
{
    [Fact]
    public async Task ActualEndpointsBindPythonParametersAndNeverPassFutureObservations()
    {
        await using var connection = new SqliteConnection("Data Source=:memory:");
        await connection.OpenAsync();
        var builder = WebApplication.CreateBuilder(new WebApplicationOptions { EnvironmentName = "Testing" });
        builder.Configuration["hostBuilder:reloadConfigOnChange"] = "false";
        builder.Logging.ClearProviders();
        builder.Services.AddDbContext<HistoryDbContext>(options => options.UseSqlite(connection));
        var engine = new CaptureEngine();
        builder.Services.AddSingleton<IForecastEngine>(engine);
        await using var app = builder.Build();
        app.MapProposalEndpoints();
        await using var scope = app.Services.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<HistoryDbContext>();
        await db.Database.ExecuteSqlRawAsync("""
            CREATE TABLE raw_data (Location_id TEXT, material_type TEXT, date TEXT, fill_level_perc TEXT);
            CREATE TABLE locations (location_id TEXT, latitude REAL, longitude REAL, is_synthetic INTEGER);
            INSERT INTO raw_data VALUES ('A','white','2026-08-01','50'), ('A','white','2026-08-20','100');
            INSERT INTO locations VALUES ('A',49.14,9.22,1);
            """);
        async Task<int> Request(string path, string query, string method = "GET", string? csv = null, CapacityScenarioRequest? capacityScenario = null)
        {
            var endpoint = ((IEndpointRouteBuilder)app).DataSources.SelectMany(s => s.Endpoints).OfType<RouteEndpoint>()
                .Single(e => e.RoutePattern.RawText == path && e.Metadata.GetMetadata<HttpMethodMetadata>()!.HttpMethods.Contains(method));
            var context = new DefaultHttpContext { RequestServices = scope.ServiceProvider };
            context.Request.Method = method;
            if (csv is not null || capacityScenario is not null)
            {
                var bytes = System.Text.Encoding.UTF8.GetBytes(capacityScenario is not null ? JsonSerializer.Serialize(capacityScenario, new JsonSerializerOptions(JsonSerializerDefaults.Web)) : JsonSerializer.Serialize(new { csv }));
                context.Request.ContentType = "application/json";
                context.Request.ContentLength = bytes.Length;
                context.Request.Body = new MemoryStream(bytes);
                context.Features.Set<Microsoft.AspNetCore.Http.Features.IHttpRequestBodyDetectionFeature>(new BodyFeature());
            } context.Request.Path = path; context.Request.QueryString = new QueryString(query);
            context.Response.Body = new MemoryStream();
            await endpoint.RequestDelegate!(context);
            return context.Response.StatusCode;
        }
        Assert.Equal(200, await Request("/api/proposal", "?asOf=2026-08-14&vehicleFixedCostMin=600&optionalValueMin=25&solverTimeLimitSeconds=2&neighbourProbability=0.2&avgSpeedKph=30&workSaturday=true&brownCompartmentM3=2&greenCompartmentM3=3&whiteCompartmentM3=4&costPerKmEuro=1.2&fixedTruckCostEuro=150"));
        Assert.Equal("proposal", engine.Action);
        Assert.Equal(480, engine.Settings!.VehicleFixedCostMin); // removed query values cannot select a legacy travel model
        Assert.Equal(25, engine.Settings.OptionalValueMin);
        Assert.Equal(2, engine.Settings.SolverTimeLimitSeconds);
        Assert.Equal(0.2, engine.Settings.NeighbourProbability);
        Assert.Equal(25, engine.Settings.AvgSpeedKph);
        Assert.True(engine.Settings.WorkSaturday);
        Assert.Equal(2, engine.Settings.BrownCompartmentM3);
        Assert.Equal(3, engine.Settings.GreenCompartmentM3);
        Assert.Equal(4, engine.Settings.WhiteCompartmentM3);
        Assert.Equal(1.2, engine.Settings.CostPerKmEuro);
        Assert.Equal(150, engine.Settings.FixedTruckCostEuro);
        var beforeInvalid = engine.Calls;
        Assert.Equal(400, await Request("/api/proposal", "?asOf=2026-08-14&brownCompartmentM3=2"));
        Assert.Equal(beforeInvalid, engine.Calls);
        Assert.Equal("2026-08-01", Assert.Single(engine.Observations!).Date);
        Assert.Equal(200, await Request("/api/fill-state", "?asOf=2026-08-14"));
        Assert.Equal("state", engine.Action);
        Assert.Equal(OperationsSettings.Default, engine.Settings);
        Assert.Equal("2026-08-01", Assert.Single(engine.Observations!).Date);
        Assert.Empty(engine.Locations!);
        var beforeInvalidState = engine.Calls;
        Assert.Equal(400, await Request("/api/fill-state", "?asOf=2026-13-01"));
        Assert.Equal(beforeInvalidState, engine.Calls);
        Assert.Equal(200, await Request("/api/forecast", "?asOf=2026-08-14&locationId=A&material=white&horizonDays=30"));
        Assert.Equal(("forecast", "A", "white", 30), (engine.Action, engine.LocationId, engine.Material, engine.Horizon));
        Assert.Equal(200, await Request("/api/simulation", "?asOf=2026-08-14&start=2026-08-10&end=2026-08-14&seed=42&truckPayloadT=8"));
        Assert.Equal(("simulation", "2026-08-10", "2026-08-14", 42), (engine.Action, engine.Start, engine.End, engine.Seed));
        Assert.Equal(8, engine.Settings!.TruckPayloadT);
        var count = engine.Calls;
        Assert.Equal(400, await Request("/api/simulation", "?asOf=2026-08-14&start=2026-08-10&end=2026-08-15"));
        Assert.Equal(400, await Request("/api/forecast", "?asOf=2026-08-14&locationId=A&material=white&horizonDays=151"));
        Assert.Equal(count, engine.Calls);
        const string upload = "Location_id,material_type,date,fill_level_perc\nUPLOAD,white,2026-08-01,60";
        Assert.Equal(200, await Request("/api/proposal", "?asOf=2026-08-14&truckPayloadT=8", "POST", upload));
        Assert.Equal(upload, engine.Csv);
        Assert.Empty(engine.Observations!);
        Assert.Equal(8, engine.Settings!.TruckPayloadT);
        Assert.Equal(200, await Request("/api/forecast", "?asOf=2026-08-14&locationId=UPLOAD&material=white&horizonDays=5", "POST", upload));
        Assert.Equal(("forecast", "UPLOAD", 5), (engine.Action, engine.LocationId, engine.Horizon));
        Assert.Equal(200, await Request("/api/simulation", "?asOf=2026-08-14&start=2026-08-10&end=2026-08-12&seed=9", "POST", upload));
        Assert.Equal(("simulation", 9), (engine.Action, engine.Seed));
        count = engine.Calls;
        Assert.Equal(400, await Request("/api/proposal", "?asOf=2026-08-14", "POST", ""));
        Assert.Equal(400, await Request("/api/proposal", "?asOf=2026-08-14", "POST", new string('x', 2_000_001)));
        Assert.Equal(400, await Request("/api/simulation", "?asOf=2026-08-14&start=2026-08-10&end=2026-08-15", "POST", upload));
        Assert.Equal(count, engine.Calls);
        engine.Reject = true;
        Assert.Equal(400, await Request("/api/proposal", "?asOf=2026-08-14", "POST", upload));
        Assert.Equal(400, await Request("/api/fill-state", "?asOf=2026-08-14"));
        engine.Reject = false;
        var capacity = new CapacityScenarioRequest { Days = 14, AlternativeIntervalDays = 10,
            AlternativeContainers = new(2, 1, 3), Overrides = [new("A", "white", 1, 2)], ContainerCostPerMonthEuro = 12 };
        Assert.Equal(200, await Request("/api/capacity-scenario", "?asOf=2026-08-14&costPerKmEuro=1.5", "POST", capacityScenario: capacity));
        Assert.Equal("capacity", engine.Action);
        Assert.Equal(14, engine.Capacity!.Days);
        Assert.Equal(10, engine.Capacity.AlternativeIntervalDays);
        Assert.Equal(new ContainerCounts(2, 1, 3), engine.Capacity.AlternativeContainers);
        Assert.Equal(new ContainerCountOverride("A", "white", 1, 2), Assert.Single(engine.Capacity.Overrides!));
        Assert.Equal(500, engine.Settings!.FixedTruckCostEuro);
        Assert.Equal(1.5, engine.Settings.CostPerKmEuro);
        Assert.Equal("2026-08-01", Assert.Single(engine.Observations!).Date);
        Assert.Single(engine.Locations!);
        var automatic = capacity with { Optimize = true, OptimizationWeeks = 2, TargetFillPercent = 95, MaxContainersPerType = 4,
            MaxContainersPerSite = 6, MinIntervalDays = 2, MaxIntervalDays = 14, SiteLimits = [new("A", 5)] };
        Assert.Equal(200, await Request("/api/capacity-scenario", "?asOf=2026-08-14", "POST", capacityScenario: automatic));
        Assert.True(engine.Capacity!.Optimize);
        Assert.Equal(2, engine.Capacity.OptimizationWeeks);
        Assert.Equal(95, engine.Capacity.TargetFillPercent);
        Assert.Equal(4, engine.Capacity.MaxContainersPerType);
        Assert.Equal(6, engine.Capacity.MaxContainersPerSite);
        Assert.Equal(2, engine.Capacity.MinIntervalDays);
        Assert.Equal(14, engine.Capacity.MaxIntervalDays);
        Assert.Equal(new SiteContainerLimit("A", 5), Assert.Single(engine.Capacity.SiteLimits!));
        var beforeCapacity = engine.Calls;
        Assert.Equal(400, await Request("/api/capacity-scenario", "?asOf=2026-08-14", "POST", capacityScenario: capacity with { Days = 32 }));
        Assert.Equal(400, await Request("/api/capacity-scenario", "?asOf=2026-08-14", "POST", capacityScenario: capacity with { BaselineContainers = null }));
        Assert.Equal(400, await Request("/api/capacity-scenario", "?asOf=2026-08-14", "POST", capacityScenario: capacity with { Overrides = [new("A", "white", 0, 1)] }));
        Assert.Equal(400, await Request("/api/capacity-scenario", "?asOf=2026-08-14", "POST", capacityScenario: capacity with { Overrides = [new("A", "white", 1, 2), new("A", "white", 1, 3)] }));
        Assert.Equal(400, await Request("/api/capacity-scenario", "?asOf=2026-08-14", "POST", capacityScenario: automatic with { TargetFillPercent = 101 }));
        Assert.Equal(400, await Request("/api/capacity-scenario", "?asOf=2026-08-14", "POST", capacityScenario: automatic with { OptimizationWeeks = 9 }));
        Assert.Equal(400, await Request("/api/capacity-scenario", "?asOf=2026-08-14", "POST", capacityScenario: automatic with { MinIntervalDays = 15 }));
        Assert.Equal(400, await Request("/api/capacity-scenario", "?asOf=2026-08-14", "POST", capacityScenario: automatic with { SiteLimits = [new("A", 3), new("A", 5)] }));
        Assert.Equal(beforeCapacity, engine.Calls);
        Assert.Equal(200, await Request("/api/capacity-scenario", "?asOf=2026-08-14", "POST", capacityScenario: capacity with { Csv = upload }));
        Assert.Equal(upload, engine.Csv);
        Assert.Empty(engine.Observations!);
        engine.Unavailable = true;
        Assert.Equal(503, await Request("/api/fill-state", "?asOf=2026-08-14"));
    }

    private sealed class BodyFeature : Microsoft.AspNetCore.Http.Features.IHttpRequestBodyDetectionFeature
    {
        public bool CanHaveBody => true;
    }

    private sealed class CaptureEngine : IForecastEngine
    {
        public string? Action, LocationId, Material, Start, End, Csv;
        public bool Reject, Unavailable;
        public int Horizon, Seed, Calls;
        public OperationsSettings? Settings;
        public CapacityScenarioRequest? Capacity;
        public IReadOnlyCollection<Observation>? Observations;
        public IReadOnlyCollection<BinLocation>? Locations;
        public Task<JsonElement> RunAsync(string action, string asOf, OperationsSettings settings,
            IReadOnlyCollection<Observation> observations, IReadOnlyCollection<BinLocation> locations,
            string? locationId = null, string? material = null, int horizonDays = 60,
            string? start = null, string? end = null, int seed = 7, CancellationToken cancellationToken = default, string? csv = null, CapacityScenarioRequest? capacityScenario = null)
        {
            if (Unavailable) throw new InvalidOperationException("Engine unavailable");
            if (Reject) throw new DatasetRejectedException(JsonSerializer.SerializeToElement(new { errors = new[] { new { rule_id = "R5", row_number = 1, message = "Invalid fill" } } }));
            Csv = csv; Capacity = capacityScenario;
            Calls++; Action = action; Settings = settings; Observations = observations; Locations = locations;
            LocationId = locationId; Material = material; Horizon = horizonDays; Start = start; End = end; Seed = seed;
            return Task.FromResult(JsonSerializer.SerializeToElement(new { asOf }));
        }
    }
}
