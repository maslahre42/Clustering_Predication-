using System.Text.Json;
using GarbageCollector.Api.Features.History;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace GarbageCollector.Api.Tests;

// Invoke the actual mapped endpoint, including ASP.NET query binding and JSON serialization,
// without opening a network socket.
public sealed class HistoryEndpointTests
{
    [Fact]
    public async Task QueryStringControlsFilteringSortingAndPagination()
    {
        await using var connection = new SqliteConnection("Data Source=:memory:");
        await connection.OpenAsync();
        var builder = WebApplication.CreateBuilder(new WebApplicationOptions { EnvironmentName = "Testing" });
        builder.Configuration["hostBuilder:reloadConfigOnChange"] = "false";
        builder.Logging.ClearProviders();
        builder.Services.AddDbContext<HistoryDbContext>(options => options.UseSqlite(connection));
        await using var app = builder.Build();
        app.MapHistoryEndpoints();
        await using var scope = app.Services.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<HistoryDbContext>();
        await db.Database.ExecuteSqlRawAsync("""
            CREATE TABLE raw_data (Location_id TEXT, material_type TEXT, date TEXT, fill_level_perc TEXT);
            INSERT INTO raw_data VALUES
              ('SITE-A', 'green', '2026-02-01', '9'),
              ('SITE-B', 'green', '2026-02-02', '80'),
              ('SITE-C', 'brown', '2026-02-02', '100'),
              ('SITE-A', 'green', '2026-04-01', '100');
            """);
        var endpoint = ((IEndpointRouteBuilder)app).DataSources.SelectMany(source => source.Endpoints).Single();
        async Task<HistoryPage> Request(string query)
        {
            var context = new DefaultHttpContext { RequestServices = scope.ServiceProvider };
            context.Request.Method = "GET";
            context.Request.Path = "/api/history";
            context.Request.QueryString = new QueryString(query);
            context.Response.Body = new MemoryStream();
            await endpoint.RequestDelegate!(context);
            Assert.Equal(200, context.Response.StatusCode);
            context.Response.Body.Position = 0;
            return (await JsonSerializer.DeserializeAsync<HistoryPage>(context.Response.Body, new JsonSerializerOptions(JsonSerializerDefaults.Web)))!;
        }
        var first = await Request("?asOf=2026-03-01&material=green&locationSearch=SITE&sortBy=fill&sortDirection=asc&page=1&pageSize=1");
        Assert.Equal(2, first.Total);
        Assert.Equal(9d, Assert.Single(first.Items).FillLevelPercent);
        var descending = await Request("?asOf=2026-03-01&material=green&sortBy=fill&sortDirection=desc&pageSize=1");
        Assert.Equal(80d, Assert.Single(descending.Items).FillLevelPercent);
        var glassAscending = await Request("?asOf=2026-03-01&sortBy=material&sortDirection=asc&pageSize=1");
        Assert.Equal("brown", Assert.Single(glassAscending.Items).Material);
        var glassDescending = await Request("?asOf=2026-03-01&sortBy=material&sortDirection=desc&pageSize=1");
        Assert.Equal("green", Assert.Single(glassDescending.Items).Material);
        var search = await Request("?asOf=2026-03-01&locationSearch=SITE-B");
        Assert.Equal("SITE-B", Assert.Single(search.Items).LocationId);
    }
}
