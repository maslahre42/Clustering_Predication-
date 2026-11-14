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
        async Task<int> Request(string path, string query, string method = "GET", string? csv = null)
        {
            var endpoint = ((IEndpointRouteBuilder)app).DataSources.SelectMany(s => s.Endpoints).OfType<RouteEndpoint>()
                .Single(e => e.RoutePattern.RawText == path && e.Metadata.GetMetadata<HttpMethodMetadata>()!.HttpMethods.Contains(method));
            var context = new DefaultHttpContext { RequestServices = scope.ServiceProvider };
            context.Request.Method = method;
            if (csv is not null)
            {
                var bytes = System.Text.Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new { csv }));
                context.Request.ContentType = "application/json";
                context.Request.ContentLength = bytes.Length;
                context.Request.Body = new MemoryStream(bytes);
                context.Features.Set<Microsoft.AspNetCore.Http.Features.IHttpRequestBodyDetectionFeature>(new BodyFeature());
            } context.Request.Path = path; context.Request.QueryString = new QueryString(query);
            context.Response.Body = new MemoryStream();
            await endpoint.RequestDelegate!(context);
            return context.Response.StatusCode;
        }
        Assert.Equal(200, await Request("/api/proposal", "?asOf=2026-08-14&vehicleFixedCostMin=600&optionalValueMin=25&solverTimeLimitSeconds=2&neighbourProbability=0.2&avgSpeedKph=30&workSaturday=true"));
        Assert.Equal("proposal", engine.Action);
        Assert.Equal(600, engine.Settings!.VehicleFixedCostMin);
        Assert.Equal(25, engine.Settings.OptionalValueMin);
        Assert.Equal(2, engine.Settings.SolverTimeLimitSeconds);
        Assert.Equal(0.2, engine.Settings.NeighbourProbability);
        Assert.Equal(30, engine.Settings.AvgSpeedKph);
        Assert.True(engine.Settings.WorkSaturday);
        Assert.Equal("2026-08-01", Assert.Single(engine.Observations!).Date);
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
    }

    private sealed class BodyFeature : Microsoft.AspNetCore.Http.Features.IHttpRequestBodyDetectionFeature
    {
        public bool CanHaveBody => true;
    }

    private sealed class CaptureEngine : IForecastEngine
    {
        public string? Action, LocationId, Material, Start, End, Csv;
        public bool Reject;
        public int Horizon, Seed, Calls;
        public OperationsSettings? Settings;
        public IReadOnlyCollection<Observation>? Observations;
        public Task<JsonElement> RunAsync(string action, string asOf, OperationsSettings settings,
            IReadOnlyCollection<Observation> observations, IReadOnlyCollection<BinLocation> locations,
            string? locationId = null, string? material = null, int horizonDays = 60,
            string? start = null, string? end = null, int seed = 7, CancellationToken cancellationToken = default, string? csv = null)
        {
            if (Reject) throw new DatasetRejectedException(JsonSerializer.SerializeToElement(new { errors = new[] { new { rule_id = "R5", row_number = 1, message = "Invalid fill" } } }));
            Csv = csv;
            Calls++; Action = action; Settings = settings; Observations = observations;
            LocationId = locationId; Material = material; Horizon = horizonDays; Start = start; End = end; Seed = seed;
            return Task.FromResult(JsonSerializer.SerializeToElement(new { asOf }));
        }
    }
}
